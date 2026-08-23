"""Local, exact-snapshot critical reading for unpublished WIP manuscripts."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel

from app.backend.api.dependencies import resolve_embedding_model, resolve_stance_scorer
from app.backend.api.job_store import JobProgress, JobStore
from app.backend.api.wip_security import require_local_wip
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.methods.critical_review import (
    ContestedSearchReport,
    extract_block_claim_sentences,
    library_article_chunk_embedding_ids,
    make_chunk_resolver,
    search_contested_claims,
)
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.wip_critical_review_repo import store_critical_review_run
from app.backend.persistence.wip_provenance_repo import PreparedSnapshot, prepare_snapshot, record_snapshot
from app.backend.persistence.wip_repo import add_activity, get_manuscript
from app.backend.wip.content import ContentIdentityError

router = APIRouter(prefix="/wip", dependencies=[Depends(require_local_wip)])


class WipCriticalReadStartResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


class WipCriticalReadJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    run: dict | None = None


def _wip_critical_deps(app: FastAPI):
    seam = getattr(app.state, "wip_critical_review_deps", None)
    if seam is not None:
        return seam["embed_model"], seam["vector_store"], seam["stance_scorer"]
    embed = resolve_embedding_model(app, local_files_only=True)
    store = app.state.vector_store or SQLiteVecVectorStore()
    stance = resolve_stance_scorer(app, local_files_only=True)
    return embed, store, stance


def _active_job(jobs: JobStore, manuscript_id: int) -> str | None:
    for job_id, job in jobs.list_all():
        if job.status in {"pending", "running"} and (job.nav or {}).get("manuscript_id") == manuscript_id:
            return job_id
    return None


def _safe_snapshot_error(exc: ContentIdentityError) -> str:
    message = str(exc)
    allowed = (
        "Select a primary manuscript file",
        "The primary manuscript file is unavailable",
        "Unsupported primary manuscript format",
        "Primary manuscript exceeds",
        "No manuscript text could be extracted",
    )
    return message if message.startswith(allowed) else "The primary manuscript could not be read."


def _snapshot_still_current(app: FastAPI, prepared: PreparedSnapshot) -> bool:
    """Best-effort filesystem/primary-selection revalidation immediately before the receipt write."""
    try:
        with app.state.engine.connect() as conn:
            current = prepare_snapshot(conn, prepared.manuscript_id)
    except (ContentIdentityError, LookupError):
        return False
    return (
        current.file_id == prepared.file_id
        and current.identity.whole_file_hash == prepared.identity.whole_file_hash
        and current.identity.extracted_text_hash == prepared.identity.extracted_text_hash
    )


@router.post(
    "/manuscripts/{manuscript_id}/critical-read",
    response_model=WipCriticalReadStartResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def critical_read_start(
    manuscript_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
) -> WipCriticalReadStartResponse:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    jobs: JobStore = request.app.state.wip_critical_review_jobs
    existing = _active_job(jobs, manuscript_id)
    if existing is not None:
        job = jobs.get(existing)
        return WipCriticalReadStartResponse(job_id=existing, status=job.status if job else "pending")
    try:
        with request.app.state.engine.connect() as conn:
            prepared = prepare_snapshot(conn, manuscript_id)
    except ContentIdentityError as exc:
        raise HTTPException(status_code=422, detail=_safe_snapshot_error(exc)) from exc
    job_id = jobs.create(nav={"manuscript_id": manuscript_id})
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(conn, manuscript_id, "tool-run-started", "Started local critical read"),
    )
    background_tasks.add_task(_run_wip_critical_read_job, request.app, job_id, prepared)
    return WipCriticalReadStartResponse(job_id=job_id, status="pending")


@router.get("/critical-read/{job_id}", response_model=WipCriticalReadJobResponse)
async def critical_read_status(
    job_id: str,
    request: Request,
    wait_seconds: float = Query(default=0.0, ge=0.0, le=25.0),
) -> WipCriticalReadJobResponse:
    jobs: JobStore[WipCriticalReadJobResponse] = request.app.state.wip_critical_review_jobs
    job = await jobs.wait_for_update(job_id, wait_seconds)
    if job is None:
        raise HTTPException(status_code=404, detail="WIP critical-read job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return WipCriticalReadJobResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_wip_critical_read_job(app: FastAPI, job_id: str, prepared: PreparedSnapshot) -> None:
    jobs: JobStore[WipCriticalReadJobResponse] = app.state.wip_critical_review_jobs
    jobs.mark_running(job_id)
    claims = extract_block_claim_sentences(
        list(prepared.identity.blocks),
        has_real_pages=Path(prepared.relative_path).suffix.casefold() == ".pdf",
    )
    total = max(1, len(claims))
    jobs.mark_progress(job_id, 0, total, "Preparing bounded manuscript claims")
    try:
        embed_model, vector_store, stance_scorer = _wip_critical_deps(app)
        provenance = {
            "embedding_model": str(getattr(embed_model, "name", type(embed_model).__name__))[:200],
            "embedding_version": str(getattr(embed_model, "version", "unknown"))[:200],
            "embedding_normalization": str(getattr(embed_model, "normalization", "unknown"))[:80],
            "vector_store": str(getattr(vector_store, "kind", type(vector_store).__name__))[:80],
            "stance_model": str(getattr(stance_scorer, "model_name", type(stance_scorer).__name__))[:200],
        }
        with app.state.engine.connect() as conn:
            eligible_ids = library_article_chunk_embedding_ids(
                conn,
                model_name=provenance["embedding_model"],
                model_version=provenance["embedding_version"],
                normalization=provenance["embedding_normalization"],
            )
            try:
                search = search_contested_claims(
                    conn,
                    None,
                    embed_model=embed_model,
                    vector_store=vector_store,
                    stance_scorer=stance_scorer,
                    resolve_chunk=make_chunk_resolver(conn),
                    claim_sentences=[claim.text for claim in claims],
                    other_chunk_ids=eligible_ids,
                    on_progress=lambda current, count: jobs.mark_progress(
                        job_id, current, max(1, count), "Comparing claims with local Library passages"
                    ),
                )
            except Exception:
                search = ContestedSearchReport([], len(claims), len(eligible_ids), 0, 0, "local-model-unavailable")
        claim_pages = {claim.text: claim.page for claim in claims}
        search = replace(
            search,
            contested_claims=[
                replace(item, claim_page=claim_pages.get(item.claim)) for item in search.contested_claims
            ],
        )
        if not _snapshot_still_current(app, prepared):
            detail = "The primary manuscript changed during the local critical read. Run it again from the new text."
            jobs.mark_error(job_id, detail)
            run_write(
                app.state.engine,
                lambda conn: add_activity(
                    conn,
                    prepared.manuscript_id,
                    "tool-run-failed",
                    "Local critical read stopped because the primary manuscript changed",
                ),
            )
            return

        def persist(conn):
            snapshot, _ = record_snapshot(conn, prepared, reason="tool-run", reason_detail="critical-read")
            return store_critical_review_run(
                conn,
                prepared,
                int(snapshot["id"]),
                claims=claims,
                search=search,
                model_provenance=provenance,
            )

        run = run_write(app.state.engine, persist)
        final_progress = JobProgress(current=total, total=total, label="Local critical read complete")
        jobs.mark_done(
            job_id,
            WipCriticalReadJobResponse(job_id=job_id, status="done", run=run),
            progress=final_progress,
        )
    except Exception:
        jobs.mark_error(job_id, "Local critical read could not complete. The manuscript remains unchanged.")
        with suppress(Exception):
            run_write(
                app.state.engine,
                lambda conn: add_activity(
                    conn,
                    prepared.manuscript_id,
                    "tool-run-failed",
                    "Local critical read could not complete",
                ),
            )
