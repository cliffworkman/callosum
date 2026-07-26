"""Add scoped My Publications citing-author snapshots.

Revision ID: 0055_my_publication_citing_authors
Revises: 0054_emerging_citing_topics
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0055_my_publication_citing_authors"
down_revision = "0054_emerging_citing_topics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "my_publication_citing_author_cache" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "my_publication_citing_author_cache",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scope_key", sa.String(length=80), nullable=False),
            sa.Column("scope", sa.JSON(), nullable=False),
            sa.Column("authors", sa.JSON(), nullable=False),
            sa.Column("coverage", sa.JSON(), nullable=False),
            sa.Column("computed_at", sa.String(length=40), nullable=False),
            sa.UniqueConstraint("scope_key", name="uq_my_publication_citing_author_scope_key"),
        )


def downgrade() -> None:
    # Like 0052/0054, keep the additive cache table on downgrade because 0001 creates current metadata on fresh
    # databases and its eventual metadata teardown owns the final drop.
    pass
