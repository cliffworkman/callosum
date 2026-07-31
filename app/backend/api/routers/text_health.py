"""PDF text-health inspection and bounded reprocessing jobs.

Local-only maintenance surface for extracted PDF text. It does not OCR, fetch metadata, or contact providers; it
only measures existing local attachments/chunks and can re-run the normal PDF extraction path for selected papers or
for PDFs whose existing chunks have no section labels.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, and_, case, func, select

from app.backend.api.job_store import JobStore
from app.backend.api.routers.paper_files import _local_attachment_path, _select_primary_pdf_attachment
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.pdf_processing.extraction import DEFAULT_CHUNKING_STRATEGY, EXTRACTION_TOOL
from app.backend.pdf_processing.ingest import PdfReprocessEmptyExtraction, reprocess_pdf_attachment
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.repository import get_attachments_for_paper, list_live_paper_ids
from app.backend.persistence.schema import attachments, chunks

router = APIRouter(tags=["text-health"])

TEXT_TINY_CHAR_THRESHOLD = 500


class TextHealthItem(BaseModel):
    paper_id: int
    has_local_pdf: bool
    chunk_count: int
    section_labeled_chunks: int
    text_chars: int
    flags: list[Literal["no_local_pdf", "no_chunks", "tiny_text", "missing_section_labels", "stale_chunk_version"]]
    status: Literal["ok", "needs_reprocess", "needs_ocr_or_better_pdf", "no_local_pdf"]


class TextHealthCounts(BaseModel):
    total: int = 0
    local_pdfs: int = 0
    no_local_pdf: int = 0
    no_chunks: int = 0
    tiny_text: int = 0
    missing_section_labels: int = 0
    stale_chunk_version: int = 0
    ok: int = 0


class TextHealthOverview(BaseModel):
    counts: TextHealthCounts
    items: list[TextHealthItem]


class TextReprocessRequest(BaseModel):
    mode: Literal["selected", "missing_section_labels"] = "selected"
    paper_ids: list[int] = Field(default_factory=list, max_length=500)


class TextReprocessSummary(BaseModel):
    total: int = 0
    reprocessed: int = 0
    chunks_removed: int = 0
    chunks_created: int = 0
    skipped_no_local_pdf: int = 0
    skipped_no_chunks: int = 0
    skipped_not_needed: int = 0
    failed: int = 0


class TextReprocessProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None


class TextReprocessResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: TextReprocessSummary | None = None
    progress: TextReprocessProgress | None = None


@router.get("/papers/text-health/overview", response_model=TextHealthOverview)
def text_health_overview(
    request: Request,
    paper_ids: list[int] = Query(default=[]),
    limit: int = Query(default=500, ge=1, le=5000),
) -> TextHealthOverview:
    with request.app.state.engine.begin() as conn:
        ids = _bounded_ids(conn, paper_ids, limit=limit)
        items = [_text_health_for_paper(conn, paper_id) for paper_id in ids]
    return TextHealthOverview(counts=_count_health(items), items=items)


@router.post(
    "/papers/text-health/reprocess",
    response_model=TextReprocessResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def text_reprocess_start(
    payload: TextReprocessRequest, background_tasks: BackgroundTasks, request: Request
) -> TextReprocessResponse:
    if payload.mode == "selected" and not payload.paper_ids:
        raise HTTPException(status_code=422, detail="Choose at least one paper to reprocess.")
    job_id = request.app.state.text_health_jobs.create()
    background_tasks.add_task(_run_text_reprocess_job, request.app, job_id, payload)
    return TextReprocessResponse(job_id=job_id, status="pending")


@router.get("/papers/text-health/reprocess/{job_id}", response_model=TextReprocessResponse)
def text_reprocess_status(job_id: str, request: Request) -> TextReprocessResponse:
    job = request.app.state.text_health_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Text reprocess job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        TextReprocessProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return TextReprocessResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _run_text_reprocess_job(app: FastAPI, job_id: str, payload: TextReprocessRequest) -> None:
    jobs: JobStore[TextReprocessResponse] = app.state.text_health_jobs
    jobs.mark_running(job_id)
    summary = TextReprocessSummary()
    try:
        with app.state.engine.begin() as conn:
            ids = _candidate_ids(conn, payload)
            summary.total = len(ids)
            store = _vector_store(app)
            model = _embedding_model(app)
            for index, paper_id in enumerate(ids, start=1):
                health = _text_health_for_paper(conn, paper_id)
                jobs.mark_progress(job_id, index, len(ids), "Reprocessing PDF text")
                if not health.has_local_pdf:
                    summary.skipped_no_local_pdf += 1
                    continue
                if health.chunk_count == 0:
                    summary.skipped_no_chunks += 1
                    continue
                if payload.mode == "missing_section_labels" and "missing_section_labels" not in health.flags:
                    summary.skipped_not_needed += 1
                    continue
                attachment = _select_primary_pdf_attachment(get_attachments_for_paper(conn, paper_id))
                pdf_path = _local_attachment_path(attachment)
                if attachment is None or pdf_path is None:
                    summary.skipped_no_local_pdf += 1
                    continue
                try:
                    result = reprocess_pdf_attachment(
                        conn, paper_id, int(attachment["id"]), pdf_path, vector_store=store, embedding_model=model
                    )
                except PdfReprocessEmptyExtraction:
                    summary.skipped_no_chunks += 1
                    continue
                except Exception:
                    summary.failed += 1
                    continue
                summary.reprocessed += 1
                summary.chunks_removed += int(result["chunks_removed"])
                summary.chunks_created += int(result["chunks_created"])
        jobs.mark_done(job_id, TextReprocessResponse(job_id=job_id, status="done", summary=summary))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _candidate_ids(conn: Connection, payload: TextReprocessRequest) -> list[int]:
    if payload.mode == "selected":
        requested = []
        seen = set()
        for paper_id in payload.paper_ids:
            if paper_id not in seen:
                requested.append(int(paper_id))
                seen.add(paper_id)
        live = set(list_live_paper_ids(conn))
        return [paper_id for paper_id in requested if paper_id in live]
    return [
        item.paper_id
        for item in (_text_health_for_paper(conn, paper_id) for paper_id in list_live_paper_ids(conn))
        if "missing_section_labels" in item.flags
    ]


def _bounded_ids(conn: Connection, requested: list[int], *, limit: int) -> list[int]:
    if requested:
        live = set(list_live_paper_ids(conn))
        ids = []
        seen = set()
        for paper_id in requested[:limit]:
            if paper_id in live and paper_id not in seen:
                ids.append(int(paper_id))
                seen.add(paper_id)
        return ids
    return list_live_paper_ids(conn)[:limit]


def _text_health_for_paper(conn: Connection, paper_id: int) -> TextHealthItem:
    has_local_pdf = _local_attachment_path(_select_primary_pdf_attachment(get_attachments_for_paper(conn, paper_id)))
    metrics = conn.execute(
        select(
            func.count(chunks.c.id).label("chunk_count"),
            func.coalesce(func.sum(func.length(chunks.c.text)), 0).label("text_chars"),
            func.coalesce(func.sum(case((chunks.c.section.is_not(None), 1), else_=0)), 0),
        )
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(chunks.c.paper_id == paper_id, attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
    ).one()
    section_count = int(metrics[2])
    stale_count = int(
        conn.execute(
            select(func.count())
            .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
            .where(
                and_(
                    chunks.c.paper_id == paper_id,
                    attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES),
                    (chunks.c.chunking_strategy != DEFAULT_CHUNKING_STRATEGY)
                    | (chunks.c.extraction_tool != EXTRACTION_TOOL),
                )
            )
        ).scalar_one()
    )
    chunk_count = int(metrics.chunk_count)
    text_chars = int(metrics.text_chars)
    flags = _health_flags(bool(has_local_pdf), chunk_count, section_count, text_chars, stale_count)
    return TextHealthItem(
        paper_id=paper_id,
        has_local_pdf=bool(has_local_pdf),
        chunk_count=chunk_count,
        section_labeled_chunks=section_count,
        text_chars=text_chars,
        flags=flags,
        status=_health_status(bool(has_local_pdf), chunk_count, flags),
    )


def _health_flags(
    has_local_pdf: bool, chunk_count: int, section_count: int, text_chars: int, stale_count: int
) -> list[str]:
    flags = []
    if not has_local_pdf:
        flags.append("no_local_pdf")
    if has_local_pdf and chunk_count == 0:
        flags.append("no_chunks")
    if has_local_pdf and chunk_count > 0 and text_chars < TEXT_TINY_CHAR_THRESHOLD:
        flags.append("tiny_text")
    if has_local_pdf and chunk_count > 0 and section_count == 0:
        flags.append("missing_section_labels")
    if has_local_pdf and stale_count > 0:
        flags.append("stale_chunk_version")
    return flags


def _health_status(has_local_pdf: bool, chunk_count: int, flags: list[str]) -> str:
    if not has_local_pdf:
        return "no_local_pdf"
    if chunk_count == 0:
        return "needs_ocr_or_better_pdf"
    if "missing_section_labels" in flags or "stale_chunk_version" in flags:
        return "needs_reprocess"
    return "ok"


def _count_health(items: list[TextHealthItem]) -> TextHealthCounts:
    counts = TextHealthCounts(total=len(items))
    for item in items:
        counts.local_pdfs += 1 if item.has_local_pdf else 0
        counts.no_local_pdf += 1 if "no_local_pdf" in item.flags else 0
        counts.no_chunks += 1 if "no_chunks" in item.flags else 0
        counts.tiny_text += 1 if "tiny_text" in item.flags else 0
        counts.missing_section_labels += 1 if "missing_section_labels" in item.flags else 0
        counts.stale_chunk_version += 1 if "stale_chunk_version" in item.flags else 0
        counts.ok += 1 if item.status == "ok" else 0
    return counts


def _vector_store(api: FastAPI) -> VectorStore:
    injected = api.state.vector_store
    if injected is not None:
        return injected
    return SQLiteVecVectorStore()


def _embedding_model(api: FastAPI) -> EmbeddingModel:
    injected = api.state.embedding_model
    if injected is not None:
        return injected
    return SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL)
