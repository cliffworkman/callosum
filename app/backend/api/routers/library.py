"""Library ingestion endpoints: folder scan (inc 87) + citation-file import (inc 93).

`POST /library/scan {folder}` runs an async job that: scans the folder (`scan_library_folder` — ingest new /
skip unchanged / mark removed), then enriches each new paper from Crossref (resilient; unresolved → the inc-80
Unsorted view) and embeds the new chunks + papers so they're searchable. Local-only: the folder is read
server-side, which is the intent on a 127.0.0.1 single-user app (see the security audit). NOT the Gemini gate —
the only egress is the Crossref DOI lookup.

`POST /library/import {content, format}` runs an async job that parses a pasted/uploaded BibTeX / RIS / CSL-JSON
file (`import_citations`), dedups, creates metadata-only papers, and embeds them. **Entirely local — no egress**
(the file is authoritative; no Crossref). The inverse of inc-70 export.

Watched folders (inc 98): scanning a folder **registers** it (`watched_folders`); `GET/DELETE /library/watched`
manage the list, and `POST /library/watched/rescan` re-scans all of them (auto-triggered on launch) so new PDFs
appear without re-adding — Zotero/Mendeley-style watching, minus a live OS file-watcher.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response  # noqa: F401
from fastapi import status as http_status
from pydantic import BaseModel, Field

from app.backend.api.job_store import JobStore
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.pipeline import embed_chunks, embed_papers
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.metadata.citation_import import MAX_IMPORT_BYTES, import_citations
from app.backend.metadata.enrichment import enrich_paper_metadata_from_crossref
from app.backend.methods.retraction import auto_check_retractions
from app.backend.pdf_processing.library_scan import scan_library_folder
from app.backend.persistence.watched_repo import (
    add_watched_folder,
    list_watched_folders,
    remove_watched_folder,
    touch_last_scanned,
)

router = APIRouter()
_log = logging.getLogger("callosum.library")


class JobProgressOut(BaseModel):
    """Determinate progress for a running scan/import (inc 142) — the UI shows "label  current / total" + a fill."""

    current: int
    total: int
    label: str


def _progress_out(job) -> JobProgressOut | None:
    p = getattr(job, "progress", None)
    return JobProgressOut(current=p.current, total=p.total, label=p.label) if p else None


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
    progress: JobProgressOut | None = None


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
    return ScanJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _process_scan_result(
    conn, scanned, *, model, store, crossref, retraction_checkers=None, on_progress: Callable[[str, int, int], None] | None = None
) -> None:
    """Enrich new papers from Crossref + embed new chunks/papers for one scan result (shared by scan + rescan).
    Crossref is resilient (unresolved → the inc-80 Unsorted view) and is NOT the Gemini gate. Inc 134: a
    best-effort retraction auto-check runs on the new papers (so a freshly scanned retracted paper flags now).
    Inc 142: ``on_progress(label, current, total)`` reports the enrich + embed phases for determinate UI progress."""
    added_papers = [int(a["paper_id"]) for a in scanned["added"]]
    added_chunks = [int(cid) for a in scanned["added"] for cid in (a.get("chunk_ids") or [])]
    for index, paper_id in enumerate(added_papers, start=1):
        if on_progress:
            on_progress("Fetching metadata", index, len(added_papers))
        try:
            enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=crossref)
        except Exception as exc:
            _log.warning("library scan: enrich failed for paper %s: %s", paper_id, exc)
    if added_chunks:
        embed_chunks(
            conn, model=model, vector_store=store, chunk_ids=added_chunks,
            on_progress=(lambda i, n: on_progress("Embedding text", i, n)) if on_progress else None,
        )
    if added_papers:
        embed_papers(
            conn, model=model, vector_store=store, paper_ids=added_papers,
            on_progress=(lambda i, n: on_progress("Embedding papers", i, n)) if on_progress else None,
        )
        if retraction_checkers:
            auto_check_retractions(conn, added_papers, checkers=retraction_checkers)


def _scan_summary(scanned) -> ScanSummary:
    return ScanSummary(
        added=len(scanned["added"]),
        unchanged=len(scanned["unchanged"]),
        removed=len(scanned["removed"]),
        errors=len(scanned["errors"]),
    )


def _run_scan_job(app: FastAPI, job_id: str, folder: str) -> None:
    jobs: JobStore[ScanJobResponse] = app.state.library_scan_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        crossref = app.state.crossref_client
        with app.state.engine.begin() as conn:
            scanned = scan_library_folder(
                conn, folder, on_progress=lambda i, n: jobs.mark_progress(job_id, i, n, "Reading PDFs")
            )
            _process_scan_result(
                conn,
                scanned,
                model=model,
                store=store,
                crossref=crossref,
                retraction_checkers=app.state.retraction_checkers,
                on_progress=lambda label, i, n: jobs.mark_progress(job_id, i, n, label),
            )
            add_watched_folder(conn, folder)  # inc 98: scanning a folder starts watching it
            touch_last_scanned(conn, folder)
        jobs.mark_done(job_id, ScanJobResponse(job_id=job_id, status="done", summary=_scan_summary(scanned)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


class WatchedFolder(BaseModel):
    id: int
    path: str
    last_scanned_at: str | None = None


@router.get("/library/watched", response_model=list[WatchedFolder])
def watched_list(request: Request) -> list[WatchedFolder]:
    with request.app.state.engine.begin() as conn:
        return [
            WatchedFolder(
                id=int(r["id"]),
                path=r["path"],
                last_scanned_at=str(r["last_scanned_at"]) if r["last_scanned_at"] else None,
            )
            for r in list_watched_folders(conn)
        ]


@router.delete("/library/watched/{folder_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def watched_remove(folder_id: int, request: Request) -> Response:
    with request.app.state.engine.begin() as conn:
        remove_watched_folder(conn, folder_id)  # drops the watch only — the papers it imported are kept
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post("/library/watched/rescan", response_model=ScanJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def watched_rescan(background_tasks: BackgroundTasks, request: Request) -> ScanJobResponse:
    # Re-scan ALL watched folders (async) — the "watch": pick up new/removed PDFs without re-adding. No-ops if
    # there are no watched folders. Auto-triggered on app launch (default on) + a manual "Re-scan all".
    job_id = request.app.state.library_scan_jobs.create()
    background_tasks.add_task(_run_watched_rescan_job, request.app, job_id)
    return ScanJobResponse(job_id=job_id, status="pending")


@router.get("/library/watched/rescan/{job_id}", response_model=ScanJobResponse)
def watched_rescan_status(job_id: str, request: Request) -> ScanJobResponse:
    job = request.app.state.library_scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Rescan job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ScanJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _run_watched_rescan_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[ScanJobResponse] = app.state.library_scan_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        crossref = app.state.crossref_client
        agg = {"added": 0, "unchanged": 0, "removed": 0, "errors": 0}
        with app.state.engine.begin() as conn:
            for row in list_watched_folders(conn):
                folder = row["path"]
                if not Path(folder).is_dir():  # a watched folder that's gone → noted, never fatal
                    agg["errors"] += 1
                    continue
                scanned = scan_library_folder(
                    conn, folder, on_progress=lambda i, n: jobs.mark_progress(job_id, i, n, "Reading PDFs")
                )
                _process_scan_result(
                    conn,
                    scanned,
                    model=model,
                    store=store,
                    crossref=crossref,
                    retraction_checkers=app.state.retraction_checkers,
                    on_progress=lambda label, i, n: jobs.mark_progress(job_id, i, n, label),
                )
                touch_last_scanned(conn, folder)
                for key in agg:
                    agg[key] += len(scanned[key])
        jobs.mark_done(job_id, ScanJobResponse(job_id=job_id, status="done", summary=ScanSummary(**agg)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


class ImportRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_IMPORT_BYTES + 1_000_000)  # boundary cap (rule #4)
    format: Literal["bibtex", "ris", "csl-json", "auto"] = "auto"


class ImportSummary(BaseModel):
    imported: int = 0
    duplicate: int = 0
    failed: int = 0
    format: str | None = None  # the resolved format (None when auto-detect couldn't recognise the file)


class ImportJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: ImportSummary | None = None
    progress: JobProgressOut | None = None


@router.post("/library/import", response_model=ImportJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def import_citations_endpoint(
    payload: ImportRequest, background_tasks: BackgroundTasks, request: Request
) -> ImportJobResponse:
    if not payload.content.strip():
        raise HTTPException(status_code=422, detail="Choose a BibTeX, RIS, or CSL-JSON file to import.")
    job_id = request.app.state.library_import_jobs.create()
    fmt = None if payload.format == "auto" else payload.format
    background_tasks.add_task(_run_import_job, request.app, job_id, payload.content, fmt)
    return ImportJobResponse(job_id=job_id, status="pending")


@router.get("/library/import/{job_id}", response_model=ImportJobResponse)
def import_status(job_id: str, request: Request) -> ImportJobResponse:
    job = request.app.state.library_import_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ImportJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _run_import_job(app: FastAPI, job_id: str, content: str, fmt: str | None) -> None:
    jobs: JobStore[ImportJobResponse] = app.state.library_import_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        with app.state.engine.begin() as conn:
            result = import_citations(conn, content, fmt)  # parse → dedup → create; no egress
            created = [int(pid) for pid in result["created"]]
            if created:  # embed the new papers' metadata so they're searchable / axis-scorable
                embed_papers(
                    conn, model=model, vector_store=store, paper_ids=created,
                    on_progress=lambda i, n: jobs.mark_progress(job_id, i, n, "Embedding papers"),
                )
                # inc 134: best-effort retraction auto-check on the imported papers (a known-retracted DOI flags now)
                auto_check_retractions(conn, created, checkers=app.state.retraction_checkers)
        jobs.mark_done(
            job_id,
            ImportJobResponse(
                job_id=job_id,
                status="done",
                summary=ImportSummary(
                    imported=len(created),
                    duplicate=int(result["duplicate"]),
                    failed=int(result["failed"]),
                    format=result["format"],
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
