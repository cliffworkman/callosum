"""Add explicit synthesis-overview lifecycle state (increment 494).

The columns are nullable for legacy compatibility. Existing non-null ``overview_json`` rows are
interpreted as complete; legacy null overviews are not silently turned into pending provider work.

Revision ID: 0075_summary_overview_lifecycle
Revises: 0074_paper_sections
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0075_summary_overview_lifecycle"
down_revision = "0074_paper_sections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # Some migration regression fixtures intentionally model only the table touched by the
    # preceding revision. A missing summaries table has nothing for this additive migration to do.
    if "summaries" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("summaries")}
    if "overview_status" not in columns:
        op.add_column("summaries", sa.Column("overview_status", sa.String(length=32), nullable=True))
    if "overview_updated_at" not in columns:
        op.add_column("summaries", sa.Column("overview_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Additive lifecycle metadata; down-migrations are not a supported Callosum workflow.
    pass
