"""Local usage-instrumentation repo (backlog #38A, inc 450). Pure repo -- no app_settings import; the enabled-
gate lives one layer up in app/backend/usage.py, matching how every other stored_X_enabled() check in this
codebase happens at the router/seam layer, never inside persistence/."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, delete, func, insert, select

from app.backend.persistence.schema_usage import USAGE_EVENT_TYPES, usage_events

USAGE_EVENT_LABELS: dict[str, str] = {
    "citation_export": "Citations exported",
    "duplicate_resolved": "Duplicates resolved",
    "metadata_reresolved": "Metadata re-resolved",
    "quote_located": "Quotes located",
    "flag_reviewed": "Flagged citations reviewed",
}


def insert_usage_event(conn: Connection, event_type: str, *, count: int = 1) -> None:
    conn.execute(insert(usage_events).values(event_type=event_type, count=count))


def usage_summary(conn: Connection, *, days: int = 30) -> list[dict[str, Any]]:
    """One row per USAGE_EVENT_TYPES entry, in that fixed order -- never sorted by count, which would read as
    a ranking. Never-empty: a type with zero events still gets a row reading 0, so absence isn't ambiguous
    with "not tracked" (Principles #6, silence isn't a certificate)."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    all_time_rows = dict(
        conn.execute(
            select(usage_events.c.event_type, func.sum(usage_events.c.count)).group_by(usage_events.c.event_type)
        ).all()
    )
    recent_rows = dict(
        conn.execute(
            select(usage_events.c.event_type, func.sum(usage_events.c.count))
            .where(usage_events.c.created_at >= cutoff)
            .group_by(usage_events.c.event_type)
        ).all()
    )
    return [
        {
            "event_type": event_type,
            "label": USAGE_EVENT_LABELS[event_type],
            "all_time": int(all_time_rows.get(event_type) or 0),
            "last_30_days": int(recent_rows.get(event_type) or 0),
        }
        for event_type in USAGE_EVENT_TYPES
    ]


def list_usage_events(conn: Connection) -> list[dict[str, Any]]:
    """The raw log, oldest first -- for export. Only event_type/count/duration_ms/created_at ever leave; no
    payload column exists to accidentally include."""
    rows = conn.execute(
        select(
            usage_events.c.event_type,
            usage_events.c.count,
            usage_events.c.duration_ms,
            usage_events.c.created_at,
        ).order_by(usage_events.c.created_at.asc())
    ).mappings()
    return [
        {
            "event_type": r["event_type"],
            "count": r["count"],
            "duration_ms": r["duration_ms"],
            "created_at": r["created_at"].isoformat()
            if hasattr(r["created_at"], "isoformat")
            else str(r["created_at"]),
        }
        for r in rows
    ]


def clear_usage_events(conn: Connection) -> int:
    """Unconditional delete -- no WHERE, no FK from any other table to usage_events, so this can never cascade
    into library data. Returns the number of rows removed."""
    result = conn.execute(delete(usage_events))
    return int(result.rowcount or 0)
