"""Add critical_read_snapshots: one durable latest Tier-1 critique backbone per paper (inc 601).

The single-paper Critical Read (backlog #12) built a ScrutinyBackboneResponse and marked it done in the
IN-MEMORY job store — nothing was persisted, so a reader-launched critique (inc 598) became unreachable once its
modal closed, and every view recomputed. This table snapshots the Tier-1 backbone per paper (current-only —
Refresh REPLACES the row, no history). `requested_at` is the monotonic per-run replacement guard; a completing
run upserts only when its requested_at is not older than the stored one, so an out-of-order Refresh cannot
clobber a newer result. `content_fingerprint` is the canonical statcheck-cache fingerprint → a passive "the
paper's full text changed since this was computed" hint only. `snapshot_schema_version` + `critical_review_version`
let the durable payload survive future code (an incompatible old snapshot reads as "refresh required").

Revision ID: 0083_critical_read_snapshots
Revises: 0082_wanted_reason_code
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0083_critical_read_snapshots"
down_revision = "0082_wanted_reason_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "critical_read_snapshots" in inspector.get_table_names():
        return
    op.create_table(
        "critical_read_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("backbone_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("critical_review_version", sa.String(length=20), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=128)),
        sa.Column("requested_at", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("paper_id", name="uq_critical_read_snapshot_paper"),
    )
    op.create_index("ix_critical_read_snapshot_paper", "critical_read_snapshots", ["paper_id"])


def downgrade() -> None:
    # Additive table, like the other inc-5xx/0074+ migrations — 0001 owns eventual teardown.
    pass
