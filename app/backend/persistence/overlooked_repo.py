"""Data access for the overlooked-work lens persistent cache (backlog #37).

One scope = ``axis_id``. ``replace_overlooked_candidates`` is authoritative: it deletes every row for the axis and
re-inserts the freshly computed set (so a stale candidate vanishes). ``read_overlooked_candidates`` returns the
cached rows + the snapshot timestamp; the router filters dismissed / now-in-library at read time. Mirrors
``gap_repo`` (inc 137). The stored rows carry the two SEPARATE visible inputs (``relevance`` + ``year_percentile``)
and NO author/identity column — the lens is identity-agnostic by construction.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select

from app.backend.methods.overlooked import OverlookedCandidate
from app.backend.persistence.schema import overlooked_candidates


def replace_overlooked_candidates(
    conn: Connection,
    axis_id: int,
    candidates: list[OverlookedCandidate],
    *,
    computed_at: str,
) -> None:
    """Replace ALL cached rows for ``axis_id`` with ``candidates`` (authoritative refresh)."""
    conn.execute(delete(overlooked_candidates).where(overlooked_candidates.c.axis_id == axis_id))
    if not candidates:
        return
    conn.execute(
        insert(overlooked_candidates),
        [
            {
                "axis_id": axis_id,
                "openalex_work_id": c.openalex_work_id,
                "doi": c.doi,
                "title": c.title,
                "year": c.year,
                "cited_by_count": c.cited_by_count,
                "relevance": c.relevance,
                "year_percentile": c.year_percentile,
                "computed_at": computed_at,
            }
            for c in candidates
        ],
    )


def read_overlooked_candidates(conn: Connection, axis_id: int) -> tuple[list[dict[str, Any]], str | None]:
    """Return (rows, computed_at) for an axis, ranked by ``relevance`` desc. ([], None) if uncomputed."""
    rows = conn.execute(
        select(overlooked_candidates)
        .where(overlooked_candidates.c.axis_id == axis_id)
        .order_by(overlooked_candidates.c.relevance.desc(), overlooked_candidates.c.id)
    ).all()
    if not rows:
        return [], None
    computed_at = rows[0]._mapping["computed_at"]
    return [dict(r._mapping) for r in rows], computed_at
