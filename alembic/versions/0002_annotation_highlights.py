"""Extend annotations table for native (callosum-authored) highlights.

Adds the columns the highlight suite needs to the existing ``annotations`` table
(which the Zotero importer already writes to). New columns are nullable so imported
rows are unaffected; ``source`` discriminates origin ("user"/"synthesis"; imported
rows leave it NULL), and ``bboxes_json`` stores rects in the increment-29
``pdf-points-top-left`` overlay basis.

Idempotent on purpose: migration 0001 runs ``metadata.create_all`` against the live
schema, so a *fresh* database already has these columns and this migration is a
no-op there; only *pre-existing* databases get the delta.

Revision ID: 0002_annotation_highlights
Revises: 0001_persistence_core
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_annotation_highlights"
down_revision = "0001_persistence_core"
branch_labels = None
depends_on = None


def _new_columns() -> list[sa.Column]:
    return [
        sa.Column("color", sa.String(50)),
        sa.Column("bboxes_json", sa.JSON()),
        sa.Column("anchor_text", sa.Text()),
        sa.Column("prefix", sa.Text()),
        sa.Column("suffix", sa.Text()),
        sa.Column("source", sa.String(50)),
        sa.Column("note", sa.Text()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("annotations")}
    missing = [column for column in _new_columns() if column.name not in existing]
    if not missing:
        # Fresh database: 0001's create_all already built the final schema. No-op.
        return
    # Existing database: add the columns. recreate="always" forces a SQLite
    # table rebuild (CREATE TABLE + copy), which is required because plain
    # ADD COLUMN rejects updated_at's non-constant CURRENT_TIMESTAMP default. The
    # rebuild reflects and preserves the existing FK (ON DELETE CASCADE) + indexes.
    with op.batch_alter_table("annotations", recreate="always") as batch:
        for column in missing:
            batch.add_column(column)


def downgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("annotations")}
    names = [column.name for column in _new_columns()]
    with op.batch_alter_table("annotations") as batch:
        for name in reversed(names):
            if name in existing:
                batch.drop_column(name)
