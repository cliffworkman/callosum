"""Add WIP reference-integrity signal/review tables (backlog #48).

Dedicated tables, not a retrofit of `reference_instances` (NOT NULL FK to `papers.id`, a disjoint id space from
`wip_manuscripts.id`) or of the generic `wip_tool_runs`/`wip_findings` (NOT NULL file/snapshot columns that
assume a manuscript-file content basis this tool doesn't have). `wip_references.id` is already the canonical
deduped `(manuscript_id, paper_id)` identity, so signals attach directly to it.

Revision ID: 0065_wip_reference_integrity
Revises: 0064_registration_comparison_triage
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0065_wip_reference_integrity"
down_revision = "0064_registration_comparison_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "wip_reference_signals" not in tables:
        op.create_table(
            "wip_reference_signals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "manuscript_id", sa.Integer(), sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "reference_id", sa.Integer(), sa.ForeignKey("wip_references.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("detector_kind", sa.String(length=60), nullable=False),
            sa.Column("detector_status", sa.String(length=60), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=False),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("snapshot_marker", sa.String(length=255), nullable=False),
            sa.Column("signal_key", sa.String(length=64), nullable=False),
            sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint(
                "reference_id", "detector_kind", "signal_key", name="uq_wip_reference_signals_ref_kind_key"
            ),
        )
        op.create_index("ix_wip_reference_signals_reference", "wip_reference_signals", ["reference_id"])
        op.create_index("ix_wip_reference_signals_manuscript", "wip_reference_signals", ["manuscript_id"])
    if "wip_reference_reviews" not in tables:
        op.create_table(
            "wip_reference_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "reference_id", sa.Integer(), sa.ForeignKey("wip_references.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("signal_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("state", sa.String(length=30), nullable=False, server_default="unreviewed"),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("review_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.CheckConstraint(
                "state IN ('unreviewed', 'dismissed', 'confirmed_problem')",
                name="wip_reference_review_state_valid",
            ),
            sa.UniqueConstraint("reference_id", "signal_fingerprint", name="uq_wip_reference_reviews_ref_fingerprint"),
        )
        op.create_index("ix_wip_reference_reviews_reference", "wip_reference_reviews", ["reference_id"])


def downgrade() -> None:
    # Additive tables, like every other WIP-provenance migration -- 0001 owns eventual metadata teardown.
    pass
