"""Add scoped My Publications emerging citing-topic snapshots.

Revision ID: 0054_emerging_citing_topics
Revises: 0053_domain_scoped_citation_gaps
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0054_emerging_citing_topics"
down_revision = "0053_domain_scoped_citation_gaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "my_publication_emerging_topic_cache" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "my_publication_emerging_topic_cache",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scope_key", sa.String(length=80), nullable=False),
            sa.Column("scope", sa.JSON(), nullable=False),
            sa.Column("topics", sa.JSON(), nullable=False),
            sa.Column("coverage", sa.JSON(), nullable=False),
            sa.Column("computed_at", sa.String(length=40), nullable=False),
            sa.UniqueConstraint("scope_key", name="uq_my_publication_emerging_topic_scope_key"),
        )


def downgrade() -> None:
    # Like 0052, keep the additive cache table on downgrade. Migration 0001 creates current metadata on fresh
    # databases, so dropping it here would make 0001's eventual metadata teardown try to drop it a second time.
    pass
