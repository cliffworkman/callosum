"""Literature gap-finder (inc 135) — works MANY of the library's papers cite but the library doesn't have.

For each live paper with a DOI, aggregate its OpenAlex `referenced_works`; a work cited by >= `min_citations` of
your papers, not already in the library and not dismissed, is a **candidate** ("cited by N of your papers"). The
count is a fact about *your* library's citing — never a global importance/quality rank; the human Adds/Dismisses.
Pure aggregation over an injected `openalex_client` (so tests run offline); coverage is reported, not implied.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, func, select

from app.backend.acquisition.registry import PaperRef
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.schema import papers

_COVERAGE_NOTE = (
    "Based on the references OpenAlex has for your library — coverage is partial, so this isn't an exhaustive "
    "list. The count is how many of your own papers cite each work, not a measure of importance."
)


@dataclass(frozen=True)
class GapCandidate:
    openalex_work_id: str
    doi: str | None
    title: str | None
    authors: list[str]
    year: int | None
    cited_by_in_library: int


def compute_gaps(
    conn: Connection,
    *,
    openalex_client,
    dismissed: set[str],
    min_citations: int = 3,
    max_candidates: int = 50,
) -> tuple[list[GapCandidate], dict]:
    """Returns (candidates, coverage) where coverage = {checked, total, note}. Bounded OpenAlex fetches."""
    doi_rows = conn.execute(
        select(papers.c.id, papers.c.doi).where(papers.c.deleted_at.is_(None), papers.c.doi.isnot(None))
    ).all()
    total_live = conn.execute(select(func.count()).select_from(papers).where(papers.c.deleted_at.is_(None))).scalar()

    # ref_id -> the set of YOUR papers that cite it (a set so a duplicate ref within one paper counts once)
    citers: dict[str, set[int]] = {}
    for paper_id, doi in doi_rows:
        try:
            refs = openalex_client.fetch_referenced_works(conn, PaperRef(doi=doi))
        except Exception:
            refs = []
        for ref_id in set(refs):
            citers.setdefault(ref_id, set()).add(int(paper_id))

    ranked = sorted(
        ((rid, c) for rid, c in citers.items() if len(c) >= min_citations and rid not in dismissed),
        key=lambda item: (-len(item[1]), item[0]),
    )

    candidates: list[GapCandidate] = []
    for ref_id, citer_ids in ranked[: max_candidates * 3]:  # bound the per-candidate metadata fetches
        meta = openalex_client.fetch_work_meta(conn, ref_id)
        doi = (meta or {}).get("doi")
        if not meta or not doi or doi in dismissed:
            continue
        if find_existing_paper_by_identity(conn, doi=doi) is not None:  # already in the library → not a gap
            continue
        candidates.append(
            GapCandidate(
                openalex_work_id=ref_id,
                doi=doi,
                title=meta.get("title"),
                authors=meta.get("authors") or [],
                year=meta.get("year"),
                cited_by_in_library=len(citer_ids),
            )
        )
        if len(candidates) >= max_candidates:
            break

    coverage = {"checked": len(doi_rows), "total": int(total_live or 0), "note": _COVERAGE_NOTE}
    return candidates, coverage
