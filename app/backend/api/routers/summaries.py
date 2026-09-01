"""Summary generation (background job) + persisted-summary read endpoints.

The trust spine: a summary is generated, every citation is independently verified, and the
verified result is read back here with per-sentence flag status and per-citation evidence.
"""

from __future__ import annotations

from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi import (
    status as http_status,
)
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import (
    get_connection,
    get_engine,
    resolve_embedding_model,
    resolve_llm_config,
    resolve_support_scorer,
)
from app.backend.api.job_store import JobStore
from app.backend.api.job_timing import stage_reporter, synthesis_timing_key
from app.backend.api.routers.summaries_response import (
    IMPORTED_STATUS,
    OverviewItemResponse,
    SummarizeJobResponse,
    SummaryCitationResponse,
    SummaryListItem,
    SummarySentenceResponse,
    _persisted_summary_response,
    _summary_list_item,
)
from app.backend.api.routers.summary_overview import resolve_overview_generator
from app.backend.api.routers.summary_overview import router as overview_router
from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.llm.cache import CachedSummaryGenerator
from app.backend.llm.egress import EgressGatedSummaryGenerator
from app.backend.persistence.repository import delete_summary, get_summary, list_summaries
from app.backend.persistence.sqlite_retry import run_write
from app.backend.summarization.generators import SummaryGenerator
from app.backend.summarization.overview_lifecycle import generate_overview
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from app.backend.summarization.reverify import NotImportedError, reverify_imported_summary

router = APIRouter()
router.include_router(overview_router)

# Re-exported for backward-compatible import paths (tools/demo/*, app/backend/demo_*.py already do
# `from app.backend.api.routers.summaries import SummarizeJobResponse` etc.) — noqa: the names above are used.
__all__ = [
    "IMPORTED_STATUS",
    "OverviewItemResponse",
    "SummarizeJobResponse",
    "SummaryCitationResponse",
    "SummaryListItem",
    "SummarySentenceResponse",
]


class SummarizeRequest(BaseModel):
    scope_type: Literal["papers", "cluster_node", "query"]
    paper_ids: list[int] | None = None
    cluster_node_id: int | None = None
    query: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)
    sections: list[str] | None = Field(default=None, max_length=16)


class SummarizeStartResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


SUMMARY_SECTION_KEYS = {
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "data_availability",
    "code_availability",
    "funding",
    "conflict_of_interest",
    "ethics",
    "references",
    "supplementary_material",
}


