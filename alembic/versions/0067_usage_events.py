"""Local usage-instrumentation table (backlog #38A) -- usage_events. An append-only log of event type/count/
timestamp only, no payload column, no FK to papers -- see schema_usage.py's docstring.

Additive + idempotent (like 0002-0066): guarded create, skipped on a fresh DB (0001 already has it via
metadata.create_all).

Revision ID: 0067_usage_events
Revises: 0066_top_factor_records
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0067_usage_events"
down_revision = "0066_top_factor_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "usage_events" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "usage_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("duration_ms", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )
        op.create_index("ix_usage_events_type_created", "usage_events", ["event_type", "created_at"])


def downgrade() -> None:
    # Additive table, like every other findings-cluster migration -- 0001 owns eventual teardown.
    pass
