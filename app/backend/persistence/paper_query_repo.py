"""Read-only paper list/query helpers extracted from ``repository.py`` to hold it under the 600-line cap (inc 301;
the inc-137/220/262 leaf-extraction pattern). Re-exported from ``repository`` so existing call sites are unchanged.
Bound-param SQLAlchemy Core only (rule #3)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Connection, RowMapping, func, select

from app.backend.persistence.schema import papers


def get_papers_for_export(conn: Connection, paper_ids: Sequence[int]) -> list[RowMapping]:
    """Full rows (incl. csl_json) for the given LIVE paper ids, ordered by id, for citation export (inc 70).
    Bound-param IN (rule #3); trashed papers are never exported."""
    if not paper_ids:
        return []
    stmt = (
        select(papers)
        .where(papers.c.id.in_(set(int(pid) for pid in paper_ids)), papers.c.deleted_at.is_(None))
        .order_by(papers.c.id)
    )
    return list(conn.execute(stmt).mappings())


def list_item_types(conn: Connection) -> list[RowMapping]:
    """Distinct CSL item types present among LIVE papers + a per-type count, most-common first (inc 91).
    Drives the library Type-filter dropdown so it only offers types that actually exist (honest facets)."""
    stmt = (
        select(papers.c.item_type, func.count().label("count"))
        .where(papers.c.deleted_at.is_(None), papers.c.item_type.is_not(None))
        .group_by(papers.c.item_type)
        .order_by(func.count().desc(), papers.c.item_type)
    )
    return list(conn.execute(stmt).mappings())
