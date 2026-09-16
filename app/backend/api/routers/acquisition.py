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
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend import app_settings
from app.backend.acquisition.acquire import acquire_first_working
from app.backend.acquisition.fetch import download_oa_pdf, import_oa_pdf
from app.backend.acquisition.openurl import build_openurl
from app.backend.acquisition.registry import PaperRef, build_default_registry
from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import _embedding_model, _vector_store
from app.backend.embeddings.admission import ensure_paper_indexed
from app.backend.metadata.doi_add import add_paper_by_doi
from app.backend.methods.retraction import auto_check_retractions
from app.backend.persistence.repository import get_paper
from integrations.crossref import CrossrefClient
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
    # Machine-readable outcome (backlog #59): "acquired" | "no_candidate" | "candidates_exhausted".
    # A truly unexpected failure is the 4th state and surfaces as status="error" (not a reason_code).
    reason_code: str | None = None


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
    # Dedup to any in-flight acquisition of THIS paper (inc 587): two concurrent acquire jobs for one
    # paper both import the downloaded PDF and collide on SQLite's single writer ("database is locked").
    # The real trigger: the by-DOI import's auto-OA job is still running when the user clicks "Acquire OA
    # copy" in Details. A finished job never matches, so a retry after a miss still starts a fresh attempt.
    job_id, created = request.app.state.acquire_jobs.create_or_get_active_matching(
        {"paper_id": paper_id}, ("paper_id",)
    )
    if created:
        background_tasks.add_task(_run_acquire_job, request.app, job_id, paper_id)
    job = request.app.state.acquire_jobs.get(job_id)
    return AcquireOaStartResponse(job_id=job_id, status=job.status if job else "pending")


class AddByDoiRequest(BaseModel):
    doi: str = Field(min_length=1, max_length=255)
    # Whether to also start the ordinary OA full-text acquisition on a newly-created paper. The backend
    # owns this orchestration (backlog #58) so the "add → OA fetch" promise never depends on the browser
    # issuing a second request. A programmatic caller can opt out.
    acquire_oa: bool = True


class AddByDoiResponse(BaseModel):
    # Metadata-import state and OA-acquisition state are DELIBERATELY separate (backlog #58): a failed PDF
    # fetch must never look like a failed DOI import. ``status`` is the metadata result; ``acquire_job_id``
    # (when set) is a SEPARATE OA-fetch job the caller polls via GET /papers/acquire-oa/{job_id}.
    status: Literal["created", "existing"]
    paper_id: int
    doi: str | None = None
    title: str | None = None
    acquire_job_id: str | None = None


