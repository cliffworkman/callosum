"""Add the ``wanted_items`` table — the OA acquisition wanted list (inc 76).

A row is a paper the user wants an open-access copy of: library-linked (``paper_id`` set) or external
(``paper_id`` NULL, carrying doi/pmid/title). Idempotent like 0002–0007: a *fresh* database already has this
table from 0001's ``metadata.create_all``, so this is a no-op there.

Revision ID: 0008_wanted_items
Revises: 0007_attachment_oa_labels
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_wanted_items"
down_revision = "0007_attachment_oa_labels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "wanted_items" in sa.inspect(bind).get_table_names():
        return  # fresh database: 0001's create_all already built the final schema. No-op.
    op.create_table(
        "wanted_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("pmid", sa.String(100), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="wanted"),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_result", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index("ix_wanted_items_paper_id", "wanted_items", ["paper_id"])
    op.create_index("ix_wanted_items_status", "wanted_items", ["status"])


def downgrade() -> None:
    # No-op by design (the table lives in the schema metadata; teardown is owned by 0001's metadata-wide
    # downgrade). Downgrades aren't a supported workflow.
    return
