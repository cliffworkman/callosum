"""Wanted-list endpoints (inc 76) — the OA acquisition "track" loop.

A persistent list of papers you want an open-access copy of (library-linked or external), a manual async
**re-check** that runs the resolver cascade over the list and auto-acquires hits, and a coverage readout.
Entirely local except the OA-database lookups + the downloads the cascade points at (NOT the Gemini egress
gate). The re-check is OA-only by construction (it resolves only through the registry).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.acquisition.registry import build_default_registry
from app.backend.acquisition.wanted import run_recheck
from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import _embedding_model, _vector_store
from app.backend.persistence import wanted_repo
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write
from integrations.openalex import OpenAlexClient

router = APIRouter()


class WantedItemResponse(BaseModel):
    id: int
    paper_id: int | None = None
    doi: str | None = None  # inc 588: the wanted row's own DOI, else the linked paper's DOI (coalesced)
    pmid: str | None = None
    title: str | None = None
    note: str | None = None
    status: str
    last_checked_at: str | None = None
    last_result: str | None = None  # human string — display/tooltip only, NOT the sort/filter key
    # inc 588: the canonical STRUCTURED OA-acquisition state for triage — derived from last_reason_code, never by
    # parsing last_result. One of: unchecked | blocked | no_oa | needs_id | error | fulfilled.
    acquisition_state: str = "unchecked"
    paper_title: str | None = None
    paper_year: int | None = None
    paper_deleted: bool = False


class WantedListResponse(BaseModel):
    items: list[WantedItemResponse]


class AddWantedRequest(BaseModel):
    paper_id: int | None = None
    doi: str | None = None
    pmid: str | None = None
    title: str | None = None
    note: str | None = None


class SyncResponse(BaseModel):
    added: int


class AcquiredByColor(BaseModel):
    gold: int = 0
    green: int = 0
    bronze: int = 0


class CoverageResponse(BaseModel):
    library_total: int
    with_pdf: int
    without_pdf: int
    acquired_oa: AcquiredByColor
    wanted_open: int
    wanted_fulfilled: int


class AcquiredOaItem(BaseModel):
    wanted_id: int
    paper_id: int
    oa_color: str
    oa_version: str
    oa_source: str


class RecheckSummary(BaseModel):
    checked: int
    acquired: list[AcquiredOaItem]
    still_wanted: int
    skipped: int
    errors: int
    truncated: bool


class RecheckJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: RecheckSummary | None = None


@router.get("/wanted", response_model=WantedListResponse)
def list_wanted_items(conn: Connection = Depends(get_connection)) -> WantedListResponse:
    return WantedListResponse(items=[_to_response(row) for row in wanted_repo.list_wanted(conn)])


@router.get("/wanted/coverage", response_model=CoverageResponse)
def wanted_coverage(conn: Connection = Depends(get_connection)) -> CoverageResponse:
    return CoverageResponse(**wanted_repo.coverage_stats(conn))


@router.post("/wanted", response_model=WantedItemResponse, status_code=http_status.HTTP_201_CREATED)
def add_wanted_item(payload: AddWantedRequest, engine: Engine = Depends(get_engine)) -> WantedItemResponse:
    if payload.paper_id is None and not (payload.doi or payload.pmid or payload.title):
        raise HTTPException(status_code=422, detail="Provide a paper_id, or a doi / pmid / title")

    def _do(conn: Connection) -> WantedItemResponse:
        if payload.paper_id is not None:
            try:
                get_paper(conn, payload.paper_id)  # validate the FK target exists
            except NoResultFound:
                raise HTTPException(status_code=404, detail="Paper not found") from None
        wanted_id = wanted_repo.add_wanted(
            conn,
            paper_id=payload.paper_id,
            doi=payload.doi,
            pmid=payload.pmid,
            title=payload.title,
            note=payload.note,
        )
        row = wanted_repo.get_wanted(conn, wanted_id)
        return _to_response(row or {"id": wanted_id, "status": "wanted"})

    return run_write(engine, _do)


@router.delete("/wanted/{item_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_wanted_item(item_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        if not wanted_repo.remove_wanted(conn, item_id):
            raise HTTPException(status_code=404, detail="Wanted item not found")
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.post("/wanted/sync-library", response_model=SyncResponse)
def sync_library(engine: Engine = Depends(get_engine)) -> SyncResponse:
    def _do(conn: Connection) -> SyncResponse:
        added = wanted_repo.sync_from_library(conn)
        return SyncResponse(added=added)

    return run_write(engine, _do)


@router.post("/wanted/recheck", response_model=RecheckJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def recheck_start(background_tasks: BackgroundTasks, request: Request) -> RecheckJobResponse:
    # Async (bulk lookups + downloads are slow): returns a job id to poll. OA-only by construction.
    # inc 588: dedup to the single active re-check — a second click returns the running job instead of starting
    # a concurrent re-check that would write to the same wanted_items rows and contend on SQLite's single writer.
    job_id, created = request.app.state.wanted_jobs.create_or_get_active()
    if created:
        background_tasks.add_task(_run_recheck_job, request.app, job_id)
    job = request.app.state.wanted_jobs.get(job_id)
    return RecheckJobResponse(job_id=job_id, status=job.status if job else "pending")


@router.get("/wanted/recheck/{job_id}", response_model=RecheckJobResponse)
def recheck_status(job_id: str, request: Request) -> RecheckJobResponse:
    job = request.app.state.wanted_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Re-check job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return RecheckJobResponse(job_id=job_id, status=job.status, detail=job.detail)


# API-facing OA-acquisition states (inc 588), derived from the STRUCTURED last_reason_code that run_recheck now
# persists. `blocked` = an OA copy was found but the automatic download was blocked (candidate(s) exhausted).
_STATE_FROM_REASON = {
    "candidates_exhausted": "blocked",
    "no_candidate": "no_oa",
    "needs_id": "needs_id",
    "error": "error",
    "acquired": "fulfilled",
}


def _acquisition_state(status: str | None, reason_code: str | None, last_result: str | None) -> str:
    """The canonical OA-acquisition state for a wanted row. A fulfilled row is always ``fulfilled``; otherwise the
    STRUCTURED ``reason_code`` wins whenever present; only a pre-inc-588 row (reason_code NULL) falls back to the
    legacy prose classifier below."""
    if status == "fulfilled":
        return "fulfilled"
    if reason_code is not None:
        return _STATE_FROM_REASON.get(reason_code, "unchecked")
    return _legacy_state_from_last_result(last_result)


def _legacy_state_from_last_result(last_result: str | None) -> str:
    """COMPATIBILITY ONLY (inc 588): derive a state for a pre-inc-588 row whose ``last_reason_code`` is NULL, by
    reading the human ``last_result`` string ``run_recheck`` used to persist. This is deliberately NOT the
    canonical derivation — a row gains a structured ``last_reason_code`` the moment it is next re-checked, after
    which this is never consulted. Kept narrow + explicitly tested so it can be removed once no NULL rows remain;
    ``human_detail()`` wording is not otherwise a durable contract."""
    if not last_result:
        return "unchecked"
    if last_result == "none":
        return "no_oa"
    if last_result == "needs-id":
        return "needs_id"
    if last_result.startswith("error:"):
        return "error"
    if "could be downloaded" in last_result:  # old human_detail() phrasing for candidates_exhausted
        return "blocked"
    return "unchecked"


def _to_response(row: dict) -> WantedItemResponse:
    checked = row.get("last_checked_at")
    return WantedItemResponse(
        id=int(row["id"]),
        paper_id=row.get("paper_id"),
        doi=row.get("doi") or row.get("paper_doi"),  # inc 588: library rows carry the DOI on the paper, not the want
        pmid=row.get("pmid"),
        title=row.get("title"),
        note=row.get("note"),
        status=row.get("status") or "wanted",
        last_checked_at=str(checked) if checked else None,
        last_result=row.get("last_result"),
        acquisition_state=_acquisition_state(row.get("status"), row.get("last_reason_code"), row.get("last_result")),
        paper_title=row.get("paper_title"),
        paper_year=row.get("paper_year"),
        paper_deleted=bool(row.get("paper_deleted_at")),
    )


def _openalex_client(app: FastAPI) -> OpenAlexClient:
    injected = app.state.openalex_client
    return injected if injected is not None else OpenAlexClient()


def _run_recheck_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[RecheckJobResponse] = app.state.wanted_jobs
    jobs.mark_running(job_id)
    try:
        # app.state.acquire_registry is a test seam (a fake registry); default builds the real cascade.
        registry = app.state.acquire_registry or build_default_registry(openalex_client=_openalex_client(app))
        summary = run_recheck(
            app.state.engine,
            registry,
            crossref_client=app.state.crossref_client,
            vector_store=_vector_store(app),
            embedding_model=_embedding_model(app),
        )
        jobs.mark_done(job_id, RecheckJobResponse(job_id=job_id, status="done", summary=RecheckSummary(**summary)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
