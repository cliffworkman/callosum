"""Background modernization state and the user's durable Pause/Resume (inc 617).

The coordinator itself lives in ``app.backend.modernization``; this router wires it into the app lifespan and reports
its structured state for the forthcoming UI. Every count is read from stored rows; there is no combined percentage
or ETA, and no response carries a path, passage or exception text.
"""

from __future__ import annotations

import contextlib
import time

from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import Connection, func, select

from app.backend.api.dependencies import preview_verifier
from app.backend.api.routers.embedding_index import DiskCheckOut, _message, index_supervisor
from app.backend.embeddings import index_runs
from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, IncompleteEmbeddingIndexError
from app.backend.embeddings.retrieval_resolution import Resolution, explanation, resolve
from app.backend.modernization import (
    PAUSED,
    CoordinatorConfig,
    ModernizationCoordinator,
    arctic_model_status,
    modernization_enabled,
    read_intent,
)
from app.backend.modernization.presentation import summarize
from app.backend.persistence.schema import papers

router = APIRouter(tags=["modernization"])


class ClassificationOut(BaseModel):
    state: str
    derivation_version: str
    papers_with_classified_chunks: int | None = None
    papers_current: int | None = None
    papers_pending: int | None = None
    papers_failed_this_session: int
    papers_without_classified_chunks: int | None = None
    automatic_recovery: bool
    needs_user: bool
    detail: str | None = None


class IndexingOut(BaseModel):
    profile: str
    state: str
    eligible_chunks: int | None = None
    indexed_chunks: int | None = None
    missing_chunks: int | None = None
    run_state: str | None = None
    run_intent: str | None = None
    run_failure_kind: str | None = None
    automatic_recovery: bool
    needs_user: bool


class RetrievalPreferenceOut(BaseModel):
    profile: str | None = None
    source: str | None = None
    legacy: bool
    arctic_activated: bool


class ModelOut(BaseModel):
    track: str
    state: str | None = None
    verified: bool
    automatic_provisioning: bool


class ProgressOut(BaseModel):
    current: int
    total: int
    label: str


class SummaryOut(BaseModel):
    """inc 620: the one plain summary Status and Settings show. No combined percentage and no time estimate."""

    state: str  # working | waiting | paused | action_required | complete | disabled
    headline: str
    automatic_recovery: bool
    needs_user: bool
    attention: list[str]
    notes: dict[str, str]
    progress: ProgressOut | None = None
    eta_seconds: None = None


class IndexRunDetailOut(BaseModel):
    state: str
    message: str
    auto_retry_scheduled: bool
    disk: DiskCheckOut | None = None


class EffectiveRetrievalOut(BaseModel):
    profile: str
    fallback_reason: str | None = None
    explanation: str
    ask_blocked: bool = False


class VerifierOut(BaseModel):
    """Which verifier the next synthesis would use (inc 619 policy, previewed without loading any model)."""

    effective: str
    effective_label: str
    preference: str
    fallback_reason: str | None = None
    explanation: str
    synthesis_blocked: bool
    automatic_deberta_enabled: bool  # the production release gates; never armed by this panel


class ModernizationOut(BaseModel):
    enabled: bool
    disabled_reason: str | None = None
    intent: str
    coordinating_here: bool
    checked_at: str | None = None
    classification: ClassificationOut
    indexing: IndexingOut
    retrieval_preference: RetrievalPreferenceOut
    model: ModelOut
    summary: SummaryOut | None = None
    index_run: IndexRunDetailOut | None = None
    library_empty: bool | None = None
    effective_retrieval: EffectiveRetrievalOut | None = None
    verifier: VerifierOut | None = None


def coordinator(app: FastAPI) -> ModernizationCoordinator:
    existing = getattr(app.state, "modernization", None)
    if existing is None:
        enabled, reason = modernization_enabled()
        existing = ModernizationCoordinator(
            app.state.engine,
            CoordinatorConfig(db_url=app.state.db_url),
            supervisor=lambda: index_supervisor(app),
            model_status=getattr(app.state, "arctic_model_status", None) or arctic_model_status,
            enabled=enabled,
            disabled_reason=reason,
        )
        app.state.modernization = existing
    return existing


def resolve_retrieval(app: FastAPI, conn: Connection) -> Resolution:
    """The effective retrieval profile right now (inc 618). Automatic selection follows the coordinator's own gating:
    off in a source checkout unless requested, so a development library behaves as before."""
    managed = coordinator(app)
    return resolve(
        conn,
        automatic=managed.enabled,
        model_status=managed.model_status,
        paused=read_intent(app.state.engine) == PAUSED,
        run=index_runs.get_run(conn, ARCTIC_S_PROFILE_KEY),
    )


def start_modernization(app: FastAPI) -> None:
    """Lifespan startup: begin checking in the background. Never blocks startup and never raises."""
    with contextlib.suppress(Exception):
        coordinator(app).start()


def stop_modernization(app: FastAPI) -> None:
    existing = getattr(app.state, "modernization", None)
    if existing is not None:
        existing.shutdown()


