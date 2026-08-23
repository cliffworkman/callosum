"""Content-addressed cache for token-expensive LLM generation (inc 61; identity hardened inc 493).

A cache hit costs zero tokens — the dominant cost lever. The key is a content hash of EVERYTHING that
determines the output (provider request semantics + generator/prompt identity + normalized prompt inputs), so
any input change misses automatically — no explicit invalidation. The cache stores the parsed generation
candidate output ONLY; the caller still runs the local citation-verification step on every result, so a hit never
serves stale verification. Persisted in SQLite (``llm_cache``), so savings survive restarts.

``CachedSummaryGenerator`` is the seam wrapper for the summary path. It is layered INSIDE the egress gate
(``EgressGated(Cached(real))``) so the egress gate's behavior is unchanged — egress-off errors before the
cache is consulted. It uses the pipeline's existing ``conn`` (threaded into ``generate``); a second SQLite
connection mid-transaction would lock, so caching is skipped (pass-through) when ``conn`` is None.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, insert, select

from app.backend.persistence.schema import llm_cache
from app.backend.summarization.generators import (
    CandidateCitation,
    CandidateSummarySentence,
    SourceChunk,
    SummaryGenerator,
)

if TYPE_CHECKING:
    from sqlalchemy import Connection

SUMMARY_CACHE_NAMESPACE = "summary"
SUMMARY_CACHE_KEY_SCHEMA = "summary-generation-v2"
_GEMINI_ENV_KEYS = ("GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION")


def canonical_hash(payload: Any) -> str:
    """sha256 of a canonical JSON encoding (sorted keys), so equal content → equal key."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GenerationCacheIdentity:
    """Secret-safe semantic identity for one synthesis generation configuration.

    The persisted signature is only a schema label plus a SHA-256 digest. Endpoint and credential values never
    enter cache rows or logs in plaintext. Provider identity is intentionally stricter than connection-pool
    identity because custom credentials can select a different tenant or deployment behind one endpoint/model.
    """

    generator_name: str
    prompt_version: str
    provider: str
    model: str
    wire_mode: str
    endpoint_identity: str
    generation_parameters: tuple[tuple[str, str | int], ...]
    credential_identity: str
    provider_environment_identity: str

    @classmethod
    def from_config(cls, *, generator_name: str, prompt_version: str, config: Any) -> GenerationCacheIdentity:
        from app.backend.llm.providers import completion_request_identity

        request = completion_request_identity(config)
        resolved_key = config.resolved_api_key()
        endpoint = request.base_url or "provider-sdk-default"
        environment = {key: os.getenv(key, "") for key in _GEMINI_ENV_KEYS} if request.wire_format == "gemini" else {}
        return cls(
            generator_name=generator_name,
            prompt_version=prompt_version,
            provider=str(config.provider),
            model=str(config.model),
            wire_mode=request.wire_format,
            endpoint_identity=canonical_hash({"endpoint": endpoint}),
            generation_parameters=request.generation_parameters,
            credential_identity=canonical_hash({"credential": resolved_key or ""}),
            provider_environment_identity=canonical_hash(environment),
        )

    @property
    def signature(self) -> str:
        return f"{SUMMARY_CACHE_KEY_SCHEMA}:{canonical_hash(self.__dict__)}"


def synthesis_generation_cache_signature(*, generator_name: str, prompt_version: str, config: Any) -> str:
    """Return the persisted, non-sensitive signature for a synthesis generator configuration."""
    return GenerationCacheIdentity.from_config(
        generator_name=generator_name,
        prompt_version=prompt_version,
        config=config,
    ).signature


def summary_generation_input_hash(
    *, cache_signature: str, source_chunks: list[SourceChunk], scope_ref: dict[str, object]
) -> str:
    """Hash every prompt-relevant synthesis input plus explicit source-version invalidation state."""
    return canonical_hash(
        {
            "cache_schema": SUMMARY_CACHE_KEY_SCHEMA,
            "generation": cache_signature,
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "chunk_version": chunk.chunk_version,
                    "page_end": chunk.page_end,
                    "page_start": chunk.page_start,
                    "paper_id": chunk.paper_id,
                    "text": chunk.text,
                }
                for chunk in source_chunks
            ],
            "scope": scope_ref,
        }
    )


