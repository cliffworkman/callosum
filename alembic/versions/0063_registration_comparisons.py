"""Persist evidence-bound registration comparison runs and review rows.

Revision ID: 0063_registration_comparisons
Revises: 0062_registration_commitments
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0063_registration_comparisons"
down_revision = "0062_registration_commitments"
branch_labels = None
depends_on = None

_STATUSES = (
    "aligned",
    "potentially-changed",
    "planned-item-not-located-in-publication",
    "reported-item-not-located-in-registration",
    "disclosed-deviation",
    "underspecified-in-registration",
    "underspecified-in-publication",
    "ambiguous-study-mapping",
    "not-comparable",
    "extraction-uncertain",
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "registration_comparison_runs" not in inspector.get_table_names():
        op.create_table(
            "registration_comparison_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "link_id",
                sa.Integer(),
                sa.ForeignKey("paper_registration_links.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "registration_version_id",
                sa.Integer(),
                sa.ForeignKey("registration_document_versions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
            sa.Column("registration_content_hash", sa.String(128), nullable=False),
            sa.Column("article_fingerprint", sa.String(128), nullable=False),
            sa.Column("supplement_fingerprint", sa.String(128)),
            sa.Column("article_source_json", sa.JSON(), nullable=False),
            sa.Column("supplement_source_json", sa.JSON(), nullable=False),
            sa.Column("commitment_extraction_version", sa.String(100), nullable=False),
            sa.Column("retrieval_version", sa.String(100), nullable=False),
            sa.Column("comparison_version", sa.String(100), nullable=False),
            sa.Column("configuration_json", sa.JSON(), nullable=False),
            sa.Column("model_versions_json", sa.JSON(), nullable=False),
            sa.Column("stale_reasons_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.CheckConstraint("status IN ('completed','stale')", name="registration_comparison_run_status_valid"),
        )
        op.create_index(
            "ix_registration_comparison_runs_paper", "registration_comparison_runs", ["paper_id", "created_at"]
        )
    if "registration_comparison_rows" not in inspector.get_table_names():
        statuses = ",".join(f"'{status}'" for status in _STATUSES)
        op.create_table(
            "registration_comparison_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("registration_comparison_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("commitment_id", sa.Integer(), sa.ForeignKey("registration_commitments.id", ondelete="SET NULL")),
            sa.Column("field_type", sa.String(100), nullable=False),
            sa.Column("registration_value_json", sa.JSON()),
            sa.Column("registration_evidence_text", sa.Text()),
            sa.Column("registration_source_locator_json", sa.JSON()),
            sa.Column("publication_value_json", sa.JSON()),
            sa.Column("publication_evidence_text", sa.Text()),
            sa.Column("publication_source_locator_json", sa.JSON()),
            sa.Column("comparison_status", sa.String(80), nullable=False),
            sa.Column("timing_status", sa.String(100)),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("uncertainty", sa.Text(), nullable=False),
            sa.Column("search_scope_json", sa.JSON(), nullable=False),
            sa.Column("registration_version_id", sa.Integer(), nullable=False),
            sa.Column("registration_content_hash", sa.String(128), nullable=False),
            sa.Column("publication_attachment_id", sa.Integer(), sa.ForeignKey("attachments.id", ondelete="SET NULL")),
            sa.Column("publication_attachment_checksum", sa.String(128)),
            sa.Column("review_state", sa.String(30), nullable=False, server_default="unreviewed"),
            sa.Column("note", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.CheckConstraint(
                f"comparison_status IN ({statuses})",
                name="registration_comparison_status_valid",
            ),
            sa.CheckConstraint(
                "review_state IN ('unreviewed','reviewed','dismissed')",
                name="registration_comparison_review_state_valid",
            ),
        )
        op.create_index("ix_registration_comparison_rows_run", "registration_comparison_rows", ["run_id", "id"])
        op.create_index(
            "ix_registration_comparison_rows_review",
            "registration_comparison_rows",
            ["review_state", "comparison_status"],
        )


def downgrade() -> None:
    # Preserve human review state, notes, evidence, and the exact document/version basis.
    pass
