"""Index-build disk guard: ``waiting_disk`` state and the last disk check on ``embedding_index_runs`` (inc 616).

A fresh database already has both from 0001's ``metadata.create_all``, so this is skipped there. An existing
database (0086's table) is rebuilt once: SQLite cannot alter a CHECK constraint in place. The table holds only
build lifecycle rows -- no vectors, no user data, no foreign keys point at it -- and every row is copied
unchanged. Idempotent: it does nothing when the constraint already allows ``waiting_disk``.

Revision ID: 0087_index_run_waiting_disk
Revises: 0086_embedding_index_runs
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0087_index_run_waiting_disk"
down_revision = "0086_embedding_index_runs"
branch_labels = None
depends_on = None

_STATES = (
    "'queued','running','pausing','paused','waiting_resources','waiting_disk','interrupted','retrying',"
    "'failed','completed','cancelled'"
)
_COPIED = (
    "profile_key, model_version, state, intent, eligible_chunks, indexed_chunks, batch_size, attempts, "
    "failures_without_progress, worker_pid, worker_token, worker_started_at, heartbeat_at, last_checkpoint_at, "
    "next_retry_at, failure_kind, failure_detail, diagnostic, peak_worker_rss_mb, min_available_mb, created_at, "
    "updated_at"
)


def upgrade() -> None:
    bind = op.get_bind()
    if "embedding_index_runs" not in sa.inspect(bind).get_table_names():
        return
    ddl = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'embedding_index_runs'")
    ).scalar_one()
    if "waiting_disk" in ddl:
        return
    op.execute("DROP TABLE IF EXISTS _embedding_index_runs_0087")
    op.create_table(
        "_embedding_index_runs_0087",
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
        sa.Column("disk_required_bytes", sa.Integer()),
        sa.Column("disk_free_bytes", sa.Integer()),
        sa.Column("disk_estimated_bytes", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint(f"state IN ({_STATES})", name="ck_embedding_index_runs_state"),
        sa.CheckConstraint("intent IN ('run', 'pause', 'cancel')", name="ck_embedding_index_runs_intent"),
    )
    op.execute(
        f"INSERT INTO _embedding_index_runs_0087 ({_COPIED}) SELECT {_COPIED} FROM embedding_index_runs"  # noqa: S608  # nosec B608 -- fixed column list
    )
    op.drop_table("embedding_index_runs")
    op.rename_table("_embedding_index_runs_0087", "embedding_index_runs")


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
