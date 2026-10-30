"""Per-library settings: ``library_settings`` (key/value), first used for the active retrieval embedding profile.

The machine-wide app-settings file is shared by every Callosum instance for the OS user, so a choice that is only
valid for one database (a retrieval profile whose index covers this library) is stored in the library.

Additive and idempotent (like 0002-0084): a *fresh* database already has the table from 0001's
``metadata.create_all``, so the create is guarded and skipped there; an existing database gets it here. No existing
row is read or written.

Revision ID: 0085_library_settings
Revises: 0084_provisional_artifacts
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0085_library_settings"
down_revision = "0084_provisional_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "library_settings" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "library_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
    )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
