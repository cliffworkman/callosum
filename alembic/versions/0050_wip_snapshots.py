"""WIP manuscript content checkpoints.

Revision ID: 0050_wip_snapshots
Revises: 0049_wip_workflow
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0050_wip_snapshots"
down_revision = "0049_wip_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    file_columns = {column["name"] for column in inspector.get_columns("wip_files")}
    if "extracted_from_whole_hash" not in file_columns:
        op.add_column("wip_files", sa.Column("extracted_from_whole_hash", sa.String(64)))
    if "wip_snapshots" not in set(inspector.get_table_names()):
        op.create_table(
            "wip_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False, unique=True),
            sa.Column(
                "manuscript_id",
                sa.Integer(),
                sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("file_id", sa.Integer(), sa.ForeignKey("wip_files.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("whole_file_hash", sa.String(64), nullable=False),
            sa.Column("extracted_text_hash", sa.String(64), nullable=False),
            sa.Column("section_hashes_json", sa.JSON()),
            sa.Column("evidence_context_json", sa.JSON(), nullable=False),
            sa.Column("extracted_char_count", sa.Integer(), nullable=False),
            sa.Column("extraction_provider", sa.String(80), nullable=False),
            sa.Column("extraction_version", sa.String(40), nullable=False),
            sa.Column("reason", sa.String(40), nullable=False),
            sa.Column("reason_detail", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint(
                "manuscript_id",
                "file_id",
                "whole_file_hash",
                "extracted_text_hash",
                "reason",
                "reason_detail",
                name="uq_wip_snapshots_content_reason",
            ),
            sa.CheckConstraint(
                "reason IN ('manual','stage-transition','submission','resubmission','primary-file-replacement','tool-run')",
                name="ck_wip_snapshots_wip_snapshots_reason",
            ),
        )
        op.create_index(
            "ix_wip_snapshots_manuscript_time",
            "wip_snapshots",
            ["manuscript_id", "created_at"],
        )


def downgrade() -> None:
    pass
