"""Preserve acquired registration document versions and canonical representations.

Revision ID: 0061_registration_versions
Revises: 0060_registration_links
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0061_registration_versions"
down_revision = "0060_registration_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "registration_document_versions" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "registration_document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "link_id", sa.Integer(), sa.ForeignKey("paper_registration_links.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("attachments.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("registered_at", sa.String(100)),
        sa.Column("registration_status", sa.String(100)),
        sa.Column("schema_name", sa.Text()),
        sa.Column("schema_version", sa.String(100)),
        sa.Column("structured_json", sa.JSON(), nullable=False),
        sa.Column("rendered_text", sa.Text()),
        sa.Column("source_metadata_json", sa.JSON(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("link_id", "content_hash", name="uq_registration_document_version_hash"),
    )
    op.create_index("ix_registration_versions_paper_id", "registration_document_versions", ["paper_id"])
    op.create_index("ix_registration_versions_link_id", "registration_document_versions", ["link_id"])


def downgrade() -> None:
    # Preserve acquired source snapshots and hashes; a destructive downgrade would erase comparison provenance.
    pass
