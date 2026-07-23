"""WIP manuscript workspace foundation: roots, stable manuscript identity, files, and activity.

Revision ID: 0048_wip_foundation
Revises: 0047_tag_source_vocabulary
Create Date: 2026-07-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0048_wip_foundation"
down_revision = "0047_tag_source_vocabulary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    if "wip_watch_roots" not in existing:
        op.create_table(
            "wip_watch_roots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("path_key", sa.Text(), nullable=False),
            sa.Column("discovery_mode", sa.String(20), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("excluded_children_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("last_scanned_at", sa.DateTime()),
            sa.Column("last_scan_status", sa.String(20)),
            sa.Column("last_scan_detail", sa.Text()),
            sa.CheckConstraint(
                "discovery_mode IN ('folder', 'children')",
                name="ck_wip_watch_roots_wip_watch_roots_discovery_mode",
            ),
            sa.UniqueConstraint("uid", name="uq_wip_watch_roots_uid"),
            sa.UniqueConstraint("path_key", name="uq_wip_watch_roots_path_key"),
        )

    if "wip_manuscripts" not in existing:
        op.create_table(
            "wip_manuscripts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False),
            sa.Column(
                "watch_root_id",
                sa.Integer(),
                sa.ForeignKey("wip_watch_roots.id", ondelete="SET NULL"),
            ),
            sa.Column("root_path", sa.Text(), nullable=False),
            sa.Column("path_key", sa.Text(), nullable=False),
            sa.Column("discovery_source", sa.String(30), server_default="watch-root", nullable=False),
            sa.Column("derived_title", sa.Text(), nullable=False),
            sa.Column("title_override", sa.Text()),
            sa.Column("state", sa.String(20), server_default="active", nullable=False),
            sa.Column("manuscript_type", sa.String(50), server_default="article", nullable=False),
            sa.Column("stage", sa.String(50), server_default="idea", nullable=False),
            sa.Column("target_journal", sa.Text()),
            sa.Column("deadline", sa.Date()),
            sa.Column("notes", sa.Text()),
            sa.Column("template_key", sa.String(80), server_default="empirical-article", nullable=False),
            sa.Column("template_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("last_filesystem_activity_at", sa.DateTime()),
            sa.Column("missing_since", sa.DateTime()),
            sa.CheckConstraint(
                "state IN ('active', 'paused', 'archived', 'missing')",
                name="ck_wip_manuscripts_wip_manuscripts_state",
            ),
            sa.UniqueConstraint("uid", name="uq_wip_manuscripts_uid"),
            sa.UniqueConstraint("path_key", name="uq_wip_manuscripts_path_key"),
        )

    if "wip_files" not in existing:
        op.create_table(
            "wip_files",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(36), nullable=False),
            sa.Column(
                "manuscript_id",
                sa.Integer(),
                sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("relative_path", sa.Text(), nullable=False),
            sa.Column("path_key", sa.Text(), nullable=False),
            sa.Column("role", sa.String(40), server_default="other", nullable=False),
            sa.Column("is_primary", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("existence_state", sa.String(20), server_default="available", nullable=False),
            sa.Column("file_size", sa.Integer()),
            sa.Column("modified_at", sa.DateTime()),
            sa.Column("whole_file_hash", sa.String(64)),
            sa.Column("extracted_text_hash", sa.String(64)),
            sa.Column("extraction_status", sa.String(30), server_default="not-run", nullable=False),
            sa.Column("extraction_error", sa.Text()),
            sa.Column("extraction_provider", sa.String(80)),
            sa.Column("extraction_version", sa.String(40)),
            sa.Column("last_scanned_at", sa.DateTime()),
            sa.CheckConstraint(
                "existence_state IN ('available', 'missing', 'unsupported', 'error')",
                name="ck_wip_files_wip_files_existence_state",
            ),
            sa.UniqueConstraint("uid", name="uq_wip_files_uid"),
            sa.UniqueConstraint("manuscript_id", "path_key", name="uq_wip_files_manuscript_path"),
        )
        op.create_index("ix_wip_files_manuscript_id", "wip_files", ["manuscript_id"])
        op.create_index(
            "uq_wip_files_one_primary",
            "wip_files",
            ["manuscript_id"],
            unique=True,
            sqlite_where=sa.text("is_primary = 1"),
        )

    if "wip_activity_events" not in existing:
        op.create_table(
            "wip_activity_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "manuscript_id",
                sa.Integer(),
                sa.ForeignKey("wip_manuscripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.JSON()),
            sa.Column("related_entity_type", sa.String(40)),
            sa.Column("related_entity_id", sa.String(80)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        )
        op.create_index(
            "ix_wip_activity_manuscript_time",
            "wip_activity_events",
            ["manuscript_id", "created_at"],
        )


def downgrade() -> None:
    # No-op by project convention: user-authored WIP metadata is not dropped.
    return
