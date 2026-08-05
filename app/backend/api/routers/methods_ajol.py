"""AJOL database download trigger (backlog #40, inc 451).

A self-contained cluster mirroring `methods_top_factor.py`'s exact shape: a status endpoint + an explicit
download job replacing the local `ajol_records` mirror from a third-party CC-BY-4.0 AJOL snapshot. It shares the
app state set up in `api/app.py` (`ajol_db_jobs` / `ajol_client`); the router is mounted there beside
`methods.router`.

`snapshot_date` is always the fixed data vintage (`integrations.ajol.adapter.AJOL_SNAPSHOT_DATE`), never the
local download timestamp -- the honesty distinction this whole feature turns on (see the adapter's module
docstring). Deliberately no auto-refresh from the PUBLISHERS job itself: `build_profiles`'s AJOL lookups must
always be a pure local read with no HTTP at request time. Only this router's explicit download action ever
fetches.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.persistence.ajol_repo import ajol_db_status
from integrations.ajol.adapter import AJOL_SNAPSHOT_DATE, AjolUnavailable, download_ajol_database

router = APIRouter()


class AjolDbStatus(BaseModel):
    count: int = 0
    retrieved_at: str | None = None
    snapshot_date: str = AJOL_SNAPSHOT_DATE


class AjolDbRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    count: int | None = None


@router.get("/methods/ajol/database", response_model=AjolDbStatus)
def ajol_database(conn: Connection = Depends(get_connection)) -> AjolDbStatus:
    status = ajol_db_status(conn)
    return AjolDbStatus(count=status["count"], retrieved_at=status["retrieved_at"])


@router.post(
    "/methods/ajol/database/refresh",
    response_model=AjolDbRefreshResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def ajol_database_refresh(background_tasks: BackgroundTasks, request: Request) -> AjolDbRefreshResponse:
    job_id = request.app.state.ajol_db_jobs.create()
    background_tasks.add_task(_run_ajol_db_refresh_job, request.app, job_id)
    return AjolDbRefreshResponse(job_id=job_id, status="pending")


@router.get("/methods/ajol/database/refresh/{job_id}", response_model=AjolDbRefreshResponse)
def ajol_database_refresh_status(job_id: str, request: Request) -> AjolDbRefreshResponse:
    job = request.app.state.ajol_db_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="AJOL database download job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return AjolDbRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_ajol_db_refresh_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[AjolDbRefreshResponse] = app.state.ajol_db_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.begin() as conn:
            count = download_ajol_database(app.state.ajol_client, conn)
        jobs.mark_done(job_id, AjolDbRefreshResponse(job_id=job_id, status="done", count=count))
    except AjolUnavailable as exc:
        jobs.mark_error(job_id, str(exc))  # oversize / network -- a clear, expected failure
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
