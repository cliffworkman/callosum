"""Retrieval-profile index builds: supervised worker, durable lifecycle, Pause/Resume/Cancel (inc 610).

The build runs in a separate worker process owned by ``IndexSupervisor``; this router only records the user's
intent and reports state. Everything shown is derived from the durable ``embedding_index_runs`` row and the stored
vectors -- never from a volatile progress counter -- and is mirrored into the in-memory ``JobStore`` only so the
global Status popover keeps working (invariant #5). Messages carry no exception text, paths or passages; the
bounded technical ``diagnostic`` is a separate field for the expandable details.
"""

from __future__ import annotations

import contextlib

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import JobProgressOut, _progress_out
from app.backend.embeddings import index_runs
from app.backend.embeddings.index_supervisor import IndexSupervisor, SupervisorConfig, ThreadLauncher
from app.backend.embeddings.profile_index import DEFAULT_INDEX_BATCH
from app.backend.embeddings.profiles import (
    BASELINE_PROFILE_KEY,
    EmbeddingProfile,
    UnknownEmbeddingProfileError,
    get_profile,
    profile_coverage,
)
from app.backend.embeddings.vector_store import InMemoryVectorStore

router = APIRouter(tags=["embedding-profiles"])

_ACTIONS = {
    "queued": ["pause", "cancel"],
    "running": ["pause", "cancel"],
    "retrying": ["pause", "cancel"],
    "waiting_resources": ["pause", "cancel"],
    "pausing": [],
    "paused": ["resume", "cancel"],
    "interrupted": ["resume", "cancel"],
    "failed": ["resume"],
    "cancelled": ["resume"],
    "completed": [],
}


class IndexRunOut(BaseModel):
    state: str
    message: str
    indexed_chunks: int
    eligible_chunks: int
    percent: float
    batch_size: int
    attempts: int
    failures_without_progress: int
    auto_retry_scheduled: bool
    failure_kind: str | None = None
    diagnostic: str | None = None
    peak_worker_rss_mb: int | None = None
    actions: list[str]


class IndexSummary(BaseModel):
    state: str
    chunks_indexed: int  # stored, current vectors for this profile (not a session counter)
    eligible_chunks: int
    cancelled: bool


class IndexJobResponse(BaseModel):
    job_id: str
    status: str
    detail: str | None = None
    summary: IndexSummary | None = None
    progress: JobProgressOut | None = None
    run: IndexRunOut | None = None


def _message(row: dict) -> str:
    state, kind = row["state"], row["failure_kind"]
    smaller = int(row["batch_size"]) < DEFAULT_INDEX_BATCH
    if state == "running":
        if smaller:
            return f"Indexing resumed with a smaller batch size ({row['batch_size']} passages at a time)."
        return "Indexing passages. Completed work is saved as it goes."
    if state == "waiting_resources":
        return "Indexing paused because available memory is low. Completed work is saved. Callosum will resume automatically when safe."
    if state == "retrying":
        if kind == "app_closed":
            return "Indexing stopped when Callosum closed. Completed work is saved and indexing will resume."
        return "Indexing was interrupted. Completed work is saved. Callosum will retry automatically."
    if state == "interrupted":
        if kind == "app_closed":
            return "Indexing stopped when Callosum closed. Completed work is saved. Resume when you're ready."
        return "Indexing was interrupted (cause unknown). Completed work is saved. Resume when you're ready."
    if state == "failed":
        return row["failure_detail"] or "Indexing stopped. Your existing index is preserved. You can retry manually."
    return {
        "queued": "Indexing will start shortly.",
        "pausing": "Stopping after the current batch. Completed work is saved.",
        "paused": "Paused. Completed work is saved. Resume when you're ready.",
        "cancelled": "Cancelled. Completed work is saved; starting again resumes from it.",
        "completed": "Index complete.",
    }.get(state, state)


