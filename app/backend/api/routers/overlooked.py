"""Overlooked-work lens (backlog #37) — per-axis discovery of works highly relevant to one of the user's axes but
under-cited for their vintage ("the Matthew effect, inverted"). A sibling of the gap-finder (`/gaps`), but keyed on
an axis and following the gap between **relevance and attention** rather than citation links.

Distinct from the citation-equity per-paper "overlooked-work remediation" (#25 SP2,
`/methods/citation-equity/overlooked`) — that asks which relevant works a single paper's reference list omitted;
this is a **library-level discovery lens**.

Honesty posture (rule #9): signal-not-verdict, with two SEPARABLE visible inputs (axis `relevance` + citations vs.
a same-vintage percentile) that are **never fused** into a composite score; **identity-agnostic** (no author/identity
field anywhere); **pull-not-push** (opened per axis, on demand); **augment-never-filter** (Add/Dismiss are the user's,
nothing is auto-added). OpenAlex fetches are public metadata (bounded, cached, fail-closed) — NOT the Gemini gate;
candidate abstracts are embedded **on-device** (never transmitted). Add/Dismiss reuse the gap flow (`/gaps/add`,
`/gaps/dismiss`). Cached per `axis_id`; GET reads the cache (filtering dismissed / now-in-library at read time),
Refresh recomputes + replaces it, running its fetch phase **fetch-outside-lock** (inc D). Credit: the Matthew effect
in science (Merton, 1968).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import _embedding_model, _vector_store
from app.backend.methods.overlooked import compute_overlooked
from app.backend.persistence.overlooked_repo import read_overlooked_candidates, replace_overlooked_candidates
from app.backend.persistence.profile_repo import dismissed_gaps
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.sqlite_retry import run_write
from integrations.openalex.sources import OpenAlexSourcesClient

router = APIRouter()


class OverlookedCandidateResponse(BaseModel):
    openalex_work_id: str
    doi: str | None = None
    title: str | None = None
    year: int | None = None
    cited_by_count: int
    relevance: float  # axis cosine similarity (local, checkable) — one of two SEPARATE inputs
    year_percentile: float | None = None  # citations vs. same-vintage peers — the other; NULL = too few to rank


class OverlookedListResponse(BaseModel):
    candidates: list[OverlookedCandidateResponse] = []
    computed_at: str | None = None  # the snapshot timestamp (None = not computed yet)


@router.get("/overlooked", response_model=OverlookedListResponse)
def overlooked_list(
    request: Request,
    axis_id: int = Query(...),
    conn: Connection = Depends(get_connection),
) -> OverlookedListResponse:
    rows, computed_at = read_overlooked_candidates(conn, axis_id)
    dismissed = dismissed_gaps(conn)
    out: list[OverlookedCandidateResponse] = []
    for row in rows:  # filter at read time so Add/Dismiss take effect without a recompute
        if row["openalex_work_id"] in dismissed or (row["doi"] and row["doi"] in dismissed):
            continue
        if row["doi"] and find_existing_paper_by_identity(conn, doi=row["doi"]) is not None:
            continue
        out.append(
            OverlookedCandidateResponse(
                openalex_work_id=row["openalex_work_id"],
                doi=row["doi"],
                title=row["title"],
                year=row["year"],
                cited_by_count=row["cited_by_count"],
                relevance=row["relevance"],
                year_percentile=row["year_percentile"],
            )
        )
    return OverlookedListResponse(candidates=out, computed_at=computed_at)


class OverlookedRefreshRequest(BaseModel):
    axis_id: int


class OverlookedRefreshResult(BaseModel):
    count: int = 0  # candidates cached


class OverlookedRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: OverlookedRefreshResult | None = None


@router.post("/overlooked/refresh", response_model=OverlookedRefreshResponse, status_code=http_status.HTTP_202_ACCEPTED)
def overlooked_refresh(
    payload: OverlookedRefreshRequest, background_tasks: BackgroundTasks, request: Request
) -> OverlookedRefreshResponse:
    job_id = request.app.state.overlooked_lens_jobs.create()
    background_tasks.add_task(_run_overlooked_lens_refresh, request.app, job_id, payload.axis_id)
    return OverlookedRefreshResponse(job_id=job_id, status="pending")


@router.get("/overlooked/refresh/{job_id}", response_model=OverlookedRefreshResponse)
def overlooked_refresh_status(job_id: str, request: Request) -> OverlookedRefreshResponse:
    job = request.app.state.overlooked_lens_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Overlooked-work job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return OverlookedRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_overlooked_lens_refresh(app: FastAPI, job_id: str, axis_id: int) -> None:
    jobs: JobStore[OverlookedRefreshResponse] = app.state.overlooked_lens_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        client = app.state.openalex_sources_client or OpenAlexSourcesClient()
        # inc D: the fetch phase (topic + works — external OpenAlex fetches; the local relevance/percentile writes
        # nothing but the harmless axis-embedding cache) runs on a READ connection with the client caching
        # self-committingly, so it never holds the write lock across network I/O; then the atomic replace is a short
        # run_write. (A fake test client has no `with_cache_engine` → used as-is.)
        fetch_client = client.with_cache_engine(engine) if hasattr(client, "with_cache_engine") else client
        model = _embedding_model(app)
        vector_store = _vector_store(app)
        computed_at = datetime.now(timezone.utc).isoformat()
        with engine.connect() as conn:
            candidates = compute_overlooked(
                conn,
                axis_id=axis_id,
                sources_client=fetch_client,
                model=model,
                vector_store=vector_store,
            )
        run_write(
            engine, lambda conn: replace_overlooked_candidates(conn, axis_id, candidates, computed_at=computed_at)
        )
        jobs.mark_done(
            job_id,
            OverlookedRefreshResponse(
                job_id=job_id, status="done", result=OverlookedRefreshResult(count=len(candidates))
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
