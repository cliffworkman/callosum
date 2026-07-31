"""Add registration discovery candidates and confirmed/rejected link state.

Revision ID: 0060_registration_links
Revises: 0059_registration_references
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0060_registration_links"
down_revision = "0059_registration_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "paper_registration_links" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "paper_registration_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("registration_doi", sa.String(500)),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("contributors_json", sa.JSON()),
        sa.Column("registered_at", sa.String(100)),
        sa.Column("registration_status", sa.String(100)),
        sa.Column("schema_name", sa.Text()),
        sa.Column("link_status", sa.String(30), nullable=False, server_default="candidate"),
        sa.Column("linkage_class", sa.String(50), nullable=False),
        sa.Column("match_method", sa.String(100), nullable=False),
        sa.Column("match_evidence_json", sa.JSON(), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("source_metadata_json", sa.JSON()),
        sa.Column("content_hash", sa.String(128)),
        sa.Column("retrieved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("paper_id", "provider", "external_id", name="uq_paper_registration_link_candidate"),
        sa.CheckConstraint(
            "link_status IN ('candidate','confirmed','rejected','unavailable','withdrawn')",
            name="registration_link_status_valid",
        ),
        sa.CheckConstraint(
            "linkage_class IN ('explicit-linkage','strong-contextual-match','similarity-candidate')",
            name="registration_linkage_class_valid",
        ),
    )
    op.create_index("ix_registration_links_paper_status", "paper_registration_links", ["paper_id", "link_status"])
    op.create_index("ix_registration_links_external", "paper_registration_links", ["provider", "external_id"])


def downgrade() -> None:
    # Preserve user confirmations/rejections and candidate provenance on downgrade.
    pass
