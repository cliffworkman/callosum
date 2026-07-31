"""Add evidence-bearing registration references extracted from papers.

Revision ID: 0059_registration_references
Revises: 0058_wip_journal_runs
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0059_registration_references"
down_revision = "0058_wip_journal_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "paper_registration_references" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "paper_registration_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id", ondelete="CASCADE")),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("visible_text", sa.Text()),
        sa.Column("evidence_snippet", sa.Text()),
        sa.Column("page", sa.Integer()),
        sa.Column("extraction_method", sa.String(length=100), nullable=False),
        sa.Column("evidence_class", sa.String(length=100), nullable=False),
        sa.Column("explicitly_printed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("page IS NULL OR page >= 1", name="registration_reference_page_positive"),
        sa.UniqueConstraint(
            "paper_id",
            "attachment_id",
            "provider",
            "external_id",
            "extraction_method",
            name="uq_registration_reference_source",
        ),
    )
    op.create_index("ix_registration_references_paper_id", "paper_registration_references", ["paper_id"])
    op.create_index("ix_registration_references_attachment_id", "paper_registration_references", ["attachment_id"])


def downgrade() -> None:
    # Additive evidence table; preserve locally extracted/manual references on downgrade.
    pass
