"""The usage-instrumentation seam (backlog #38A, inc 450). One function every instrumented call site routes
through, so the enabled-gate and the event-type allowlist are enforced exactly once, centrally, and can never be
forgotten at a call site.

`record_event()` takes the CALLER's already-open Connection -- it never opens its own. SQLite runs in WAL mode
with a 5s busy_timeout (persistence/database.py); WAL still allows only one writer, and several call sites
(dismiss_duplicates, merge_papers_endpoint, reference_integrity_review, ...) already run inside an open write
transaction. A record_event() that opened a second connection nested inside one of those would contend for the
same single-writer lock the outer transaction hasn't released yet -- a real deadlock, only resolved by the
busy_timeout expiring into "database is locked". Do not "simplify" this into owning its own transaction.
"""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend import app_settings
from app.backend.persistence import usage_repo
from app.backend.persistence.schema_usage import USAGE_EVENT_TYPES


def record_event(conn: Connection, event_type: str, *, count: int = 1) -> None:
    if event_type not in USAGE_EVENT_TYPES:
        raise ValueError(f"Unknown usage event type: {event_type}")  # a call-site bug, not user input
    if not app_settings.stored_usage_events_enabled():
        return  # the single central gate -- disabled means disabled, no new events recorded anywhere
    usage_repo.insert_usage_event(conn, event_type, count=count)
