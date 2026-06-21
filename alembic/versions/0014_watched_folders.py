"""Watched library folders (inc 98): a ``watched_folders`` table backing folder-watching — persist scanned
folders + auto-rescan to pick up new PDFs (Zotero/Mendeley-style).

Additive and idempotent (like 0002–0013): a *fresh* database already has the table from 0001's
``metadata.create_all``, so the create is guarded and skipped there; an existing database gets it here.

Revision ID: 0014_watched_folders
Revises: 0013_my_publication_dismissed_works
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_watched_folders"
down_revision = "0013_my_publication_dismissed_works"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "watched_folders" not in inspector.get_table_names():
        op.create_table(
            "watched_folders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("path", name="uq_watched_folders_path"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
