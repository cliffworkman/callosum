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
from app.backend.embeddings.profiles import BASELINE_PROFILE_KEY, EmbeddingProfile
from app.backend.model_provisioning import local_files_only_for
from app.backend.model_runtime import PINNED_MODEL_REVISIONS
from app.backend.summarization.nli_profiles import NliProfile, verify_nli_checkpoint
from app.backend.summarization.verification import DEFAULT_NLI_MODEL, NLISupportScorer, StanceScorer, SupportScorer

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
    from app.backend import providers_store

    if providers_store.active_provider()["id"] == "managed_local":
        from app.backend.llm.managed_local import resolve_managed_local_provider

        return resolve_managed_local_provider(app.state.provider_client_runtime)
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
        revision=revision if revision is not None else PINNED_MODEL_REVISIONS.get(name),
        device=device,
        backend=backend,
    )


def resolve_profile_embedding_model(app: FastAPI, profile: EmbeddingProfile) -> EmbeddingModel:
    """The encoder for one embedding profile. The baseline resolves exactly like ``resolve_embedding_model`` (same
    wrapper, same stored identity); other profiles carry their full encoding contract. Tests inject per-profile
    fakes through ``app.state.profile_embedding_models``."""
    injected = (getattr(app.state, "profile_embedding_models", None) or {}).get(profile.key)
    if injected is not None:
        return injected
    if profile.key == BASELINE_PROFILE_KEY:
        return resolve_embedding_model(app)
    return app.state.model_runtime_registry.get_embedding_model(
        name=profile.model_name,
        version=profile.model_version,
        normalization=profile.normalization,
        revision=profile.revision,
        query_prefix=profile.query_prefix,
        document_prefix=profile.document_prefix,
        expected_pooling=profile.pooling,
        expected_max_seq_length=profile.max_seq_length,
        lazy_indexing=profile.lazy_indexing,
        profile_key=profile.key,
        local_files_only=local_files_only_for(profile.model_name),  # inc 615: offline once provisioned
    )


def resolve_support_scorer(
    app: FastAPI,
    *,
    model_name: str = DEFAULT_NLI_MODEL,
    local_files_only: bool = False,
    nli_profile: NliProfile | None = None,
) -> SupportScorer:
    """Resolve synthesis support semantics over the app's shared NLI runtime. A non-baseline ``nli_profile`` is
    loaded at its pinned revision and its label/architecture/tokenizer contract is verified before use. No profile
    carries an embedding fallback: an inference failure raises ``NLIInferenceError`` and fails the job."""
    injected = getattr(app.state, "support_scorer", None)
    if injected is not None:
        return injected
    registry = app.state.model_runtime_registry
    if nli_profile is not None and nli_profile.enforce_contract:
        # inc 615: a provisioned checkpoint loads offline; the MiniLM2 baseline path below is unchanged.
        local_files_only = local_files_only or local_files_only_for(nli_profile.model_name)
        runtime = registry.get_nli_runtime(
            model_name=nli_profile.model_name, revision=nli_profile.revision, local_files_only=local_files_only
        )
        runtime.run(lambda model: verify_nli_checkpoint(model, nli_profile))
        return NLISupportScorer(
            model_name=nli_profile.model_name,
            local_files_only=local_files_only,
            revision=nli_profile.revision,
            fallback_scorer=None,
            _runtime=runtime,
        )
    return registry.get_support_scorer(
        model_name=model_name,
        local_files_only=local_files_only,
        revision=PINNED_MODEL_REVISIONS.get(model_name),
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
        revision=PINNED_MODEL_REVISIONS.get(model_name),
    )


def require_superuser() -> None:
    """403s unless the currently signed-in identity (the single-slot ORCID session, inc 195) is a verified
    superuser. A reusable gate for any endpoint not yet proven safe for general release — inc 195 deferred
    what the flag gates; this is the mechanism, applied first to `GET /diagnostics`."""
    if not app_settings.oauth_account_status()["is_superuser"]:
        raise HTTPException(status_code=403, detail="Superuser access required")
