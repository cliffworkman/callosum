"""Literature gap-finder (inc 135 backward; inc 137 forward + axis-scoped + persistent cache).

Surfaces external works related to >= N of the user's library papers that the library doesn't have — discovery
**candidates** the user Adds or Dismisses:

- **backward**: works that >= N of your papers CITE ("cited by N of your papers").
- **forward**: works that CITE >= N of your papers ("cites N of your papers").

`axis_id` restricts the scan to that axis's members. The count is a fact about the user's own library, never a
quality/importance rank; nothing is auto-added. OpenAlex fetches are public metadata (bounded, cached,
fail-closed) — NOT the Gemini gate. Add is metadata-only into the general library (the PDF stays the separate
OA-acquire lane → no paywall circumvention). Results are cached per (direction, axis_id); GET reads the cache (and
filters dismissed / now-in-library at read time), Refresh recomputes + replaces it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, Engine

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.job_store import JobStore
from app.backend.clustering.gapfinder import compute_gaps
from app.backend.clustering.my_publications import import_citing_work
from app.backend.persistence.gap_repo import read_gap_candidates, replace_gap_candidates
from app.backend.persistence.profile_repo import dismiss_gap, dismissed_gaps
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.sqlite_retry import run_write
from integrations.openalex.adapter import OpenAlexClient

router = APIRouter()

GAP_MIN_CITATIONS = 3  # a work related to >= this many of your papers is a candidate
GAP_MAX_CANDIDATES = 50
Direction = Literal["backward", "forward"]


class GapCandidateResponse(BaseModel):
    openalex_work_id: str
    doi: str | None = None
    title: str | None = None
    authors: list[str] = []
    year: int | None = None
    cited_by_in_library: int


class GapsListResponse(BaseModel):
    candidates: list[GapCandidateResponse] = []
    computed_at: str | None = None  # the snapshot timestamp (None = not computed yet)


@router.get("/gaps", response_model=GapsListResponse)
def gaps_list(
    request: Request,
    direction: Direction = "backward",
    axis_id: int | None = Query(default=None),
    conn: Connection = Depends(get_connection),
) -> GapsListResponse:
    rows, computed_at = read_gap_candidates(conn, direction, axis_id)
    dismissed = dismissed_gaps(conn)
    out: list[GapCandidateResponse] = []
    for row in rows:  # filter at read time so Add/Dismiss take effect without a recompute
        if row["openalex_work_id"] in dismissed or (row["doi"] and row["doi"] in dismissed):
            continue
        if row["doi"] and find_existing_paper_by_identity(conn, doi=row["doi"]) is not None:
            continue
        out.append(
            GapCandidateResponse(
                openalex_work_id=row["openalex_work_id"],
                doi=row["doi"],
                title=row["title"],
                authors=row["authors"] or [],
                year=row["year"],
                cited_by_in_library=row["cited_by_in_library"],
            )
        )
    return GapsListResponse(candidates=out, computed_at=computed_at)


class GapRefreshRequest(BaseModel):
    direction: Direction = "backward"
    axis_id: int | None = None


class GapRefreshResult(BaseModel):
    checked: int = 0  # papers with a DOI that were scanned
    total: int = 0  # live papers in scope
    note: str = ""  # the coverage caveat
    count: int = 0  # candidates cached


class GapRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: GapRefreshResult | None = None


@router.post("/gaps/refresh", response_model=GapRefreshResponse, status_code=http_status.HTTP_202_ACCEPTED)
def gaps_refresh(payload: GapRefreshRequest, background_tasks: BackgroundTasks, request: Request) -> GapRefreshResponse:
    job_id = request.app.state.gap_jobs.create()
    background_tasks.add_task(_run_gap_refresh, request.app, job_id, payload.direction, payload.axis_id)
    return GapRefreshResponse(job_id=job_id, status="pending")


@router.get("/gaps/refresh/{job_id}", response_model=GapRefreshResponse)
def gaps_refresh_status(job_id: str, request: Request) -> GapRefreshResponse:
    job = request.app.state.gap_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Gap-finder job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return GapRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


class GapAddRequest(BaseModel):
    doi: str
    openalex_work_id: str | None = None
    title: str | None = None


class GapAddResponse(BaseModel):
    status: str  # imported | exists | invalid
    paper_id: int | None = None


@router.post("/gaps/add", response_model=GapAddResponse)
def gaps_add(payload: GapAddRequest, request: Request, engine: Engine = Depends(get_engine)) -> GapAddResponse:
    # Metadata-only + deduped into the GENERAL library (reuses the inc-119 citing-import flow). Idempotent — safe to
    # re-run on a writer-lock retry: it dedupes by identity and the Crossref lookup is cached (no double egress).
    def _do(conn: Connection) -> GapAddResponse:
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
        return GapAddResponse(status=str(result.get("status")), paper_id=result.get("paper_id"))

    return run_write(engine, _do)


class GapDismissRequest(BaseModel):
    openalex_work_id: str | None = None
    doi: str | None = None


@router.post("/gaps/dismiss", status_code=http_status.HTTP_204_NO_CONTENT)
def gaps_dismiss(payload: GapDismissRequest, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        for key in (payload.openalex_work_id, payload.doi):
            if key:
                dismiss_gap(conn, key)  # dismiss both the OA id + the DOI so it can't resurface either way
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


def _run_gap_refresh(app: FastAPI, job_id: str, direction: str, axis_id: int | None) -> None:
    jobs: JobStore[GapRefreshResponse] = app.state.gap_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        client = app.state.openalex_client or OpenAlexClient()
        # inc D: the fetch phase (compute_gaps — external OpenAlex fetches; no conn writes but the response cache)
        # runs on a READ connection with the client caching self-committingly, so it never holds the write lock;
        # then the single atomic replace is a short run_write. (A fake test client caches nothing → used as-is.)
        fetch_client = client.with_cache_engine(engine) if hasattr(client, "with_cache_engine") else client
        computed_at = datetime.now(timezone.utc).isoformat()
        with engine.connect() as conn:
            candidates, coverage = compute_gaps(
                conn,
                openalex_client=fetch_client,
                dismissed=dismissed_gaps(conn),
                direction=direction,
                axis_id=axis_id,
                min_citations=GAP_MIN_CITATIONS,
                max_candidates=GAP_MAX_CANDIDATES,
            )
        run_write(
            engine, lambda conn: replace_gap_candidates(conn, direction, axis_id, candidates, computed_at=computed_at)
        )
        result = GapRefreshResult(
            checked=coverage["checked"], total=coverage["total"], note=coverage["note"], count=len(candidates)
        )
        jobs.mark_done(job_id, GapRefreshResponse(job_id=job_id, status="done", result=result))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
