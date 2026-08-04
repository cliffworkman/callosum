"""Persistent Work-in-Progress manuscript workspaces.

WIP deliberately has its own data model: a manuscript is a research product rooted in a local directory, never a
subtype of the bibliographic ``papers`` record. These tables register on the shared metadata and are re-exported by
``schema.py``.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from app.backend.persistence.schema_base import metadata

WIP_DISCOVERY_MODES = ("folder", "children")
WIP_STATES = ("active", "paused", "archived", "missing")
WIP_FILE_STATES = ("available", "missing", "unsupported", "error")

wip_watch_roots = Table(
    "wip_watch_roots",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("uid", String(36), nullable=False, unique=True),
    Column("path", Text, nullable=False),
    Column("path_key", Text, nullable=False, unique=True),
    Column("discovery_mode", String(20), nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("1")),
    Column("excluded_children_json", JSON, nullable=False, server_default=text("'[]'")),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("last_scanned_at", DateTime),
    Column("last_scan_status", String(20)),
    Column("last_scan_detail", Text),
    CheckConstraint(
        "discovery_mode IN ('folder', 'children')",
        name="wip_watch_roots_discovery_mode",
    ),
)

wip_manuscripts = Table(
    "wip_manuscripts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("uid", String(36), nullable=False, unique=True),
    Column("watch_root_id", Integer, ForeignKey("wip_watch_roots.id", ondelete="SET NULL")),
    Column("root_path", Text, nullable=False),
    Column("path_key", Text, nullable=False, unique=True),
    Column("discovery_source", String(30), nullable=False, server_default="watch-root"),
    Column("derived_title", Text, nullable=False),
    Column("title_override", Text),
    Column("state", String(20), nullable=False, server_default="active"),
    Column("manuscript_type", String(50), nullable=False, server_default="article"),
    Column("stage", String(50), nullable=False, server_default="idea"),
    Column("target_journal", Text),
    Column("deadline", Date),
    Column("notes", Text),
    Column("template_key", String(80), nullable=False, server_default="empirical-article"),
    Column("template_version", Integer, nullable=False, server_default=text("1")),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("last_filesystem_activity_at", DateTime),
    Column("missing_since", DateTime),
    CheckConstraint(
        "state IN ('active', 'paused', 'archived', 'missing')",
        name="wip_manuscripts_state",
    ),
)

wip_files = Table(
    "wip_files",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("uid", String(36), nullable=False, unique=True),
    Column("manuscript_id", Integer, ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("relative_path", Text, nullable=False),
    Column("path_key", Text, nullable=False),
    Column("role", String(40), nullable=False, server_default="other"),
    Column("is_primary", Boolean, nullable=False, server_default=text("0")),
    Column("existence_state", String(20), nullable=False, server_default="available"),
    Column("file_size", Integer),
    Column("modified_at", DateTime),
    Column("whole_file_hash", String(64)),
    Column("extracted_text_hash", String(64)),
    Column("extracted_from_whole_hash", String(64)),
    Column("extraction_status", String(30), nullable=False, server_default="not-run"),
    Column("extraction_error", Text),
    Column("extraction_provider", String(80)),
    Column("extraction_version", String(40)),
    Column("last_scanned_at", DateTime),
    UniqueConstraint("manuscript_id", "path_key", name="uq_wip_files_manuscript_path"),
    CheckConstraint(
        "existence_state IN ('available', 'missing', 'unsupported', 'error')",
        name="wip_files_existence_state",
    ),
)
Index(
    "uq_wip_files_one_primary",
    wip_files.c.manuscript_id,
    unique=True,
    sqlite_where=wip_files.c.is_primary.is_(True),
)
Index("ix_wip_files_manuscript_id", wip_files.c.manuscript_id)

wip_activity_events = Table(
    "wip_activity_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("manuscript_id", Integer, ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("event_type", String(80), nullable=False),
    Column("summary", Text, nullable=False),
    Column("metadata_json", JSON),
    Column("related_entity_type", String(40)),
    Column("related_entity_id", String(80)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
)
Index("ix_wip_activity_manuscript_time", wip_activity_events.c.manuscript_id, wip_activity_events.c.created_at)

# Workflow tables share this concern and are re-exported here so schema.py needs one compact registration import.
# inc 404: a lightweight per-manuscript Journals search receipt (topic/weighting/counts only, never the full
# ranked profile list -- see schema_wip_journal_runs.py's own docstring for why).
from app.backend.persistence.schema_wip_journal_runs import wip_journal_runs  # noqa: E402,F401
from app.backend.persistence.schema_wip_provenance import (  # noqa: E402,F401
    wip_findings,
    wip_snapshots,
    wip_tool_runs,
)

# backlog #48: reference-integrity signals for a manuscript's linked Library references (see the module's own
# docstring for why this is dedicated rather than a retrofit of reference_instances/wip_tool_runs/wip_findings).
from app.backend.persistence.schema_wip_reference_integrity import (  # noqa: E402,F401
    wip_reference_reviews,
    wip_reference_signals,
)
from app.backend.persistence.schema_wip_workflow import wip_references, wip_sections, wip_tasks  # noqa: E402,F401
