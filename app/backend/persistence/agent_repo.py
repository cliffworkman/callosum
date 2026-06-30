"""Data access for the agent-writes audit log (B1 SP2).

One row per MCP-agent write — the action + the target paper + enough `detail_json` to undo it — backing the
Settings "AI agent activity" review + one-click revert. Bound parameters only (rule #3).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update

from app.backend.persistence.schema import agent_writes, notes


def record_agent_write(
    conn: Connection, *, action: str, target_paper_id: int | None, detail: dict[str, Any], tool: str = ""
) -> int:
    result = conn.execute(
        insert(agent_writes).values(action=action, target_paper_id=target_paper_id, detail_json=detail, tool=tool)
    )
    return int(result.inserted_primary_key[0])


def list_agent_writes(conn: Connection, *, limit: int = 100) -> list[RowMapping]:
    rows = conn.execute(select(agent_writes).order_by(agent_writes.c.id.desc()).limit(limit)).mappings()
    return list(rows)


def get_agent_write(conn: Connection, write_id: int) -> RowMapping | None:
    return conn.execute(select(agent_writes).where(agent_writes.c.id == write_id)).mappings().one_or_none()


def mark_reverted(conn: Connection, write_id: int) -> None:
    conn.execute(update(agent_writes).where(agent_writes.c.id == write_id).values(reverted_at=func.current_timestamp()))


def delete_note(conn: Connection, note_id: int) -> bool:
    return conn.execute(delete(notes).where(notes.c.id == note_id)).rowcount > 0
