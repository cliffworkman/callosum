"""User-attached paper content: freeform notes and PDF highlights/annotations. Split out of schema.py
(inc 467, over the 600-line cap) — same leaf pattern as schema_grim_checks.py etc. on the shared
schema_base metadata."""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func

from app.backend.persistence.schema_base import metadata

notes = Table(
    "notes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("body", Text, nullable=False),
    Column("import_source", String(100)),
    Column("external_id", String(255)),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_notes_paper_id", "paper_id"),
)

annotations = Table(
    "annotations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("attachment_id", ForeignKey("attachments.id", ondelete="CASCADE")),
    Column("page", Integer),
    Column("annotation_type", String(100)),
    Column("body", Text),
    Column("position_json", JSON),
    Column("coordinate_system", String(100)),
    Column("import_source", String(100)),
    Column("external_id", String(255)),
    # Native (callosum-authored) annotation columns. Added in 0002 for the highlight
    # suite; nullable so imported (e.g. Zotero) rows are unaffected. `source`
    # discriminates origin ("user" now; "synthesis" in a later increment); imported
    # rows leave it NULL. Native rows carry bboxes_json (pdf-points-top-left, the
    # increment-29 overlay basis) rather than the import-shaped position_json.
    Column("color", String(50)),
    Column("bboxes_json", JSON),
    Column("anchor_text", Text),
    Column("prefix", Text),
    Column("suffix", Text),
    Column("source", String(50)),
    Column("note", Text),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    ),
    Index("ix_annotations_paper_id", "paper_id"),
    Index("ix_annotations_attachment_id", "attachment_id"),
)
