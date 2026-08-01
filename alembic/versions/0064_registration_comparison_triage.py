"""Persist optional LLM display annotations for registration comparison rows.

Revision ID: 0064_registration_comparison_triage
Revises: 0063_registration_comparisons
Create Date: 2026-08-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0064_registration_comparison_triage"
down_revision = "0063_registration_comparisons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "registration_comparison_triage_annotations" in inspector.get_table_names():
        return
    op.create_table(
        "registration_comparison_triage_annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("registration_comparison_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "row_id",
            sa.Integer(),
            sa.ForeignKey("registration_comparison_rows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("show_in_triage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rationale", sa.Text()),
        sa.Column("concerns_json", sa.JSON(), nullable=False),
        sa.Column("basis", sa.Text()),
        sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("model_id", sa.String(200)),
        sa.Column("prompt_version", sa.String(120), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint(
            "label IN ('prioritize','uncertain','likely_noise')",
            name="registration_comparison_triage_label_valid",
        ),
        sa.UniqueConstraint("row_id", name="uq_registration_comparison_triage_row"),
    )
    op.create_index(
        "ix_registration_comparison_triage_run",
        "registration_comparison_triage_annotations",
        ["run_id", "row_id"],
    )


def downgrade() -> None:
    # Preserve model annotations and their evidence receipts unless the user exports/removes them deliberately.
    pass
