"""Gemini-backed summary generation."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.backend.llm.cache import synthesis_generation_cache_signature
from app.backend.llm.egress import DataEgressDisabledError
from app.backend.llm.usage import log_usage
from app.backend.summarization.generators import (
    CandidateCitation,
    CandidateSummarySentence,
    SourceChunk,
    TruncatedGenerationError,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from app.backend.provider_runtime import ProviderClientRuntime

# Bumped whenever ``_prompt`` or candidate parsing semantics change. Model/provider request semantics are
# independently represented by ``GenerationCacheIdentity`` in app/backend/llm/cache.py.
SUMMARY_PROMPT_VERSION = "summary-v5"

# ``DataEgressDisabledError`` is re-exported (its canonical home is app/backend/llm/egress.py) so the
# provider self-checks below and the existing `from integrations.gemini import DataEgressDisabledError`
# imports keep resolving unchanged.
__all__ = ["DataEgressDisabledError", "GeminiConfig", "LLMConfig", "GeminiSummaryGenerator"]


@dataclass(frozen=True)
class LLMConfig:
    """Provider-neutral LLM config (inc 149; unified provider roster inc 256). `provider` is a roster id (a
    builtin gemini/openai/anthropic/local OR a custom uuid); `wire_format` selects the transport
    (gemini SDK / messages / chat_completions / responses); `api_key` is the ACTIVE provider's resolved key;
    `base_url` is the provider's endpoint (None for the gemini SDK). Every call routes through
    ``app.backend.llm.providers.complete(config, prompt)``; egress is decided endpoint-based from this config."""

    model: str = "gemini-2.5-flash-lite"
    api_key_env: str = "GOOGLE_API_KEY"
    api_key: str | None = field(default=None, repr=False)
    provider: str = "gemini"
    wire_format: str = "gemini"
    base_url: str | None = None  # the provider's endpoint host (None for the gemini SDK)
    data_egress_enabled: bool = False
    help_assistant_enabled: bool = False
    http_trust_env: bool = True
    provider_runtime: ProviderClientRuntime | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_environment(cls, *, provider_runtime: ProviderClientRuntime | None = None) -> "LLMConfig":
        # BYOK (inc 146/149/256): the Settings UI stores the active provider id + per-provider key + egress
        # consent; the provider roster (base_url/wire_format/model) is resolved via ``providers_store``. Stored
        # values OVERLAY the env defaults (env stays the fallback). Lazy imports keep integrations/ loosely coupled.
        from app.backend import providers_store
        from app.backend.app_settings import load_settings

        stored = load_settings()
        record = providers_store.active_provider()
        provider = record["id"]
        env_egress = os.getenv("CALLOSUM_ALLOW_DATA_EGRESS", "").strip().lower() in {"1", "true", "yes"}
        stored_egress = stored.get("data_egress_enabled")
        enabled = stored_egress if isinstance(stored_egress, bool) else env_egress
        # The help assistant has its OWN, independent toggle: it sends only the user's question + the public
        # help docs (never library text), so it must NOT be gated by the library data-egress flag above. The
        # stored UI value overlays the env default (like egress).
        env_help = os.getenv("CALLOSUM_HELP_ASSISTANT_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        stored_help = stored.get("help_assistant_enabled")
        help_enabled = stored_help if isinstance(stored_help, bool) else env_help
        return cls(
            provider=provider,
            wire_format=record["wire_format"],
            model=providers_store.active_model(),
            api_key=_resolve_key(provider),
            base_url=record["base_url"],
            data_egress_enabled=enabled,
            help_assistant_enabled=help_enabled,
            provider_runtime=provider_runtime,
        )

    def resolved_api_key(self) -> str | None:
        # The active provider's key. The GOOGLE_API_KEY env fallback applies only to gemini (the others have no
        # env fallback baked into a directly-constructed config; from_environment resolves their stored keys).
        return self.api_key or (os.getenv(self.api_key_env) if self.provider == "gemini" else None)


def _resolve_key(provider: str) -> str | None:
    # The stored key comes from the OS keychain (if available) or the local file (inc 152); env is the fallback.
    from app.backend.app_settings import get_provider_key

    key = get_provider_key(provider)
    if key:
        return key
    env_var = {"gemini": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(provider)
    return os.getenv(env_var) if env_var else None


# Back-compat alias: the config is multi-provider now, but ~12 call sites import ``GeminiConfig``.
GeminiConfig = LLMConfig


@dataclass(frozen=True)
class GeminiSummaryGenerator:
    config: GeminiConfig
    name: str = "gemini-summary-generator"

    @property
    def cache_signature(self) -> str:
        """Secret-safe identity for provider request semantics plus this generator/prompt version."""
        return synthesis_generation_cache_signature(
            generator_name=self.name,
            prompt_version=SUMMARY_PROMPT_VERSION,
            config=self.config,
        )

    def generate(
        self,
        *,
        source_chunks: list[SourceChunk],
        scope_ref: dict[str, object],
        engine: "Engine | None" = None,  # caching is handled by the wrapper; the provider ignores it
    ) -> list[CandidateSummarySentence]:
        from app.backend.llm.providers import complete, requires_egress

        if requires_egress(self.config) and not self.config.data_egress_enabled:
            raise DataEgressDisabledError("Summary generation requires explicit data-egress consent.")
        result = complete(
            self.config,
            _prompt(source_chunks=source_chunks, scope_ref=scope_ref, provider=getattr(self.config, "provider", None)),
        )
        log_usage("summary", self.config.model, result)
        text = str(result.text or "[]")
        try:
            sentences = _parse_response_text(text)
        except (ValueError, KeyError, TypeError):
            # The model ran out of output room mid-JSON. The claims it finished are whole and still
            # face the full local verification pipeline, so keep them rather than discarding a long
            # wait entirely -- but never silently: TruncatedGenerationError forces every caller to
            # decide what to tell the user, and stops the cache wrapper storing a partial answer as
            # if it were a complete one.
            salvaged = _sentences_from(salvage_complete_objects(text))
            if not salvaged:
                raise
            raise TruncatedGenerationError(sentences=salvaged) from None
        if result.truncated and sentences:
            raise TruncatedGenerationError(sentences=sentences)
        return sentences


# The managed Local AI preview runs a fixed 12,288-token context (2,048 reserved for output — see
# app/backend/llm/managed_local.py's _PREVIEW_CONTEXT_TOKENS/max_output_tokens), unlike cloud providers'
# effectively unbounded context. A multi-paper synthesis's top_k scales up to 50 chunks (one per selected
# paper, app/frontend/js/20_synthesis.jsx's MAX_CHUNKS) with no per-chunk or total character cap today, so a
# large selection can silently overflow the managed context with no local guard. Truncating each chunk's
# TEXT (never dropping a chunk) preserves the "every selected paper gets representation" retrieval contract
# while bounding total prompt size; a truncated prefix remains a genuine substring of the stored chunk, so
# the #1 verbatim-quote verification bar downstream is unaffected.
_MANAGED_LOCAL_TOTAL_CHUNK_CHARS = 10_000


def _prompt(*, source_chunks: list[SourceChunk], scope_ref: dict[str, object], provider: str | None = None) -> str:
    per_chunk_limit = (
        max(200, _MANAGED_LOCAL_TOTAL_CHUNK_CHARS // len(source_chunks))
        if provider == "managed_local" and source_chunks
        else None
    )
    chunks_json = [
        {
            "chunk_id": chunk.chunk_id,
            "paper_id": chunk.paper_id,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "text": chunk.text[:per_chunk_limit] if per_chunk_limit is not None else chunk.text,
        }
        for chunk in source_chunks
    ]
    return (
        "Answer the scope question as a concise evidence synthesis. The returned JSON array MUST contain 4 to 7 "
        "objects, and each object's text MUST be exactly one complete standalone sentence. Include "
        "important qualifications or null findings present in the supplied evidence. When the scope names an "
        "explicit paper selection, use evidence across those papers when relevant rather than repeatedly citing "
        "one source. Return JSON only: an array of objects with keys text and citations. Each citation must "
        "contain 1 to 3 citations. Each citation must contain chunk_id and the shortest sufficient contiguous "
        "verbatim quote from that chunk. No quote may exceed 80 words. Cite only evidence that directly supports "
        "that sentence, and do not invent citations. Scope: "
        f"{json.dumps(scope_ref, ensure_ascii=True)}\n"
        f"Chunks: {json.dumps(chunks_json, ensure_ascii=True)}"
    )


def _parse_response_text(text: str) -> list[CandidateSummarySentence]:
    payload = json.loads(_strip_code_fence(text))
    return _sentences_from(payload)


def _sentences_from(payload: object) -> list[CandidateSummarySentence]:
    sentences = []
    for item in payload:  # type: ignore[union-attr]
        citations = [
            CandidateCitation(chunk_id=int(citation["chunk_id"]), quote=str(citation["quote"]))
            for citation in item.get("citations", [])
        ]
        sentences.append(CandidateSummarySentence(text=str(item["text"]), citations=citations))
    return sentences


def salvage_complete_objects(text: str) -> list[dict]:
    """Every complete object at the start of a truncated JSON array.

    A response that stopped mid-token — the model hit its output ceiling — is not garbage: the claims
    it finished before running out are whole, and each one still faces the full local verification
    pipeline afterwards (invariant #1), so this widens what can be READ without widening what is
    TRUSTED. That is the same rationale ``first_embedded_json`` above documents for itself, and this
    reuses its ``raw_decode`` technique rather than introducing a second parser.

    Returns only objects, never a partial one: decoding stops at the first element that does not
    decode cleanly, and any object missing the fields a claim needs is dropped. Syntactic completeness
    is NOT sufficient -- only the managed-local path constrains output with a grammar, so a cloud
    provider can emit a well-formed object whose citation has no ``quote`` at all. Converting that
    raised ``KeyError`` from inside the recovery path, turning a salvageable truncation into a crash.
    An empty list means nothing survived and the caller must fail rather than present an empty
    synthesis as an answer.
    """

    def usable(value: object) -> bool:
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            return False
        citations = value.get("citations")
        if not isinstance(citations, list):
            return False
        return all(
            isinstance(citation, dict) and citation.get("chunk_id") is not None and citation.get("quote") is not None
            for citation in citations
        )

    body = _strip_code_fence(text)
    start = body.find("[")
    if start < 0:
        return []
    decoder = json.JSONDecoder()
    objects: list[dict] = []
    index = start + 1
    while index < len(body):
        while index < len(body) and body[index] in " \t\r\n,":
            index += 1
        if index >= len(body) or body[index] != "{":
            break
        try:
            value, index = decoder.raw_decode(body, index)
        except ValueError:
            break  # the element the model was mid-way through when it ran out
        if not isinstance(value, dict):
            break
        if not usable(value):
            break  # the element the model was mid-way through, or one the grammar never constrained
        objects.append(value)
    return objects


def first_embedded_json(text: str, *, want: type, accept: Callable[[object], bool] | None = None) -> object | None:
    """The first balanced JSON value of type ``want`` (dict or list) embedded anywhere in ``text``.

    A small local model -- and occasionally a cloud one -- returns the requested JSON wrapped in prose: a
    "Here is the JSON:" preamble, a reasoning block, or trailing commentary. A whole-string ``json.loads``
    rejects all of that outright, so the real answer is discarded and the feature silently degrades to its
    local fallback. Scanning for the first decodable value of the expected shape recovers the answer the
    model actually gave. Callers still validate, cap, and dedupe every field afterwards, so this widens what
    can be READ without widening what is TRUSTED.

    ``accept`` narrows *which* embedded value counts. Without it the FIRST decodable value wins, so a model
    that emits a schema echo, an empty ``{}``, or a scratch object inside a reasoning block before its real
    answer defeats the recovery it was written for. Callers that know the shape they need (e.g. "a dict with
    a non-empty label") pass a predicate and keep scanning past the decoys.
    """
    opener = "{" if want is dict else "["
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != opener:
            continue
        try:
            payload, _ = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(payload, want) and (accept is None or accept(payload)):
            return payload
    return None


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped
