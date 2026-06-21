"""Library folder scan (inc 87) — ingest new PDFs from a user-pointed folder; reconcile removed ones.

`POST /library/scan {folder}` runs an async job that: scans the folder (`scan_library_folder` — ingest new /
skip unchanged / mark removed), then enriches each new paper from Crossref (resilient; unresolved → the inc-80
Unsorted view) and embeds the new chunks + papers so they're searchable. Local-only: the folder is read
server-side, which is the intent on a 127.0.0.1 single-user app (see the security audit). NOT the Gemini gate —
the only egress is the Crossref DOI lookup.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request  # noqa: F401
from fastapi import status as http_status
from pydantic import BaseModel

from app.backend.api.job_store import JobStore
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.pipeline import embed_chunks, embed_papers
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.metadata.enrichment import enrich_paper_metadata_from_crossref
from app.backend.pdf_processing.library_scan import scan_library_folder

router = APIRouter()
_log = logging.getLogger("callosum.library")


class ScanRequest(BaseModel):
    folder: str


class ScanSummary(BaseModel):
    added: int = 0
    unchanged: int = 0
    removed: int = 0
    errors: int = 0


class ScanJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: ScanSummary | None = None


@router.post("/library/scan", response_model=ScanJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def scan_folder(payload: ScanRequest, background_tasks: BackgroundTasks, request: Request) -> ScanJobResponse:
    folder = Path(payload.folder.strip()) if payload.folder and payload.folder.strip() else None
    if folder is None or not folder.is_dir():
        raise HTTPException(status_code=422, detail="Folder not found — enter an existing directory path.")
    job_id = request.app.state.library_scan_jobs.create()
    background_tasks.add_task(_run_scan_job, request.app, job_id, str(folder))
    return ScanJobResponse(job_id=job_id, status="pending")


@router.get("/library/scan/{job_id}", response_model=ScanJobResponse)
def scan_status(job_id: str, request: Request) -> ScanJobResponse:
    job = request.app.state.library_scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ScanJobResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_scan_job(app: FastAPI, job_id: str, folder: str) -> None:
    jobs: JobStore[ScanJobResponse] = app.state.library_scan_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        crossref = app.state.crossref_client
        with app.state.engine.begin() as conn:
            scanned = scan_library_folder(conn, folder)
            added_papers = [int(a["paper_id"]) for a in scanned["added"]]
            added_chunks = [int(cid) for a in scanned["added"] for cid in (a.get("chunk_ids") or [])]
            for paper_id in added_papers:  # Crossref metadata (resilient; unresolved → Unsorted). NOT the Gemini gate.
                try:
                    enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=crossref)
                except Exception as exc:
                    _log.warning("library scan: enrich failed for paper %s: %s", paper_id, exc)
            if added_chunks:
                embed_chunks(conn, model=model, vector_store=store, chunk_ids=added_chunks)
            if added_papers:
                embed_papers(conn, model=model, vector_store=store, paper_ids=added_papers)
        jobs.mark_done(
            job_id,
            ScanJobResponse(
                job_id=job_id,
                status="done",
                summary=ScanSummary(
                    added=len(scanned["added"]),
                    unchanged=len(scanned["unchanged"]),
                    removed=len(scanned["removed"]),
                    errors=len(scanned["errors"]),
                ),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _embedding_model(app: FastAPI) -> EmbeddingModel:
    injected = app.state.embedding_model
    if injected is not None:
        return injected
    return SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL)


def _vector_store(app: FastAPI) -> VectorStore:
    return app.state.vector_store if app.state.vector_store is not None else SQLiteVecVectorStore()
