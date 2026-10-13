"""Exact-identity reuse of work already done inside one recovery round. Opt-in; nothing here runs by default.

Three kinds of work repeat in a recovery round, and each is reused only when its inputs are byte-identical:

1. **A search.** Two recovery targets of the same child can resolve to the same query over the same candidate
   papers with the same requested-information list. The second search would retrieve the same passages and
   send the same prompts. It is skipped; the second target still gets its own log row, naming the target
   whose search it shares, so each requirement keeps its own recovery status.
2. **A worker model call.** Keyed on the full prompt, the output schema, the output cap and the worker's
   model, thinking setting and options. A passage examined for a different subquestion or a different
   requested-information list produces a different prompt and is therefore a different call.
3. **A source verification.** Keyed on the claim text, the cited chunk (id, version and text) and the quote.
   The verifier is deterministic, so the stored result is the result.

No similarity threshold, no normalisation beyond canonical JSON, and no question-specific rule. A failed
call or a mechanical no-answer is never stored, so it is attempted again exactly as before. Anything that
cannot be keyed is processed normally.

What this does not claim: a worker model at temperature 0 is not perfectly repeatable on a GPU. In the
preserved q_aib run 148 of 157 repeated prompts returned byte-identical output and 9 returned a differently
worded claim. Reuse returns the first answer; it does not reproduce that incidental variation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def worker_identity(config) -> dict:
    """What makes two worker calls the same model call, beyond their prompt: model, thinking and options."""
    return {
        "kind": type(config).__name__,
        "model": getattr(config, "model", None),
        "think": getattr(config, "think", None),
        "base_options": getattr(config, "base_options", None),
    }


@dataclass
class RecoveryReuse:
    retrieval_config: dict = field(default_factory=dict)
    calls: dict = field(default_factory=dict)
    verifications: dict = field(default_factory=dict)
    searches: dict = field(default_factory=dict)
    counts: dict = field(
        default_factory=lambda: {
            "searches_run": 0,
            "searches_reused": 0,
            "calls_run": 0,
            "calls_reused": 0,
            "call_seconds_of_first_runs_reused": 0.0,
            "verifications_run": 0,
            "verifications_reused": 0,
        }
    )

    # ---- searches -----------------------------------------------------------------------------------------------------
    def search_key(self, *, child_id, action, query, paper_ids, subquestion_text, obligations) -> str:
        return _digest(
            {
                "child": child_id,
                "action": action,
                "query": query,
                "paper_ids": list(paper_ids),
                "subquestion_text": subquestion_text,
                "obligations": obligations,
                "retrieval_config": self.retrieval_config,
            }
        )

    def search_done(self, key: str):
        return self.searches.get(key)

    def record_search(self, key: str, *, target, existing_hits: int) -> None:
        self.counts["searches_run"] += 1
        self.searches.setdefault(key, {"target": target, "existing_hits": existing_hits})

    # ---- worker model calls -------------------------------------------------------------------------------------------
    def call_key(self, *, config, prompt: str, output_cap: int, json_schema) -> str:
        return _digest(
            {"worker": worker_identity(config), "prompt": prompt, "output_cap": output_cap, "schema": json_schema}
        )

    def reused_call(self, key: str):
        stored = self.calls.get(key)
        if stored is None:
            return None
        self.counts["calls_reused"] += 1
        self.counts["call_seconds_of_first_runs_reused"] += stored.elapsed_seconds
        extra = {**(stored.extra or {}), "reused_identical_call": True, "wall_seconds": 0.0, "load_seconds": 0.0}
        return replace(stored, elapsed_seconds=0.0, extra=extra)

    def record_call(self, key: str, result) -> None:
        self.counts["calls_run"] += 1
        if result.provider_ok:
            self.calls.setdefault(key, result)

    def receipt(self) -> dict:
        return {
            **{k: (round(v, 1) if isinstance(v, float) else v) for k, v in self.counts.items()},
            "distinct_searches": len(self.searches),
            "distinct_calls_stored": len(self.calls),
            "distinct_verifications_stored": len(self.verifications),
        }


class ReusingVerifier:
    """The run's verifier, answering a repeated identical (claim, cited chunk, quote) item from its first result.

    Order and length of ``verify_many``'s result are preserved, and items not seen before go to the real verifier
    in one batch, as they would have without this wrapper. Everything else is the wrapped verifier's own.
    """

    def __init__(self, verifier, reuse: RecoveryReuse) -> None:
        self._verifier = verifier
        self._reuse = reuse

    def __getattr__(self, name):
        return getattr(self._verifier, name)

    @staticmethod
    def _key(sentence, citation, chunk) -> str:
        return _digest(
            {
                "claim": sentence,
                "chunk_id": citation.chunk_id,
                "quote": citation.quote,
                "chunk_version": getattr(chunk, "chunk_version", None),
                "chunk_text_sha256": hashlib.sha256(getattr(chunk, "text", "").encode("utf-8")).hexdigest(),
            }
        )

    def verify_many(self, conn, *, items, source_chunks):
        by_id = {chunk.chunk_id: chunk for chunk in source_chunks}
        keys = [
            self._key(sentence, citation, by_id[citation.chunk_id]) if citation.chunk_id in by_id else None
            for sentence, citation in items
        ]
        results = [self._reuse.verifications.get(key) if key is not None else None for key in keys]
        fresh = [index for index, result in enumerate(results) if result is None]
        self._reuse.counts["verifications_reused"] += len(items) - len(fresh)
        if fresh:
            # The real verifier scores each item against its own cited chunk; the pool it is handed only has to
            # contain those chunks, so passing the same pool keeps every fresh item's inputs exactly as before.
            computed = self._verifier.verify_many(
                conn, items=[items[index] for index in fresh], source_chunks=source_chunks
            )
            self._reuse.counts["verifications_run"] += len(fresh)
            for index, result in zip(fresh, computed, strict=True):
                results[index] = result
                if keys[index] is not None:
                    self._reuse.verifications.setdefault(keys[index], result)
        return results


@dataclass
class ReuseRuntimeView:
    """What the recovery round reads from the runtime, with the verifier swapped for the reusing one."""

    model: object
    vector_store: object
    verifier: object
