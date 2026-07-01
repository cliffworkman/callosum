"""Add ``summaries.imported_json`` — the self-contained display blob for a RELAYED (imported) synthesis (B2 SP2, inc 235).

A synthesis imported from a library bundle carries the SENDER's verification (statuses computed against the sender's
chunks), so it is NOT re-verified locally and must never enter the local verification tables. Instead it is stored as
a self-contained display blob (sentences + per-citation quote/page/status/source-paper at region precision), keyed off
``status="imported"`` and ``imported_json IS NOT NULL``. Native syntheses leave this NULL (unchanged). Nullable JSON,
no server default → a plain ADD COLUMN suffices; idempotent (a fresh DB already has it from 0001's metadata.create_all).

Revision ID: 0032_summary_imported_json
Revises: 0031_paper_read_priority
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0032_summary_imported_json"
down_revision = "0031_paper_read_priority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("summaries")}
    if "imported_json" not in existing:
        with op.batch_alter_table("summaries") as batch:
            batch.add_column(sa.Column("imported_json", sa.JSON()))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("summaries")}
    if "imported_json" in existing:
        with op.batch_alter_table("summaries") as batch:
            batch.drop_column("imported_json")
