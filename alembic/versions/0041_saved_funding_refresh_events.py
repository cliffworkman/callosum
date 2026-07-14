"""saved_funding_refresh_events.

Revision ID: 0041_saved_funding_refresh_events
Revises: 0040_allow_duplicate_paper_dois
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

from alembic import op

revision = "0041_saved_funding_refresh_events"
down_revision = "0040_allow_duplicate_paper_dois"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    if "saved_funding_refresh_events" in _tables():
        return
    op.create_table(
        "saved_funding_refresh_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "saved_item_id",
            sa.Integer(),
            sa.ForeignKey("saved_funding_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_kind", sa.String(length=40), nullable=False),
        sa.Column("canonical_item_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=80), nullable=False),
        sa.Column("provider_status", sa.String(length=120)),
        sa.Column("changes_json", sqlite.JSON(), nullable=False),
        sa.Column(
            "linked_opportunity_id",
            sa.Integer(),
            sa.ForeignKey("funding_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("checked_at", sa.String(), server_default=sa.func.current_timestamp()),
    )
    op.create_index(
        "ix_saved_funding_refresh_events_saved_item",
        "saved_funding_refresh_events",
        ["saved_item_id"],
    )


def downgrade() -> None:
    pass