def persisted_generation_signature(cache_signature: str) -> str:
    """Hash even injected/custom generator signatures before writing cache metadata."""
    return f"{SUMMARY_CACHE_KEY_SCHEMA}:{canonical_hash({'generation': cache_signature})}"


def llm_cache_get(conn: "Connection", *, namespace: str, input_hash: str) -> Any | None:
    row = conn.execute(
        select(llm_cache.c.output_json).where(
            llm_cache.c.namespace == namespace,
            llm_cache.c.input_hash == input_hash,
        )
    ).first()
    return row[0] if row is not None else None


def llm_cache_set(conn: "Connection", *, namespace: str, input_hash: str, signature: str, output: Any) -> None:
    # OR IGNORE: a concurrent/duplicate insert for the same (namespace, input_hash) is harmless.
    conn.execute(
        insert(llm_cache)
        .prefix_with("OR IGNORE")
        .values(namespace=namespace, input_hash=input_hash, signature=signature, output_json=output)
    )


def llm_cache_delete(conn: "Connection", *, namespace: str, input_hash: str) -> None:
    conn.execute(delete(llm_cache).where(llm_cache.c.namespace == namespace, llm_cache.c.input_hash == input_hash))


def repair_summary_cache(conn: "Connection") -> dict[str, int]:
    """Remove malformed cached summary-generation rows.

    This is deliberately narrow: only summary-generation cache rows whose payload no longer deserializes into
    candidate sentences are deleted. Persisted summaries, verification evidence, chunks, and non-summary cache
    namespaces are untouched.
    """
    scanned = 0
    removed = 0
    rows = conn.execute(
        select(llm_cache.c.id, llm_cache.c.output_json).where(llm_cache.c.namespace == SUMMARY_CACHE_NAMESPACE)
    ).mappings()
    for row in rows:
        scanned += 1
        try:
            _deserialize_candidates(row["output_json"])
        except (KeyError, TypeError, ValueError):
            conn.execute(delete(llm_cache).where(llm_cache.c.id == row["id"]))
            removed += 1
    return {"scanned": scanned, "removed": removed}


@dataclass(frozen=True)
class CachedSummaryGenerator:
    """Content-addressed cache around a ``SummaryGenerator`` (caches the token-expensive generate step only)."""

    inner: SummaryGenerator

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def cache_signature(self) -> str:
        return getattr(self.inner, "cache_signature", self.inner.name)

    def generate(
        self,
        *,
        source_chunks: list[SourceChunk],
        scope_ref: dict[str, object],
        conn: "Connection | None" = None,
    ) -> list[CandidateSummarySentence]:
        if conn is None:
            return self.inner.generate(source_chunks=source_chunks, scope_ref=scope_ref)
        cache_signature = self.cache_signature
        key = summary_generation_input_hash(
            cache_signature=cache_signature,
            source_chunks=source_chunks,
            scope_ref=scope_ref,
        )
        cached = llm_cache_get(conn, namespace=SUMMARY_CACHE_NAMESPACE, input_hash=key)
        if cached is not None:
            try:
                return _deserialize_candidates(cached)
            except (KeyError, TypeError, ValueError):
                llm_cache_delete(conn, namespace=SUMMARY_CACHE_NAMESPACE, input_hash=key)
        result = self.inner.generate(source_chunks=source_chunks, scope_ref=scope_ref)
        llm_cache_set(
            conn,
            namespace=SUMMARY_CACHE_NAMESPACE,
            input_hash=key,
            signature=persisted_generation_signature(cache_signature),
            output=_serialize_candidates(result),
        )
        return result


def _serialize_candidates(candidates: list[CandidateSummarySentence]) -> dict:
    return {
        "sentences": [
            {"text": c.text, "citations": [{"chunk_id": cit.chunk_id, "quote": cit.quote} for cit in c.citations]}
            for c in candidates
        ]
    }


def _deserialize_candidates(payload: Any) -> list[CandidateSummarySentence]:
    sentences = payload.get("sentences", []) if isinstance(payload, dict) else []
    return [
        CandidateSummarySentence(
            text=str(item.get("text", "")),
            citations=[
                CandidateCitation(chunk_id=int(c["chunk_id"]), quote=str(c["quote"])) for c in item.get("citations", [])
            ],
        )
        for item in sentences
    ]
