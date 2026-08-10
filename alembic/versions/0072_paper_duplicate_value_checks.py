"""Add per-paper saved repeated-values checks.

Revision ID: 0072_paper_duplicate_value_checks
Revises: 0071_paper_debit_checks
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0072_paper_duplicate_value_checks"
down_revision = "0071_paper_debit_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "paper_duplicate_value_checks" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "paper_duplicate_value_checks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("label", sa.String(length=120)),
            sa.Column("values_json", sa.JSON(), nullable=False),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )
        op.create_index("ix_paper_duplicate_value_checks_paper_id", "paper_duplicate_value_checks", ["paper_id"])


def downgrade() -> None:
    # Additive table, like 0052/0054-0057/0070/0071 — 0001 owns eventual metadata teardown.
    pass
