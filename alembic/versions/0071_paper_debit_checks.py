"""Add per-paper saved DEBIT checks.

Revision ID: 0071_paper_debit_checks
Revises: 0070_saved_beyond_library_suggestions
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0071_paper_debit_checks"
down_revision = "0070_saved_beyond_library_suggestions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "paper_debit_checks" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "paper_debit_checks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("label", sa.String(length=120)),
            sa.Column("mean", sa.String(length=40), nullable=False),
            sa.Column("sd", sa.String(length=40), nullable=False),
            sa.Column("n", sa.Integer(), nullable=False),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )
        op.create_index("ix_paper_debit_checks_paper_id", "paper_debit_checks", ["paper_id"])


def downgrade() -> None:
    # Additive table, like 0052/0054-0057/0070 — 0001 owns eventual metadata teardown.
    pass
