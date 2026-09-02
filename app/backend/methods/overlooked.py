"""Overlooked-work lens engine (backlog #37): surface external works highly relevant to one of the user's axes but
under-cited for their vintage — "work you're likely missing because the field overlooked it, not because it's weak."

This is a SIGNAL, not a verdict, with **two separable, visible inputs** — axis *relevance* (local cosine similarity,
checkable) and *citations vs. a same-vintage baseline* (the raw count + its percentile among same-year peers) —
that are **never fused into one score**. It is **identity-agnostic** (it measures the *work's* attention-vs-relevance,
never who wrote it — there is no author/identity field anywhere) and **local**: relevance is computed by embedding
each candidate's abstract **on-device**; the only thing that egresses is the axis label + topic id (via the sources
client). Credit the lineage: this operationalizes the *Matthew effect in science* (Merton, 1968).

The pipeline: axis label → OpenAlex topic → the topic's works (with citation counts + reconstructed abstracts) →
drop works already in the library (this is discovery) → relevance = cosine(axis vector, local-embedded abstract) →
per-`publication_year` citation percentile among the fetched sample (only where a year has enough peers to be
meaningful) → keep the low-percentile candidates, rank by relevance, cap. See
`.claude/docs/specs/2026-07-16-overlooked-work-lens-design.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import Connection

from app.backend.clustering.axis_scoring import _embed_axis
from app.backend.persistence.repository import find_existing_paper_by_identity, get_axis

DEFAULT_CANDIDATE_CAP = 25
DEFAULT_LOW_PERCENTILE = 0.25  # "under-cited for its vintage" = at/below the 25th percentile of same-year peers
DEFAULT_MIN_YEAR_PEERS = 5  # a year needs at least this many peers before a percentile is meaningful (else: shown-less)


@dataclass(frozen=True)
class OverlookedCandidate:
    """One surfaced work: the two separable, visible inputs (`relevance` + `year_percentile`) beside its raw
    `cited_by_count` and descriptive metadata. NO composite score; NO author/identity field (identity-agnostic —
    authors are re-fetched only if the user chooses to Add the work to the library)."""

    openalex_work_id: str
    doi: str | None
    title: str | None
    year: int | None
    cited_by_count: int
    relevance: float
    year_percentile: float | None

    def to_dict(self) -> dict:
        return {
            "openalex_work_id": self.openalex_work_id,
            "doi": self.doi,
            "title": self.title,
            "year": self.year,
            "cited_by_count": self.cited_by_count,
            "relevance": self.relevance,
            "year_percentile": self.year_percentile,
        }


def compute_overlooked(
    conn: Connection,
    *,
    axis_id: int,
    sources_client,
    model,
    vector_store,
    cap: int = DEFAULT_CANDIDATE_CAP,
    low_percentile: float = DEFAULT_LOW_PERCENTILE,
    min_year_peers: int = DEFAULT_MIN_YEAR_PEERS,
) -> list[OverlookedCandidate]:
    """Compute the overlooked-work candidates for `axis_id`. Pure over its inputs (the only writes are `_embed_axis`'s
    idempotent axis-embedding cache); fail-closed via the sources client → []. The two inputs are never combined."""
    axis = get_axis(conn, axis_id)
    if axis is None:
        return []
    label = str(axis["label"] or "").strip()
    if not label:
        return []
    topic_lookup = getattr(sources_client, "fetch_topic_for_subject_strict", sources_client.fetch_topic_for_subject)
    works_lookup = getattr(sources_client, "fetch_topic_works_strict", sources_client.fetch_topic_works)
    topic_id = topic_lookup(conn, label)
    if not topic_id:
        return []
    works = works_lookup(conn, topic_id)
    works = [w for w in works if not _in_library(conn, w)]
    if not works:
        return []

    # Relevance (local): cosine between the axis vector and each candidate's on-device-embedded abstract.
    axis_vec = _l2(_embed_axis(conn, axis=axis, model=model, vector_store=vector_store))
    texts = [(w.abstract or w.title or "") for w in works]
    vecs = [_l2(v) for v in model.encode_texts(texts)]
    relevance = {w.openalex_work_id: _cos(axis_vec, v) for w, v in zip(works, vecs, strict=True)}

    # Vintage baseline (local): percentile of cited_by_count among same publication_year peers in the fetched sample.
    peers_by_year: dict[int, list[int]] = {}
    for w in works:
        if w.year is not None:
            peers_by_year.setdefault(w.year, []).append(w.cited_by_count)
    percentile: dict[str, float | None] = {}
    for w in works:
        peers = peers_by_year.get(w.year, []) if w.year is not None else []
        percentile[w.openalex_work_id] = (
            _percentile_rank(w.cited_by_count, peers) if len(peers) >= min_year_peers else None
        )

    out = [
        OverlookedCandidate(
            openalex_work_id=w.openalex_work_id,
            doi=w.doi,
            title=w.title,
            year=w.year,
            cited_by_count=w.cited_by_count,
            relevance=round(relevance[w.openalex_work_id], 4),
            year_percentile=round(percentile[w.openalex_work_id], 4),  # type: ignore[arg-type]
        )
        for w in works
        if percentile[w.openalex_work_id] is not None and percentile[w.openalex_work_id] <= low_percentile
    ]
    out.sort(key=lambda c: -c.relevance)
    return out[:cap]


def _in_library(conn: Connection, work) -> bool:
    if work.doi and find_existing_paper_by_identity(conn, doi=work.doi) is not None:
        return True
    return find_existing_paper_by_identity(conn, openalex_work_id=work.openalex_work_id) is not None


def _l2(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else list(vector)


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _percentile_rank(value: int, peers: list[int]) -> float:
    """Fraction of same-year peers cited FEWER times than `value` (in [0, 1]); low = under-cited for its vintage."""
    if not peers:
        return 0.0
    return sum(1 for c in peers if c < value) / len(peers)
