"""Add per-paper reading state: ``papers.read_at`` + ``papers.priority`` (inc 220).

Both are user-set workflow markers — ``read_at`` (NULL = unread; a timestamp = the user marked it read,
manual) and ``priority`` (NULL = unset; a user triage label "high"/"normal"/"low", never an AI score).
Nullable, no server default, so a plain ADD COLUMN suffices (the inc-24 ``tags.color`` pattern). Idempotent:
a *fresh* database already has both columns from 0001's ``metadata.create_all``, so this is a no-op there;
only pre-existing databases get the delta.

Revision ID: 0031_paper_read_priority
Revises: 0030_reading_queue
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0031_paper_read_priority"
down_revision = "0030_reading_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("papers")}
    with op.batch_alter_table("papers") as batch:
        if "read_at" not in existing:
            batch.add_column(sa.Column("read_at", sa.DateTime()))
        if "priority" not in existing:
            batch.add_column(sa.Column("priority", sa.String(20)))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("papers")}
    with op.batch_alter_table("papers") as batch:
        if "read_at" in existing:
            batch.drop_column("read_at")
        if "priority" in existing:
            batch.drop_column("priority")
