"""A lightweight receipt of a Journals (venue-fit) search run against a WIP manuscript (inc 404).

Discover > Journals is deliberately ephemeral for a Library paper (`publishers.py`: "Ephemeral job result; no
table/migration") -- recomputing is cheap, so the full ranked profile list is never persisted. This table doesn't
reverse that: it stores only a compact summary (topic/weighting/counts), never the profiles themselves, so a WIP
manuscript's own workspace tab can show "a search happened, roughly what it returned" without caching the heavy
result. Only rows for manuscript-tagged runs are ever written; the paper/abstract paths are untouched.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, func

from app.backend.persistence.schema_base import metadata

wip_journal_runs = Table(
    "wip_journal_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("manuscript_id", ForeignKey("wip_manuscripts.id", ondelete="CASCADE"), nullable=False),
    Column("topic_id", String(200)),
    Column("weighting", Float, nullable=False),
    Column("considered", Integer, nullable=False),
    Column("shown", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_wip_journal_runs_manuscript_id", "manuscript_id"),
)
