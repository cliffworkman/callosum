"""Add per-paper saved GRIM/GRIMMER checks.

Revision ID: 0057_paper_grim_checks
Revises: 0056_paper_statcheck_cache
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0057_paper_grim_checks"
down_revision = "0056_paper_statcheck_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "paper_grim_checks" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "paper_grim_checks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("label", sa.String(length=120)),
            sa.Column("mean", sa.String(length=40), nullable=False),
            sa.Column("sd", sa.String(length=40)),
            sa.Column("n", sa.Integer(), nullable=False),
            sa.Column("items", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )
        op.create_index("ix_paper_grim_checks_paper_id", "paper_grim_checks", ["paper_id"])


def downgrade() -> None:
    # Additive table, like 0052/0054/0055/0056 — 0001 owns eventual metadata teardown.
    pass
