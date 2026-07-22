"""The sync-server's storage schema (SQLAlchemy Core, dialect-portable: Postgres in prod, SQLite in tests).

Two tables, both scoped per user (the OIDC ``sub``): ``sync_records`` holds the latest opaque blob per
``(user, collection, record_id)`` with its version + a per-user monotonic ``seq`` (the client cursor); ``sync_cursor``
holds each user's high-water ``seq`` so a push can assign the next one race-safely (a single counter row to lock,
rather than ``MAX(seq)+1`` across the table).
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
