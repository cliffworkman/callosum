"""Add the ``dismissed_duplicate_pairs`` table (persistent "not a duplicate" dismissals).

The duplicate-detection scan drops these canonical (low < high) pairs before its union-find, so a pair the
user marked "not a duplicate" never re-flags. Idempotent like 0002–0005: a *fresh* database already has the
table from 0001's ``metadata.create_all``, so this is a no-op there.

Revision ID: 0006_dismissed_duplicate_pairs
Revises: 0005_llm_generation_cache
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_dismissed_duplicate_pairs"
down_revision = "0005_llm_generation_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("dismissed_duplicate_pairs"):
        return  # fresh database: 0001's create_all already built the final schema. No-op.
    op.create_table(
        "dismissed_duplicate_pairs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id_low", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_id_high", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("paper_id_low < paper_id_high", name="ck_dismissed_duplicate_pairs_canonical_pair_order"),
        sa.UniqueConstraint("paper_id_low", "paper_id_high", name="uq_dismissed_duplicate_pairs_low_high"),
    )


def downgrade() -> None:
    # No-op by design: the table is in the schema metadata, so teardown is owned by 0001's metadata-wide
    # downgrade (dropping it here too would double-drop). Downgrades aren't a supported workflow.
    return
