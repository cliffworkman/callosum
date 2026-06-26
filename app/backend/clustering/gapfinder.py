"""Literature gap-finder (inc 135 backward; inc 137 forward + axis-scoped).

Two directions, both honest counts over *your* library — never a global importance/quality rank:

- **backward** (inc 135): for each library paper, aggregate its OpenAlex `referenced_works`; a work cited by
  >= `min_citations` of your papers, not in the library and not dismissed, is a candidate ("cited by N of your
  papers").
- **forward** (inc 137): for each library paper, aggregate the works that **cite** it; an external work that
  cites >= `min_citations` of your papers is a candidate ("cites N of your papers").

`axis_id` restricts the scanned papers to that axis's members (the inc-63 cluster-node subquery). Pure aggregation
over an injected `openalex_client` (tests run offline); coverage is reported, not implied. The human Adds/Dismisses.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, func, select

from app.backend.acquisition.registry import PaperRef
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.schema import cluster_node_papers, cluster_nodes, papers

_NOTE_BACKWARD = (
    "Based on the references OpenAlex has for your library — coverage is partial, so this isn't an exhaustive "
    "list. The count is how many of your own papers cite each work, not a measure of importance."
)
_NOTE_FORWARD = (
    "Based on the citing works OpenAlex records for your library — coverage is partial, so this isn't an "
    "exhaustive list. The count is how many of your own papers each work cites, not a measure of importance."
)


@dataclass(frozen=True)
class GapCandidate:
    openalex_work_id: str
    doi: str | None
    title: str | None
    authors: list[str]
    year: int | None
    cited_by_in_library: int


def _scoped_paper_rows(conn: Connection, axis_id: int | None) -> list[tuple[int, str]]:
    """Live papers with a DOI; if axis_id given, restrict to that axis's members (inc-63 subquery)."""
    stmt = select(papers.c.id, papers.c.doi).where(papers.c.deleted_at.is_(None), papers.c.doi.isnot(None))
    if axis_id is not None:
        axis_members = (
            select(cluster_node_papers.c.paper_id)
            .join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
            .where(cluster_nodes.c.axis_id == axis_id)
        )
        stmt = stmt.where(papers.c.id.in_(axis_members))
    return [(int(pid), doi) for pid, doi in conn.execute(stmt).all()]


def _scope_total(conn: Connection, axis_id: int | None) -> int:
    """Count of live papers in scope (with or without a DOI) — the denominator for the coverage line."""
    stmt = select(func.count()).select_from(papers).where(papers.c.deleted_at.is_(None))
    if axis_id is not None:
        axis_members = (
            select(cluster_node_papers.c.paper_id)
            .join(cluster_nodes, cluster_nodes.c.id == cluster_node_papers.c.cluster_node_id)
            .where(cluster_nodes.c.axis_id == axis_id)
        )
        stmt = stmt.where(papers.c.id.in_(axis_members))
    return int(conn.execute(stmt).scalar() or 0)


def _emit(
    conn: Connection,
    citers: dict[str, set[int]],
    meta_by_id: dict[str, dict],
    dismissed: set[str],
    min_citations: int,
    max_candidates: int,
) -> list[GapCandidate]:
    """Rank by count, exclude dismissed / no-DOI / already-in-library, build candidates."""
    ranked = sorted(
        ((wid, c) for wid, c in citers.items() if len(c) >= min_citations and wid not in dismissed),
        key=lambda item: (-len(item[1]), item[0]),
    )
    candidates: list[GapCandidate] = []
    for work_id, citer_ids in ranked:
        meta = meta_by_id.get(work_id)
        doi = (meta or {}).get("doi")
        if not meta or not doi or doi in dismissed:
            continue
        if find_existing_paper_by_identity(conn, doi=doi) is not None:  # already in the library → not a gap
            continue
        candidates.append(
            GapCandidate(
                openalex_work_id=work_id,
                doi=doi,
                title=meta.get("title"),
                authors=meta.get("authors") or [],
                year=meta.get("year"),
                cited_by_in_library=len(citer_ids),
            )
        )
        if len(candidates) >= max_candidates:
            break
    return candidates


def compute_gaps(
    conn: Connection,
    *,
    openalex_client,
    dismissed: set[str],
    direction: str = "backward",
    axis_id: int | None = None,
    min_citations: int = 3,
    max_candidates: int = 50,
) -> tuple[list[GapCandidate], dict]:
    """Returns (candidates, coverage) where coverage = {checked, total, note}. Bounded OpenAlex fetches."""
    scoped = _scoped_paper_rows(conn, axis_id)

    # work_id -> the set of YOUR papers it relates to (a set so a duplicate within one paper counts once)
    citers: dict[str, set[int]] = {}
    meta_by_id: dict[str, dict] = {}

    if direction == "forward":
        for paper_id, doi in scoped:
            try:
                work_id = openalex_client.fetch_work_id(conn, PaperRef(doi=doi))
                citing = openalex_client.fetch_citing_works(conn, work_id) if work_id else []
            except Exception:
                citing = []
            for cw in citing:
                cid = cw.get("openalex_work_id")
                if not cid:
                    continue
                citers.setdefault(cid, set()).add(paper_id)
                meta_by_id.setdefault(cid, cw)  # metadata rides the citing dict — no second fetch
        note = _NOTE_FORWARD
    else:  # backward
        for paper_id, doi in scoped:
            try:
                refs = openalex_client.fetch_referenced_works(conn, PaperRef(doi=doi))
            except Exception:
                refs = []
            for ref_id in set(refs):
                citers.setdefault(ref_id, set()).add(paper_id)
        # backward needs a metadata fetch per surviving candidate (bound it: only those over the threshold)
        eligible = sorted(
            (wid for wid, c in citers.items() if len(c) >= min_citations and wid not in dismissed),
            key=lambda wid: (-len(citers[wid]), wid),
        )[: max_candidates * 3]
        for ref_id in eligible:
            meta = openalex_client.fetch_work_meta(conn, ref_id)
            if meta:
                meta_by_id[ref_id] = meta
        note = _NOTE_BACKWARD

    candidates = _emit(conn, citers, meta_by_id, dismissed, min_citations, max_candidates)
    coverage = {"checked": len(scoped), "total": _scope_total(conn, axis_id), "note": note}
    return candidates, coverage
