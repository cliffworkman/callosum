"""SP4a — the public-key directory's storage logic (pure SQLAlchemy Core, dialect-portable). Every row is
scoped by ``user_id`` (the OIDC ``sub``); a lookup is always by exact id — there is no listing/search function
here, structurally, not just by convention (backlog #15's own divergence fence: this stays an identity lookup,
never a user directory).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Connection, insert, select, update

from sync_server.schema import share_identities


@dataclass(frozen=True)
class IdentityRecord:
    public_key: str  # base64 of a raw 32-byte X25519 public key
    display_name: str | None  # UX-only, caller-supplied, never verified


def register_public_key(conn: Connection, user_id: str, public_key: str, display_name: str | None) -> None:
    """Upsert the caller's own current public key. Registering a new key silently supersedes any prior one for
    this user (there is exactly one *current* identity per user in SP4a — key history/rotation is out of scope
    here)."""
    values = dict(public_key=public_key, display_name=display_name, updated_at=datetime.now(timezone.utc))
    updated = conn.execute(
        update(share_identities).where(share_identities.c.user_id == user_id).values(**values)
    ).rowcount
    if not updated:
        conn.execute(insert(share_identities).values(user_id=user_id, **values))


def lookup_public_key(conn: Connection, user_id: str) -> IdentityRecord | None:
    """The public key registered for exactly this ``user_id``, or None. Never matches a partial/fuzzy id."""
    row = conn.execute(
        select(share_identities.c.public_key, share_identities.c.display_name).where(
            share_identities.c.user_id == user_id
        )
    ).first()
    return IdentityRecord(public_key=row[0], display_name=row[1]) if row is not None else None
