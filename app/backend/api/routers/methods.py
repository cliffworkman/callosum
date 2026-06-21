"""Deterministic Methods producers (inc 95–97).

`GET /papers/{paper_id}/statcheck` recomputes reported NHST p-values from the paper's extracted text — sync,
read-only, **local, no egress, no LLM**. A signal, not a verdict (see `methods/statcheck.py`).

`POST /methods/statcheck/run` (async, inc 97) batch-checks the whole live library and persists one summary row
per paper into `open_science_signals`, so the library can be **filtered** to papers with reporting
inconsistencies (`GET /papers?signal=statcheck-inconsistent`). A *filter to review*, never a rank or score.

The concern lives in its own router (like tags.py's suggested-tags) to keep papers.py lean; the per-paper path is
3 segments so it never collides with `/papers/{paper_id}`.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.methods.statcheck import run_statcheck
from app.backend.persistence.repository import get_chunks_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.signals_repo import count_statcheck_flagged, store_statcheck

router = APIRouter()
_log = logging.getLogger("callosum.methods")


class StatcheckResult(BaseModel):
    raw: str
    test_type: str
    reported_p: str
    computed_p: float
    consistency: str  # consistent | inconsistent | decision-error
    page: int | None = None


class StatcheckResponse(BaseModel):
    checked: int
    inconsistent: int
    decision_errors: int
    results: list[StatcheckResult]


@router.get("/papers/{paper_id}/statcheck", response_model=StatcheckResponse)
def paper_statcheck(paper_id: int, conn: Connection = Depends(get_connection)) -> StatcheckResponse:
    # Deterministic, local recomputation over the paper's extracted text. No chunks (a metadata-only paper) →
    # checked: 0, an honest "no extractable text" — never an error.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    report = run_statcheck(get_chunks_for_paper(conn, paper_id))
    return StatcheckResponse(
        checked=report.checked,
        inconsistent=report.inconsistent,
        decision_errors=report.decision_errors,
        results=[
            StatcheckResult(
                raw=r.raw,
                test_type=r.test_type,
                reported_p=r.reported_p,
                computed_p=r.computed_p,
                consistency=r.consistency,
                page=r.page,
            )
            for r in report.results
        ],
    )


# ── library-wide batch (inc 97): persist a per-paper summary so the library can be filtered to inconsistencies ──


class StatcheckRunSummary(BaseModel):
    total: int = 0  # live papers
    checked: int = 0  # papers with ≥1 detected APA test
    flagged: int = 0  # papers with ≥1 inconsistency or decision error


class StatcheckRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: StatcheckRunSummary | None = None


@router.post("/methods/statcheck/run", response_model=StatcheckRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def statcheck_run(background_tasks: BackgroundTasks, request: Request) -> StatcheckRunResponse:
    # Batch-check every live paper (async — bounded by paper count + the per-paper MAX_RESULTS). Persists one
    # summary row per paper into open_science_signals; re-running overwrites. Local, no egress, no LLM.
    job_id = request.app.state.statcheck_jobs.create()
    background_tasks.add_task(_run_statcheck_all_job, request.app, job_id)
    return StatcheckRunResponse(job_id=job_id, status="pending")


class StatcheckLibrarySummary(BaseModel):
    flagged: int = 0  # papers a batch run flagged (status='inconsistent') — drives the library "N flagged" chip


@router.get("/methods/statcheck/summary", response_model=StatcheckLibrarySummary)
def statcheck_library_summary(conn: Connection = Depends(get_connection)) -> StatcheckLibrarySummary:
    return StatcheckLibrarySummary(flagged=count_statcheck_flagged(conn))


@router.get("/methods/statcheck/run/{job_id}", response_model=StatcheckRunResponse)
def statcheck_run_status(job_id: str, request: Request) -> StatcheckRunResponse:
    job = request.app.state.statcheck_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Statcheck job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return StatcheckRunResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_statcheck_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[StatcheckRunResponse] = app.state.statcheck_jobs
    jobs.mark_running(job_id)
    try:
        total = checked = flagged = 0
        with app.state.engine.begin() as conn:
            for paper_id in list_live_paper_ids(conn):
                total += 1
                report = run_statcheck(get_chunks_for_paper(conn, paper_id))
                if report.checked > 0:
                    checked += 1
                if report.inconsistent + report.decision_errors > 0:
                    flagged += 1
                store_statcheck(
                    conn,
                    paper_id,
                    checked=report.checked,
                    inconsistent=report.inconsistent,
                    decision_errors=report.decision_errors,
                )
        jobs.mark_done(
            job_id,
            StatcheckRunResponse(
                job_id=job_id,
                status="done",
                summary=StatcheckRunSummary(total=total, checked=checked, flagged=flagged),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
