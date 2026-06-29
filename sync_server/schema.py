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
