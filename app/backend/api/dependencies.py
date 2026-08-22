"""Shared FastAPI dependencies for the Callosum API routers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import Engine

from app.backend import app_settings
from app.backend.embeddings.models import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_NORMALIZATION,
    EmbeddingModel,
)
from app.backend.summarization.verification import DEFAULT_NLI_MODEL, StanceScorer, SupportScorer

if TYPE_CHECKING:
    from integrations.gemini.generator import LLMConfig


def get_connection(request: Request):
    engine: Engine = request.app.state.engine
    with engine.connect() as conn:
        yield conn


def get_engine(request: Request) -> Engine:
    """The app engine, for short mutating handlers that wrap their read+write unit in ``run_write`` (transaction-level
    retry on a transient SQLite writer lock) instead of taking a single ``get_connection`` connection."""
    return request.app.state.engine


def resolve_llm_config(app: FastAPI) -> LLMConfig:
    """Resolve current provider settings with this app's reusable client runtime attached."""
    from integrations.gemini.generator import LLMConfig

    return LLMConfig.from_environment(provider_runtime=app.state.provider_client_runtime)


def resolve_embedding_model(
    app: FastAPI,
    *,
    name: str = DEFAULT_EMBEDDING_MODEL,
    version: str | None = None,
    normalization: str = DEFAULT_NORMALIZATION,
    batch_size: int = 32,
    local_files_only: bool = False,
    revision: str | None = None,
    device: str | None = None,
    backend: str = "torch",
) -> EmbeddingModel:
    """Explicit injection wins; otherwise resolve the app-owned compatible wrapper/runtime."""
    injected = getattr(app.state, "embedding_model", None)
    if injected is not None:
        return injected
    return app.state.model_runtime_registry.get_embedding_model(
        name=name,
        version=version,
        normalization=normalization,
        batch_size=batch_size,
        local_files_only=local_files_only,
        revision=revision,
        device=device,
        backend=backend,
    )


def resolve_support_scorer(
    app: FastAPI,
    *,
    embedding_model: EmbeddingModel,
    model_name: str = DEFAULT_NLI_MODEL,
    local_files_only: bool = False,
) -> SupportScorer:
    """Resolve synthesis support semantics over the app's shared NLI runtime."""
    injected = getattr(app.state, "support_scorer", None)
    if injected is not None:
        return injected
    return app.state.model_runtime_registry.get_support_scorer(
        embedding_model=embedding_model,
        model_name=model_name,
        local_files_only=local_files_only,
    )


def resolve_stance_scorer(
    app: FastAPI,
    *,
    model_name: str = DEFAULT_NLI_MODEL,
    local_files_only: bool = False,
) -> StanceScorer:
    """Resolve feature-specific stance semantics over the app's shared NLI runtime."""
    injected = getattr(app.state, "stance_scorer", None)
    if injected is not None:
        return injected
    return app.state.model_runtime_registry.get_stance_scorer(
        model_name=model_name,
        local_files_only=local_files_only,
    )


def require_superuser() -> None:
    """403s unless the currently signed-in identity (the single-slot ORCID session, inc 195) is a verified
    superuser. A reusable gate for any endpoint not yet proven safe for general release — inc 195 deferred
    what the flag gates; this is the mechanism, applied first to `GET /diagnostics`."""
    if not app_settings.oauth_account_status()["is_superuser"]:
        raise HTTPException(status_code=403, detail="Superuser access required")