def _run_detail(app: FastAPI) -> tuple[dict | None, IndexRunDetailOut | None]:
    with app.state.engine.connect() as conn:
        row = index_runs.get_run(conn, ARCTIC_S_PROFILE_KEY)
    if row is None:
        return None, None
    disk = None
    if row["disk_required_bytes"] is not None:
        disk = DiskCheckOut(
            required_free_bytes=row["disk_required_bytes"],
            free_bytes=row["disk_free_bytes"],
            estimated_remaining_bytes=row["disk_estimated_bytes"],
        )
    detail = IndexRunDetailOut(
        state=row["state"],
        message=_message(row),
        auto_retry_scheduled=row["state"] in ("retrying", "waiting_resources", "waiting_disk")
        and row["intent"] == "run",
        disk=disk,
    )
    return row, detail


def summary_of(app: FastAPI, status: dict) -> tuple[dict, IndexRunDetailOut | None]:
    """(inc-620 summary, index run detail) from a coordinator status. Reads stored rows only; never loads a model."""
    row, detail = _run_detail(app)
    message = detail.message if detail is not None and row["state"] in index_runs.ACTIVE_STATES else None
    return summarize(status, run_message=message), detail


_RETRIEVAL_TTL_SECONDS = 60.0


def _effective_retrieval(app: FastAPI, status: dict) -> EffectiveRetrievalOut:
    """The inc-618 resolution, re-run only when an input it depends on moved (or after a minute): it counts the
    Arctic index coverage, which a poll every few seconds should not repeat on a large library."""
    indexing, preference = status["indexing"], status["retrieval_preference"]
    key = (
        indexing["eligible_chunks"],
        indexing["indexed_chunks"],
        indexing["run_state"],
        status["model"]["state"],
        status["intent"],
        preference["profile"],
        preference["source"],
        status["checked_at"],
    )
    cached = getattr(app.state, "modernization_retrieval_cache", None)
    if cached and cached[0] == key and time.monotonic() - cached[1] < _RETRIEVAL_TTL_SECONDS:
        return cached[2]
    with app.state.engine.connect() as conn:
        try:
            resolution = resolve_retrieval(app, conn)
            out = EffectiveRetrievalOut(
                profile=resolution.profile.key,
                fallback_reason=resolution.fallback_reason,
                explanation=explanation(resolution),
            )
        except IncompleteEmbeddingIndexError as exc:
            out = EffectiveRetrievalOut(profile=preference["profile"] or "", explanation=str(exc), ask_blocked=True)
    app.state.modernization_retrieval_cache = (key, time.monotonic(), out)
    return out


def _verifier(app: FastAPI) -> VerifierOut:
    preview = preview_verifier(app)
    profile = preview["profile"]
    return VerifierOut(
        effective=profile.key,
        effective_label=profile.label,
        preference=preview["preference"].key or "automatic",
        fallback_reason=None if preview["fallback_reason"] == "user_choice" else preview["fallback_reason"],
        explanation=preview["explanation"],
        synthesis_blocked=preview["synthesis_blocked"] is not None,
        automatic_deberta_enabled=preview["gates_armed"],
    )


def _full(app: FastAPI, status: dict) -> ModernizationOut:
    summary, detail = summary_of(app, status)
    with app.state.engine.connect() as conn:
        live = conn.execute(select(func.count()).select_from(papers).where(papers.c.deleted_at.is_(None))).scalar_one()
    return ModernizationOut(
        **status,
        summary=SummaryOut(**summary),
        index_run=detail,
        library_empty=live == 0,
        effective_retrieval=_effective_retrieval(app, status),
        verifier=_verifier(app),
    )


@router.get("/modernization", response_model=ModernizationOut)
def modernization_status(request: Request) -> ModernizationOut:
    return _full(request.app, coordinator(request.app).status())


@router.post("/modernization/pause", response_model=ModernizationOut)
def pause_modernization(request: Request) -> ModernizationOut:
    """Durable: no automatic classification or Arctic indexing restarts, including after a restart, until Resume.
    Idempotent; it never changes a retrieval or verifier choice."""
    return _full(request.app, coordinator(request.app).pause())


@router.post("/modernization/resume", response_model=ModernizationOut)
def resume_modernization(request: Request) -> ModernizationOut:
    return _full(request.app, coordinator(request.app).resume())


# ---- the one Status entry ----------------------------------------------------------------------------------------

MODERNIZATION_STORE = "modernization"
_STATUS_OF = {"working": "running", "waiting": "running", "paused": "pending", "action_required": "error"}


def modernization_status_job(app: FastAPI) -> dict | None:
    """The unified "Library modernization" Status row, or None when there is nothing to show (disabled, or complete).
    Derived on every read from the coordinator's stored-row status: no second source of truth and no progress kept
    in memory, so it is the same after a restart and in every window. It never carries a path, passage or exception."""
    managed = coordinator(app)
    if not managed.enabled:
        return None  # no row and no coverage scan in a build that does not modernize automatically
    status = managed.status()
    summary, _ = summary_of(app, status)
    job_status = _STATUS_OF.get(summary["state"])
    if job_status is None:
        return None
    notes = [summary["notes"][key] for key in ("indexing", "classification", "model")]
    return {
        "store": MODERNIZATION_STORE,
        "job_id": "library",
        "label": "Library modernization",
        "status": job_status,
        "detail": summary["headline"],
        "progress": dict(summary["progress"], eta_seconds=None) if summary["progress"] else None,
        "notes": summary["attention"] + [n for n in notes if n not in summary["attention"]],
        "persistent": True,
        "nav": {"workspace": "settings", "section": "modernization"},
        "compute_kind": "Local AI",
    }
