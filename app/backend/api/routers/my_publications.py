"""My Publications endpoints (inc 78) — the user's own-papers axis.

A profile (name/variants/ORCID), an async **refresh** that resolves the identity via OpenAlex and (re)writes
the pinned ``kind="my_publications"`` axis, a **decide** (confirm/reject a candidate, persisted), and a
**delete** (dismiss the card without losing the profile/decisions). LLM-free; OpenAlex is metadata egress, not
the Gemini gate.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, Engine, delete
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.job_store import JobStore
from app.backend.clustering.axis_assignments import add_manual_assignment, remove_assignment
from app.backend.clustering.my_publications import (
    _get_axis_id,
    _resolve_fetch,
    _resolve_persist,
    build_dashboard,
    import_citing_work,
    import_missing_work,
    my_publication_documents,
)
from app.backend.clustering.my_publications_domains import _decompose_compute
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.llm.egress import DataEgressDisabledError, EgressGatedResearchSummaryGenerator
from app.backend.persistence.profile_repo import (
    dismiss_work,
    get_profile,
    rename_domain,
    set_decision,
    set_my_publications_dismissed,
    set_research_domains,
    set_research_summary,
    set_starred,
    undismiss_work,
    upsert_profile,
)
from app.backend.persistence.repository import find_existing_paper_by_identity, get_paper
from app.backend.persistence.schema import axes
from app.backend.persistence.sqlite_retry import run_write
from integrations.gemini import GeminiConfig, GeminiResearchSummaryGenerator, ResearchSummaryGenerator
from integrations.openalex import OpenAlexAuthorClient

router = APIRouter()

MAX_SUMMARY_LEN = 4000  # cap the persisted research summary (mirrors the annotation-note cap)


class ProfileResponse(BaseModel):
    display_name: str | None = None
    name_variants: list[str] = []
    orcid: str | None = None
    has_author_id: bool = False
    dismissed: bool = False


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    name_variants: list[str] = []
    orcid: str | None = None


class MyPubsSummary(BaseModel):
    status: str
    name: str | None = None
    matched_by: str | None = None
    indexed_works: int | None = None
    in_library: int | None = None
    confirmed: int | None = None
    candidates: int | None = None
    axis_id: int | None = None


class RefreshJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: MyPubsSummary | None = None


class DecideRequest(BaseModel):
    paper_id: int
    decision: Literal["confirmed", "rejected"]


class DashboardMetrics(BaseModel):
    works_count: int = 0
    cited_by_count: int = 0
    h_index: int = 0
    i10_index: int = 0


class YearCount(BaseModel):
    year: int
    count: int


class YearImpact(BaseModel):
    year: int
    works_count: int = 0
    cited_by_count: int = 0


class Domain(BaseModel):
    label: str
    terms: list[str] = []
    paper_count: int = 0
    citation_count: int = 0
    paper_years: list[int] = []  # for the dashboard's client-side chart re-filter
    paper_ids: list[int] = []  # inc 118 (SP2): member paper ids, for client-side group-by-domain


class MissingWork(BaseModel):
    doi: str
    title: str | None = None
    year: int | None = None
    cited_by_count: int = 0


class OpenAlexExtra(BaseModel):  # inc 117 — extra OpenAlex facts for the dashboard's OpenAlex card
    two_year_mean_citedness: float = 0.0
    affiliation: str | None = None
    openalex_author_id: str | None = None


class PaperCitation(BaseModel):  # inc 119 (SP3): OpenAlex cited-by count + work id for one of the user's papers
    cited_by_count: int = 0
    openalex_work_id: str | None = None


class DashboardResponse(BaseModel):
    status: str  # "ok" | "no-identity" | "not-resolved"
    name: str | None = None
    as_of: str | None = None  # when the OpenAlex data was cached (honest snapshot timestamp)
    metrics: DashboardMetrics | None = None
    pubs_by_year: list[YearCount] = []
    counts_by_year: list[YearImpact] = []
    indexed_works: int | None = None
    in_library: int | None = None
    gap: int | None = None
    research_summary: str | None = None
    domains: list[Domain] = []  # inc 83: the domain decomposition, sorted by citations (impact)
    missing_works: list[MissingWork] = []  # inc 85: indexed works not in the library (the gap), by citations
    dismissed_works: list[MissingWork] = []  # inc 91: works dismissed from the queue (so a dismissal can be undone)
    openalex_extra: OpenAlexExtra | None = None  # inc 117: 2-yr mean citedness + affiliation for the OpenAlex card
    starred_count: int = 0  # inc 117 (#8): hide the "⭐ only" toggle when there are no starred pubs
    starred_ids: list[int] = []  # inc 118 (SP2 #17): starred paper ids, for starred-first sorting
    paper_citations: dict[str, PaperCitation] = {}  # inc 119 (SP3 #14): {paper_id: {cited_by_count, openalex_work_id}}


class SummaryResponse(BaseModel):
    summary: str


class SummaryUpdateRequest(BaseModel):
    summary: str | None = None


class SummaryGenerateRequest(BaseModel):
    starred_only: bool = False  # inc 84: scope the draft to the user's starred publications


class StarRequest(BaseModel):
    paper_id: int
    starred: bool = True


class WorkActionRequest(BaseModel):
    doi: str


class WorkImportResponse(BaseModel):
    status: str  # imported | exists | not-author-work | not-resolved | invalid
    paper_id: int | None = None


class CitingWorkResponse(BaseModel):  # inc 119 (SP3 #14): a paper that cites one of the user's works (a candidate)
    doi: str | None = None
    title: str | None = None
    year: int | None = None
    cited_by_count: int = 0
    authors: list[str] = []
    in_library: bool = False


class CitingResponse(BaseModel):
    works: list[CitingWorkResponse] = []
    total: int = 0
    capped: bool = False  # True when OpenAlex returned more than the cap (coverage stated, not implied)


class CitingImportRequest(BaseModel):
    doi: str
    title: str | None = None
    openalex_work_id: str | None = None


class DomainJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    domain_count: int | None = None
    result_status: str | None = None  # the decompose outcome: ok | too-few | not-resolved


@router.get("/my-publications/profile", response_model=ProfileResponse)
def get_my_publications_profile(conn: Connection = Depends(get_connection)) -> ProfileResponse:
    return _profile_response(get_profile(conn))


@router.put("/my-publications/profile", response_model=ProfileResponse)
def put_my_publications_profile(payload: ProfileUpdateRequest, engine: Engine = Depends(get_engine)) -> ProfileResponse:
    def _do(conn: Connection) -> ProfileResponse:
        profile = upsert_profile(
            conn, display_name=payload.display_name, name_variants=payload.name_variants, orcid=payload.orcid
        )
        return _profile_response(profile)

    return run_write(engine, _do)


@router.post("/my-publications/refresh", response_model=RefreshJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def refresh_my_publications(background_tasks: BackgroundTasks, request: Request) -> RefreshJobResponse:
    # Async: resolving + paginating a prolific author's works is slow. A manual refresh clears the dismissed flag.
    job_id = request.app.state.mypubs_jobs.create()
    background_tasks.add_task(_run_refresh_job, request.app, job_id)
    return RefreshJobResponse(job_id=job_id, status="pending")


@router.get("/my-publications/refresh/{job_id}", response_model=RefreshJobResponse)
def refresh_my_publications_status(job_id: str, request: Request) -> RefreshJobResponse:
    job = request.app.state.mypubs_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return RefreshJobResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.post("/my-publications/decide", status_code=http_status.HTTP_204_NO_CONTENT)
def decide_my_publications(payload: DecideRequest, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        try:
            get_paper(conn, payload.paper_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Paper not found") from None
        set_decision(conn, payload.paper_id, payload.decision)
        axis_id = _get_axis_id(conn)
        if axis_id is not None:
            if payload.decision == "confirmed":
                add_manual_assignment(conn, axis_id=int(axis_id), paper_id=payload.paper_id)  # → manual member (NULL)
            else:
                remove_assignment(conn, axis_id=int(axis_id), paper_id=payload.paper_id)  # drop rejected candidate
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.get("/my-publications/dashboard", response_model=DashboardResponse)
def get_my_publications_dashboard(request: Request, conn: Connection = Depends(get_connection)) -> DashboardResponse:
    # Layer-1 impact dashboard: a cache-only read of the resolved OpenAlex record + works + the local library.
    # Makes NO network call (gated on the profile having been resolved → openalex_author_id set).
    return DashboardResponse(**build_dashboard(conn, author_client=_author_client(request.app)))


@router.post("/my-publications/domains", response_model=DomainJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def decompose_my_publications(background_tasks: BackgroundTasks, request: Request) -> DomainJobResponse:
    # Async: clustering loads the embedding model + refreshes the works cache. Returns a job id to poll.
    job_id = request.app.state.mypubs_domain_jobs.create()
    background_tasks.add_task(_run_domains_job, request.app, job_id)
    return DomainJobResponse(job_id=job_id, status="pending")


@router.get("/my-publications/domains/{job_id}", response_model=DomainJobResponse)
def decompose_my_publications_status(job_id: str, request: Request) -> DomainJobResponse:
    job = request.app.state.mypubs_domain_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Domain job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return DomainJobResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.post("/my-publications/works/import", response_model=WorkImportResponse)
def import_my_publications_work(
    payload: WorkActionRequest, request: Request, engine: Engine = Depends(get_engine)
) -> WorkImportResponse:
    # Import an OpenAlex-attributed work missing from the library — metadata-only (Crossref DOI enrich; the
    # import hook auto-adds it to My Pubs). Guardrail: only the author's OWN indexed works. NOT the Gemini gate.
    # Idempotent (dedupes; cached lookups) → safe to re-run on a writer-lock retry.
    def _do(conn: Connection) -> WorkImportResponse:
        result = import_missing_work(
            conn,
            doi=payload.doi,
            author_client=_author_client(request.app),
            crossref_client=request.app.state.crossref_client,
        )
        status = str(result.get("status"))
        if status in ("invalid", "not-author-work"):
            raise HTTPException(status_code=422, detail="That DOI is not among your OpenAlex-indexed works.")
        if status == "not-resolved":
            raise HTTPException(status_code=409, detail="Resolve your publications first (Settings → Refresh).")
        return WorkImportResponse(status=status, paper_id=result.get("paper_id"))

    return run_write(engine, _do)


@router.post("/my-publications/works/dismiss", status_code=http_status.HTTP_204_NO_CONTENT)
def dismiss_my_publications_work(payload: WorkActionRequest, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        dismiss_work(conn, payload.doi)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.post("/my-publications/works/undismiss", status_code=http_status.HTTP_204_NO_CONTENT)
def undismiss_my_publications_work(payload: WorkActionRequest, engine: Engine = Depends(get_engine)) -> Response:
    # Un-dismiss a previously-dismissed missing work (inc 91) → it returns to the review queue. Mirror of the
    # inc-67 un-dismiss-duplicates control. Local, idempotent, non-destructive.
    def _do(conn: Connection) -> Response:
        undismiss_work(conn, payload.doi)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


class RenameDomainRequest(BaseModel):
    paper_ids: list[int]
    label: str


@router.post("/my-publications/domains/rename", status_code=http_status.HTTP_204_NO_CONTENT)
def rename_my_publications_domain(payload: RenameDomainRequest, engine: Engine = Depends(get_engine)) -> Response:
    # SP2 (inc 118, #15): rename a research domain (identified by its paper_ids set); marks it custom so a
    # Re-decompose preserves the name by paper-overlap. Local profile-JSON write; no egress.
    if not payload.label.strip():
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Label cannot be empty.")

    def _do(conn: Connection) -> Response:
        if not rename_domain(conn, payload.paper_ids, payload.label):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No domain matches those papers."
            )
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.post("/my-publications/summary/generate", response_model=SummaryResponse)
def generate_my_publications_summary(
    payload: SummaryGenerateRequest, request: Request, conn: Connection = Depends(get_connection)
) -> SummaryResponse:
    # Generate a DRAFT research summary from the user's OWN publication titles/abstracts. Library text →
    # egress-gated (off → 503, like suggest-terms). Does NOT persist; the user reviews/edits then PUTs.
    only_ids = None
    if payload.starred_only:
        only_ids = {int(x) for x in (get_profile(conn) or {}).get("starred_paper_ids") or []}
        if not only_ids:
            raise HTTPException(status_code=422, detail="Star some publications first, or turn off 'starred only'.")
    documents = my_publication_documents(conn, only_paper_ids=only_ids)
    if not documents:
        raise HTTPException(
            status_code=422,
            detail="No publications in your My Publications axis yet — set your profile and Refresh first.",
        )
    try:
        summary = _research_summary_generator(request.app).generate(documents=documents)
    except DataEgressDisabledError:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI summary needs data egress: set CALLOSUM_ALLOW_DATA_EGRESS=1 and GOOGLE_API_KEY, then restart.",
        ) from None
    except Exception as exc:  # any Gemini/network failure → surface, never 500
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY, detail=f"Summary generation failed: {exc}"
        ) from None
    return SummaryResponse(summary=summary)


@router.put("/my-publications/summary", response_model=SummaryResponse)
def put_my_publications_summary(payload: SummaryUpdateRequest, engine: Engine = Depends(get_engine)) -> SummaryResponse:
    text = (payload.summary or "").strip()
    if len(text) > MAX_SUMMARY_LEN:
        raise HTTPException(status_code=422, detail=f"Summary must be at most {MAX_SUMMARY_LEN} characters.")

    def _do(conn: Connection) -> SummaryResponse:
        set_research_summary(conn, text or None)
        return SummaryResponse(summary=(get_profile(conn) or {}).get("research_summary") or "")

    return run_write(engine, _do)


@router.post("/my-publications/star", status_code=http_status.HTTP_204_NO_CONTENT)
def star_my_publication(payload: StarRequest, engine: Engine = Depends(get_engine)) -> Response:
    # Star/unstar a paper (inc 84) — drives the "use starred only" summary scope. Local; idempotent.
    def _do(conn: Connection) -> Response:
        set_starred(conn, payload.paper_id, payload.starred)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.get("/my-publications/citing/{work_id}", response_model=CitingResponse)
def get_citing_works(work_id: str, request: Request, conn: Connection = Depends(get_connection)) -> CitingResponse:
    # inc 119 (SP3 #14): the papers OpenAlex records as citing one of the user's works — discovery candidates,
    # not authoritative/complete. On-demand + cached; metadata egress only (NOT the Gemini gate). Fail-closed.
    works, capped = _author_client(request.app).fetch_citing_works(conn, work_id)
    out = [
        CitingWorkResponse(
            doi=w.doi,
            title=w.title,
            year=w.year,
            cited_by_count=w.cited_by_count,
            authors=list(w.authors),
            in_library=(w.doi is not None and find_existing_paper_by_identity(conn, doi=w.doi) is not None),
        )
        for w in works
    ]
    return CitingResponse(works=out, total=len(out), capped=capped)


@router.post("/my-publications/citing/import", response_model=WorkImportResponse)
def import_citing_work_endpoint(
    payload: CitingImportRequest, request: Request, engine: Engine = Depends(get_engine)
) -> WorkImportResponse:
    # inc 119 (SP3 #14): import a citing paper (metadata-only, deduped) into the general library — NOT My Pubs.
    # Crossref DOI enrich only (not the Gemini gate); the PDF stays the separate OA-acquire step.
    # Idempotent (dedupes; cached lookups) → safe to re-run on a writer-lock retry.
    def _do(conn: Connection) -> WorkImportResponse:
        result = import_citing_work(
            conn,
            doi=payload.doi,
            openalex_work_id=payload.openalex_work_id,
            title=payload.title,
            crossref_client=request.app.state.crossref_client,
        )
        if str(result.get("status")) == "invalid":
            raise HTTPException(status_code=422, detail="A DOI is required.")
        return WorkImportResponse(status=str(result.get("status")), paper_id=result.get("paper_id"))

    return run_write(engine, _do)


@router.delete("/my-publications", status_code=http_status.HTTP_204_NO_CONTENT)
def dismiss_my_publications(engine: Engine = Depends(get_engine)) -> Response:
    # Dismiss the card (the deleted-don't-auto-regenerate flag) + remove the axis (CASCADE clears memberships).
    # The profile + decisions survive; a manual refresh clears the flag and rebuilds.
    def _do(conn: Connection) -> Response:
        set_my_publications_dismissed(conn, True)
        axis_id = _get_axis_id(conn)
        if axis_id is not None:
            conn.execute(delete(axes).where(axes.c.id == int(axis_id)))
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


def _profile_response(profile: dict[str, Any] | None) -> ProfileResponse:
    if not profile:
        return ProfileResponse()
    return ProfileResponse(
        display_name=profile.get("display_name"),
        name_variants=list(profile.get("name_variants") or []),
        orcid=profile.get("orcid"),
        has_author_id=bool(profile.get("openalex_author_id")),
        dismissed=bool(profile.get("my_publications_dismissed")),
    )


def _author_client(app: FastAPI) -> OpenAlexAuthorClient:
    injected = app.state.openalex_author_client
    return injected if injected is not None else OpenAlexAuthorClient()


def _research_summary_generator(app: FastAPI) -> ResearchSummaryGenerator:
    config = GeminiConfig.from_environment()
    inner = app.state.research_summary_generator
    if inner is None:
        inner = GeminiResearchSummaryGenerator(config=config)
    # Authoritative egress gate at the seam — covers the injected generator AND the default (invariant #3;
    # endpoint-aware: a loopback provider needs no egress consent).
    return EgressGatedResearchSummaryGenerator(
        inner=inner,
        data_egress_enabled=config.data_egress_enabled,
        provider=config.provider,
        wire_format=config.wire_format,
        base_url=config.base_url,
    )


def _run_refresh_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[RefreshJobResponse] = app.state.mypubs_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        client = _author_client(app)
        # inc D: the fetch phase (author resolve + works fetch) runs on a READ connection with the author client
        # caching self-committingly, so it never holds the write lock; then set_dismissed + the membership rewrite
        # are one short run_write (a fresh snapshot after the fetch — avoids a snapshot-upgrade on the persist).
        fetch_client = client.with_cache_engine(engine) if hasattr(client, "with_cache_engine") else client
        with engine.connect() as conn:
            status, author, works = _resolve_fetch(conn, author_client=fetch_client, force=True)
        if status is not None:
            summary = status
        else:

            def _persist(conn):
                set_my_publications_dismissed(conn, False)  # a manual refresh un-dismisses
                return _resolve_persist(conn, author, works)

            summary = run_write(engine, _persist)
        jobs.mark_done(job_id, RefreshJobResponse(job_id=job_id, status="done", summary=MyPubsSummary(**summary)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _run_domains_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[DomainJobResponse] = app.state.mypubs_domain_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        model = _embedding_model(app)
        client = _author_client(app)
        # inc D: local clustering + the OpenAlex works refresh (metadata egress, NOT the Gemini gate) run on a READ
        # connection with the client caching self-committingly (lock-free); then the single set_research_domains
        # write is a short run_write.
        fetch_client = client.with_cache_engine(engine) if hasattr(client, "with_cache_engine") else client
        with engine.connect() as conn:
            status, domains = _decompose_compute(conn, model=model, author_client=fetch_client)
        if status is not None:
            summary = status
        else:
            run_write(engine, lambda conn: set_research_domains(conn, domains))
            summary = {"status": "ok", "domain_count": len(domains)}
        jobs.mark_done(
            job_id,
            DomainJobResponse(
                job_id=job_id,
                status="done",
                domain_count=summary.get("domain_count"),
                result_status=summary.get("status"),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _embedding_model(app: FastAPI) -> EmbeddingModel:
    injected = app.state.embedding_model
    if injected is not None:
        return injected
    return SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL)
