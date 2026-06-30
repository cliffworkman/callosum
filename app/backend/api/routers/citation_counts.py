"""Library-wide per-paper citation counts (inc 210, A2).

``POST /papers/citation-counts/refresh`` (async) fetches each live paper's OpenAlex ``cited_by_count`` (by DOI)
and stores it in ``paper_citation_counts``, so every library card can show the verbatim count + an "as of <date>".
A *displayed fact*, shown with its source — never folded into a composite or used to silently rank (Principles
#2/#7). The fetch reuses the already-audited, cached OpenAlex DOI lookup; egress is **public metadata**, NOT the
Gemini library-text gate. Bounded by the live-with-DOI paper count; each fetch is cached so re-runs are cheap.

The concern lives in its own router (3-segment path) so ``/papers/citation-counts/refresh`` never collides with
``/papers/{paper_id}`` — it is included before ``papers.router`` (the duplicates.py/fulltext.py precedent).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel

from app.backend.acquisition.registry import PaperRef
from app.backend.api.job_store import JobStore
from app.backend.persistence.repository import list_live_papers_with_doi, upsert_citation_count
from integrations.openalex.adapter import OpenAlexClient

router = APIRouter(tags=["citation-counts"])


class CitationRefreshSummary(BaseModel):
    total: int = 0  # live papers with a DOI (the bounded fetch set)
    updated: int = 0  # papers an OpenAlex count was found + stored for


class CitationRefreshProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None  # inc 225: rough seconds-remaining for the "~Ns" hint


class CitationRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: CitationRefreshSummary | None = None
    progress: CitationRefreshProgress | None = None


@router.post(
    "/papers/citation-counts/refresh",
    response_model=CitationRefreshResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def citation_counts_refresh(background_tasks: BackgroundTasks, request: Request) -> CitationRefreshResponse:
    job_id = request.app.state.citation_count_jobs.create()
    background_tasks.add_task(_run_citation_counts_job, request.app, job_id)
    return CitationRefreshResponse(job_id=job_id, status="pending")


@router.get("/papers/citation-counts/refresh/{job_id}", response_model=CitationRefreshResponse)
def citation_counts_status(job_id: str, request: Request) -> CitationRefreshResponse:
    job = request.app.state.citation_count_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Citation-counts job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        CitationRefreshProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return CitationRefreshResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _run_citation_counts_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[CitationRefreshResponse] = app.state.citation_count_jobs
    jobs.mark_running(job_id)
    client = app.state.openalex_client or OpenAlexClient()
    try:
        updated = 0
        with app.state.engine.begin() as conn:
            rows = list_live_papers_with_doi(conn)
            total = len(rows)
            for i, row in enumerate(rows):
                count = client.fetch_cited_by_count(conn, PaperRef(doi=row["doi"]))
                if count is not None:  # 0 is a real count and is stored; None = no work/field → leave honest "—"
                    upsert_citation_count(conn, int(row["id"]), count)
                    updated += 1
                jobs.mark_progress(job_id, i + 1, total, "Fetching citation counts")
        jobs.mark_done(
            job_id,
            CitationRefreshResponse(
                job_id=job_id, status="done", summary=CitationRefreshSummary(total=total, updated=updated)
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
