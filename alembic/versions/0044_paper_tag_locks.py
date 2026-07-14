"""Per-paper tag locks.

Revision ID: 0044_paper_tag_locks
Revises: 0043_funding_llm_triage_annotations
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0044_paper_tag_locks"
down_revision = "0043_funding_llm_triage_annotations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("paper_tags")}
    if "locked" not in columns:
        op.add_column("paper_tags", sa.Column("locked", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    return
