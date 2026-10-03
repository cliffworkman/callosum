"""The user's personal library lists: saved searches and the reading queue. Split out of schema.py (over the
600-line cap) -- same leaf pattern as schema_annotations.py on the shared schema_base metadata; schema.py re-exports both
tables at the point they used to be defined, so table registration order and every importer are unchanged."""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Table, Text, UniqueConstraint, func

from app.backend.persistence.schema_base import metadata

# Saved searches (inc 208, A1): a named bundle of the existing library facets (q / search_field / item_type / axis /
# tag / needs_review / signal / sort), stored as a JSON `params` blob and recalled from the library header. A metadata
# predicate over the existing GET /papers filters — NOT a semantic lens (that's an axis). Local; name is UNIQUE.
saved_searches = Table(
    "saved_searches",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("params", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("name", name="uq_saved_searches_name"),
)

# Reading queue (inc 219): a personal, ordered to-read list — papers the user wants to read, drag-to-reorder. NOT an
# axis (no semantic scoring) — its own small table + its own left-pane "Queue" tab. One row per paper (UNIQUE);
# `position` drives the manual order (the inc-211 curated-axis pattern); CASCADE drops a row when its paper is purged.
reading_queue = Table(
    "reading_queue",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("position", Integer),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("paper_id", name="uq_reading_queue_paper"),
)
