"""Local usage-instrumentation table (backlog #38A, inc 450) — Stage 1 of the research-impact-analytics future
track (`.claude/docs/future-tracks/opus4.8_future-tracks_researchimpactanalytics.md`). An append-only log of
event *types*, *counts*, and *timestamps* only — deliberately no payload/detail/JSON column and no FK to
``papers``, so the schema itself structurally forecloses a content leak or paper-identifying reconstruction,
rather than relying on a policy statement alone. Zero egress; this table is read/exported/cleared locally only.

Split into its own file rather than folded into ``schema_findings.py``'s grab-bag of derived per-paper caches:
this is a fundamentally different shape (an unkeyed append-only log, not a paper-keyed cache), and a future
reviewer auditing "no payload column was ever added here" benefits from one small dedicated file to check.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Index, Integer, String, Table, func

from app.backend.persistence.schema_base import metadata

usage_events = Table(
    "usage_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("event_type", String(40), nullable=False),
    Column("count", Integer, nullable=False, server_default="1"),
    Column("duration_ms", Integer),  # always NULL this increment -- no instrumented op has a server-side
    # duration yet; an honest, stated limitation rather than a fabricated timing.
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_usage_events_type_created", "event_type", "created_at"),
)

# The closed, reviewable event-type vocabulary (the design doc's own "tedium reduction" / "care-in-action"
# taxonomy) -- enforced at the Python/API boundary (citations.py's style_store.style_exists precedent), not a
# DB CHECK constraint, since SQLite CHECK requires a full table rebuild to extend and this list is expected to
# grow as future increments instrument more operations.
USAGE_EVENT_TYPES: tuple[str, ...] = (
    "citation_export",
    "duplicate_resolved",
    "metadata_reresolved",
    "quote_located",
    "flag_reviewed",
)
