"""Literature gap-finder (inc 135).

Surfaces external works that >= N of the user's library papers CITE but the library doesn't have ("cited by N of
your papers") — discovery **candidates** the user Adds or Dismisses. The count is a fact about the user's own
library's citing, never a quality/importance rank; nothing is auto-added. The OpenAlex `referenced_works` fetches
are public metadata (bounded, cached, fail-closed) — NOT the Gemini gate. Add is metadata-only into the general
library (the PDF stays the separate OA-acquire lane → no paywall circumvention).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.clustering.gapfinder import compute_gaps
from app.backend.clustering.my_publications import import_citing_work
from app.backend.persistence.profile_repo import dismiss_gap, dismissed_gaps
from integrations.openalex.adapter import OpenAlexClient

router = APIRouter()

GAP_MIN_CITATIONS = 3  # a work cited by >= this many of your papers is a candidate
GAP_MAX_CANDIDATES = 50


class GapCandidateResponse(BaseModel):
    openalex_work_id: str
    doi: str | None = None
    title: str | None = None
    authors: list[str] = []
    year: int | None = None
    cited_by_in_library: int


class GapsResult(BaseModel):
    candidates: list[GapCandidateResponse] = []
    checked: int = 0  # papers with a DOI that were scanned
    total: int = 0  # live papers
    note: str = ""  # the coverage caveat


class GapRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: GapsResult | None = None


@router.post("/gaps/find", response_model=GapRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def gaps_find(background_tasks: BackgroundTasks, request: Request) -> GapRunResponse:
    job_id = request.app.state.gap_jobs.create()
    background_tasks.add_task(_run_gap_job, request.app, job_id)
    return GapRunResponse(job_id=job_id, status="pending")


@router.get("/gaps/find/{job_id}", response_model=GapRunResponse)
def gaps_find_status(job_id: str, request: Request) -> GapRunResponse:
    job = request.app.state.gap_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Gap-finder job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return GapRunResponse(job_id=job_id, status=job.status, detail=job.detail)


class GapAddRequest(BaseModel):
    doi: str
    openalex_work_id: str | None = None
    title: str | None = None


class GapAddResponse(BaseModel):
    status: str  # imported | exists | invalid
    paper_id: int | None = None


@router.post("/gaps/add", response_model=GapAddResponse)
def gaps_add(payload: GapAddRequest, request: Request, conn: Connection = Depends(get_connection)) -> GapAddResponse:
    # Metadata-only + deduped into the GENERAL library (reuses the inc-119 citing-import flow). Idempotent.
    result = import_citing_work(
        conn,
        doi=payload.doi,
        openalex_work_id=payload.openalex_work_id,
        title=payload.title,
        crossref_client=request.app.state.crossref_client,
        imported_source="gap-import",
    )
    if result.get("status") == "invalid":
        raise HTTPException(status_code=422, detail="A DOI is required to add a gap candidate.")
    conn.commit()
    return GapAddResponse(status=str(result.get("status")), paper_id=result.get("paper_id"))


class GapDismissRequest(BaseModel):
    openalex_work_id: str | None = None
    doi: str | None = None


@router.post("/gaps/dismiss", status_code=http_status.HTTP_204_NO_CONTENT)
def gaps_dismiss(payload: GapDismissRequest, conn: Connection = Depends(get_connection)) -> Response:
    for key in (payload.openalex_work_id, payload.doi):
        if key:
            dismiss_gap(conn, key)  # dismiss both the OA id + the DOI so it can't resurface either way
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


def _run_gap_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[GapRunResponse] = app.state.gap_jobs
    jobs.mark_running(job_id)
    try:
        client = app.state.openalex_client or OpenAlexClient()
        with app.state.engine.begin() as conn:
            candidates, coverage = compute_gaps(
                conn,
                openalex_client=client,
                dismissed=dismissed_gaps(conn),
                min_citations=GAP_MIN_CITATIONS,
                max_candidates=GAP_MAX_CANDIDATES,
            )
        result = GapsResult(
            candidates=[GapCandidateResponse(**asdict(c)) for c in candidates],
            checked=coverage["checked"],
            total=coverage["total"],
            note=coverage["note"],
        )
        jobs.mark_done(job_id, GapRunResponse(job_id=job_id, status="done", result=result))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
