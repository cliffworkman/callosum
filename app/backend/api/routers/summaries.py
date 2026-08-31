"""Summary generation (background job) + persisted-summary read endpoints.

The trust spine: a summary is generated, every citation is independently verified, and the
verified result is read back here with per-sentence flag status and per-citation evidence.
"""

from __future__ import annotations

from datetime import datetime
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

from app.backend.api.dependencies import (
    get_connection,
    get_engine,
    resolve_embedding_model,
    resolve_llm_config,
    resolve_support_scorer,
)
from app.backend.api.job_store import JobStore
from app.backend.api.job_timing import stage_reporter, synthesis_timing_key
from app.backend.api.routers.paper_files import _is_pdf_attachment
from app.backend.api.routers.summary_overview import resolve_overview_generator
from app.backend.api.routers.summary_overview import router as overview_router
from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.llm.cache import CachedSummaryGenerator
from app.backend.llm.egress import EgressGatedSummaryGenerator
from app.backend.persistence.repository import delete_summary, get_summary, list_summaries
from app.backend.persistence.schema import (
    attachments,
    chunks,
    citation_mappings,
    evidence_quotes,
    papers,
    summary_sentences,
)
from app.backend.persistence.sqlite_retry import run_write
from app.backend.summarization.generators import SummaryGenerator
from app.backend.summarization.overview_lifecycle import (
    OverviewStatus,
    generate_overview,
    overview_status_for_row,
)
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from app.backend.summarization.reverify import NotImportedError, reverify_imported_summary

router = APIRouter()
router.include_router(overview_router)


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


class SummaryCitationResponse(BaseModel):
    mapping_id: int | None = None  # None for a relayed (imported) citation — no local mapping/evidence/chunk id
    evidence_quote_id: int | None = None
    chunk_id: int | None = None
    paper_id: int | None = None  # None = the source paper isn't in the recipient's library (evidence still shown)
    paper_title: str
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    quote: str
    retrieval_confidence: float
    quote_confidence: float
    support_confidence: float
    status: str
    coordinate_precision: str | None = None
    bbox_json: Any | None = None
    attachment_id: int | None = None  # #5: only set when the underlying attachment is a PDF (never docx/html/etc.)


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
    source_chunk_count: int | None = None
    section_filter: list[str] = []
    sentences: list[SummarySentenceResponse] | None = None
    overview: list[OverviewItemResponse] | None = None
    overview_status: OverviewStatus = "not_requested"
    overview_updated_at: datetime | None = None
    imported: bool = False  # B2 SP2: a relayed synthesis — the sender's assessment, region precision, not re-verified


class SummaryListItem(BaseModel):
    summary_id: int
    scope_type: str
    scope_label: str
    status: str
    created_at: str | None = None
    sentence_count: int
    verified_sentence_count: int
    flagged_sentence_count: int
    imported: bool = False  # B2 SP2: flags a relayed synthesis in the history list


IMPORTED_STATUS = "imported"  # a relayed synthesis carries the sender's verification (B2 SP2)
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


def _persisted_summary_response(conn: Connection, *, summary_id: int, job_id: str) -> SummarizeJobResponse:
    summary = get_summary(conn, summary_id)
    imported_blob = summary["imported_json"] if "imported_json" in summary else None
    if imported_blob:  # B2 SP2: a relayed synthesis — build the response from its self-contained display blob
        return _imported_summary_response(imported_blob, summary_id=summary_id, job_id=job_id)
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
        source_chunk_count=_source_chunk_count_from_ref(summary["scope_ref_json"]),
        section_filter=_section_filter_from_ref(summary["scope_ref_json"]),
        sentences=[_summary_sentence_response(conn, sentence) for sentence in sentence_rows],
        overview=overview,
        overview_status=overview_status_for_row(summary),
        overview_updated_at=summary["overview_updated_at"],
    )


