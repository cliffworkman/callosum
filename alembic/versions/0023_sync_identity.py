"""Sync identity map (accounts SP3b): ``sync_identity`` (collection, local_id ↔ sync_uid) — a stable global UUID per
syncable row so multi-device sync keys on a device-independent id, not the local auto-increment ``id``. Local-only;
see ``2026-06-29-accounts-sync-design.md``.

Additive + idempotent (like 0002-0022): a fresh DB already has the table from 0001's ``metadata.create_all``, so the
create is guarded + skipped there; an existing DB gets it here. No backfill — the engine assigns a ``sync_uid`` lazily
to any row lacking one on the first ``collect_local``.

Revision ID: 0023_sync_identity
Revises: 0022_sync
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0023_sync_identity"
down_revision = "0022_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sync_identity" not in set(inspector.get_table_names()):
        op.create_table(
            "sync_identity",
            sa.Column("collection", sa.String(length=60), nullable=False),
            sa.Column("local_id", sa.String(length=120), nullable=False),
            sa.Column("sync_uid", sa.String(length=64), nullable=False),
            sa.PrimaryKeyConstraint("collection", "local_id", name="pk_sync_identity"),
            sa.UniqueConstraint("collection", "sync_uid", name="uq_sync_identity_collection_uid"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
