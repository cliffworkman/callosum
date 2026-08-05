"""Local usage-instrumentation API (backlog #38A, inc 450) — record/summarize/export/clear the local
usage_events log. Recording is gated by the usage_events_enabled setting (app/backend/usage.py's record_event());
reading/exporting/clearing are NEVER gated — the local log is inspectable, exportable, and deletable at any time
regardless of on/off state, per the design doc's non-negotiable constraint. Zero egress: everything here is a
local SQLite read/write, nothing calls out."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app.backend import app_settings
from app.backend.api.dependencies import get_connection, get_engine
from app.backend.persistence import usage_repo
from app.backend.persistence.schema_usage import USAGE_EVENT_TYPES
from app.backend.persistence.sqlite_retry import run_write
from app.backend.usage import record_event

router = APIRouter()


class UsageEventIn(BaseModel):
    event_type: str
    count: int = Field(default=1, ge=1, le=1000)


class UsageTypeSummary(BaseModel):
    event_type: str
    label: str
    all_time: int
    last_30_days: int


class UsageSummaryResponse(BaseModel):
    enabled: bool
    types: list[UsageTypeSummary]


class UsageClearResult(BaseModel):
    deleted: int


@router.post("/usage/events", status_code=204)
def record_usage_event_endpoint(payload: UsageEventIn, engine: Engine = Depends(get_engine)) -> Response:
    # The frontend-facing generic recorder — needed for events with no natural backend call to hook (e.g. the
    # Cite pane's "Open source region"). Validated against the closed allowlist here too (not just inside
    # record_event()), since this endpoint accepts an arbitrary string from the client.
    if payload.event_type not in USAGE_EVENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown usage event type: {payload.event_type}")

    def _do(conn: Connection) -> Response:
        record_event(conn, payload.event_type, count=payload.count)
        return Response(status_code=204)

    return run_write(engine, _do)


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def usage_summary_endpoint(conn: Connection = Depends(get_connection)) -> UsageSummaryResponse:
    return UsageSummaryResponse(
        enabled=app_settings.stored_usage_events_enabled(),
        types=[UsageTypeSummary(**row) for row in usage_repo.usage_summary(conn)],
    )


@router.get("/usage/export")
def usage_export_endpoint(conn: Connection = Depends(get_connection)) -> Response:
    # Read-only, local, no egress; the filename is a constant (no request data in the path) — mirrors
    # export_citations' Content-Disposition pattern. Never gated by the enabled toggle.
    rows = usage_repo.list_usage_events(conn)
    return Response(
        content=json.dumps({"events": rows}, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="callosum-usage-log.json"'},
    )


@router.post("/usage/clear", response_model=UsageClearResult)
def usage_clear_endpoint(engine: Engine = Depends(get_engine)) -> UsageClearResult:
    # Unconditional delete of usage_events only — no FK from any other table to it, so this can never touch
    # library data. Never gated by the enabled toggle (clearing must work even while recording is off).
    def _do(conn: Connection) -> UsageClearResult:
        deleted = usage_repo.clear_usage_events(conn)
        return UsageClearResult(deleted=deleted)

    return run_write(engine, _do)
