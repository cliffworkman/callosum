"""Add a lightweight per-manuscript Journals (venue-fit) search receipt.

Revision ID: 0058_wip_journal_runs
Revises: 0057_paper_grim_checks
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0058_wip_journal_runs"
down_revision = "0057_paper_grim_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "wip_journal_runs" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "wip_journal_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "manuscript_id", sa.Integer(), sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("topic_id", sa.String(length=200)),
            sa.Column("weighting", sa.Float(), nullable=False),
            sa.Column("considered", sa.Integer(), nullable=False),
            sa.Column("shown", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )
        op.create_index("ix_wip_journal_runs_manuscript_id", "wip_journal_runs", ["manuscript_id"])


def downgrade() -> None:
    # Additive table, like 0052/0054/0055/0056/0057 -- 0001 owns eventual metadata teardown.
    pass
