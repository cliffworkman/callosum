"""critical_review_candidates — Tier-2 critique candidate store (backlog #12).

Revision ID: 0035_critical_review_candidates
Revises: 0034_extraction_proposals
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0035_critical_review_candidates"
down_revision = "0034_extraction_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "critical_review_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concern", sa.Text(), nullable=False),
        sa.Column("anchor_quote", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("stance", sa.String(length=20)),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("signature", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_critical_review_candidates_cr_status_valid",
        ),
    )
    op.create_index("ix_cr_candidates_paper_id", "critical_review_candidates", ["paper_id"])
