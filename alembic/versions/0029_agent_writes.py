"""B1 SP2: the agent_writes audit table (MCP agent writes — the review + revert log).

Additive + idempotent (like 0021-0028): a fresh DB already has the table from 0001's metadata.create_all
(it's on the shared metadata), so the create is guarded + skipped there; an existing DB gets it here. No-op downgrade.

Revision ID: 0029_agent_writes
Revises: 0028_cluster_node_paper_position
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0029_agent_writes"
down_revision = "0028_cluster_node_paper_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "agent_writes" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "agent_writes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("target_paper_id", sa.Integer()),
            sa.Column("tool", sa.String(length=40)),
            sa.Column("detail_json", sa.JSON(), nullable=False),
            sa.Column("reverted_at", sa.DateTime()),
        )
        op.create_index("ix_agent_writes_created", "agent_writes", ["created_at"])


def downgrade() -> None:
    # No-op by design (the table lives in 0001's metadata; downgrades aren't a supported workflow).
    return
