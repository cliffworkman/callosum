"""Add the per-axis scoring cutoff (``axes.scoring_gain``).

Stores the assignment cutoff an axis was last scored at (assigned = similarity >= gain); NULL means
"use the current default". Nullable, no server default, so a plain ADD COLUMN suffices (no table
rebuild). Idempotent like 0002: a *fresh* database already has the column from 0001's
``metadata.create_all``, so this is a no-op there; only pre-existing databases get the delta.

Revision ID: 0003_axis_scoring_gain
Revises: 0002_annotation_highlights
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_axis_scoring_gain"
down_revision = "0002_annotation_highlights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("axes")}
    if "scoring_gain" in existing:
        return  # fresh database: 0001's create_all already built the final schema. No-op.
    with op.batch_alter_table("axes") as batch:
        batch.add_column(sa.Column("scoring_gain", sa.Float()))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("axes")}
    if "scoring_gain" in existing:
        with op.batch_alter_table("axes") as batch:
            batch.drop_column("scoring_gain")
