"""Gap-finder persistent cache (inc 137): the ``gap_candidates`` table — one row per cached candidate, scoped by
``(direction, axis_id)``. A refresh replaces all rows for a scope; ``GET /gaps`` reads here.

Additive + idempotent (like 0002-0018): a fresh DB already has the table from 0001's ``metadata.create_all``, so
the create is guarded and skipped there; an existing DB gets it here.

Revision ID: 0019_gap_candidates
Revises: 0018_profile_dismissed_gaps
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0019_gap_candidates"
down_revision = "0018_profile_dismissed_gaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "gap_candidates" not in inspector.get_table_names():
        op.create_table(
            "gap_candidates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("direction", sa.String(length=20), nullable=False),
            sa.Column("axis_id", sa.Integer()),
            sa.Column("openalex_work_id", sa.String(length=40), nullable=False),
            sa.Column("doi", sa.String(length=255)),
            sa.Column("title", sa.Text()),
            sa.Column("authors", sa.JSON()),
            sa.Column("year", sa.Integer()),
            sa.Column("cited_by_in_library", sa.Integer(), nullable=False),
            sa.Column("computed_at", sa.String(length=40), nullable=False),
            sa.Index("ix_gap_candidates_scope", "direction", "axis_id"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
