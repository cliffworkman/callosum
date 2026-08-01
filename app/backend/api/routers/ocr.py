"""OCR a scanned / image-only PDF into a searchable copy (inc 231, backlog B3).

``POST /papers/ocr/run {paper_id}`` (async) renders the paper's PDF, runs local Tesseract to embed an OCR text
layer, attaches the searchable copy (promoted to **primary**, the original kept as a secondary), and extracts it
through the normal chunk + embedding pipeline — so a scanned paper becomes searchable + embeddable + citable with
**exact** highlights and selectable text. Fully **local — no egress** (Tesseract + local embeddings, like statcheck),
NOT the Gemini gate. Offered only for a PDF paper with **no text layer** (``chunk_count == 0``) so the worker only
ever *adds* chunks (re-OCR of an already-chunked paper is a follow-up).

Own router (3-segment ``/papers/ocr/*`` path, registered before ``papers.router``) — the citation_counts.py
precedent, so the literal ``/papers/ocr/*`` wins over ``/papers/{paper_id}``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select, update

from app.backend.acquisition.fetch import library_dir, library_filename_for
from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import _embedding_model, _vector_store
from app.backend.api.routers.paper_files import _local_attachment_path, _select_primary_pdf_attachment
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.pdf_processing.ocr import OCR_IMPORT_SOURCE, TesseractUnavailable, make_searchable_pdf
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import get_attachments_for_paper, get_chunks_for_paper, get_paper
from app.backend.persistence.schema import attachments, papers

router = APIRouter(tags=["ocr"])


class OcrRequest(BaseModel):
    paper_id: int


class OcrProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None


class OcrResult(BaseModel):
    pages: int
    chunks_created: int


class OcrResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: OcrResult | None = None
    progress: OcrProgress | None = None


@router.post("/papers/ocr/run", response_model=OcrResponse, status_code=http_status.HTTP_202_ACCEPTED)
def ocr_run(body: OcrRequest, background_tasks: BackgroundTasks, request: Request) -> OcrResponse:
    # Validate synchronously so the client gets a clean 404/422 without polling.
    with request.app.state.engine.begin() as conn:
        row = conn.execute(select(papers.c.id).where(papers.c.id == body.paper_id)).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        att = _select_primary_pdf_attachment(get_attachments_for_paper(conn, body.paper_id))
        if _local_attachment_path(att) is None:
            raise HTTPException(status_code=422, detail="This paper has no local PDF to OCR.")
        if get_chunks_for_paper(conn, body.paper_id, document_roles=ARTICLE_DOCUMENT_ROLES, limit=1):
            raise HTTPException(
                status_code=422,
                detail="This paper already has extractable text; OCR is only for scanned PDFs with none.",
            )
    job_id = request.app.state.ocr_jobs.create(nav={"paper_id": body.paper_id})
    background_tasks.add_task(_run_ocr_job, request.app, job_id, body.paper_id)
    return OcrResponse(job_id=job_id, status="pending")


@router.get("/papers/ocr/run/{job_id}", response_model=OcrResponse)
def ocr_status(job_id: str, request: Request) -> OcrResponse:
    job = request.app.state.ocr_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="OCR job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        OcrProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return OcrResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _run_ocr_job(app: FastAPI, job_id: str, paper_id: int) -> None:
    jobs: JobStore[OcrResponse] = app.state.ocr_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.begin() as conn:
            src_path = _local_attachment_path(_select_primary_pdf_attachment(get_attachments_for_paper(conn, paper_id)))
            if src_path is None:
                jobs.mark_error(job_id, "This paper has no local PDF to OCR.")
                return
            out_path = _unique_ocr_path(library_dir(), get_paper(conn, paper_id))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pages = make_searchable_pdf(
                src_path,
                out_path,
                on_progress=lambda i, t: jobs.mark_progress(job_id, i, t, "Reading pages (OCR)"),
            )
            # Promote the searchable copy to primary; demote the original scanned attachment (non-destructive — the
            # original file stays on disk, just no longer the primary PDF the viewer + quote-location read).
            conn.execute(update(attachments).where(attachments.c.paper_id == paper_id).values(role="secondary"))
            result = attach_pdf_to_paper(
                conn, paper_id, out_path, storage_mode="managed", import_source=OCR_IMPORT_SOURCE, role="primary"
            )
            chunk_ids = result["chunk_ids"]
            embed_chunks(
                conn,
                model=_embedding_model(app),
                vector_store=_vector_store(app),
                chunk_ids=chunk_ids,
                on_progress=lambda i, t: jobs.mark_progress(job_id, i, t, "Embedding text"),
            )
        jobs.mark_done(
            job_id,
            OcrResponse(job_id=job_id, status="done", result=OcrResult(pages=pages, chunks_created=len(chunk_ids))),
        )
    except TesseractUnavailable as exc:
        jobs.mark_error(job_id, str(exc))
    except Exception as exc:  # noqa: BLE001 — any engine/render failure becomes a graceful job error, never a crash
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _unique_ocr_path(lib: Path, paper) -> Path:
    """A managed path for the searchable copy, named per the library convention + an "(OCR)" marker; deduped."""
    base = library_filename_for(paper)
    stem = base[:-4] if base.lower().endswith(".pdf") else base
    candidate = lib / f"{stem} (OCR).pdf"
    counter = 1
    while candidate.exists():
        candidate = lib / f"{stem} (OCR-{counter}).pdf"
        counter += 1
    return candidate