def index_run_out(conn: Connection, profile: EmbeddingProfile, coverage: dict | None = None) -> IndexRunOut | None:
    row = index_runs.get_run(conn, profile.key)
    if row is None:
        return None
    coverage = coverage or profile_coverage(conn, profile)
    eligible, indexed = coverage["eligible_chunks"], coverage["indexed_chunks"]  # stored vectors, not the row
    return IndexRunOut(
        state=row["state"],
        message=_message(row),
        indexed_chunks=indexed,
        eligible_chunks=eligible,
        percent=round(100.0 * indexed / eligible, 1) if eligible else 100.0,
        batch_size=int(row["batch_size"]),
        attempts=int(row["attempts"]),
        failures_without_progress=int(row["failures_without_progress"]),
        auto_retry_scheduled=row["state"] in ("retrying", "waiting_resources") and row["intent"] == "run",
        failure_kind=row["failure_kind"],
        diagnostic=row["diagnostic"],
        peak_worker_rss_mb=row["peak_worker_rss_mb"],
        actions=_ACTIONS.get(row["state"], []),
    )


# ---- supervisor + Status mirror -------------------------------------------------------------------------------


def _jobs(app: FastAPI) -> JobStore[IndexJobResponse]:
    return app.state.embedding_index_jobs


def _launcher_for(app: FastAPI, supervisor: IndexSupervisor):  # type: ignore[no-untyped-def]
    injected = getattr(app.state, "profile_embedding_models", None) or {}
    if injected:  # tests and fake profiles: same worker loop, in a thread
        store = app.state.vector_store if app.state.vector_store is not None else InMemoryVectorStore()
        return ThreadLauncher(app.state.engine, lambda key: injected[key], store)
    return supervisor.launcher


def index_supervisor(app: FastAPI) -> IndexSupervisor:
    supervisor = getattr(app.state, "index_supervisor", None)
    if supervisor is None:
        supervisor = IndexSupervisor(
            app.state.engine,
            SupervisorConfig(db_url=app.state.db_url),
            on_update=lambda row: _mirror(app, row),
        )
        app.state.index_supervisor = supervisor
    supervisor.launcher = _launcher_for(app, supervisor)
    return supervisor


def _mirror(app: FastAPI, row: dict) -> None:
    """Reflect the durable row into Status. Waiting and retrying stay visible as running work with a label."""
    jobs = _jobs(app)
    ids: dict[str, str] = app.state.embedding_index_job_ids
    key = row["profile_key"]
    job_id = ids.get(key)
    job = jobs.get(job_id) if job_id else None
    if job is None or job.status in ("done", "error"):
        if row["state"] not in index_runs.ACTIVE_STATES:
            return
        job_id, _ = jobs.create_or_get_active()
        ids[key] = job_id
    label = _message(row)
    if row["state"] in index_runs.ACTIVE_STATES:
        jobs.mark_progress(job_id, int(row["indexed_chunks"]), max(1, int(row["eligible_chunks"])), label[:120])
        return
    summary = IndexSummary(
        state=row["state"],
        chunks_indexed=int(row["indexed_chunks"]),
        eligible_chunks=int(row["eligible_chunks"]),
        cancelled=row["state"] in ("paused", "cancelled", "interrupted"),
    )
    if row["state"] == "failed":
        jobs.mark_error(job_id, label)
    else:
        jobs.mark_done(job_id, IndexJobResponse(job_id=job_id, status="done", summary=summary), nav=None)


def active_index_job_id(app: FastAPI) -> str | None:
    for job_id, job in _jobs(app).list_all():
        if job.status in ("pending", "running"):
            return job_id
    return None


def reconcile_index_builds(app: FastAPI) -> None:
    """Lifespan startup: recover builds a previous session left active, then start watching."""
    supervisor = index_supervisor(app)
    for row in supervisor.reconcile_on_startup():
        if row:
            _mirror(app, row)
    supervisor.start_monitor()


