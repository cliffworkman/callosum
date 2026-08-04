"""TOP Factor database download trigger (backlog #40).

A self-contained cluster mirroring `methods_retraction.py`'s Retraction Watch DB section exactly: a status
endpoint + an explicit refresh job downloading the Center for Open Science's TOP Factor CSV snapshot into the
local `top_factor_records` mirror. It shares the app state set up in `api/app.py` (`top_factor_db_jobs` /
`top_factor_client`); the router is mounted there beside `methods.router`.

Deliberately no auto-refresh from the PUBLISHERS job itself -- unlike Retraction Watch's best-effort
auto-refresh before a batch check, `build_profiles`'s TOP Factor lookups must always be a pure local read with
no HTTP at request time. Only this router's explicit refresh action ever downloads.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.persistence.top_factor_repo import top_factor_db_status
from integrations.top_factor.adapter import TopFactorUnavailable, download_top_factor_database

router = APIRouter()


class TopFactorDbStatus(BaseModel):
    count: int = 0
    retrieved_at: str | None = None


class TopFactorDbRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    count: int | None = None


@router.get("/methods/top-factor/database", response_model=TopFactorDbStatus)
def top_factor_database(conn: Connection = Depends(get_connection)) -> TopFactorDbStatus:
    status = top_factor_db_status(conn)
    return TopFactorDbStatus(count=status["count"], retrieved_at=status["retrieved_at"])


@router.post(
    "/methods/top-factor/database/refresh",
    response_model=TopFactorDbRefreshResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def top_factor_database_refresh(background_tasks: BackgroundTasks, request: Request) -> TopFactorDbRefreshResponse:
    job_id = request.app.state.top_factor_db_jobs.create()
    background_tasks.add_task(_run_top_factor_db_refresh_job, request.app, job_id)
    return TopFactorDbRefreshResponse(job_id=job_id, status="pending")


@router.get("/methods/top-factor/database/refresh/{job_id}", response_model=TopFactorDbRefreshResponse)
def top_factor_database_refresh_status(job_id: str, request: Request) -> TopFactorDbRefreshResponse:
    job = request.app.state.top_factor_db_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="TOP Factor database refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return TopFactorDbRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_top_factor_db_refresh_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[TopFactorDbRefreshResponse] = app.state.top_factor_db_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.begin() as conn:
            count = download_top_factor_database(app.state.top_factor_client, conn)
        jobs.mark_done(job_id, TopFactorDbRefreshResponse(job_id=job_id, status="done", count=count))
    except TopFactorUnavailable as exc:
        jobs.mark_error(job_id, str(exc))  # oversize / network -- a clear, expected failure
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
