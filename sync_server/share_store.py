"""SP4b/c -- the share mailbox's storage logic (pure SQLAlchemy Core, dialect-portable). `create_share` is the
write; `list_shares_for_recipient`/`get_share` (SP4c) are the reads the recipient-facing "Shared with me"
surface needs, on the same `shares` table (already indexed on `recipient_sub` for exactly this).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, insert, select

from sync_server.schema import shares


def create_share(conn: Connection, *, sender_sub: str, recipient_sub: str, wrapped_key: str, ciphertext: str) -> int:
    """Persist one share addressed to `recipient_sub`. Both `wrapped_key` and `ciphertext` are opaque strings
    the server never parses or decodes. Returns the new row's id."""
    result = conn.execute(
        insert(shares).values(
            sender_sub=sender_sub,
            recipient_sub=recipient_sub,
            wrapped_key=wrapped_key,
            ciphertext=ciphertext,
            created_at=datetime.now(timezone.utc),
        )
    )
    return int(result.inserted_primary_key[0])


def list_shares_for_recipient(conn: Connection, recipient_sub: str, *, limit: int = 200) -> list[dict[str, Any]]:
    """The caller's own inbox -- id/sender/timestamp only, never `wrapped_key`/`ciphertext` (keeps the list
    response small; content is fetched per-item via `get_share`)."""
    rows = conn.execute(
        select(shares.c.id, shares.c.sender_sub, shares.c.created_at)
        .where(shares.c.recipient_sub == recipient_sub)
        .order_by(shares.c.created_at.desc())
        .limit(limit)
    ).mappings()
    return [dict(r) for r in rows]


def get_share(conn: Connection, share_id: int) -> dict[str, Any] | None:
    """The full row (including ciphertext), or None if it doesn't exist. Callers MUST check `recipient_sub`
    against the caller's own identity before returning content -- this function does no authorization."""
    row = conn.execute(select(shares).where(shares.c.id == share_id)).mappings().first()
    return None if row is None else dict(row)