@router.post(
    "/summarize",
    response_model=SummarizeStartResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def summarize_start(
    payload: SummarizeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> SummarizeStartResponse:
    _validate_summary_request(payload)
    nav = {"paper_ids": payload.paper_ids} if payload.paper_ids else None
    job_id = request.app.state.summary_jobs.create(nav=nav)
    background_tasks.add_task(_run_summarize_job, request.app, job_id, payload)
    return SummarizeStartResponse(job_id=job_id, status="pending")


@router.get("/summarize/{job_id}", response_model=SummarizeJobResponse)
async def summarize_status(
    job_id: str,
    request: Request,
    wait_seconds: float = Query(default=0.0, ge=0.0, le=25.0),
) -> SummarizeJobResponse:
    jobs: JobStore[SummarizeJobResponse] = request.app.state.summary_jobs
    job = await jobs.wait_for_update(job_id, wait_seconds)
    if job is None:
        raise HTTPException(status_code=404, detail="Summary job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return SummarizeJobResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/summaries", response_model=list[SummaryListItem])
def summaries_index(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_connection),
) -> list[SummaryListItem]:
    return [_summary_list_item(row) for row in list_summaries(conn, limit=limit, offset=offset)]


@router.get("/summaries/{summary_id}", response_model=SummarizeJobResponse)
def summary_detail(summary_id: int, conn: Connection = Depends(get_connection)) -> SummarizeJobResponse:
    try:
        get_summary(conn, summary_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Summary not found") from None
    return _persisted_summary_response(conn, summary_id=summary_id, job_id=f"summary:{summary_id}")


@router.delete("/summaries/{summary_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def summary_delete(summary_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        try:
            get_summary(conn, summary_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Summary not found") from None
        delete_summary(conn, summary_id)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


@router.post("/summaries/{summary_id}/reverify", response_model=SummarizeJobResponse)
def summary_reverify(
    summary_id: int, request: Request, conn: Connection = Depends(get_connection)
) -> SummarizeJobResponse:
    """B2 SP3: re-verify a RELAYED (imported) synthesis against the local library → convert it in place to native.
    Fully local — retrieval + NLI + quote-location, no egress, no LLM. 422 if the summary isn't imported."""
    try:
        get_summary(conn, summary_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Summary not found") from None
    api = request.app
    try:
        model = _embedding_model(api)
        reverify_imported_summary(
            conn,
            summary_id,
            model=model,
            vector_store=_vector_store(api),
            support_scorer=resolve_support_scorer(api, embedding_model=model),
        )
    except NotImportedError:
        raise HTTPException(status_code=422, detail="Only an imported synthesis can be re-verified.") from None
    conn.commit()
    return _persisted_summary_response(conn, summary_id=summary_id, job_id=f"summary:{summary_id}")


def _validate_summary_request(request: SummarizeRequest) -> None:
    if request.scope_type == "papers" and not request.paper_ids:
        raise HTTPException(status_code=400, detail="scope_type='papers' requires paper_ids")
    if request.scope_type == "cluster_node" and request.cluster_node_id is None:
        raise HTTPException(status_code=400, detail="scope_type='cluster_node' requires cluster_node_id")
    if request.scope_type == "query" and not (request.query and request.query.strip()):
        raise HTTPException(status_code=400, detail="scope_type='query' requires query")
    request.sections = _normalize_summary_sections(request.sections)


def _summary_scope_from_request(request: SummarizeRequest) -> SummaryScope:
    return SummaryScope(
        scope_type=request.scope_type,
        paper_ids=request.paper_ids,
        cluster_node_id=request.cluster_node_id,
        query=request.query.strip() if request.query else None,
        sections=request.sections,
    )


def _normalize_summary_sections(sections: list[str] | None) -> list[str] | None:
    if not sections:
        return None
    normalized: list[str] = []
    invalid: list[str] = []
    for item in sections:
        key = str(item or "").strip().lower().replace("-", "_")
        if not key:
            continue
        if key not in SUMMARY_SECTION_KEYS:
            invalid.append(str(item))
            continue
        if key not in normalized:
            normalized.append(key)
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown synthesis section filter: {', '.join(invalid)}")
    return normalized or None


def _run_summarize_job(api: FastAPI, job_id: str, request: SummarizeRequest) -> None:
    from app.backend.llm.managed_local import ManagedLocalTargetError

    jobs: JobStore[SummarizeJobResponse] = api.state.summary_jobs
    jobs.mark_running(job_id)
    overview_generator = None
    try:
        llm_config = resolve_llm_config(api)
        calibration_key = synthesis_timing_key(llm_config)
        generator = _summary_generator(api)
        overview_generator = resolve_overview_generator(api)
        model = _embedding_model(api)
        store = _vector_store(api)
        support_scorer = resolve_support_scorer(api, embedding_model=model)
        config = api.state.verifier_config
        engine: Engine = api.state.engine
        with engine.begin() as conn:
            result = summarize_scope(
                conn,
                scope=_summary_scope_from_request(request),
                generator=generator,
                model=model,
                vector_store=store,
                top_k=request.top_k,
                verifier_config=config,
                support_scorer=support_scorer,
                overview_requested=overview_generator is not None,
                on_progress=lambda i, n, label: jobs.mark_progress(job_id, i, n, label),
                on_stage=stage_reporter(jobs, job_id, calibration_key),
            )
        # Phase A has committed. Reread the authoritative trust spine from a fresh connection before
        # publishing completion; no generated-but-unverified or uncommitted response can reach JobStore.
        with engine.connect() as conn:
            response = _persisted_summary_response(conn, summary_id=result.summary_id, job_id=job_id)
        # inc 415: publish the finished synthesis id as a small Status-navigation hint (see job_store.Job.nav)
        # so a Status-popover click can reopen this exact synthesis, not just the Ask tab in general.
        jobs.mark_done(job_id, response, nav={"summary_id": result.summary_id})
    except ManagedLocalTargetError as exc:
        # Never leaves ManagedLocalTargetError's bare internal code (e.g. "descriptor_unreadable") as the
        # only diagnostic — Synthesize's own generic classifier (19_synthesis_failures.jsx) recognizes this
        # exact "Local AI is not ready" wording and routes the user to Settings instead of a bare Retry.
        jobs.mark_error(job_id, f"Local AI is not ready ({exc.code}). Check Settings → AI features.")
        return
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
        return

    # Phase B is supplementary. ``generate_overview`` acquires/commits running state, closes its read
    # connection before provider work, and isolates every failure from the already-durable primary result.
    if response.overview_status == "pending" and overview_generator is not None:
        generate_overview(
            engine,
            summary_id=result.summary_id,
            generator=overview_generator,
            jobs=api.state.overview_jobs,
        )
        # Preserve direct status-read compatibility after Phase B without changing the first
        # completion boundary: observers were already woken with the committed primary above.
        with engine.connect() as conn:
            refreshed = _persisted_summary_response(conn, summary_id=result.summary_id, job_id=job_id)
        jobs.mark_done(job_id, refreshed, nav={"summary_id": result.summary_id})


def _summary_generator(api: FastAPI) -> SummaryGenerator:
    from app.backend.llm.providers import requires_egress

    config = resolve_llm_config(api)
    inner = api.state.summary_generator
    if inner is None:
        # A loopback provider (builtin `local` or a localhost custom) needs neither egress consent nor a key.
        if requires_egress(config):
            if not config.data_egress_enabled:
                raise RuntimeError("summary generation requires data-egress consent (Settings → AI features)")
            if not config.resolved_api_key():
                raise RuntimeError("summary generation requires an API key (Settings → AI features)")
        from app.backend.llm.managed_local import managed_summary_generator

        inner = managed_summary_generator(config)
    # Content-addressed cache INSIDE the egress gate (so egress-off still errors before the cache is
    # consulted), then the authoritative egress gate OUTSIDE — covers the injected provider AND the default.
    return EgressGatedSummaryGenerator(
        inner=CachedSummaryGenerator(inner=inner),
        data_egress_enabled=config.data_egress_enabled,
        provider=config.provider,
        wire_format=config.wire_format,
        base_url=config.base_url,
    )


def _embedding_model(api: FastAPI) -> EmbeddingModel:
    return resolve_embedding_model(api)


def _vector_store(api: FastAPI) -> VectorStore:
    injected = api.state.vector_store
    if injected is not None:
        return injected
    return SQLiteVecVectorStore()
