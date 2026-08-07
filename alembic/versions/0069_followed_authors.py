"""Followed-authors gap-finder source (backlog #29, inc 454): the followed_authors subscription table + its
followed_author_candidates cache -- a lightweight OpenAlex-author subscription (reuses the existing
OpenAlexAuthorClient resolution) whose absent-from-library works surface as gap-finder candidates, provenance
"by <author> (followed)". Sibling to gap_candidates, not a new column on it.

Additive + idempotent (like 0002-0068): guarded create, skipped on a fresh DB (0001 already has it via
metadata.create_all).

Revision ID: 0069_followed_authors
Revises: 0068_ajol_records
Create Date: 2026-08-07
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0069_followed_authors"
down_revision = "0068_ajol_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "followed_authors" not in tables:
        op.create_table(
            "followed_authors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("author_id", sa.String(length=20), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("orcid", sa.String(length=64)),
            sa.Column("matched_by", sa.String(length=10), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("last_refreshed_at", sa.String(length=40)),
            sa.UniqueConstraint("author_id", name="uq_followed_authors_author_id"),
        )
    if "followed_author_candidates" not in tables:
        op.create_table(
            "followed_author_candidates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("author_id", sa.String(length=20), nullable=False),
            sa.Column("author_display_name", sa.Text()),
            sa.Column("openalex_work_id", sa.String(length=40)),
            sa.Column("doi", sa.String(length=255)),
            sa.Column("title", sa.Text()),
            sa.Column("year", sa.Integer()),
            sa.Column("cited_by_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("computed_at", sa.String(length=40), nullable=False),
        )
        op.create_index("ix_followed_author_candidates_author", "followed_author_candidates", ["author_id"])


def downgrade() -> None:
    # Additive tables, like every other findings-cluster migration -- 0001 owns eventual teardown.
    pass
