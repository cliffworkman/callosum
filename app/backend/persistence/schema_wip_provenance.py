"""Content checkpoints for unpublished WIP manuscripts."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.backend.persistence.schema_base import metadata

WIP_SNAPSHOT_REASONS = (
    "manual",
    "stage-transition",
    "submission",
    "resubmission",
    "primary-file-replacement",
    "tool-run",
)

wip_snapshots = Table(
    "wip_snapshots",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("uid", String(36), nullable=False, unique=True),
    Column("manuscript_id", Integer, ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("file_id", Integer, ForeignKey("wip_files.id", ondelete="RESTRICT"), nullable=False),
    Column("whole_file_hash", String(64), nullable=False),
    Column("extracted_text_hash", String(64), nullable=False),
    Column("section_hashes_json", JSON),
    Column("evidence_context_json", JSON, nullable=False),
    Column("extracted_char_count", Integer, nullable=False),
    Column("extraction_provider", String(80), nullable=False),
    Column("extraction_version", String(40), nullable=False),
    Column("reason", String(40), nullable=False),
    Column("reason_detail", Text, nullable=False, server_default=""),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint(
        "manuscript_id",
        "file_id",
        "whole_file_hash",
        "extracted_text_hash",
        "reason",
        "reason_detail",
        name="uq_wip_snapshots_content_reason",
    ),
    CheckConstraint(
        "reason IN ('manual','stage-transition','submission','resubmission','primary-file-replacement','tool-run')",
        name="wip_snapshots_reason",
    ),
)
Index("ix_wip_snapshots_manuscript_time", wip_snapshots.c.manuscript_id, wip_snapshots.c.created_at)
