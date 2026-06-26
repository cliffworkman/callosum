"""Data access for the gap-finder persistent cache (inc 137).

One scope = ``(direction, axis_id)``. ``replace_gap_candidates`` is authoritative: it deletes every row for the
scope and re-inserts the freshly computed set (so a stale candidate vanishes). ``read_gap_candidates`` returns the
cached rows + the snapshot timestamp; the router filters dismissed / now-in-library at read time.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, and_, delete, insert, select

from app.backend.clustering.gapfinder import GapCandidate
from app.backend.persistence.schema import gap_candidates


def _scope_clause(direction: str, axis_id: int | None):
    if axis_id is None:
        return and_(gap_candidates.c.direction == direction, gap_candidates.c.axis_id.is_(None))
    return and_(gap_candidates.c.direction == direction, gap_candidates.c.axis_id == axis_id)


def replace_gap_candidates(
    conn: Connection,
    direction: str,
    axis_id: int | None,
    candidates: list[GapCandidate],
    *,
    computed_at: str,
) -> None:
    """Replace ALL cached rows for ``(direction, axis_id)`` with ``candidates`` (authoritative refresh)."""
    conn.execute(delete(gap_candidates).where(_scope_clause(direction, axis_id)))
    if not candidates:
        return
    conn.execute(
        insert(gap_candidates),
        [
            {
                "direction": direction,
                "axis_id": axis_id,
                "openalex_work_id": c.openalex_work_id,
                "doi": c.doi,
                "title": c.title,
                "authors": c.authors,
                "year": c.year,
                "cited_by_in_library": c.cited_by_in_library,
                "computed_at": computed_at,
            }
            for c in candidates
        ],
    )


def read_gap_candidates(
    conn: Connection, direction: str, axis_id: int | None
) -> tuple[list[dict[str, Any]], str | None]:
    """Return (rows, computed_at) for a scope, ordered by ``cited_by_in_library`` desc. ([], None) if uncomputed."""
    rows = conn.execute(
        select(gap_candidates)
        .where(_scope_clause(direction, axis_id))
        .order_by(gap_candidates.c.cited_by_in_library.desc(), gap_candidates.c.id)
    ).all()
    if not rows:
        return [], None
    computed_at = rows[0]._mapping["computed_at"]
    return [dict(r._mapping) for r in rows], computed_at
