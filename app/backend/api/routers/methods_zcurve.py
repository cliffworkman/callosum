"""z-curve (inc 470): collection-level replication/discovery-rate estimator over a USER-SELECTED set of papers.

Sibling to `methods.py`'s p-curve endpoints (kept separate: `methods.py` is at the 600-line cap — see
`app/backend/methods/zcurve.py` for the math). Ephemeral (no persistence): runs over an ad-hoc selection and
returns the result. Reuses the statcheck extractor for the exact p-values, exactly like p-curve. Collection-level
only — never per-paper, never a score for any author (the no-accusation boundary). The interpretation (evidential
value vs concern) is the user's.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel

from app.backend.api.job_store import JobStore
from app.backend.methods.statcheck import run_statcheck
from app.backend.methods.zcurve import ZcurveResult, run_zcurve
from app.backend.persistence.document_roles import ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES
from app.backend.persistence.repository import get_chunks_for_paper, list_live_paper_ids

MAX_ZCURVE_PAPERS = 1000  # bound the selection a z-curve runs over (rule #4), mirrors MAX_PCURVE_PAPERS

router = APIRouter()


class ZcurveIncludedTest(BaseModel):
    paper_id: int
    page: int | None = None
    z: float
    p: float
    raw: str


class ZcurveResultModel(BaseModel):
    n_papers: int
    k_total_extracted: int
    k_significant: int
    odr: float | None = None
    edr: float | None = None
    edr_ci: tuple[float, float] | None = None
    err: float | None = None
    err_ci: tuple[float, float] | None = None
    z0: float | None = None
    included_tests: list[ZcurveIncludedTest] = []
    low_reliability: bool = True
    note: str = ""


class ZcurveRunRequest(BaseModel):
    paper_ids: list[int]


class ZcurveRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: ZcurveResultModel | None = None


@router.post("/methods/zcurve/run", response_model=ZcurveRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def zcurve_run(payload: ZcurveRunRequest, background_tasks: BackgroundTasks, request: Request) -> ZcurveRunResponse:
    ids = list(dict.fromkeys(payload.paper_ids))[:MAX_ZCURVE_PAPERS]  # de-dup, preserve order, cap (rule #4)
    if not ids:
        raise HTTPException(status_code=422, detail="z-curve requires at least one paper_id")
    job_id = request.app.state.zcurve_jobs.create()
    background_tasks.add_task(_run_zcurve_job, request.app, job_id, ids)
    return ZcurveRunResponse(job_id=job_id, status="pending")


@router.get("/methods/zcurve/run/{job_id}", response_model=ZcurveRunResponse)
def zcurve_run_status(job_id: str, request: Request) -> ZcurveRunResponse:
    job = request.app.state.zcurve_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="z-curve job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ZcurveRunResponse(job_id=job_id, status=job.status, detail=job.detail)


def _zcurve_to_model(result: ZcurveResult) -> ZcurveResultModel:
    return ZcurveResultModel(
        n_papers=result.n_papers,
        k_total_extracted=result.k_total_extracted,
        k_significant=result.k_significant,
        odr=result.odr,
        edr=result.edr,
        edr_ci=result.edr_ci,
        err=result.err,
        err_ci=result.err_ci,
        z0=result.z0,
        included_tests=[
            ZcurveIncludedTest(paper_id=t.paper_id, page=t.page, z=t.z, p=t.p, raw=t.raw) for t in result.included_tests
        ],
        low_reliability=result.low_reliability,
        note=result.note,
    )


def _run_zcurve_job(app: FastAPI, job_id: str, paper_ids: list[int]) -> None:
    jobs: JobStore[ZcurveRunResponse] = app.state.zcurve_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.begin() as conn:
            live = set(list_live_paper_ids(conn))  # exclude trashed papers from the analysis
            per_paper = [
                (
                    pid,
                    run_statcheck(
                        get_chunks_for_paper(conn, pid, document_roles=ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES)
                    ).results,
                )
                for pid in paper_ids
                if pid in live
            ]
            result = run_zcurve(per_paper)
        jobs.mark_done(job_id, ZcurveRunResponse(job_id=job_id, status="done", result=_zcurve_to_model(result)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
