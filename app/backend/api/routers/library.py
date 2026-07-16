"""Library ingestion endpoints: folder scan, watched-folder rescan, citation import, and bundle import.

Folder scans read local PDFs, add new content, skip checksum duplicates, mark missing scan-sourced files, then
enrich/embed new papers. Citation imports are metadata-only and local. Watched folders are explicit rows plus the
always-watched library folder; rescans are pull-style jobs, not an OS file watcher.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field

from app.backend.acquisition.fetch import library_dir
from app.backend.api.job_store import JobStore
from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, EmbeddingModel, SentenceTransformerEmbeddingModel
from app.backend.embeddings.pipeline import embed_chunks, embed_papers
from app.backend.embeddings.vector_store import SQLiteVecVectorStore, VectorStore
from app.backend.metadata.citation_import import MAX_IMPORT_BYTES, import_citations
from app.backend.metadata.enrichment import enrich_paper_metadata_from_crossref
from app.backend.metadata.library_bundle import MAX_BUNDLE_BYTES, BundleError, build_bundle, import_bundle, parse_bundle
from app.backend.methods.retraction import auto_check_retractions
from app.backend.pdf_processing.library_scan import scan_library_folder
from app.backend.persistence.sqlite_retry import commit_each, run_write
from app.backend.persistence.watched_repo import (
    add_watched_folder,
    list_watched_folders,
    remove_watched_folder,
    touch_last_scanned,
)

router = APIRouter()
_log = logging.getLogger("callosum.library")


def _path_key(p: Path) -> str:
    """A normalized key for comparing folder paths (resolve + casefold — Windows is case-insensitive)."""
    try:
        return str(p.resolve()).casefold()
    except OSError:
        return str(p).casefold()


class JobProgressOut(BaseModel):
    """Determinate progress for a running scan/import (inc 142) — the UI shows "label  current / total" + a fill,
    plus a rough "~Ns left" ETA (inc 225) once there's progress to extrapolate from."""

    current: int
    total: int
    label: str
    eta_seconds: int | None = None


def _progress_out(job) -> JobProgressOut | None:
    p = getattr(job, "progress", None)
    return JobProgressOut(current=p.current, total=p.total, label=p.label, eta_seconds=job.eta_seconds()) if p else None


class ScanRequest(BaseModel):
    folder: str


_SCAN_ERROR_DETAIL_CAP = 25  # how many per-file failure reasons to surface in the done-summary (inc 155)
_SCAN_ALREADY_RUNNING_DETAIL = "A library folder scan or watched-folder rescan is already running."


class ScanError(BaseModel):
    path: str
    error: str


class ScanSummary(BaseModel):
    added: int = 0
    unchanged: int = 0
    removed: int = 0
    errors: int = 0
    error_details: list[ScanError] = []  # inc 155: which files couldn't be read + why (capped)


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
    return _start_scan_family_job(request, background_tasks, _run_scan_job, str(folder))


@router.get("/library/scan/{job_id}", response_model=ScanJobResponse)
def scan_status(job_id: str, request: Request) -> ScanJobResponse:
    job = request.app.state.library_scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return ScanJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _process_scan_result(
    engine,
    scanned,
    *,
    model,
    store,
    crossref,
    retraction_checkers=None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> None:
    """Enrich + embed each newly scanned paper in its OWN committed transaction (per-paper), so the write lock is
    released between papers instead of held for the whole run (inc A). One paper's hard failure is skipped +
    logged, never aborting the rest — partial progress is usable and the scan is idempotent (content-hash dedup).
    Crossref stays resilient (unresolved → the inc-80 Unsorted view) and is NOT the Gemini gate. Inc 134: a
    best-effort retraction auto-check runs per new paper. Inc 142: ``on_progress(label, current, total)`` reports
    progress across the papers."""
    added = scanned["added"]  # [{paper_id, chunk_ids}]
    total = len(added)

    def process_one(conn, item):
        paper_id = int(item["paper_id"])
        chunk_ids = [int(cid) for cid in (item.get("chunk_ids") or [])]
        try:
            enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=crossref)
        except Exception as exc:  # enrich stays best-effort (unresolved → Unsorted); never fails the item
            _log.warning("library scan: enrich failed for paper %s: %s", paper_id, exc)
        if chunk_ids:
            embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)
        embed_papers(conn, model=model, vector_store=store, paper_ids=[paper_id])
        if retraction_checkers:
            auto_check_retractions(conn, [paper_id], checkers=retraction_checkers)

    for index, item in enumerate(added, start=1):
        if on_progress:
            on_progress("Processing", index, total)
        commit_each(engine, [item], process_one, on_item_error="skip", logger=_log)


