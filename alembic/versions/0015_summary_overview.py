"""Synthesis Overview (inc 124): a ``summaries.overview_json`` column holding the per-sentence evidence-traceable
Overview — [{text, claim_ordinals:[int]}], narrativizing the verified claims.

Additive + idempotent (like 0002-0014): a fresh DB already has the column from 0001's ``metadata.create_all``, so
the add is guarded and skipped there; an existing DB gets it here.

Revision ID: 0015_summary_overview
Revises: 0014_watched_folders
Create Date: 2026-06-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_summary_overview"
down_revision = "0014_watched_folders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("summaries")}
    if "overview_json" not in columns:
        op.add_column("summaries", sa.Column("overview_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
