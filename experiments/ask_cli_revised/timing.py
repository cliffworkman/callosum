"""Wall-clock spans for the Ask run. Opt-in and observational: a span never changes an argument or a result.

``collect()`` activates a collector for the block; ``span(name)`` adds elapsed time to it and is a no-op when
no collector is active. Spans are flat named totals, so a span opened inside another is counted in both;
``summary`` reports each as measured and leaves the arithmetic to the reader.

``TimedVerifier`` splits one source verification into the steps the shared verifier already has as methods.
It subclasses the shared verifier and only wraps those methods in spans.
"""

from __future__ import annotations

import contextlib
import time

from app.backend.summarization.verification import LocalCitationVerifier

_ACTIVE: "Timings | None" = None


class Timings:
    def __init__(self) -> None:
        self.totals: dict[str, list] = {}

    def add(self, name: str, seconds: float) -> None:
        entry = self.totals.setdefault(name, [0, 0.0])
        entry[0] += 1
        entry[1] += seconds

    def summary(self) -> dict:
        return {name: {"count": n, "seconds": round(s, 3)} for name, (n, s) in sorted(self.totals.items())}


@contextlib.contextmanager
def collect():
    global _ACTIVE
    previous, _ACTIVE = _ACTIVE, Timings()
    try:
        yield _ACTIVE
    finally:
        _ACTIVE = previous


def active() -> bool:
    return _ACTIVE is not None


@contextlib.contextmanager
def span(name: str):
    collector = _ACTIVE
    if collector is None:
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        collector.add(name, time.perf_counter() - started)


class TimedVerifier(LocalCitationVerifier):
    """The shared verifier with its own steps timed. No step's inputs, outputs or order change."""

    @classmethod
    def wrapping(cls, verifier: LocalCitationVerifier) -> "TimedVerifier":
        return cls(
            model=verifier.model,
            vector_store=verifier.vector_store,
            config=verifier.config,
            support_scorer=verifier.support_scorer,
        )

    def verify_many(self, conn, *, items, source_chunks):
        with span("verify.total"):
            return super().verify_many(conn, items=items, source_chunks=source_chunks)

    def _embedding_lookup(self, conn, *, candidate_chunk_ids):
        with span("verify.chunk_embedding_lookup_db"):
            return super()._embedding_lookup(conn, candidate_chunk_ids=candidate_chunk_ids)

    def _retrieval_confidence_from_vector(self, conn, *, vector, cited_chunk_id, embedding_to_chunk):
        with span("verify.similarity_search"):
            return super()._retrieval_confidence_from_vector(
                conn, vector=vector, cited_chunk_id=cited_chunk_id, embedding_to_chunk=embedding_to_chunk
            )

    def _quote_confidence(self, conn, *, citation, cited_chunk):
        with span("verify.quote_match_and_location"):
            return super()._quote_confidence(conn, citation=citation, cited_chunk=cited_chunk)

    def _support_and_contradiction_many(self, pairs):
        with span("verify.nli"):
            return super()._support_and_contradiction_many(pairs)