def _scan_summary(scanned) -> ScanSummary:
    return ScanSummary(
        added=len(scanned["added"]),
        unchanged=len(scanned["unchanged"]),
        removed=len(scanned["removed"]),
        errors=len(scanned["errors"]),
        error_details=[ScanError(path=e["path"], error=e["error"]) for e in scanned["errors"][:_SCAN_ERROR_DETAIL_CAP]],
    )


def _run_scan_job(app: FastAPI, job_id: str, folder: str) -> None:
    jobs: JobStore[ScanJobResponse] = app.state.library_scan_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        crossref = app.state.crossref_client
        engine = app.state.engine
        # Phase 1 (extraction + insert) commits as its own unit (A2 will make it per-file); phase 2 (enrich +
        # embed) commits per paper inside _process_scan_result, so the write lock is released between papers.
        scanned = run_write(
            engine,
            lambda conn: scan_library_folder(
                conn, folder, on_progress=lambda i, n, name: jobs.mark_progress(job_id, i, n, f"Reading {name}")
            ),
        )
        _process_scan_result(
            engine,
            scanned,
            model=model,
            store=store,
            crossref=crossref,
            retraction_checkers=app.state.retraction_checkers,
            on_progress=lambda label, i, n: jobs.mark_progress(job_id, i, n, label),
        )
        run_write(engine, lambda conn: (add_watched_folder(conn, folder), touch_last_scanned(conn, folder)))
        jobs.mark_done(job_id, ScanJobResponse(job_id=job_id, status="done", summary=_scan_summary(scanned)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        _clear_active_scan_family_job(app, job_id)


class WatchedFolder(BaseModel):
    id: int  # 0 = the always-watched library folder (the pinned default, inc 160); >=1 = a user-added folder
    path: str
    last_scanned_at: str | None = None
    is_default: bool = False  # inc 160: the library folder, always watched + not removable


@router.get("/library/watched", response_model=list[WatchedFolder])
def watched_list(request: Request) -> list[WatchedFolder]:
    # The library folder (`library_dir()`) is ALWAYS watched (inc 160) — pinned first as a non-removable default,
    # even with no registered rows. A user folder equal to it is folded into that pin (never listed twice).
    lib = library_dir()
    lib_key = _path_key(lib)
    with request.app.state.engine.begin() as conn:
        rows = list(list_watched_folders(conn))
    lib_row = next((r for r in rows if _path_key(Path(r["path"])) == lib_key), None)
    out = [
        WatchedFolder(
            id=0,
            path=str(lib),
            last_scanned_at=str(lib_row["last_scanned_at"]) if lib_row and lib_row["last_scanned_at"] else None,
            is_default=True,
        )
    ]
    for r in rows:
        if _path_key(Path(r["path"])) == lib_key:
            continue  # the library folder is shown as the pinned default above
        out.append(
            WatchedFolder(
                id=int(r["id"]),
                path=r["path"],
                last_scanned_at=str(r["last_scanned_at"]) if r["last_scanned_at"] else None,
            )
        )
    return out


@router.delete("/library/watched/{folder_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def watched_remove(folder_id: int, request: Request) -> Response:
    if folder_id == 0:  # the library folder is always watched (inc 160)
        raise HTTPException(status_code=422, detail="The library folder is always watched and can't be removed.")
    with request.app.state.engine.begin() as conn:
        remove_watched_folder(conn, folder_id)  # drops the watch only — the papers it imported are kept
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post("/library/watched/rescan", response_model=ScanJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def watched_rescan(background_tasks: BackgroundTasks, request: Request) -> ScanJobResponse:
    # Re-scan ALL watched folders (async) — the "watch": pick up new/removed PDFs without re-adding. No-ops if
    # there are no watched folders. Auto-triggered on app launch (default on) + a manual "Re-scan all".
    return _start_scan_family_job(request, background_tasks, _run_watched_rescan_job)


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
        engine = app.state.engine
        agg = {"added": 0, "unchanged": 0, "removed": 0, "errors": 0}
        error_details: list[ScanError] = []  # inc 155: per-file failures across all watched folders (capped)
        # inc 160: the library folder is ALWAYS rescanned (the pinned default) — even with no registered rows, so
        # a PDF dropped into it is picked up on launch/focus. Then the user-added folders (skip the library folder
        # if a user also added it, so it isn't scanned twice). inc A: each folder's insert phase commits as its own
        # unit and its enrich+embed commits per paper, so the write lock is released between folders + papers.
        lib = library_dir()
        lib_key = _path_key(lib)
        with engine.connect() as conn:
            targets: list[str] = [str(lib)] if lib.is_dir() else []
            targets += [r["path"] for r in list_watched_folders(conn) if _path_key(Path(r["path"])) != lib_key]
        for folder in targets:
            if not Path(folder).is_dir():  # a watched folder that's gone → noted, never fatal
                agg["errors"] += 1
                if len(error_details) < _SCAN_ERROR_DETAIL_CAP:
                    error_details.append(ScanError(path=folder, error="watched folder no longer exists"))
                continue
            scanned = run_write(
                engine,
                lambda conn, f=folder: scan_library_folder(
                    conn, f, on_progress=lambda i, n, name: jobs.mark_progress(job_id, i, n, f"Reading {name}")
                ),
            )
            _process_scan_result(
                engine,
                scanned,
                model=model,
                store=store,
                crossref=crossref,
                retraction_checkers=app.state.retraction_checkers,
                on_progress=lambda label, i, n: jobs.mark_progress(job_id, i, n, label),
            )
            run_write(engine, lambda conn, f=folder: touch_last_scanned(conn, f))
            for key in agg:
                agg[key] += len(scanned[key])
            for e in scanned["errors"]:
                if len(error_details) < _SCAN_ERROR_DETAIL_CAP:
                    error_details.append(ScanError(path=e["path"], error=e["error"]))
        jobs.mark_done(
            job_id,
            ScanJobResponse(job_id=job_id, status="done", summary=ScanSummary(**agg, error_details=error_details)),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        _clear_active_scan_family_job(app, job_id)


def _start_scan_family_job(request: Request, background_tasks: BackgroundTasks, runner, *args) -> ScanJobResponse:
    """Single-flight guard for write-heavy PDF scan/rescan jobs; callers poll the active run."""
    app = request.app
    jobs: JobStore[ScanJobResponse] = app.state.library_scan_jobs
    lock = app.state.library_scan_singleflight_lock
    with lock:
        active_job_id = getattr(app.state, "active_library_scan_job_id", None)
        if active_job_id:
            active = jobs.get(active_job_id)
            if active is not None and active.status in ("pending", "running"):
                return ScanJobResponse(
                    job_id=active_job_id,
                    status=active.status,
                    detail=_SCAN_ALREADY_RUNNING_DETAIL,
                    progress=_progress_out(active),
                )
        job_id = jobs.create()
        app.state.active_library_scan_job_id = job_id
        background_tasks.add_task(runner, app, job_id, *args)
    return ScanJobResponse(job_id=job_id, status="pending")


def _clear_active_scan_family_job(app: FastAPI, job_id: str) -> None:
    lock = getattr(app.state, "library_scan_singleflight_lock", None)
    if lock is None:
        return
    with lock:
        if getattr(app.state, "active_library_scan_job_id", None) == job_id:
            app.state.active_library_scan_job_id = None


class ImportRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_IMPORT_BYTES + 1_000_000)  # boundary cap (rule #4)
    format: Literal["bibtex", "ris", "csl-json", "auto"] = "auto"


class ImportSummary(BaseModel):
    imported: int = 0
    duplicate: int = 0
    failed: int = 0
    skipped: int = 0  # entries dropped at parse (no title AND no DOI, or beyond the record cap) — inc 173
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
                    conn,
                    model=model,
                    vector_store=store,
                    paper_ids=created,
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
                    skipped=int(result["skipped"]),
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


# ── portable library bundle (B2 SP1): export/import metadata + tags + annotations + axis defs, NO PDFs ──────────


class BundleExportRequest(BaseModel):
    scope: Literal["library", "selection"] = "library"
    paper_ids: list[int] = Field(default_factory=list)


class BundleImportRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_BUNDLE_BYTES + 1_000_000)  # boundary cap (rule #4)


class BundleImportSummary(BaseModel):
    papers_created: int = 0
    papers_merged: int = 0
    tags_applied: int = 0
    annotations_added: int = 0
    axes_created: int = 0
    axes_members_added: int = 0
    syntheses_imported: int = 0
    skipped: int = 0


class BundleImportJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: BundleImportSummary | None = None
    progress: JobProgressOut | None = None


@router.post("/library/bundle/export")
def bundle_export(payload: BundleExportRequest, request: Request) -> Response:
    """Serialize the library (or a selection) to a downloadable JSON bundle — metadata + tags + annotations +
    (whole-library only) axis definitions; **NO PDFs**. Local read; no egress (a file the user hands off)."""
    if payload.scope == "selection" and not payload.paper_ids:
        raise HTTPException(status_code=422, detail="Select at least one paper to export as a bundle.")
    with request.app.state.engine.begin() as conn:
        bundle = build_bundle(conn, scope=payload.scope, paper_ids=payload.paper_ids or None)
    return Response(
        content=json.dumps(bundle, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="callosum-library-bundle.json"'},
    )


@router.post(
    "/library/bundle/import", response_model=BundleImportJobResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def bundle_import_endpoint(
    payload: BundleImportRequest, background_tasks: BackgroundTasks, request: Request
) -> BundleImportJobResponse:
    if not payload.content.strip():
        raise HTTPException(status_code=422, detail="Choose a callosum library bundle (.json) to import.")
    job_id = request.app.state.library_bundle_import_jobs.create()
    background_tasks.add_task(_run_bundle_import_job, request.app, job_id, payload.content)
    return BundleImportJobResponse(job_id=job_id, status="pending")


@router.get("/library/bundle/import/{job_id}", response_model=BundleImportJobResponse)
def bundle_import_status(job_id: str, request: Request) -> BundleImportJobResponse:
    job = request.app.state.library_bundle_import_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Bundle import job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return BundleImportJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _run_bundle_import_job(app: FastAPI, job_id: str, content: str) -> None:
    jobs: JobStore[BundleImportJobResponse] = app.state.library_bundle_import_jobs
    jobs.mark_running(job_id)
    try:
        bundle = parse_bundle(content)  # bounded + version-checked; raises BundleError on a bad file
        model = _embedding_model(app)
        store = _vector_store(app)
        with app.state.engine.begin() as conn:
            result = import_bundle(conn, bundle)  # additive, non-destructive; no egress
            created = [int(pid) for pid in result["created"]]
            if created:  # embed the new papers' metadata so they join search / axis-scoring / dedup
                embed_papers(
                    conn,
                    model=model,
                    vector_store=store,
                    paper_ids=created,
                    on_progress=lambda i, n: jobs.mark_progress(job_id, i, n, "Embedding papers"),
                )
        jobs.mark_done(
            job_id,
            BundleImportJobResponse(job_id=job_id, status="done", summary=BundleImportSummary(**result["summary"])),
        )
    except BundleError as exc:
        jobs.mark_error(job_id, str(exc))
    except Exception as exc:  # noqa: BLE001 — any failure → a graceful job error, never a crash
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
