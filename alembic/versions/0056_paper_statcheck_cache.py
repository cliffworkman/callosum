"""Add per-paper statcheck result cache.

Revision ID: 0056_paper_statcheck_cache
Revises: 0055_my_publication_citing_authors
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0056_paper_statcheck_cache"
down_revision = "0055_my_publication_citing_authors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "paper_statcheck_cache" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "paper_statcheck_cache",
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("checked", sa.Integer(), nullable=False),
            sa.Column("inconsistent", sa.Integer(), nullable=False),
            sa.Column("decision_errors", sa.Integer(), nullable=False),
            sa.Column("results_json", sa.JSON(), nullable=False),
            sa.Column("coverage_json", sa.JSON(), nullable=False),
            sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("computed_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )


def downgrade() -> None:
    # Like 0052/0054/0055, keep the additive cache table on downgrade — 0001 owns eventual metadata teardown.
    pass
