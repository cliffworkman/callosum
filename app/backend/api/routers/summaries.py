"""Summary generation (background job) + persisted-summary read endpoints.

The trust spine: a summary is generated, every citation is independently verified, and the
verified result is read back here with per-sentence flag status and per-citation evidence.
"""

from __future__ import annotations

from typing import Any, Literal

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
from sqlalchemy import Connection, Engine, select
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.llm.cache import CachedSummaryGenerator
from app.backend.llm.egress import EgressGatedSummaryGenerator
from app.backend.persistence.repository import delete_summary, get_summary, list_summaries
from app.backend.persistence.schema import (
    chunks,
    citation_mappings,
    evidence_quotes,
    papers,
    summary_sentences,
)
from app.backend.summarization.generators import SummaryGenerator
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from integrations.gemini import GeminiConfig, GeminiSummaryGenerator

router = APIRouter()


class SummarizeRequest(BaseModel):
    scope_type: Literal["papers", "cluster_node", "query"]
    paper_ids: list[int] | None = None
    cluster_node_id: int | None = None
    query: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)


class SummarizeStartResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


class SummaryCitationResponse(BaseModel):
    mapping_id: int
    evidence_quote_id: int
    chunk_id: int
    paper_id: int
    paper_title: str
    page_start: int | None = None
    page_end: int | None = None
    quote: str
    retrieval_confidence: float
    quote_confidence: float
    support_confidence: float
    status: str
    coordinate_precision: str | None = None
    bbox_json: Any | None = None


class SummarySentenceResponse(BaseModel):
    sentence_id: int
    ordinal: int
    text: str
    flagged: bool
    citations: list[SummaryCitationResponse]


class OverviewItemResponse(BaseModel):
    text: str
    claim_ordinals: list[int]  # ordinals of the verified sentences this Overview sentence restates


class SummarizeJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary_id: int | None = None
    summary_status: str | None = None
    sentences: list[SummarySentenceResponse] | None = None
    overview: list[OverviewItemResponse] | None = None


class SummaryListItem(BaseModel):
    summary_id: int
    scope_type: str
    scope_label: str
    status: str
    created_at: str | None = None
    sentence_count: int
    verified_sentence_count: int
    flagged_sentence_count: int


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
    job_id = request.app.state.summary_jobs.create()
    background_tasks.add_task(_run_summarize_job, request.app, job_id, payload)
    return SummarizeStartResponse(job_id=job_id, status="pending")


@router.get("/summarize/{job_id}", response_model=SummarizeJobResponse)
def summarize_status(job_id: str, request: Request) -> SummarizeJobResponse:
    job = request.app.state.summary_jobs.get(job_id)
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
def summary_delete(summary_id: int, conn: Connection = Depends(get_connection)) -> Response:
    try:
        get_summary(conn, summary_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Summary not found") from None
    delete_summary(conn, summary_id)
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


def _validate_summary_request(request: SummarizeRequest) -> None:
    if request.scope_type == "papers" and not request.paper_ids:
        raise HTTPException(status_code=400, detail="scope_type='papers' requires paper_ids")
    if request.scope_type == "cluster_node" and request.cluster_node_id is None:
        raise HTTPException(status_code=400, detail="scope_type='cluster_node' requires cluster_node_id")
    if request.scope_type == "query" and not (request.query and request.query.strip()):
        raise HTTPException(status_code=400, detail="scope_type='query' requires query")


def _summary_scope_from_request(request: SummarizeRequest) -> SummaryScope:
    return SummaryScope(
        scope_type=request.scope_type,
        paper_ids=request.paper_ids,
        cluster_node_id=request.cluster_node_id,
        query=request.query.strip() if request.query else None,
    )


def _run_summarize_job(api: FastAPI, job_id: str, request: SummarizeRequest) -> None:
    jobs: JobStore[SummarizeJobResponse] = api.state.summary_jobs
    jobs.mark_running(job_id)
    try:
        generator = _summary_generator(api)
        model = _embedding_model(api)
        store = _vector_store(api)
        support_scorer = api.state.support_scorer
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
                overview_generator=_overview_generator(api),
            )
            response = _persisted_summary_response(conn, summary_id=result.summary_id, job_id=job_id)
        jobs.mark_done(job_id, response)
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _summary_generator(api: FastAPI) -> SummaryGenerator:
    inner = api.state.summary_generator
    if inner is None:
        config = GeminiConfig.from_environment()
        if not config.data_egress_enabled:
            raise RuntimeError("summary generation requires CALLOSUM_ALLOW_DATA_EGRESS=true and a Gemini API key")
        if not config.resolved_api_key():
            raise RuntimeError(f"summary generation requires CALLOSUM_ALLOW_DATA_EGRESS=true and {config.api_key_env}")
        inner = GeminiSummaryGenerator(config=config)
    # Content-addressed cache INSIDE the egress gate (so egress-off still errors before the cache is
    # consulted), then the authoritative egress gate OUTSIDE — covers the injected provider AND the default.
    return EgressGatedSummaryGenerator(
        inner=CachedSummaryGenerator(inner=inner),
        data_egress_enabled=GeminiConfig.from_environment().data_egress_enabled,
    )


def _overview_generator(api: FastAPI):
    from app.backend.llm.egress import EgressGatedOverviewGenerator
    from integrations.gemini.overview import GeminiOverviewGenerator

    inner = api.state.overview_generator
    if inner is None:
        config = GeminiConfig.from_environment()
        if not (config.data_egress_enabled and config.resolved_api_key()):
            return None  # no overview without egress + a key; the verified claims stand alone
        inner = GeminiOverviewGenerator(config=config)
    return EgressGatedOverviewGenerator(
        inner=inner, data_egress_enabled=GeminiConfig.from_environment().data_egress_enabled
    )


