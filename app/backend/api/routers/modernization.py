"""Background modernization state and the user's durable Pause/Resume (inc 617).

The coordinator itself lives in ``app.backend.modernization``; this router wires it into the app lifespan and reports
its structured state for the forthcoming UI. Every count is read from stored rows; there is no combined percentage
or ETA, and no response carries a path, passage or exception text.
"""

from __future__ import annotations

import contextlib

from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel

from app.backend.api.routers.embedding_index import index_supervisor
from app.backend.modernization import (
    CoordinatorConfig,
    ModernizationCoordinator,
    arctic_model_status,
    modernization_enabled,
)

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


class ModelOut(BaseModel):
    track: str
    state: str | None = None
    verified: bool
    automatic_provisioning: bool


class ModernizationOut(BaseModel):
    enabled: bool
    disabled_reason: str | None = None
    intent: str
    coordinating_here: bool
    checked_at: str | None = None
    classification: ClassificationOut
    indexing: IndexingOut
    model: ModelOut


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


def start_modernization(app: FastAPI) -> None:
    """Lifespan startup: begin checking in the background. Never blocks startup and never raises."""
    with contextlib.suppress(Exception):
        coordinator(app).start()


def stop_modernization(app: FastAPI) -> None:
    existing = getattr(app.state, "modernization", None)
    if existing is not None:
        existing.shutdown()


@router.get("/modernization", response_model=ModernizationOut)
def modernization_status(request: Request) -> ModernizationOut:
    return ModernizationOut(**coordinator(request.app).status())


@router.post("/modernization/pause", response_model=ModernizationOut)
def pause_modernization(request: Request) -> ModernizationOut:
    """Durable: no automatic classification or Arctic indexing restarts, including after a restart, until Resume."""
    return ModernizationOut(**coordinator(request.app).pause())


@router.post("/modernization/resume", response_model=ModernizationOut)
def resume_modernization(request: Request) -> ModernizationOut:
    return ModernizationOut(**coordinator(request.app).resume())
