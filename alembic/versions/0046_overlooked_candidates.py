"""Overlooked-work lens persistent cache (backlog #37): the ``overlooked_candidates`` table — one row per surfaced
candidate, scoped by ``axis_id``. A refresh replaces all rows for an axis; ``GET /overlooked`` reads here.

Additive + idempotent (like 0002-0045): a fresh DB already has the table from 0001's ``metadata.create_all``, so the
create is guarded and skipped there; an existing DB gets it here. No down-migration. Identity-agnostic by
construction — there is NO author column; ``relevance`` + ``year_percentile`` are two separate inputs, never fused.

Revision ID: 0046_overlooked_candidates
Revises: 0045_cr_candidate_related_papers
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0046_overlooked_candidates"
down_revision = "0045_cr_candidate_related_papers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "overlooked_candidates" not in inspector.get_table_names():
        op.create_table(
            "overlooked_candidates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("axis_id", sa.Integer(), nullable=False),
            sa.Column("openalex_work_id", sa.String(length=40), nullable=False),
            sa.Column("doi", sa.String(length=255)),
            sa.Column("title", sa.Text()),
            sa.Column("year", sa.Integer()),
            sa.Column("cited_by_count", sa.Integer(), nullable=False),
            sa.Column("relevance", sa.Float(), nullable=False),
            sa.Column("year_percentile", sa.Float()),
            sa.Column("computed_at", sa.String(length=40), nullable=False),
            sa.Index("ix_overlooked_candidates_axis", "axis_id"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
