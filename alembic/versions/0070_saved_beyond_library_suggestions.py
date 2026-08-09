"""Persistent, dismissible beyond-library suggestion queue (backlog #30's last open piece, inc 465): the
saved_beyond_library_suggestions table. One row per explicitly-saved suggestion, keyed by its own stable
cross-provider dedup_key. status is a soft state (pending | dismissed | added), never a hard delete.

Additive + idempotent (like 0002-0069): guarded create, skipped on a fresh DB (0001 already has it via
metadata.create_all).

Revision ID: 0070_saved_beyond_library_suggestions
Revises: 0069_followed_authors
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0070_saved_beyond_library_suggestions"
down_revision = "0069_followed_authors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "saved_beyond_library_suggestions" not in tables:
        op.create_table(
            "saved_beyond_library_suggestions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("dedup_key", sa.String(length=512), nullable=False, unique=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("sources", sa.JSON()),
            sa.Column("doi", sa.String(length=255)),
            sa.Column("pmid", sa.String(length=32)),
            sa.Column("abstract", sa.Text()),
            sa.Column("authors", sa.JSON()),
            sa.Column("journal", sa.Text()),
            sa.Column("year", sa.Integer()),
            sa.Column("url", sa.Text()),
            sa.Column("reason", sa.Text()),
            sa.Column("evidence_text", sa.Text()),
            sa.Column("evidence_kind", sa.String(length=20)),
            sa.Column("relationship_kind", sa.String(length=40)),
            sa.Column("relationship_label", sa.Text()),
            sa.Column("anchor_paper_id", sa.Integer()),
            sa.Column("anchor_title", sa.Text()),
            sa.Column("source_query", sa.Text()),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("saved_at", sa.String(length=40), nullable=False),
        )


def downgrade() -> None:
    # Additive table, like every other findings-cluster migration -- 0001 owns eventual teardown.
    pass
