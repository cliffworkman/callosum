"""Data access for the reading queue (inc 219).

A personal, ordered to-read list — papers the user wants to read, drag-to-reorder. NOT an axis (no semantic
scoring): its own small table, recalled from the left-pane "Queue" tab. ``position`` drives the manual order
(the inc-211 curated-axis pattern); the list excludes soft-deleted (trashed) papers. One row per paper (UNIQUE) →
add is idempotent. Bound-param SQLAlchemy Core (rule #3). Extracted to its own module (like saved_search_repo /
tags_repo) so repository.py stays under the 600-line cap.
"""

from __future__ import annotations

from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update

from app.backend.persistence.schema import papers, reading_queue


def list_reading_queue(conn: Connection) -> list[RowMapping]:
    """The queue, ordered by manual position (NULLS last, then id), joined to papers for display. Excludes trashed
    papers (a soft-deleted paper stays linked until purged, but must not show in the queue)."""
    stmt = (
        select(
            papers.c.id,
            papers.c.title,
            papers.c.year,
            papers.c.csl_json,
            papers.c.first_author_family_name,
            reading_queue.c.position,
        )
        .select_from(reading_queue.join(papers, papers.c.id == reading_queue.c.paper_id))
        .where(papers.c.deleted_at.is_(None))
        .order_by(reading_queue.c.position.is_(None), reading_queue.c.position, papers.c.id)
    )
    return list(conn.execute(stmt).mappings())


def is_in_queue(conn: Connection, paper_id: int) -> bool:
    return conn.execute(select(reading_queue.c.id).where(reading_queue.c.paper_id == paper_id)).scalar() is not None


def add_to_queue(conn: Connection, paper_id: int) -> bool:
    """Append a paper to the end of the queue. Idempotent: returns False if it's already queued (no duplicate row).
    Caller commits."""
    if is_in_queue(conn, paper_id):
        return False
    next_pos = conn.execute(select(func.coalesce(func.max(reading_queue.c.position), -1) + 1)).scalar_one()
    conn.execute(insert(reading_queue).values(paper_id=paper_id, position=next_pos))
    return True


def remove_from_queue(conn: Connection, paper_id: int) -> bool:
    """Remove a paper from the queue (the × and ✓ Done both call this). False if it wasn't queued. Caller commits."""
    result = conn.execute(delete(reading_queue).where(reading_queue.c.paper_id == paper_id))
    return bool(result.rowcount)


def set_queue_order(conn: Connection, paper_ids: list[int]) -> None:
    """Write the manual order: position = index in ``paper_ids`` (the drag-to-reorder write). ``paper_ids`` must be
    EXACTLY the queue's current members (no partial / foreign ids), else ValueError. Caller commits."""
    current = {int(r[0]) for r in conn.execute(select(reading_queue.c.paper_id))}
    if len(paper_ids) != len(current) or {int(p) for p in paper_ids} != current:
        raise ValueError("paper_ids must be exactly the reading queue's current members")
    for index, pid in enumerate(paper_ids):
        conn.execute(update(reading_queue).where(reading_queue.c.paper_id == int(pid)).values(position=index))
