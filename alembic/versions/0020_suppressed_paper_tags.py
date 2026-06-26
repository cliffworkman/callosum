"""Suppressed imported-keyword tags (inc 143): the ``suppressed_paper_tags`` table — when the librarian deletes an
imported ``keyword:*`` tag, remember it per paper so a later re-resolve / backfill doesn't silently re-add it.

Additive + idempotent (like 0002-0019): a fresh DB already has the table from 0001's ``metadata.create_all``, so
the create is guarded and skipped there; an existing DB gets it here.

Revision ID: 0020_suppressed_paper_tags
Revises: 0019_gap_candidates
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_suppressed_paper_tags"
down_revision = "0019_gap_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "suppressed_paper_tags" not in inspector.get_table_names():
        op.create_table(
            "suppressed_paper_tags",
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("tag_name", sa.Text(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
