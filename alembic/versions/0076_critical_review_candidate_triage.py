"""Persist optional LLM display annotations for critical-review Tier-2 candidates.

Mirrors 0064's registration-comparison triage table exactly, keyed by candidate_id instead of a
run_id/row_id pair (a critical-review candidate has no "run" grouping concept — accept/reject
already act per-candidate-id, paper-agnostic).

Revision ID: 0076_critical_review_candidate_triage
Revises: 0075_summary_overview_lifecycle
Create Date: 2026-08-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0076_critical_review_candidate_triage"
down_revision = "0075_summary_overview_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "critical_review_candidate_triage" in inspector.get_table_names():
        return
    if "critical_review_candidates" not in inspector.get_table_names():
        return
    op.create_table(
        "critical_review_candidate_triage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("critical_review_candidates.id", ondelete="CASCADE"),
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
            name="cr_candidate_triage_label_valid",
        ),
        sa.UniqueConstraint("candidate_id", name="uq_cr_candidate_triage_candidate"),
    )
    op.create_index(
        "ix_cr_candidate_triage_candidate",
        "critical_review_candidate_triage",
        ["candidate_id"],
    )


def downgrade() -> None:
    # Preserve model annotations unless the user exports/removes them deliberately (0064 precedent).
    pass
