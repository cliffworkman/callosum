"""Retrieval embedding profiles (coverage, index builds, selection) and the verification NLI profile selection.

Local only: building an index runs the profile's pinned local model over this library's own chunks; nothing leaves
the machine (a first use may fetch the pinned weights from the Hugging Face Hub, a model request, not library text).
Only Ask's evidence retrieval follows the selected profile; citation verification stays on the MiniLM baseline.
"""

from __future__ import annotations

from threading import Lock

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field

from app.backend.api.dependencies import resolve_profile_embedding_model
from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import JobProgressOut, _progress_out
from app.backend.embeddings.profile_index import build_profile_index
from app.backend.embeddings.profiles import (
    BASELINE_PROFILE_KEY,
    PROFILES,
    EmbeddingProfile,
    UnknownEmbeddingProfileError,
    active_retrieval_profile,
    get_profile,
    profile_coverage,
    set_active_retrieval_profile,
)
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.persistence.sqlite_retry import run_write
from app.backend.summarization.nli_profiles import (
    BASELINE_NLI_PROFILE_KEY,
    NLI_PROFILES,
    UnknownNliProfileError,
    active_nli_profile,
    get_nli_profile,
    set_active_nli_profile,
    verify_nli_checkpoint,
)

router = APIRouter(tags=["embedding-profiles"])
_cancel_lock = Lock()


class ProfileCoverage(BaseModel):
    eligible_chunks: int
    indexed_chunks: int
    missing_chunks: int
    complete: bool
    live_papers: int
    papers_with_eligible_chunks: int
    papers_without_passage_text: int


class ProfileOut(BaseModel):
    key: str
    label: str
    model_name: str
    revision: str
    model_version: str
    normalization: str
    query_prefix: str
    document_prefix: str
    pooling: str | None
    qualification: str
    is_baseline: bool
    coverage: ProfileCoverage


class ProfilesResponse(BaseModel):
    active: str
    verification_model: str  # what citation verification uses regardless of the retrieval profile
    profiles: list[ProfileOut]
    index_job_id: str | None = None


class SelectProfileRequest(BaseModel):
    key: str = Field(min_length=1, max_length=40)


class IndexSummary(BaseModel):
    papers_pending: int
    papers_indexed: int
    chunks_indexed: int
    cancelled: bool


class IndexJobResponse(BaseModel):
    job_id: str
    status: str
    detail: str | None = None
    summary: IndexSummary | None = None
    progress: JobProgressOut | None = None


def _jobs(app: FastAPI) -> JobStore[IndexJobResponse]:
    return app.state.embedding_index_jobs


def _profile_out(profile: EmbeddingProfile, coverage: dict) -> ProfileOut:
    return ProfileOut(
        key=profile.key,
        label=profile.label,
        model_name=profile.model_name,
        revision=profile.revision,
        model_version=profile.model_version,
        normalization=profile.normalization,
        query_prefix=profile.query_prefix,
        document_prefix=profile.document_prefix,
        pooling=profile.pooling,
        qualification=profile.qualification,
        is_baseline=profile.key == BASELINE_PROFILE_KEY,
        coverage=ProfileCoverage(**coverage),
    )


def _active_index_job(app: FastAPI) -> str | None:
    for job_id, job in _jobs(app).list_all():
        if job.status in ("pending", "running"):
            return job_id
    return None


def _state(request: Request) -> ProfilesResponse:
    with request.app.state.engine.connect() as conn:
        active = active_retrieval_profile(conn)
        profiles = [_profile_out(p, profile_coverage(conn, p)) for p in PROFILES.values()]
    return ProfilesResponse(
        active=active.key,
        verification_model=PROFILES[BASELINE_PROFILE_KEY].label,
        profiles=profiles,
        index_job_id=_active_index_job(request.app),
    )


def _known(key: str) -> EmbeddingProfile:
    try:
        return get_profile(key)
    except UnknownEmbeddingProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.get("/embedding-profiles", response_model=ProfilesResponse)
def list_profiles(request: Request) -> ProfilesResponse:
    return _state(request)


@router.put("/embedding-profiles/active", response_model=ProfilesResponse)
def select_profile(payload: SelectProfileRequest, request: Request) -> ProfilesResponse:
    profile = _known(payload.key)
    engine = request.app.state.engine
    with engine.connect() as conn:
        coverage = profile_coverage(conn, profile)
    if not profile.lazy_indexing and not coverage["complete"]:
        raise HTTPException(
            status_code=409,
            detail=f"The {profile.label} index covers {coverage['indexed_chunks']} of {coverage['eligible_chunks']} "
            "passages. Build it before selecting this profile.",
        )
    run_write(engine, lambda conn: set_active_retrieval_profile(conn, profile.key))
    return _state(request)


