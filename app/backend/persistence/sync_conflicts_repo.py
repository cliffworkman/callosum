"""SP3c: the conflict-review repo — list/get/resolve rows in `sync_conflicts` (the losing side of a last-write-wins
merge, kept for recovery so a multi-device edit collision is surfaced, never silently dropped — value A4).

Resolving **"theirs"** is a pure bookkeeping flip: the remote value already won and is live in the domain table, so
nothing else needs writing. Resolving **"mine"** restores the kept losing payload via
`sync.engine.apply_conflict_resolution` (the same apply path a remote winner takes) — the next `run_sync` picks the
restored row up as an ordinary local change and pushes it, out-versioning the remote side with no separate
versioning logic here.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import Connection, select, update

from app.backend.persistence.schema import sync_conflicts
from app.backend.sync.engine import apply_conflict_resolution


def list_unresolved_conflicts(conn: Connection) -> list[dict]:
    rows = conn.execute(
        select(sync_conflicts).where(sync_conflicts.c.resolved == 0).order_by(sync_conflicts.c.detected_at.desc())
    ).mappings()
    return [dict(r) for r in rows]


def get_conflict(conn: Connection, conflict_id: int) -> dict | None:
    row = conn.execute(select(sync_conflicts).where(sync_conflicts.c.id == conflict_id)).mappings().first()
    return None if row is None else dict(row)


def resolve_conflict(conn: Connection, conflict_id: int, side: Literal["mine", "theirs"]) -> bool:
    """Resolve one conflict. Returns False if the id doesn't exist, is already resolved, or (side="mine") the
    local write couldn't complete (an unresolved FK dependency) — the caller must treat False as a failure, never
    mark a conflict resolved without the value actually having been restored."""
    row = get_conflict(conn, conflict_id)
    if row is None or row["resolved"]:
        return False
    if side == "mine":
        ok = apply_conflict_resolution(conn, row["collection"], row["record_id"], row["losing_payload"] or {})
        if not ok:
            return False
    conn.execute(update(sync_conflicts).where(sync_conflicts.c.id == conflict_id).values(resolved=1))
    return True
