"""SP4c: the recipient-side cross-user provenance log — record what happened to a share the local user acted on
(imported or dismissed), and let the "Shared with me" panel skip re-nagging about one already handled.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, insert, select

from app.backend.persistence.schema import received_shares


def record_import(conn: Connection, *, share_id: int, sender_sub: str, summary: dict[str, Any]) -> None:
    conn.execute(
        insert(received_shares).values(
            share_id=share_id, sender_sub=sender_sub, status="imported", summary_json=summary
        )
    )


def record_dismissal(conn: Connection, *, share_id: int, sender_sub: str) -> None:
    conn.execute(
        insert(received_shares).values(share_id=share_id, sender_sub=sender_sub, status="dismissed", summary_json=None)
    )


def status_for_share_ids(conn: Connection, share_ids: list[int]) -> dict[int, str]:
    """``{share_id: status}`` for whichever of `share_ids` have already been acted on; missing keys = never
    acted on yet (still pending in the recipient's inbox)."""
    if not share_ids:
        return {}
    rows = conn.execute(
        select(received_shares.c.share_id, received_shares.c.status).where(received_shares.c.share_id.in_(share_ids))
    )
    return {int(r.share_id): r.status for r in rows}
