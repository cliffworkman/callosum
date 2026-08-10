"""Superuser-only diagnostics (inc 468) — the first real application of `require_superuser`
(inc 195's deferred superuser capabilities). Local operational state not shown anywhere else in the
app: library stats, exposure/config state, and app/version identity. Plain counts and config booleans
only — no paper titles/content, no secrets, no tokens; never a composite score (Principles #7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend import app_settings
from app.backend.api.dependencies import get_connection, require_superuser
from app.backend.api.routers.health import _database_status, reported_app_version
from app.backend.persistence.diagnostics_repo import library_stats

router = APIRouter()


class DiagnosticsResponse(BaseModel):
    paper_count: int
    chunk_count: int
    embedding_count: int
    remote_access_enabled: bool
    sync_enabled: bool
    sync_server_configured: bool
    app_version: str | None
    db_reachable: bool
    db_migrated: bool


@router.get("/diagnostics", response_model=DiagnosticsResponse, dependencies=[Depends(require_superuser)])
def diagnostics(conn: Connection = Depends(get_connection)) -> DiagnosticsResponse:
    stats = library_stats(conn)
    reachable, at_head, _current, _head = _database_status(conn)
    sync = app_settings.stored_sync_settings()
    return DiagnosticsResponse(
        **stats,
        remote_access_enabled=app_settings.stored_remote_access(),
        sync_enabled=sync["enabled"],
        sync_server_configured=bool(sync["server_url"]),
        app_version=reported_app_version(),
        db_reachable=reachable,
        db_migrated=at_head,
    )
