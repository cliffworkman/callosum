"""Native Zotero library import (backlog #57 Phase 1) — reads Zotero's own zotero.sqlite directly
(copy-then-read, integrations/zotero/adapter.py; app/backend/importers/zotero.py) for full fidelity:
PDFs extracted + chunked, collections/tags/notes/annotations carried over — vs. the generic
BibTeX/RIS/CSL-JSON path in library.py (metadata-only). A known, disclosed limitation (unchanged by
this increment, integrations/zotero/README.md): imported annotation POSITIONS stay in raw
Zotero-reader-JSON form, so imported highlights show their quoted text/comment but can't be
jumped-to or drawn on the PDF yet (backlog #57 Phase 4).

Split into its own sibling router (rule #1) — library.py is already at the 600-line cap.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field

from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import JobProgressOut, _embedding_model, _progress_out, _vector_store
from app.backend.embeddings.pipeline import embed_chunks, embed_papers
from app.backend.importers.zotero import ZoteroAttachmentRecord, import_zotero_library
from app.backend.methods.retraction import auto_check_retractions
from app.backend.persistence.sqlite_retry import commit_each

router = APIRouter()
_log = logging.getLogger("callosum.library_zotero")

_ZOTERO_DIR_MAX_LEN = 4096  # boundary cap (rule #4)
_ATTACHMENT_ERROR_DETAIL_CAP = 25


class ZoteroImportRequest(BaseModel):
    zotero_data_dir: str = Field(min_length=1, max_length=_ZOTERO_DIR_MAX_LEN)


class ZoteroAttachmentErrorOut(BaseModel):
    key: str
    error: str


class ZoteroImportSummary(BaseModel):
    papers_created: int = 0
    papers_matched: int = 0
    attachments_created: int = 0
    chunks_created: int = 0
    attachment_errors: int = 0
    attachment_error_details: list[ZoteroAttachmentErrorOut] = Field(default_factory=list)


class ZoteroImportJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: ZoteroImportSummary | None = None
    progress: JobProgressOut | None = None


@router.post(
    "/library/zotero/import", response_model=ZoteroImportJobResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def zotero_import_endpoint(
    payload: ZoteroImportRequest, background_tasks: BackgroundTasks, request: Request
) -> ZoteroImportJobResponse:
    raw = payload.zotero_data_dir.strip()
    data_dir = Path(raw) if raw else None
    if data_dir is None or not data_dir.is_dir():
        raise HTTPException(
            status_code=422, detail="Zotero data directory not found — enter an existing directory path."
        )
    job_id = request.app.state.zotero_import_jobs.create()
    background_tasks.add_task(_run_zotero_import_job, request.app, job_id, str(data_dir))
    return ZoteroImportJobResponse(job_id=job_id, status="pending")


@router.get("/library/zotero/import/{job_id}", response_model=ZoteroImportJobResponse)
def zotero_import_status(job_id: str, request: Request) -> ZoteroImportJobResponse:
    job = request.app.state.zotero_import_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Zotero import job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ZoteroImportJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _run_zotero_import_job(app: FastAPI, job_id: str, zotero_data_dir: str) -> None:
    jobs: JobStore[ZoteroImportJobResponse] = app.state.zotero_import_jobs
    jobs.mark_running(job_id)
    engine = app.state.engine
    attachment_errors: list[ZoteroAttachmentErrorOut] = []

    def _on_attachment_error(attachment: ZoteroAttachmentRecord, exc: Exception) -> None:
        attachment_errors.append(ZoteroAttachmentErrorOut(key=attachment.key, error=f"{type(exc).__name__}: {exc}"))

    def _on_progress(current: int, total: int) -> None:
        jobs.mark_progress(job_id, current, total, "Reading your Zotero library")

    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        # The whole read+import commits as ONE unit, matching import_zotero_library's own transactional
        # contract (one `conn`, not `engine`) — the same way tools/validation_harness.py and
        # tests/test_zotero_importer.py already call it. Deliberately NOT run_write: its retry-on-lock would
        # silently restart the whole library read from scratch on a late collision, wrong for a multi-minute job.
        with engine.begin() as conn:
            result = import_zotero_library(
                conn, zotero_data_dir, on_attachment_error=_on_attachment_error, on_progress=_on_progress
            )

        created_ids = set(result.created_paper_ids)
        touched_ids = list(dict.fromkeys(list(result.created_paper_ids) + list(result.chunk_ids_by_paper.keys())))

        def _post_process(conn, paper_id):
            chunk_ids = result.chunk_ids_by_paper.get(paper_id)
            if chunk_ids:
                embed_chunks(conn, model=model, vector_store=store, chunk_ids=list(chunk_ids))
            if paper_id in created_ids:
                embed_papers(conn, model=model, vector_store=store, paper_ids=[paper_id])
                auto_check_retractions(conn, [paper_id], checkers=app.state.retraction_checkers)

        for index, paper_id in enumerate(touched_ids, start=1):
            jobs.mark_progress(job_id, index, len(touched_ids), "Embedding")
            commit_each(engine, [paper_id], _post_process, on_item_error="skip", logger=_log)

        jobs.mark_done(
            job_id,
            ZoteroImportJobResponse(
                job_id=job_id,
                status="done",
                summary=ZoteroImportSummary(
                    papers_created=result.papers_created,
                    papers_matched=result.papers_matched,
                    attachments_created=result.attachments_created,
                    chunks_created=result.chunks_created,
                    attachment_errors=len(attachment_errors),
                    attachment_error_details=attachment_errors[:_ATTACHMENT_ERROR_DETAIL_CAP],
                ),
            ),
        )
    except FileNotFoundError:
        jobs.mark_error(
            job_id,
            f"No Zotero library found at {zotero_data_dir} — this should be Zotero's own data directory "
            "(it should contain a zotero.sqlite file), not a folder of PDFs.",
        )
    except Exception as exc:  # noqa: BLE001 — any failure -> a graceful job error, never a crash
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
