"""Grounded My Publications citation-gap snapshot.

Revision ID: 0052_my_publication_citation_gaps
Revises: 0051_wip_tool_runs
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0052_my_publication_citation_gaps"
down_revision = "0051_wip_tool_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "my_publication_citation_gap_cache" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "my_publication_citation_gap_cache",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("candidates", sa.JSON(), nullable=False),
            sa.Column("coverage", sa.JSON(), nullable=False),
            sa.Column("computed_at", sa.String(40), nullable=False),
        )


def downgrade() -> None:
    pass