def shutdown_index_builds(app: FastAPI) -> None:
    supervisor = getattr(app.state, "index_supervisor", None)
    if supervisor is not None:
        supervisor.shutdown()


# ---- endpoints ------------------------------------------------------------------------------------------------


def _buildable(key: str) -> EmbeddingProfile:
    try:
        profile = get_profile(key)
    except UnknownEmbeddingProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    if profile.key == BASELINE_PROFILE_KEY:
        raise HTTPException(status_code=400, detail="The baseline is indexed automatically at import.")
    return profile


def _job_response(app: FastAPI, job_id: str, profile_key: str | None) -> IndexJobResponse:
    job = _jobs(app).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    run = None
    if profile_key is not None:
        with app.state.engine.connect() as conn:
            run = index_run_out(conn, get_profile(profile_key))
    if job.status == "done" and job.result is not None:
        return job.result.model_copy(update={"run": run})
    return IndexJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job), run=run)


def _profile_of_job(app: FastAPI, job_id: str) -> str | None:
    return next((k for k, v in app.state.embedding_index_job_ids.items() if v == job_id), None)


@router.post(
    "/embedding-profiles/{key}/index", response_model=IndexJobResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def start_index(key: str, request: Request) -> IndexJobResponse:
    """Start, or explicitly resume, the supervised build. A second request while one runs joins it."""
    profile = _buildable(key)
    row = index_supervisor(request.app).start(profile)
    _mirror(request.app, row)
    job_id = request.app.state.embedding_index_job_ids.get(profile.key)
    if job_id is None:  # already complete: report it without inventing a running job
        job_id, _ = _jobs(request.app).create_or_get_active()
        request.app.state.embedding_index_job_ids[profile.key] = job_id
        _mirror(request.app, row)
    return _job_response(request.app, job_id, profile.key)


@router.get("/embedding-profiles/index/{job_id}", response_model=IndexJobResponse)
def index_status(job_id: str, request: Request) -> IndexJobResponse:
    supervisor = getattr(request.app.state, "index_supervisor", None)
    if supervisor is not None:
        with contextlib.suppress(Exception):
            supervisor.tick()  # observe a finished worker even when the lifespan monitor isn't running
    return _job_response(request.app, job_id, _profile_of_job(request.app, job_id))


@router.post("/embedding-profiles/index/{job_id}/cancel", response_model=IndexJobResponse)
def stop_index_job(job_id: str, request: Request) -> IndexJobResponse:
    """Pause after the batch in progress commits; everything indexed so far is kept and Resume continues."""
    key = _profile_of_job(request.app, job_id)
    if key is None or _jobs(request.app).get(job_id) is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    _mirror(request.app, index_supervisor(request.app).pause(key))
    return _job_response(request.app, job_id, key)


def _act(request: Request, key: str, action: str) -> IndexRunOut:
    profile = _buildable(key)
    supervisor = index_supervisor(request.app)
    with request.app.state.engine.connect() as conn:
        exists = index_runs.get_run(conn, profile.key) is not None
    if action != "resume" and not exists:
        raise HTTPException(status_code=409, detail="No index build has been started for this model.")
    row = supervisor.start(profile) if action == "resume" else getattr(supervisor, action)(profile.key)
    _mirror(request.app, row)
    with request.app.state.engine.connect() as conn:
        run = index_run_out(conn, profile)
    assert run is not None
    return run


@router.post("/embedding-profiles/{key}/index/pause", response_model=IndexRunOut)
def pause_index(key: str, request: Request) -> IndexRunOut:
    return _act(request, key, "pause")


@router.post("/embedding-profiles/{key}/index/resume", response_model=IndexRunOut)
def resume_index(key: str, request: Request) -> IndexRunOut:
    return _act(request, key, "resume")


@router.post("/embedding-profiles/{key}/index/cancel", response_model=IndexRunOut)
def cancel_index(key: str, request: Request) -> IndexRunOut:
    return _act(request, key, "cancel")
