"""SP4b -- the share mailbox's storage logic (pure SQLAlchemy Core, dialect-portable). `create_share` is the
only write; there is deliberately no `list`/`get` function yet -- SP4c (a future stage, backlog #15) adds
those when the recipient-facing "Shared with me" surface actually needs them, on the same `shares` table
(already indexed on `recipient_sub` for exactly that future query).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Connection, insert

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
