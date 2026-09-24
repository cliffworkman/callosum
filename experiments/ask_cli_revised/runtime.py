"""Runtime wiring: reuse production read/inference infrastructure against a DB copy.

Qwen (managed local) is REQUIRED for the intermediate stages — if it is not provisioned the experiment is
BLOCKED and says so; it is never silently replaced by a cloud provider. Gemini is resolved only for the
terminal-synthesis fork.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine

from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, DEFAULT_NORMALIZATION, EmbeddingModel
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.model_runtime import PINNED_MODEL_REVISIONS, ModelRuntimeRegistry
from app.backend.persistence.database import make_engine
from app.backend.provider_runtime import ProviderClientRuntime
from app.backend.summarization.verification import (
    LocalCitationVerifier,
    VerificationConfig,
    default_support_scorer,
)


class QwenUnavailableError(RuntimeError):
    """Managed-local Qwen is not provisioned. The experiment fails closed rather than using cloud."""


@dataclass
class ExperimentRuntime:
    engine: Engine
    model: EmbeddingModel
    vector_store: SQLiteVecVectorStore
    verifier: LocalCitationVerifier
    provider_runtime: ProviderClientRuntime
    qwen_config: object | None  # ManagedProviderConfig — None when no role is bound to managed-local Qwen
    gemini_config: object | None  # terminal only; None if no key
    registry: ModelRuntimeRegistry

    def close(self) -> None:
        try:
            self.provider_runtime.close()
        finally:
            try:
                self.registry.close()
            finally:
                self.engine.dispose()


def build_runtime(
    db_path: str | Path, *, want_gemini: bool = False, want_verifier: bool = True, want_qwen: bool = True
) -> ExperimentRuntime:
    """Construct the isolated runtime over ``db_path`` (a COPY). Raises QwenUnavailableError if Qwen is not
    provisioned (``CALLOSUM_APP_DATA_DIR`` + a live descriptor, e.g. via ``python tools/run_local_ai.py``).

    ``want_verifier=False`` skips the NLI CrossEncoder load (Run 0.5 calibration only needs the embedding
    model + Qwen config; loading the verifier is wasted memory and can OOM a constrained machine).
    ``want_qwen=False`` is for a topology that binds no role to managed-local Qwen (every worker is Ollama-native),
    so such an arm does not depend on a descriptor it never uses."""
    db_url = f"sqlite:///{Path(db_path).resolve().as_posix()}"
    engine = make_engine(db_url)
    registry = ModelRuntimeRegistry()
    provider_runtime = ProviderClientRuntime()
    model = registry.get_embedding_model(
        name=DEFAULT_EMBEDDING_MODEL,
        normalization=DEFAULT_NORMALIZATION,
        revision=PINNED_MODEL_REVISIONS.get(DEFAULT_EMBEDDING_MODEL),
    )
    vector_store = SQLiteVecVectorStore()
    verifier = None
    if want_verifier:
        support_scorer = default_support_scorer(model)
        verifier = LocalCitationVerifier(
            model=model, vector_store=vector_store, config=VerificationConfig(), support_scorer=support_scorer
        )

    qwen_config = _resolve_qwen(provider_runtime) if want_qwen else None
    gemini_config = _resolve_gemini(provider_runtime) if want_gemini else None

    return ExperimentRuntime(
        engine=engine,
        model=model,
        vector_store=vector_store,
        verifier=verifier,
        provider_runtime=provider_runtime,
        qwen_config=qwen_config,
        gemini_config=gemini_config,
        registry=registry,
    )


def _resolve_qwen(provider_runtime: ProviderClientRuntime):
    from app.backend.llm.managed_local import ManagedLocalTargetError, resolve_managed_local_provider

    try:
        return resolve_managed_local_provider(provider_runtime)
    except ManagedLocalTargetError as exc:
        raise QwenUnavailableError(
            "Managed-local Qwen is not provisioned (code: "
            f"{getattr(exc, 'code', exc)}). Start it with `python tools/run_local_ai.py` and set "
            "CALLOSUM_APP_DATA_DIR to its dev app-data dir, then re-run. The experiment does NOT fall back "
            "to a cloud provider for intermediate work."
        ) from exc


def _resolve_gemini(provider_runtime: ProviderClientRuntime):
    """Terminal-only Gemini config from the environment/BYOK. Returns None if no key is resolvable."""
    from app.backend.llm.providers import requires_egress
    from integrations.gemini.generator import LLMConfig

    config = LLMConfig.from_environment(provider_runtime=provider_runtime)
    if requires_egress(config) and not config.resolved_api_key():
        return None
    return config
