"""Add ``papers.deleted_at`` for soft-delete (Trash / Restore).

A NULL ``deleted_at`` means the paper is live; a timestamp means it's in the Trash (hidden from the
library, axes, and clustering, but its rows are kept so it's fully restorable and nothing orphans).
Nullable, no server default → a plain ADD COLUMN suffices. Idempotent like 0002/0003: a *fresh*
database already has the column from 0001's ``metadata.create_all``, so this is a no-op there.

Revision ID: 0004_paper_soft_delete
Revises: 0003_axis_scoring_gain
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_paper_soft_delete"
down_revision = "0003_axis_scoring_gain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("papers")}
    if "deleted_at" in existing:
        return  # fresh database: 0001's create_all already built the final schema. No-op.
    with op.batch_alter_table("papers") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime()))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("papers")}
    if "deleted_at" in existing:
        with op.batch_alter_table("papers") as batch:
            batch.drop_column("deleted_at")
