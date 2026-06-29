"""Add an optional per-tag color (``tags.color``).

Stores a fixed-palette KEY (e.g. "blue"), never arbitrary hex — the frontend maps the key to a theme-aware
token; NULL = uncolored. Nullable, no server default, so a plain ADD COLUMN suffices. Idempotent like 0003:
a *fresh* database already has the column from 0001's ``metadata.create_all``, so this is a no-op there;
only pre-existing databases get the delta.

Revision ID: 0024_tag_color
Revises: 0023_sync_identity
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0024_tag_color"
down_revision = "0023_sync_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("tags")}
    if "color" in existing:
        return  # fresh database: 0001's create_all already built the final schema. No-op.
    with op.batch_alter_table("tags") as batch:
        batch.add_column(sa.Column("color", sa.String(20)))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("tags")}
    if "color" in existing:
        with op.batch_alter_table("tags") as batch:
            batch.drop_column("color")
