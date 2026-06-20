"""Create persistence core schema.

Revision ID: 0001_persistence_core
Revises:
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
from app.backend.persistence.schema import metadata

revision = "0001_persistence_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")

    for table in reversed(metadata.sorted_tables):
        op.drop_table(table.name)

    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")