def _imported_summary_response(blob: Any, *, summary_id: int, job_id: str) -> SummarizeJobResponse:
    """Build the response for a RELAYED synthesis from its display blob (B2 SP2): region-precision citations, the
    sender's statuses, `imported=True`. Never touches the verification tables."""
    sentences = []
    for i, st in enumerate(blob.get("sentences") or []):
        if not isinstance(st, dict):
            continue
        citations = [
            SummaryCitationResponse(
                paper_id=c.get("paper_id"),
                paper_title=str(c.get("paper_title") or ""),
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                section=c.get("section"),
                quote=str(c.get("quote") or ""),
                retrieval_confidence=float(c.get("retrieval_confidence") or 0.0),
                quote_confidence=float(c.get("quote_confidence") or 0.0),
                support_confidence=float(c.get("support_confidence") or 0.0),
                status=str(c.get("status") or "unverified"),
                coordinate_precision="region",  # the sender's box is for the sender's PDF — always region here
            )
            for c in (st.get("citations") or [])
            if isinstance(c, dict)
        ]
        sentences.append(
            SummarySentenceResponse(
                sentence_id=i,
                ordinal=int(st.get("ordinal") or i),
                text=str(st.get("text") or ""),
                flagged=bool(st.get("flagged")),
                citations=citations,
            )
        )
    ov = blob.get("overview")
    overview = (
        [
            OverviewItemResponse(text=str(i["text"]), claim_ordinals=[int(o) for o in i["claim_ordinals"]])
            for i in ov
            if isinstance(i, dict) and i.get("text") and isinstance(i.get("claim_ordinals"), list)
        ]
        if isinstance(ov, list)
        else None
    )
    return SummarizeJobResponse(
        job_id=job_id,
        status="done",
        summary_id=summary_id,
        summary_status=IMPORTED_STATUS,
        section_filter=[],
        sentences=sentences,
        overview=overview,
        overview_status="complete" if overview else "not_requested",
        imported=True,
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
                chunks.c.section,
                chunks.c.attachment_id,
                attachments.c.content_type.label("attachment_content_type"),
                attachments.c.attachment_type,
                papers.c.title.label("paper_title"),
            )
            .select_from(
                citation_mappings.join(evidence_quotes, evidence_quotes.c.citation_mapping_id == citation_mappings.c.id)
                .join(chunks, chunks.c.id == evidence_quotes.c.chunk_id)
                .join(papers, papers.c.id == chunks.c.paper_id)
                # inner join is safe: chunks.attachment_id is a non-nullable FK (every chunk has one)
                .join(attachments, attachments.c.id == chunks.c.attachment_id)
            )
            .where(citation_mappings.c.summary_sentence_id == sentence_id)
            .order_by(citation_mappings.c.id)
        ).mappings()
    )


def _summary_citation_response(row: Any) -> SummaryCitationResponse:
    bbox_json = row["bbox_json"]
    chunk_id = row["evidence_chunk_id"] or row["mapping_chunk_id"]
    # #5: only surface attachment_id when it's a real PDF — a citation whose text came from a non-PDF
    # supplementary-text attachment (docx/html/jats-xml, role="supplementary-text") must keep degrading to the
    # paper's primary PDF (today's honest null-precision fallback), not 404 as "no local PDF" for a paper that
    # actually has one.
    is_pdf = _is_pdf_attachment(
        {"content_type": row["attachment_content_type"], "attachment_type": row["attachment_type"]}
    )
    return SummaryCitationResponse(
        mapping_id=row["mapping_id"],
        evidence_quote_id=row["evidence_quote_id"],
        chunk_id=chunk_id,
        paper_id=row["paper_id"],
        paper_title=row["paper_title"],
        page_start=row["page_start"],
        page_end=row["page_end"],
        section=row["section"],
        quote=row["quote_text"],
        retrieval_confidence=row["retrieval_confidence"],
        quote_confidence=row["quote_confidence"],
        support_confidence=row["support_confidence"],
        status=row["status"],
        coordinate_precision=_coordinate_precision_from_bbox(bbox_json),
        bbox_json=bbox_json,
        attachment_id=row["attachment_id"] if is_pdf else None,
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
        imported=row["status"] == IMPORTED_STATUS,
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


def _source_chunk_count_from_ref(scope_ref: Any) -> int | None:
    if not isinstance(scope_ref, dict) or scope_ref.get("source_chunk_count") is None:
        return None
    try:
        return int(scope_ref["source_chunk_count"])
    except (TypeError, ValueError):
        return None


def _section_filter_from_ref(scope_ref: Any) -> list[str]:
    if not isinstance(scope_ref, dict) or not isinstance(scope_ref.get("sections"), list):
        return []
    return [str(item) for item in scope_ref["sections"] if str(item)]


def _coordinate_precision_from_bbox(bbox_json: Any) -> str | None:
    if isinstance(bbox_json, list):
        for item in bbox_json:
            if isinstance(item, dict) and item.get("coordinate_precision"):
                return str(item["coordinate_precision"])
    if isinstance(bbox_json, dict) and bbox_json.get("coordinate_precision"):
        return str(bbox_json["coordinate_precision"])
    return None
