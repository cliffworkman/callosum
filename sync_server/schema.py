"""The sync-server's storage schema (SQLAlchemy Core, dialect-portable: Postgres in prod, SQLite in tests).

Four tables, all scoped per user (the OIDC ``sub``): ``sync_records`` holds the latest opaque blob per
``(user, collection, record_id)`` with its version + a per-user monotonic ``seq`` (the client cursor); ``sync_cursor``
holds each user's high-water ``seq`` so a push can assign the next one race-safely (a single counter row to lock,
rather than ``MAX(seq)+1`` across the table); ``share_identities`` (SP4a, backlog #15) is a public-key directory —
one row per user's *current* X25519 public key, reachable only by exact ``sub`` (never listed/searched — see
``identity_store.py``); ``shares`` (SP4b, backlog #15) holds one row per live share, addressed by
``recipient_sub`` (indexed for SP4c's future "list mine" query) — both ``wrapped_key`` and ``ciphertext`` are
opaque to the server; it can decrypt neither.
"""

from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()

# One row per syncable record, per user. ciphertext is an OPAQUE AES-GCM blob (base64) the server never reads;
# NULL iff this record is a tombstone (deleted).
sync_records = sa.Table(
    "sync_records",
    metadata,
    sa.Column("user_id", sa.String(length=255), nullable=False),
    sa.Column("collection", sa.String(length=60), nullable=False),
    sa.Column("record_id", sa.String(length=200), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("ciphertext", sa.Text()),  # NULL for a tombstone
    sa.Column("seq", sa.BigInteger(), nullable=False),
    # backlog #15 (retention): stamped on every push (insert or update) — used to age out old tombstones. Nullable
    # since an existing prod row (pre-migration) won't have one until its next push; see `ensure_updated_at_column`
    # for the one-time, idempotent ALTER TABLE that adds this column to an already-deployed table.
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.PrimaryKeyConstraint("user_id", "collection", "record_id", name="pk_sync_records"),
    sa.Index("ix_sync_records_user_seq", "user_id", "seq"),
)

# Per-user monotonic sequence high-water mark — the row a push locks to assign the next seq(s).
sync_cursor = sa.Table(
    "sync_cursor",
    metadata,
    sa.Column("user_id", sa.String(length=255), primary_key=True),
    sa.Column("seq", sa.BigInteger(), nullable=False, server_default="0"),
)

# SP4a (backlog #15): one row per user's current public key. `public_key` is base64 of a raw 32-byte X25519 key
# (public — safe in the clear). `display_name` is a UX-only label the caller supplies at registration time
# (e.g. from their own ORCID sign-in) — the server never verifies it; it is never a security claim.
share_identities = sa.Table(
    "share_identities",
    metadata,
    sa.Column("user_id", sa.String(length=255), primary_key=True),
    sa.Column("public_key", sa.String(length=200), nullable=False),
    sa.Column("display_name", sa.String(length=200)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

# SP4b (backlog #15): one row per live share. `wrapped_key` is the small JSON-encoded `WrappedKey` envelope
# (`app/backend/sync/sharing.py`); `ciphertext` is `encrypt_payload`'s opaque AES-GCM blob of a
# `build_bundle()` payload. Both are meaningless to the server -- it stores and relays bytes, nothing more.
# `sender_sub` comes from the authenticated bearer token at write time (never client-supplied), so a share's
# origin is trustworthy even though the envelope itself carries no sender authentication (see sharing.py).
shares = sa.Table(
    "shares",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("sender_sub", sa.String(length=255), nullable=False),
    sa.Column("recipient_sub", sa.String(length=255), nullable=False),
    sa.Column("wrapped_key", sa.Text(), nullable=False),
    sa.Column("ciphertext", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    # SP4d (backlog #15): NULL = still live; set once, never cleared -- a sender withdrawing a share before its
    # recipient imports it. The server has no concept of "imported" (that lives only in the recipient's own
    # local `received_shares` table, SP4c) -- revoking only ever means "stop this from being imported if it
    # hasn't been already," never "undo a delivery."
    sa.Column("revoked_at", sa.DateTime(timezone=True)),
    sa.Index("ix_shares_recipient_sub", "recipient_sub"),
)


def ensure_updated_at_column(engine: sa.Engine) -> None:
    """One-time, idempotent defensive ALTER for the `updated_at` column added in backlog #15.

    This is deliberately NOT a general migration tool (that remains its own separate, un-scoped follow-on —
    see `sync_server/README.md`'s "Not yet" section) — it exists only because `metadata.create_all()` (the
    lifespan's existing v1 "create-on-start" approach) never alters an already-existing table, so an
    already-deployed `sync_records` table would silently lack this column forever without one targeted,
    dialect-portable ALTER. Safe to call every startup: checks via `Inspector` first, so a fresh (or
    already-migrated) table is a no-op.
    """
    inspector = sa.inspect(engine)
    if "sync_records" not in inspector.get_table_names():
        return  # create_all will create it WITH the column — nothing to add
    columns = {c["name"] for c in inspector.get_columns("sync_records")}
    if "updated_at" in columns:
        return
    with engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE sync_records ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE"))


def ensure_revoked_at_column(engine: sa.Engine) -> None:
    """One-time, idempotent defensive ALTER for the `revoked_at` column added in backlog #15's SP4d. Same
    shape as `ensure_updated_at_column` above, for the same reason: `metadata.create_all()` never alters an
    already-existing table. Safe to call every startup."""
    inspector = sa.inspect(engine)
    if "shares" not in inspector.get_table_names():
        return  # create_all will create it WITH the column -- nothing to add
    columns = {c["name"] for c in inspector.get_columns("shares")}
    if "revoked_at" in columns:
        return
    with engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE shares ADD COLUMN revoked_at TIMESTAMP WITH TIME ZONE"))
