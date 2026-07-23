"""Manuscript workflow records: sections, tasks, and links to Library references."""

from __future__ import annotations

from sqlalchemy import (
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

WIP_SECTION_STATUSES = (
    "not-started",
    "outlined",
    "drafting",
    "complete",
    "needs-revision",
    "under-review",
    "approved",
    "not-applicable",
)
WIP_TASK_STATUSES = ("open", "in-progress", "blocked", "complete", "deferred", "cancelled")
WIP_REFERENCE_STATES = (
    "cited",
    "possibly-cited",
    "background-reading",
    "to-cite",
    "rejected-for-use",
    "needs-verification",
)

wip_sections = Table(
    "wip_sections",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("uid", String(36), nullable=False, unique=True),
    Column("manuscript_id", Integer, ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("name", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("status", String(30), nullable=False, server_default="not-started"),
    Column("notes", Text),
    Column("content_detected", Boolean, nullable=False, server_default=text("0")),
    Column("is_custom", Boolean, nullable=False, server_default=text("0")),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("manuscript_id", "position", name="uq_wip_sections_position"),
    CheckConstraint(
        "status IN ('not-started','outlined','drafting','complete','needs-revision','under-review','approved','not-applicable')",
        name="wip_sections_status",
    ),
)
Index("ix_wip_sections_manuscript_id", wip_sections.c.manuscript_id)

wip_tasks = Table(
    "wip_tasks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("uid", String(36), nullable=False, unique=True),
    Column("manuscript_id", Integer, ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("title", Text, nullable=False),
    Column("description", Text),
    Column("status", String(30), nullable=False, server_default="open"),
    Column("due_date", Date),
    Column("section_id", Integer, ForeignKey("wip_sections.id", ondelete="SET NULL")),
    Column("file_id", Integer, ForeignKey("wip_files.id", ondelete="SET NULL")),
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="SET NULL")),
    Column("finding_id", Integer),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("completed_at", DateTime),
    CheckConstraint(
        "status IN ('open','in-progress','blocked','complete','deferred','cancelled')",
        name="wip_tasks_status",
    ),
)
Index("ix_wip_tasks_manuscript_status", wip_tasks.c.manuscript_id, wip_tasks.c.status)

wip_references = Table(
    "wip_references",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("manuscript_id", Integer, ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("relationship_state", String(30), nullable=False, server_default="possibly-cited"),
    Column("notes", Text),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("manuscript_id", "paper_id", name="uq_wip_references_manuscript_paper"),
    CheckConstraint(
        "relationship_state IN ('cited','possibly-cited','background-reading','to-cite','rejected-for-use','needs-verification')",
        name="wip_references_state",
    ),
)
Index("ix_wip_references_paper_id", wip_references.c.paper_id)
