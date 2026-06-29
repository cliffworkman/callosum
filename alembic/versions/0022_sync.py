"""Sync bookkeeping (accounts SP3a): ``sync_state`` (per-record change-tracking) + ``sync_conflicts`` (the
surfaced losing side of a last-write-wins merge). Local-only; see ``2026-06-29-accounts-sync-design.md``.

Additive + idempotent (like 0002-0021): a fresh DB already has the tables from 0001's ``metadata.create_all``, so
each create is guarded + skipped there; an existing DB gets them here.

Revision ID: 0022_sync
Revises: 0021_feed
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0022_sync"
down_revision = "0021_feed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "sync_state" not in tables:
        op.create_table(
            "sync_state",
            sa.Column("collection", sa.String(length=60), nullable=False),
            sa.Column("record_id", sa.String(length=120), nullable=False),
            sa.Column("content_hash", sa.String(length=64)),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("deleted", sa.Integer(), server_default="0", nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("last_synced_seq", sa.Integer()),
            sa.PrimaryKeyConstraint("collection", "record_id", name="pk_sync_state"),
        )
    if "sync_conflicts" not in tables:
        op.create_table(
            "sync_conflicts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("collection", sa.String(length=60), nullable=False),
            sa.Column("record_id", sa.String(length=120), nullable=False),
            sa.Column("losing_version", sa.Integer()),
            sa.Column("losing_payload", sa.JSON()),
            sa.Column("detected_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("resolved", sa.Integer(), server_default="0", nullable=False),
            sa.Index("ix_sync_conflicts_unresolved", "resolved"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