@router.post("/papers/by-doi", response_model=AddByDoiResponse, status_code=http_status.HTTP_201_CREATED)
def add_paper_by_doi_endpoint(
    body: AddByDoiRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> AddByDoiResponse:
    """Add a paper by DOI (backlog #58): resolve → dedup → create the metadata record via the shared
    ``add_paper_by_doi`` primitive, then (opt-in, backend-orchestrated) start OA full-text acquisition on a
    newly-created paper. An invalid or unresolvable DOI fails honestly (422) and creates nothing."""
    # Fall back to a default CrossrefClient when app.state has none (it is only set when injected — e.g. in
    # tests); mirrors paper_enrich._crossref. Without this the running app's app.state.crossref_client is None
    # and every DOI would "fail to resolve" even though Crossref is reachable (caught by #58's live smoke test).
    crossref_client = request.app.state.crossref_client or CrossrefClient()
    result = add_paper_by_doi(conn, body.doi, crossref_client=crossref_client, imported_source="doi-import")
    if result.status == "invalid":
        raise HTTPException(status_code=422, detail="That does not look like a valid DOI.")
    if result.status == "unresolved":
        raise HTTPException(
            status_code=422,
            detail=f"Could not resolve '{result.doi}' to a record. Nothing was added — check the DOI and try again.",
        )
    conn.commit()  # persist the created/looked-up paper before returning and before the OA job's own connection runs
    # Post-admission indexing invariant (#61): a paper is indexed regardless of which front end admitted it.
    # After the commit, in its own transaction, and never fatal to an otherwise-successful import.
    if result.status == "created":
        ensure_paper_indexed(
            request.app.state.engine,
            result.paper_id,
            model=_embedding_model(request.app),
            vector_store=_vector_store(request.app),
        )
    acquire_job_id: str | None = None
    if result.status == "created" and body.acquire_oa:
        # Same per-paper dedup as acquire_oa_start (inc 587) — defensive/consistent (a brand-new paper has
        # no in-flight job yet, but this keeps a single acquisition-per-paper invariant at every entry point).
        acquire_job_id, created = request.app.state.acquire_jobs.create_or_get_active_matching(
            {"paper_id": result.paper_id}, ("paper_id",)
        )
        if created:
            background_tasks.add_task(_run_acquire_job, request.app, acquire_job_id, result.paper_id)
    return AddByDoiResponse(
        status=result.status,
        paper_id=result.paper_id,
        doi=result.doi,
        title=result.title,
        acquire_job_id=acquire_job_id,
    )


@router.get("/papers/acquire-oa/{job_id}", response_model=AcquireOaResponse)
def acquire_oa_status(job_id: str, request: Request) -> AcquireOaResponse:
    job = request.app.state.acquire_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Acquire job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return AcquireOaResponse(job_id=job_id, status=job.status, detail=job.detail)


class LibraryLinkResponse(BaseModel):
    configured: bool  # is an institutional OpenURL resolver base set in Settings? (opt-in; default off)
    url: str | None = None  # the OpenURL for the USER'S browser to open — callosum never fetches it
    detail: str | None = None


@router.get("/papers/{paper_id}/library-link", response_model=LibraryLinkResponse)
def paper_library_link(paper_id: int, conn: Connection = Depends(get_connection)) -> LibraryLinkResponse:
    """Build the institution link-resolver (OpenURL) URL for a paper — the free-and-legal hand-off for when no OA
    copy is found. Returns the URL for the *user's own browser* to open (routing through their library's official
    resolver + their own SSO); callosum **never fetches it** (no SSRF, no credentials, no scraping). Dormant until
    the user sets an OpenURL resolver base in Settings."""
    try:
        paper = get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    base = app_settings.stored_openurl_resolver_base()
    if not base:
        return LibraryLinkResponse(configured=False)
    url = build_openurl(base, paper["csl_json"] or {}, doi=paper["doi"])
    if url is None:
        return LibraryLinkResponse(configured=True, detail="This record has no DOI or title to resolve.")
    return LibraryLinkResponse(configured=True, url=url)


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
        # Candidate cascade (backlog #59): try each authorized-OA candidate in resolver-priority order
        # until one downloads; a 403/404 on the first no longer terminates the attempt. Resolve + download
        # (each outside/inside its own txn) are owned by acquire_first_working. `download_oa_pdf` is passed
        # explicitly (not left to the cascade's default) so this module's name stays the injection seam tests
        # monkeypatch.
        outcome = acquire_first_working(engine, registry, ref, download=download_oa_pdf)
        if not outcome.acquired:
            # Two honest, distinct non-acquired states — never an opaque terminal error (which is reserved
            # for a truly unexpected exception below): no OA candidate at all vs. candidate(s) found but
            # none downloadable (403/404/stale). Both are found=False with a machine-readable reason_code.
            jobs.mark_done(
                job_id,
                AcquireOaResponse(
                    job_id=job_id,
                    status="done",
                    found=False,
                    paper_id=paper_id,
                    detail=outcome.human_detail(),
                    reason_code=outcome.reason_code,
                ),
            )
            return
        location, temp_path = outcome.location, outcome.temp_path
        with engine.begin() as conn:
            result = import_oa_pdf(
                conn,
                location,
                temp_path,
                paper_id=paper_id,
                crossref_client=app.state.crossref_client,
                vector_store=_vector_store(app),
                embedding_model=_embedding_model(app),
            )
            # inc 224: a freshly OA-acquired paper was just Crossref-enriched (DOI populated) — auto-check
            # retraction now (the inc-134 on-import hook; best-effort, swallows per-paper errors → can't break
            # the acquire). The retraction checkers are the same already-audited set on app.state.
            auto_check_retractions(conn, [paper_id], checkers=app.state.retraction_checkers)
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
                reason_code="acquired",
            ),
        )
    except Exception as exc:
        # The 4th, deliberately-opaque state: a truly unexpected failure (not an OaFetchError, which the
        # cascade already handled as candidate fallback) — never silently reclassified as "no OA copy".
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
