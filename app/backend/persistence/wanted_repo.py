"""Data access for the OA-acquisition wanted list (inc 76).

A ``wanted_items`` row is a paper the user wants an open-access copy of — library-linked (``paper_id`` set, a
PDF-less library paper) or external (``paper_id`` NULL, a not-yet-imported paper carrying its own
doi/pmid/title). Split out (like ``tags_repo``/``dedup_repo``/``acquisition_repo``) to keep ``repository.py``
under the 600-line cap. All bound-param (rule #3).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, and_, delete, func, insert, or_, select, update

from app.backend.persistence.schema import attachments, papers, wanted_items


def _has_available_pdf():
    """A fresh correlated EXISTS: the paper (papers.c.id, in the enclosing query) has an available PDF."""
    return (
        select(attachments.c.id)
        .where(
            attachments.c.paper_id == papers.c.id,
            attachments.c.attachment_type == "pdf",
            attachments.c.availability == "available",
        )
        .exists()
    )


def add_wanted(
    conn: Connection,
    *,
    paper_id: int | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    title: str | None = None,
    note: str | None = None,
) -> int:
    """Get-or-create a wanted row. Library wants dedup by ``paper_id``; external wants by doi, else pmid, else
    title (among external rows). Returns the row id."""
    doi_n = doi.strip().lower() if doi and doi.strip() else None
    pmid_n = str(pmid).strip() if pmid and str(pmid).strip() else None
    title_n = title.strip() if title and title.strip() else None

    if paper_id is not None:
        existing = conn.execute(select(wanted_items.c.id).where(wanted_items.c.paper_id == paper_id)).scalar()
        if existing is not None:
            return int(existing)
    else:
        cond = None
        if doi_n:
            cond = and_(wanted_items.c.paper_id.is_(None), func.lower(wanted_items.c.doi) == doi_n)
        elif pmid_n:
            cond = and_(wanted_items.c.paper_id.is_(None), wanted_items.c.pmid == pmid_n)
        elif title_n:
            cond = and_(wanted_items.c.paper_id.is_(None), func.lower(wanted_items.c.title) == title_n.lower())
        if cond is not None:
            existing = conn.execute(select(wanted_items.c.id).where(cond)).scalar()
            if existing is not None:
                return int(existing)

    result = conn.execute(
        insert(wanted_items).values(
            paper_id=paper_id, doi=doi_n, pmid=pmid_n, title=title_n, note=note, status="wanted"
        )
    )
    return int(result.inserted_primary_key[0])


def list_wanted(conn: Connection) -> list[dict[str, Any]]:
    """All wanted rows, newest-first within status, with the linked paper's title/year (LEFT JOIN)."""
    j = wanted_items.outerjoin(papers, wanted_items.c.paper_id == papers.c.id)
    rows = conn.execute(
        select(
            wanted_items.c.id,
            wanted_items.c.paper_id,
            wanted_items.c.doi,
            wanted_items.c.pmid,
            wanted_items.c.title,
            wanted_items.c.note,
            wanted_items.c.status,
            wanted_items.c.last_checked_at,
            wanted_items.c.last_result,
            papers.c.title.label("paper_title"),
            papers.c.year.label("paper_year"),
            papers.c.deleted_at.label("paper_deleted_at"),
        )
        .select_from(j)
        .order_by(wanted_items.c.status, wanted_items.c.id.desc())
    ).mappings()
    return [dict(r) for r in rows]


def get_wanted(conn: Connection, wanted_id: int) -> dict[str, Any] | None:
    row = conn.execute(select(wanted_items).where(wanted_items.c.id == wanted_id)).mappings().first()
    return dict(row) if row is not None else None


def remove_wanted(conn: Connection, wanted_id: int) -> bool:
    return conn.execute(delete(wanted_items).where(wanted_items.c.id == wanted_id)).rowcount > 0


def sync_from_library(conn: Connection) -> int:
    """Add a wanted row for every live PDF-less library paper not already on the list. Returns count added."""
    already = select(wanted_items.c.paper_id).where(wanted_items.c.paper_id.is_not(None))
    paper_ids = (
        conn.execute(
            select(papers.c.id).where(
                papers.c.deleted_at.is_(None), ~_has_available_pdf(), papers.c.id.not_in(already)
            )
        )
        .scalars()
        .all()
    )
    for pid in paper_ids:
        conn.execute(insert(wanted_items).values(paper_id=int(pid), status="wanted"))
    return len(paper_ids)


def list_open(conn: Connection) -> list[dict[str, Any]]:
    """Open ("wanted") rows for the re-check: includes a library row's own paper identifiers, and excludes
    rows whose linked paper is soft-deleted (don't acquire for a trashed paper)."""
    j = wanted_items.outerjoin(papers, wanted_items.c.paper_id == papers.c.id)
    rows = conn.execute(
        select(
            wanted_items.c.id,
            wanted_items.c.paper_id,
            wanted_items.c.doi,
            wanted_items.c.pmid,
            wanted_items.c.title,
            papers.c.doi.label("paper_doi"),
            papers.c.title.label("paper_title"),
            papers.c.csl_json.label("paper_csl_json"),
        )
        .select_from(j)
        .where(
            wanted_items.c.status == "wanted",
            or_(wanted_items.c.paper_id.is_(None), papers.c.deleted_at.is_(None)),
        )
        .order_by(wanted_items.c.id)
    ).mappings()
    return [dict(r) for r in rows]


def mark_checked(conn: Connection, wanted_id: int, *, result: str) -> None:
    conn.execute(
        update(wanted_items)
        .where(wanted_items.c.id == wanted_id)
        .values(last_checked_at=func.current_timestamp(), last_result=result, updated_at=func.current_timestamp())
    )


def mark_fulfilled(conn: Connection, wanted_id: int, *, paper_id: int, result: str) -> None:
    conn.execute(
        update(wanted_items)
        .where(wanted_items.c.id == wanted_id)
        .values(
            status="fulfilled",
            paper_id=paper_id,
            last_checked_at=func.current_timestamp(),
            last_result=result,
            updated_at=func.current_timestamp(),
        )
    )


def coverage_stats(conn: Connection) -> dict[str, Any]:
    """Live-paper OA coverage: totals (with/without PDF), acquired attachments by OA color, wanted counts."""
    live = papers.c.deleted_at.is_(None)
    total = conn.execute(select(func.count()).select_from(papers).where(live)).scalar() or 0
    with_pdf = conn.execute(select(func.count()).select_from(papers).where(live, _has_available_pdf())).scalar() or 0
    acquired = {"gold": 0, "green": 0, "bronze": 0}
    color_rows = conn.execute(
        select(attachments.c.oa_color, func.count())
        .select_from(attachments.join(papers, attachments.c.paper_id == papers.c.id))
        .where(live, attachments.c.oa_color.is_not(None))
        .group_by(attachments.c.oa_color)
    ).all()
    for color, n in color_rows:
        if color in acquired:
            acquired[color] = int(n)
    wanted_open = (
        conn.execute(select(func.count()).select_from(wanted_items).where(wanted_items.c.status == "wanted")).scalar() or 0
    )
    wanted_fulfilled = (
        conn.execute(select(func.count()).select_from(wanted_items).where(wanted_items.c.status == "fulfilled")).scalar()
        or 0
    )
    return {
        "library_total": int(total),
        "with_pdf": int(with_pdf),
        "without_pdf": int(total) - int(with_pdf),
        "acquired_oa": acquired,
        "wanted_open": int(wanted_open),
        "wanted_fulfilled": int(wanted_fulfilled),
    }
