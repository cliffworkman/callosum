"""Store evidence-bearing canonical registration commitments.

Revision ID: 0062_registration_commitments
Revises: 0061_registration_versions
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0062_registration_commitments"
down_revision = "0061_registration_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "registration_commitments" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "registration_commitments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("registration_document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "link_id", sa.Integer(), sa.ForeignKey("paper_registration_links.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id", ondelete="SET NULL")),
        sa.Column("field_type", sa.String(100), nullable=False),
        sa.Column("study_label", sa.Text()),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("structured_value_json", sa.JSON(), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("source_section", sa.Text()),
        sa.Column("source_key", sa.String(500), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("chunks.id", ondelete="SET NULL")),
        sa.Column("source_locator_json", sa.JSON(), nullable=False),
        sa.Column("extraction_method", sa.String(100), nullable=False),
        sa.Column("extraction_confidence", sa.String(30), nullable=False),
        sa.Column("registration_content_hash", sa.String(128), nullable=False),
        sa.Column("extraction_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint(
            "version_id",
            "field_type",
            "source_key",
            "extraction_version",
            name="uq_registration_commitment_source",
        ),
        sa.CheckConstraint("ordinal >= 0", name="registration_commitment_ordinal_nonnegative"),
        sa.CheckConstraint("page IS NULL OR page >= 1", name="registration_commitment_page_positive"),
        sa.CheckConstraint(
            "extraction_confidence IN ('high','medium','low')",
            name="registration_commitment_confidence_valid",
        ),
    )
    op.create_index("ix_registration_commitments_version", "registration_commitments", ["version_id", "ordinal"])
    op.create_index("ix_registration_commitments_paper", "registration_commitments", ["paper_id", "field_type"])


def downgrade() -> None:
    # Preserve extracted evidence and the exact source version it names.
    pass
