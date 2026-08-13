"""Add received_shares (SP4c: the recipient-side cross-user provenance log for the sharing feature).

Revision ID: 0073_received_shares
Revises: 0072_paper_duplicate_value_checks
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0073_received_shares"
down_revision = "0072_paper_duplicate_value_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "received_shares" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "received_shares",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("share_id", sa.Integer(), nullable=False, unique=True),
            sa.Column("sender_sub", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("acted_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("summary_json", sa.JSON()),
            sa.CheckConstraint("status IN ('imported', 'dismissed')", name="received_share_status_valid"),
        )


def downgrade() -> None:
    # Additive table, like 0052/0054-0057/0070-0072 — 0001 owns eventual metadata teardown.
    pass
