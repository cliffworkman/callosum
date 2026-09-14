"""Read the persisted single-paper critique snapshot (inc 601), split from critical_review.py for the 600-line
cap (the inc-226 sibling-router pattern). The WRITE lives in critical_review.py's job (persist on completion);
this is the reaccessible READ: it recomputes nothing and runs nothing — the caller enforces the inc-598
fulltext gate (chunk_count > 0) before offering Run/Refresh.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.api.routers.critical_review import (
    SNAPSHOT_SCHEMA_VERSION,
    CriticalReadJobResponse,
    ScrutinyBackboneResponse,
)
from app.backend.methods.critical_review import CRITICAL_REVIEW_VERSION
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence.statcheck_cache_repo import compute_content_fingerprint

router = APIRouter()


class CriticalReadSnapshotResponse(BaseModel):
    # The persisted latest critique for a paper (inc 601). `backbone` is None when nothing is saved OR when a
    # saved payload is version-incompatible/unparseable (`refresh_required=True`) — never a misrendered old
    # payload. `stale` = the paper's full text changed since this was computed (a passive hint ONLY; NOT
    # evidence-source/retraction detection — that's the deferred backlog issue). `running_job_id` lets the
    # caller keep a live Refresh visibly running over a stale snapshot instead of presenting the old result as
    # active (c5).
    backbone: ScrutinyBackboneResponse | None = None
    computed_at: datetime | None = None
    requested_at: str | None = None
    stale: bool = False
    refresh_required: bool = False
    running_job_id: str | None = None


def _active_critical_read_job_id(app: FastAPI, paper_id: int) -> str | None:
    """The id of a pending/running single-paper critical-read job for this paper, if any (c5). Mirrors the
    JobStore paper-match dedup key used by critical_read_start."""
    jobs: JobStore[CriticalReadJobResponse] = app.state.critical_review_jobs
    for jid, job in jobs.list_all():
        if job.status in ("pending", "running") and (job.nav or {}).get("paper_id") == paper_id:
            return jid
    return None


@router.get("/papers/{paper_id}/critical-read/snapshot", response_model=CriticalReadSnapshotResponse)
def critical_read_snapshot(
    paper_id: int, request: Request, conn: Connection = Depends(get_connection)
) -> CriticalReadSnapshotResponse:
    """The paper's latest persisted critique + a live-run indicator, so a reader-launched critique is reopenable
    without recompute and a running Refresh stays visibly running. Runs nothing."""
    running_job_id = _active_critical_read_job_id(request.app, paper_id)
    row = repo.read_backbone_snapshot(conn, paper_id)
    if row is None:
        return CriticalReadSnapshotResponse(running_job_id=running_job_id)
    # c4: an old payload from before a version bump — or one that no longer parses against the canonical schema
    # — reads as "refresh required", never a crash or a silently-misrendered result.
    if (
        str(row["critical_review_version"]) != CRITICAL_REVIEW_VERSION
        or int(row["snapshot_schema_version"]) != SNAPSHOT_SCHEMA_VERSION
    ):
        return CriticalReadSnapshotResponse(
            refresh_required=True, computed_at=row["computed_at"], running_job_id=running_job_id
        )
    try:
        backbone = ScrutinyBackboneResponse.model_validate(row["backbone_json"])
    except (ValidationError, TypeError, ValueError):
        return CriticalReadSnapshotResponse(
            refresh_required=True, computed_at=row["computed_at"], running_job_id=running_job_id
        )
    fp = row["content_fingerprint"]
    stale = fp is not None and fp != compute_content_fingerprint(conn, paper_id)
    return CriticalReadSnapshotResponse(
        backbone=backbone,
        computed_at=row["computed_at"],
        requested_at=row["requested_at"],
        stale=stale,
        running_job_id=running_job_id,
    )
