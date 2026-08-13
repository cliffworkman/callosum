"""SP4b/c -- the share mailbox's storage logic (pure SQLAlchemy Core, dialect-portable). `create_share` is the
write; `list_shares_for_recipient`/`get_share` (SP4c) are the reads the recipient-facing "Shared with me"
surface needs, on the same `shares` table (already indexed on `recipient_sub` for exactly this).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, insert, select, update

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
    """The caller's own inbox -- id/sender/timestamp/revoked only, never `wrapped_key`/`ciphertext` (keeps the
    list response small; content is fetched per-item via `get_share`)."""
    rows = conn.execute(
        select(shares.c.id, shares.c.sender_sub, shares.c.created_at, shares.c.revoked_at)
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


def revoke_share(conn: Connection, share_id: int, sender_sub: str) -> None:
    """Mark a share revoked (idempotent -- the WHERE guard means a second call is a harmless no-op, never
    re-stamping the timestamp). The CALLER must already have verified `sender_sub` owns this share (via
    `get_share`) before calling -- this function does no authorization, mirroring `get_share`'s own documented
    division of responsibility."""
    conn.execute(
        update(shares)
        .where(shares.c.id == share_id, shares.c.sender_sub == sender_sub, shares.c.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


def list_shares_for_sender(conn: Connection, sender_sub: str, *, limit: int = 200) -> list[dict[str, Any]]:
    """The caller's own sent-list -- id/recipient/timestamp/revoked only, never `wrapped_key`/`ciphertext`
    (mirrors `list_shares_for_recipient`'s own restraint). There is deliberately no `imported` field here: that
    state lives only on the recipient's own device (SP4c's local `received_shares` table) and is never reported
    back to the sender or this server -- sharing has no read receipts."""
    rows = conn.execute(
        select(shares.c.id, shares.c.recipient_sub, shares.c.created_at, shares.c.revoked_at)
        .where(shares.c.sender_sub == sender_sub)
        .order_by(shares.c.created_at.desc())
        .limit(limit)
    ).mappings()
    return [dict(r) for r in rows]
