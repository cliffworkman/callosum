"""Durable embedding-profile index build lifecycle: ``embedding_index_runs`` (inc 610).

Additive and idempotent (like 0002-0085): a *fresh* database already has the table from 0001's
``metadata.create_all``, so the create is guarded and skipped there; an existing database gets it here. No existing
row is read or written, and no vector is touched.

Revision ID: 0086_embedding_index_runs
Revises: 0085_library_settings
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0086_embedding_index_runs"
down_revision = "0085_library_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "embedding_index_runs" in sa.inspect(op.get_bind()).get_table_names():
        return
    states = "'queued','running','pausing','paused','waiting_resources','interrupted','retrying','failed','completed','cancelled'"
    op.create_table(
        "embedding_index_runs",
        sa.Column("profile_key", sa.String(40), primary_key=True),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("intent", sa.String(12), nullable=False),
        sa.Column("eligible_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures_without_progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worker_pid", sa.Integer()),
        sa.Column("worker_token", sa.String(40)),
        sa.Column("worker_started_at", sa.DateTime()),
        sa.Column("heartbeat_at", sa.DateTime()),
        sa.Column("last_checkpoint_at", sa.DateTime()),
        sa.Column("next_retry_at", sa.DateTime()),
        sa.Column("failure_kind", sa.String(40)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("diagnostic", sa.Text()),
        sa.Column("peak_worker_rss_mb", sa.Integer()),
        sa.Column("min_available_mb", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint(f"state IN ({states})", name="ck_embedding_index_runs_state"),
        sa.CheckConstraint("intent IN ('run', 'pause', 'cancel')", name="ck_embedding_index_runs_intent"),
    )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
