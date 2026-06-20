"""Literature acquisition endpoints (legally-clear OA lane, Increment A) — an async per-paper OA fetch.

Resolve a PDF-less paper to a database-asserted open-access PDF (OpenAlex), download + validate it, and import
it into the local library as a `managed` attachment labeled with OA color/version/source. Entirely local; the
resolver seam (`acquisition/registry.py`) makes a non-OA / arbitrary-URL fetch structurally impossible. Mirrors
the duplicates async-job pattern; registered BEFORE `papers.router` so the literal `/papers/acquire-oa*` paths
win over `/papers/{paper_id}`.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.acquisition.fetch import download_oa_pdf, import_oa_pdf
from app.backend.acquisition.registry import PaperRef, build_default_registry
from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.persistence.repository import get_paper
from integrations.openalex import OpenAlexClient

router = APIRouter()


class AcquireOaStartResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


class AcquireOaResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    found: bool | None = None
    paper_id: int | None = None
    attachment_id: int | None = None
    oa_color: str | None = None
    oa_version: str | None = None
    oa_source: str | None = None
    bronze_unstable: bool | None = None
    detail: str | None = None


@router.post(
    "/papers/{paper_id}/acquire-oa", response_model=AcquireOaStartResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def acquire_oa_start(
    paper_id: int, background_tasks: BackgroundTasks, request: Request, conn: Connection = Depends(get_connection)
) -> AcquireOaStartResponse:
    # Async (external lookup + download + extract is slow): returns a job id to poll. Validate the paper first.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    job_id = request.app.state.acquire_jobs.create()
    background_tasks.add_task(_run_acquire_job, request.app, job_id, paper_id)
    return AcquireOaStartResponse(job_id=job_id, status="pending")


@router.get("/papers/acquire-oa/{job_id}", response_model=AcquireOaResponse)
def acquire_oa_status(job_id: str, request: Request) -> AcquireOaResponse:
    job = request.app.state.acquire_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Acquire job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return AcquireOaResponse(job_id=job_id, status=job.status, detail=job.detail)


def _openalex_client(app: FastAPI) -> OpenAlexClient:
    injected = app.state.openalex_client
    return injected if injected is not None else OpenAlexClient()


def _paper_ref(paper) -> PaperRef | None:
    csl = paper["csl_json"] or {}
    pmid = csl.get("PMID") or csl.get("pmid")
    try:
        return PaperRef(doi=paper["doi"], pmid=str(pmid) if pmid else None, title=paper["title"])
    except ValueError:
        return None


def _run_acquire_job(app: FastAPI, job_id: str, paper_id: int) -> None:
    jobs: JobStore[AcquireOaResponse] = app.state.acquire_jobs
    jobs.mark_running(job_id)
    try:
        engine: Engine = app.state.engine
        with engine.connect() as conn:
            ref = _paper_ref(get_paper(conn, paper_id))
        if ref is None:
            jobs.mark_done(
                job_id,
                AcquireOaResponse(
                    job_id=job_id,
                    status="done",
                    found=False,
                    paper_id=paper_id,
                    detail="paper has no DOI / PMID / title to resolve",
                ),
            )
            return
        registry = build_default_registry(openalex_client=_openalex_client(app))
        with engine.begin() as conn:  # resolve writes the external_api_cache
            location = registry.resolve(conn, ref)
        if location is None:
            jobs.mark_done(
                job_id,
                AcquireOaResponse(
                    job_id=job_id,
                    status="done",
                    found=False,
                    paper_id=paper_id,
                    detail="no authorized open-access copy found",
                ),
            )
            return
        temp_path = download_oa_pdf(location)  # network — outside any DB transaction
        with engine.begin() as conn:
            result = import_oa_pdf(
                conn, location, temp_path, paper_id=paper_id, crossref_client=app.state.crossref_client
            )
        jobs.mark_done(
            job_id,
            AcquireOaResponse(
                job_id=job_id,
                status="done",
                found=True,
                paper_id=paper_id,
                attachment_id=result["attachment_id"],
                oa_color=result["oa_color"],
                oa_version=result["oa_version"],
                oa_source=result["oa_source"],
                bronze_unstable=result["bronze_unstable"],
                detail=f"imported {result['filename']}",
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
