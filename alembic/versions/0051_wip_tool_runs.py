"""Generic tool runs and WIP findings.

Revision ID: 0051_wip_tool_runs
Revises: 0050_wip_snapshots
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0051_wip_tool_runs"
down_revision = "0050_wip_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "tool_runs" not in existing:
        op.create_table(
            "tool_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False, unique=True),
            sa.Column("tool_id", sa.String(100), nullable=False),
            sa.Column("tool_version", sa.String(80), nullable=False),
            sa.Column("callosum_version", sa.String(40), nullable=False),
            sa.Column("parameters_json", sa.JSON(), nullable=False),
            sa.Column("result_summary", sa.Text(), nullable=False),
            sa.Column("structured_result_json", sa.JSON(), nullable=False),
            sa.Column("coverage", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("error_detail", sa.Text()),
            sa.Column("executed_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.CheckConstraint("status IN ('running','complete','failed')", name="ck_tool_runs_tool_runs_status"),
        )
        op.create_index("ix_tool_runs_tool_time", "tool_runs", ["tool_id", "executed_at"])
    if "wip_tool_runs" not in existing:
        op.create_table(
            "wip_tool_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tool_run_id", sa.Integer(), sa.ForeignKey("tool_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "manuscript_id",
                sa.Integer(),
                sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("file_id", sa.Integer(), sa.ForeignKey("wip_files.id", ondelete="RESTRICT"), nullable=False),
            sa.Column(
                "snapshot_id",
                sa.Integer(),
                sa.ForeignKey("wip_snapshots.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("relevant_content_hash", sa.String(64), nullable=False),
            sa.UniqueConstraint("tool_run_id", name="uq_wip_tool_runs_tool_run_id"),
        )
        op.create_index("ix_wip_tool_runs_manuscript", "wip_tool_runs", ["manuscript_id"])
    if "wip_findings" not in existing:
        op.create_table(
            "wip_findings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False, unique=True),
            sa.Column("tool_run_id", sa.Integer(), sa.ForeignKey("tool_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "manuscript_id",
                sa.Integer(),
                sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("file_id", sa.Integer(), sa.ForeignKey("wip_files.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("wip_sections.id", ondelete="SET NULL")),
            sa.Column("reference_id", sa.Integer(), sa.ForeignKey("wip_references.id", ondelete="SET NULL")),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("finding_type", sa.String(80), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("details_json", sa.JSON(), nullable=False),
            sa.Column("quote", sa.Text()),
            sa.Column("context", sa.Text()),
            sa.Column("coordinate_precision", sa.String(20)),
            sa.Column("disposition", sa.String(30)),
            sa.Column("resolution_notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.CheckConstraint("kind IN ('fact','candidate')", name="ck_wip_findings_wip_findings_kind"),
            sa.CheckConstraint("severity IN ('info','warning','high')", name="ck_wip_findings_wip_findings_severity"),
            sa.CheckConstraint(
                "coordinate_precision IS NULL OR coordinate_precision IN ('exact','region')",
                name="ck_wip_findings_wip_findings_coordinate_precision",
            ),
            sa.CheckConstraint(
                "disposition IS NULL OR disposition IN "
                "('open','acknowledged','resolved','dismissed','false-positive','deferred','superseded')",
                name="ck_wip_findings_wip_findings_disposition",
            ),
        )
        op.create_index("ix_wip_findings_manuscript", "wip_findings", ["manuscript_id"])
        op.create_index("ix_wip_findings_run", "wip_findings", ["tool_run_id"])


def downgrade() -> None:
    pass