@router.post(
    "/embedding-profiles/{key}/index", response_model=IndexJobResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def start_index(key: str, background_tasks: BackgroundTasks, request: Request) -> IndexJobResponse:
    profile = _known(key)
    if profile.key == BASELINE_PROFILE_KEY:
        raise HTTPException(status_code=400, detail="The baseline is indexed automatically at import.")
    jobs = _jobs(request.app)
    job_id, created = jobs.create_or_get_active()  # one build at a time; a second request joins the first
    if created:
        background_tasks.add_task(_run_index_job, request.app, job_id, profile)
    job = jobs.get(job_id)
    return IndexJobResponse(job_id=job_id, status=job.status if job else "pending")


@router.get("/embedding-profiles/index/{job_id}", response_model=IndexJobResponse)
def index_status(job_id: str, request: Request) -> IndexJobResponse:
    job = _jobs(request.app).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return IndexJobResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


@router.post("/embedding-profiles/index/{job_id}/cancel", response_model=IndexJobResponse)
def cancel_index(job_id: str, request: Request) -> IndexJobResponse:
    """Stops after the paper in progress commits; everything indexed so far is kept and a later build resumes."""
    job = _jobs(request.app).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Index job not found")
    with _cancel_lock:
        request.app.state.embedding_index_cancelled.add(job_id)
    return index_status(job_id, request)


def _run_index_job(app: FastAPI, job_id: str, profile: EmbeddingProfile) -> None:
    jobs = _jobs(app)
    jobs.mark_running(job_id)
    try:
        model = resolve_profile_embedding_model(app, profile)
        store = app.state.vector_store if app.state.vector_store is not None else SQLiteVecVectorStore()
        stats = build_profile_index(
            app.state.engine,
            model=model,
            vector_store=store,
            on_progress=lambda i, n, label: jobs.mark_progress(job_id, i, n, label),
            should_cancel=lambda: job_id in app.state.embedding_index_cancelled,
        )
        jobs.mark_done(job_id, IndexJobResponse(job_id=job_id, status="done", summary=IndexSummary(**stats)), nav=None)
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        with _cancel_lock:
            app.state.embedding_index_cancelled.discard(job_id)


# ---- verification NLI profile (synthesis citation verification only) ------------------------------------------


class NliProfileOut(BaseModel):
    key: str
    label: str
    model_name: str
    revision: str
    qualification: str
    is_baseline: bool


class NliProfilesResponse(BaseModel):
    active: str
    thresholds_calibrated_on: str
    profiles: list[NliProfileOut]


def _nli_state(request: Request) -> NliProfilesResponse:
    with request.app.state.engine.connect() as conn:
        active = active_nli_profile(conn)
    return NliProfilesResponse(
        active=active.key,
        thresholds_calibrated_on=NLI_PROFILES[BASELINE_NLI_PROFILE_KEY].label,
        profiles=[
            NliProfileOut(
                key=p.key,
                label=p.label,
                model_name=p.model_name,
                revision=p.revision,
                qualification=p.qualification,
                is_baseline=p.key == BASELINE_NLI_PROFILE_KEY,
            )
            for p in NLI_PROFILES.values()
        ],
    )


@router.get("/verification-nli-profiles", response_model=NliProfilesResponse)
def list_nli_profiles(request: Request) -> NliProfilesResponse:
    return _nli_state(request)


@router.put("/verification-nli-profiles/active", response_model=NliProfilesResponse)
def select_nli_profile(payload: SelectProfileRequest, request: Request) -> NliProfilesResponse:
    """Selecting a non-baseline profile loads its pinned checkpoint and verifies its contract first, so a mismatched
    checkpoint is refused here rather than mid-synthesis."""
    try:
        profile = get_nli_profile(payload.key)
    except UnknownNliProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    app = request.app
    if profile.enforce_contract and getattr(app.state, "support_scorer", None) is None:
        try:
            runtime = app.state.model_runtime_registry.get_nli_runtime(
                model_name=profile.model_name, revision=profile.revision
            )
            runtime.run(lambda model: verify_nli_checkpoint(model, profile))
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"{profile.label} could not be verified: {exc}") from None
    run_write(app.state.engine, lambda conn: set_active_nli_profile(conn, profile.key))
    return _nli_state(request)
