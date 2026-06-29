"""Saved searches (inc 208, A1): a ``saved_searches`` table — a named bundle of the existing library facets
(q / search_field / item_type / axis / tag / needs_review / signal / sort) stored as a JSON ``params`` blob,
recalled from the library header. A metadata predicate over the existing GET /papers filters (NOT a semantic lens).

Additive + idempotent (like 0021): a fresh DB already has the table from 0001's ``metadata.create_all``, so the
create is guarded and skipped there; an existing DB gets it here.

Revision ID: 0025_saved_searches
Revises: 0024_tag_color
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0025_saved_searches"
down_revision = "0024_tag_color"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "saved_searches" not in tables:
        op.create_table(
            "saved_searches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("params", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.UniqueConstraint("name", name="uq_saved_searches_name"),
        )


def downgrade() -> None:
    # No-op by design (mirrors 0021/0022): the table lives in 0001's `metadata`, whose downgrade loops over
    # `metadata.sorted_tables` and drops it. A real drop_table here would double-drop (0001 drops it again → error).
    return