def _embedding_model(api: FastAPI) -> EmbeddingModel:
    injected = api.state.embedding_model
    if injected is not None:
        return injected
    return SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL)


def _vector_store(api: FastAPI) -> VectorStore:
    injected = api.state.vector_store
    if injected is not None:
        return injected
    return SQLiteVecVectorStore()


def _persisted_summary_response(conn: Connection, *, summary_id: int, job_id: str) -> SummarizeJobResponse:
    summary = get_summary(conn, summary_id)
    sentence_rows = list(
        conn.execute(
            select(summary_sentences)
            .where(summary_sentences.c.summary_id == summary_id)
            .order_by(summary_sentences.c.ordinal, summary_sentences.c.id)
        ).mappings()
    )
    overview_raw = summary["overview_json"] if "overview_json" in summary else None
    overview = (
        [
            OverviewItemResponse(text=str(i["text"]), claim_ordinals=[int(o) for o in i["claim_ordinals"]])
            for i in overview_raw
            if isinstance(i, dict) and i.get("text") and isinstance(i.get("claim_ordinals"), list)
        ]
        if isinstance(overview_raw, list)
        else None
    )
    return SummarizeJobResponse(
        job_id=job_id,
        status="done",
        summary_id=summary_id,
        summary_status=summary["status"],
        sentences=[_summary_sentence_response(conn, sentence) for sentence in sentence_rows],
        overview=overview,
    )


def _summary_sentence_response(conn: Connection, sentence: Any) -> SummarySentenceResponse:
    citations = [_summary_citation_response(row) for row in _summary_citation_rows(conn, int(sentence["id"]))]
    return SummarySentenceResponse(
        sentence_id=int(sentence["id"]),
        ordinal=int(sentence["ordinal"]),
        text=sentence["text"],
        flagged=not citations or any(citation.status != "verified" for citation in citations),
        citations=citations,
    )


def _summary_citation_rows(conn: Connection, sentence_id: int) -> list[Any]:
    return list(
        conn.execute(
            select(
                citation_mappings.c.id.label("mapping_id"),
                citation_mappings.c.chunk_id.label("mapping_chunk_id"),
                citation_mappings.c.status,
                evidence_quotes.c.id.label("evidence_quote_id"),
                evidence_quotes.c.chunk_id.label("evidence_chunk_id"),
                evidence_quotes.c.quote_text,
                evidence_quotes.c.page_start,
                evidence_quotes.c.page_end,
                evidence_quotes.c.bbox_json,
                evidence_quotes.c.retrieval_confidence,
                evidence_quotes.c.quote_confidence,
                evidence_quotes.c.support_confidence,
                chunks.c.paper_id,
                papers.c.title.label("paper_title"),
            )
            .select_from(
                citation_mappings.join(evidence_quotes, evidence_quotes.c.citation_mapping_id == citation_mappings.c.id)
                .join(chunks, chunks.c.id == evidence_quotes.c.chunk_id)
                .join(papers, papers.c.id == chunks.c.paper_id)
            )
            .where(citation_mappings.c.summary_sentence_id == sentence_id)
            .order_by(citation_mappings.c.id)
        ).mappings()
    )


def _summary_citation_response(row: Any) -> SummaryCitationResponse:
    bbox_json = row["bbox_json"]
    chunk_id = row["evidence_chunk_id"] or row["mapping_chunk_id"]
    return SummaryCitationResponse(
        mapping_id=row["mapping_id"],
        evidence_quote_id=row["evidence_quote_id"],
        chunk_id=chunk_id,
        paper_id=row["paper_id"],
        paper_title=row["paper_title"],
        page_start=row["page_start"],
        page_end=row["page_end"],
        quote=row["quote_text"],
        retrieval_confidence=row["retrieval_confidence"],
        quote_confidence=row["quote_confidence"],
        support_confidence=row["support_confidence"],
        status=row["status"],
        coordinate_precision=_coordinate_precision_from_bbox(bbox_json),
        bbox_json=bbox_json,
    )


def _summary_list_item(row: Any) -> SummaryListItem:
    return SummaryListItem(
        summary_id=row["id"],
        scope_type=row["scope_type"],
        scope_label=_summary_scope_label(row["scope_type"], row["scope_ref_json"]),
        status=row["status"],
        created_at=str(row["created_at"]) if row["created_at"] is not None else None,
        sentence_count=int(row["sentence_count"]),
        verified_sentence_count=int(row["verified_sentence_count"]),
        flagged_sentence_count=int(row["flagged_sentence_count"]),
    )


def _summary_scope_label(scope_type: str, scope_ref: Any) -> str:
    if not isinstance(scope_ref, dict):
        return scope_type
    if scope_type == "query":
        query = scope_ref.get("query")
        return str(query) if query else "Query summary"
    if scope_type == "papers":
        paper_ids = scope_ref.get("paper_ids") or []
        if isinstance(paper_ids, list) and paper_ids:
            return f"{len(paper_ids)} paper{'s' if len(paper_ids) != 1 else ''}"
        return "Paper summary"
    if scope_type == "cluster_node":
        cluster_node_id = scope_ref.get("cluster_node_id")
        return f"Cluster node {cluster_node_id}" if cluster_node_id is not None else "Cluster summary"
    return scope_type


def _coordinate_precision_from_bbox(bbox_json: Any) -> str | None:
    if isinstance(bbox_json, list):
        for item in bbox_json:
            if isinstance(item, dict) and item.get("coordinate_precision"):
                return str(item["coordinate_precision"])
    if isinstance(bbox_json, dict) and bbox_json.get("coordinate_precision"):
        return str(bbox_json["coordinate_precision"])
    return None
