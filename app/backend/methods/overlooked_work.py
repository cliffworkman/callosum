"""Overlooked-work finder — the topical remediation of the citation-equity audit (inc 228, backlog #25 SP2).

Given a paper's reference list, surface topically-relevant work the list OMITS — candidates the author may have
missed — ranked by **local** content-embedding similarity (scientific-paper embeddings) between the focal paper's
title+abstract and each candidate's, each with an inspectable "why this is a real topical match" (the labeled
cosine + shared OpenAlex concepts).

Load-bearing (the spec's veto-level lines + the A-A no-accusation boundary):
- **Only SURFACE / ADD — never suggest dropping a citation.** There is no "drop" path here, structurally.
- **The reason is topical relevance — never an author's identity.** No identity is read, computed, or shown;
  equity improves as a *byproduct* of better scholarship, not as a reason to cite anyone.
- **No quota, no tokenism.** "Relevant work you may have missed," never "add N to hit a target."
- Candidates the human judges (#3/#5; nothing auto-inserts); one labeled cosine, no opaque composite (#7); the
  shared-concept basis is inspectable (#8). Ranked by **topical match**, never by citation count (which would
  amplify the Matthew effect the audit measures).

Pure + local + no-I/O (takes already-fetched OpenAlex candidate dicts + an embedding model). Bounded (rule #4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

DEFAULT_THRESHOLD = (
    0.55  # cosine floor — below this a candidate is not "clearly relevant" → not shown (no fabricated relevance)
)
MAX_CANDIDATES = 1000  # defensive cap on the pool to embed (rule #4)
DEFAULT_TOP_K = 12


@dataclass(frozen=True)
class OverlookedCandidate:
    openalex_work_id: str | None
    doi: str | None
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    match: float  # 0..1 — the labeled cosine to the focal paper (the inspectable "why", not a verdict)
    shared_concepts: list[str]  # focal ∩ candidate concept names (the inspectable shared topic)
    abstract: str | None  # so the user can READ before deciding — the basis, not just a title + a number
    in_library: bool  # already in your library (relevant, just not cited here) — shown, not "add"-able

    def to_dict(self) -> dict[str, Any]:
        return {
            "openalex_work_id": self.openalex_work_id,
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "match": self.match,
            "shared_concepts": self.shared_concepts,
            "abstract": self.abstract,
            "in_library": self.in_library,
        }


def _candidate_text(c: dict) -> str:
    title = str(c.get("title") or "").strip()
    abstract = str(c.get("abstract") or "").strip()
    return (title + ". " + abstract).strip() if abstract else title


def _unit_rows(vectors: list[list[float]]) -> np.ndarray:
    arr = np.asarray(vectors, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / (norms + 1e-12)


def rank_overlooked(
    *,
    focal_text: str,
    candidates: list[dict[str, Any]],
    focal_concepts: list[str] | None,
    embedding_model: Any,
    threshold: float = DEFAULT_THRESHOLD,
    top_k: int = DEFAULT_TOP_K,
) -> list[OverlookedCandidate]:
    """Rank `candidates` (OpenAlex meta-with-abstract dicts; the worker has already excluded the already-cited +
    the focal itself, and stamped each with `in_library`) by local embedding cosine to `focal_text`. Keep only
    those ≥ `threshold` (no fabricated relevance), top_k by score. The shared-concept "why" = focal ∩ candidate
    OpenAlex concepts. **No identity, no verdict, no drop, no quota.**"""
    pool = [c for c in candidates if _candidate_text(c)][:MAX_CANDIDATES]
    if not focal_text.strip() or not pool:
        return []
    vectors = embedding_model.encode_texts([focal_text] + [_candidate_text(c) for c in pool])
    units = _unit_rows(vectors)
    focal_u, cand_u = units[0], units[1:]
    sims = cand_u @ focal_u
    focal_cset = {str(x).lower() for x in (focal_concepts or [])}
    out: list[OverlookedCandidate] = []
    for c, sim in zip(pool, sims, strict=False):
        score = round(float(max(0.0, min(1.0, sim))), 2)
        if score < threshold:
            continue  # below the bar → not shown (silence ≠ certificate, but no fabricated relevance either)
        shared = [str(x) for x in (c.get("concepts") or []) if str(x).lower() in focal_cset][:6]
        out.append(
            OverlookedCandidate(
                openalex_work_id=c.get("openalex_work_id"),
                doi=c.get("doi"),
                title=str(c.get("title") or "untitled"),
                authors=[str(a) for a in (c.get("authors") or [])][:5],
                year=c.get("year") if isinstance(c.get("year"), int) else None,
                venue=c.get("venue"),
                match=score,
                shared_concepts=shared,
                abstract=(str(c["abstract"]) if c.get("abstract") else None),
                in_library=bool(c.get("in_library")),
            )
        )
    out.sort(key=lambda x: x.match, reverse=True)
    return out[:top_k]
