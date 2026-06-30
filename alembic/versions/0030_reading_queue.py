"""Reading queue (inc 219): a ``reading_queue`` table — a personal, ordered to-read list of papers, surfaced as a
left-pane "Queue" tab with drag-to-reorder. One row per paper (UNIQUE); ``position`` drives the manual order; CASCADE
drops a row when its paper is purged. NOT an axis (no semantic scoring) — its own small table.

Additive + idempotent (like 0021-0029): a fresh DB already has the table from 0001's ``metadata.create_all`` (it's on
the shared metadata), so the create is guarded + skipped there; an existing DB gets it here. No-op downgrade.

Revision ID: 0030_reading_queue
Revises: 0029_agent_writes
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0030_reading_queue"
down_revision = "0029_agent_writes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "reading_queue" not in tables:
        op.create_table(
            "reading_queue",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("position", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.UniqueConstraint("paper_id", name="uq_reading_queue_paper"),
        )


def downgrade() -> None:
    # No-op by design (mirrors 0021-0029): the table lives in 0001's `metadata`, whose downgrade loops over
    # `metadata.sorted_tables` and drops it. A real drop_table here would double-drop (0001 drops it again → error).
    return
