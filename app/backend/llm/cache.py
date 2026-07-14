"""Content-addressed cache for token-expensive LLM generation (inc 61).

A cache hit costs zero tokens — the dominant cost lever. The key is a content hash of EVERYTHING that
determines the output (the generator's model+prompt-version ``cache_signature`` + the normalized inputs),
so any input change misses automatically — no explicit invalidation. The cache stores the raw generation
output ONLY; the caller still runs the local citation-verification step on every result, so a hit never
serves stale verification. Persisted in SQLite (``llm_cache``), so savings survive restarts.

``CachedSummaryGenerator`` is the seam wrapper for the summary path. It is layered INSIDE the egress gate
(``EgressGated(Cached(real))``) so the egress gate's behavior is unchanged — egress-off errors before the
cache is consulted. It uses the pipeline's existing ``conn`` (threaded into ``generate``); a second SQLite
connection mid-transaction would lock, so caching is skipped (pass-through) when ``conn`` is None.
"""

from __future__ import annotations

import hashlib
import json
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


def canonical_hash(payload: Any) -> str:
    """sha256 of a canonical JSON encoding (sorted keys), so equal content → equal key."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
        key = canonical_hash(
            {
                "sig": self.cache_signature,
                # The chunk SET (id + version + text) fully determines generation; top_k is captured
                # implicitly (it shaped the set). chunk_version changing (re-extraction) misses correctly.
                "chunks": [[c.chunk_id, c.chunk_version, c.text] for c in source_chunks],
                "scope": scope_ref,
            }
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
            signature=self.cache_signature,
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
