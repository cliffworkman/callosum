"""Application-owned lifecycle management for local transformer runtimes.

The registry owns loaded model objects, not feature semantics.  Embedding and NLI
wrappers remain separate where their normalization, thresholds, or probability
interpretation differ, while compatible wrappers share the same underlying weights.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock, RLock
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ModelRuntimeIdentity:
    """Settings that materially determine one loaded transformer runtime."""

    family: str
    model_name: str
    revision: str | None = None
    device: str | None = None
    local_files_only: bool = False
    backend: str = "torch"


class ManagedModelRuntime:
    """One lazily loaded model plus independent load and inference guards."""

    def __init__(self, identity: ModelRuntimeIdentity, factory: Callable[[], object]) -> None:
        self.identity = identity
        self._factory = factory
        self._model: object | None = None
        self._load_lock = Lock()
        self._inference_lock = Lock()
        self.load_attempts = 0
        self.load_count = 0

    def get(self) -> object:
        model = self._model
        if model is not None:
            return model
        with self._load_lock:
            if self._model is None:
                self.load_attempts += 1
                # Assignment occurs only after a successful construction.  A failed
                # first load therefore leaves the entry retryable.
                model = self._factory()
                self._model = model
                self.load_count += 1
            return self._model

    def run(self, operation: Callable[[object], T]) -> T:
        """Run only model inference under the per-identity safety lock."""
        model = self.get()
        with self._inference_lock:
            return operation(model)

    @property
    def loaded_model(self) -> object | None:
        """Expose identity for diagnostics/tests without triggering a load."""
        return self._model

    def close(self) -> None:
        """Release this app's reference after in-flight loading/inference finishes."""
        with self._load_lock:
            with self._inference_lock:
                model, self._model = self._model, None
                close = getattr(model, "close", None)
                if callable(close):
                    close()


class ModelRuntimeRegistry:
    """Per-FastAPI-application registry for embedding and CrossEncoder runtimes."""

    def __init__(
        self,
        *,
        sentence_transformer_factory: Callable[[ModelRuntimeIdentity], object] | None = None,
        cross_encoder_factory: Callable[[ModelRuntimeIdentity], object] | None = None,
    ) -> None:
        self._sentence_transformer_factory = sentence_transformer_factory or _load_sentence_transformer
        self._cross_encoder_factory = cross_encoder_factory or _load_cross_encoder
        self._entries: dict[ModelRuntimeIdentity, ManagedModelRuntime] = {}
        self._embedding_models: dict[tuple[object, ...], object] = {}
        self._support_scorers: dict[tuple[object, ...], object] = {}
        self._stance_scorers: dict[ModelRuntimeIdentity, object] = {}
        self._registry_lock = RLock()
        self._closed = False

    def get_embedding_model(
        self,
        *,
        name: str,
        version: str | None = None,
        normalization: str,
        batch_size: int = 32,
        local_files_only: bool = False,
        revision: str | None = None,
        device: str | None = None,
        backend: str = "torch",
    ) -> object:
        identity = ModelRuntimeIdentity(
            family="sentence-transformer",
            model_name=name,
            revision=revision,
            device=device,
            local_files_only=local_files_only,
            backend=backend,
        )
        key = (identity, version or name, normalization, batch_size)
        with self._registry_lock:
            self._ensure_open()
            model = self._embedding_models.get(key)
            if model is None:
                from app.backend.embeddings.models import SentenceTransformerEmbeddingModel

                runtime = self._runtime(identity, self._sentence_transformer_factory)
                model = SentenceTransformerEmbeddingModel(
                    name=name,
                    version=version,
                    normalization=normalization,
                    batch_size=batch_size,
                    local_files_only=local_files_only,
                    revision=revision,
                    device=device,
                    backend=backend,
                    _runtime=runtime,
                )
                self._embedding_models[key] = model
            return model

    def get_nli_runtime(
        self,
        *,
        model_name: str,
        local_files_only: bool = False,
        revision: str | None = None,
        device: str | None = None,
        backend: str = "torch",
    ) -> ManagedModelRuntime:
        identity = ModelRuntimeIdentity(
            family="cross-encoder",
            model_name=model_name,
            revision=revision,
            device=device,
            local_files_only=local_files_only,
            backend=backend,
        )
        with self._registry_lock:
            self._ensure_open()
            return self._runtime(identity, self._cross_encoder_factory)

    def get_support_scorer(
        self,
        *,
        embedding_model: object,
        model_name: str,
        local_files_only: bool = False,
        revision: str | None = None,
        device: str | None = None,
        backend: str = "torch",
    ) -> object:
        runtime = self.get_nli_runtime(
            model_name=model_name,
            local_files_only=local_files_only,
            revision=revision,
            device=device,
            backend=backend,
        )
        key = (runtime.identity, id(embedding_model))
        with self._registry_lock:
            scorer = self._support_scorers.get(key)
            if scorer is None:
                from app.backend.summarization.verification import EmbeddingSupportScorer, NLISupportScorer

                scorer = NLISupportScorer(
                    model_name=model_name,
                    local_files_only=local_files_only,
                    revision=revision,
                    device=device,
                    backend=backend,
                    fallback_scorer=EmbeddingSupportScorer(embedding_model),  # type: ignore[arg-type]
                    _runtime=runtime,
                )
                self._support_scorers[key] = scorer
            return scorer

    def get_stance_scorer(
        self,
        *,
        model_name: str,
        local_files_only: bool = False,
        revision: str | None = None,
        device: str | None = None,
        backend: str = "torch",
    ) -> object:
        runtime = self.get_nli_runtime(
            model_name=model_name,
            local_files_only=local_files_only,
            revision=revision,
            device=device,
            backend=backend,
        )
        with self._registry_lock:
            scorer = self._stance_scorers.get(runtime.identity)
            if scorer is None:
                from app.backend.summarization.verification import NLIStanceScorer

                scorer = NLIStanceScorer(
                    model_name=model_name,
                    local_files_only=local_files_only,
                    revision=revision,
                    device=device,
                    backend=backend,
                    _runtime=runtime,
                )
                self._stance_scorers[runtime.identity] = scorer
            return scorer

    def runtime_entries(self) -> tuple[ManagedModelRuntime, ...]:
        """Stable snapshot for lifecycle diagnostics and benchmark assertions."""
        with self._registry_lock:
            return tuple(self._entries.values())

    def close(self) -> None:
        with self._registry_lock:
            if self._closed:
                return
            self._closed = True
            entries = tuple(self._entries.values())
            self._embedding_models.clear()
            self._support_scorers.clear()
            self._stance_scorers.clear()
            self._entries.clear()
        for entry in entries:
            entry.close()

    def _runtime(
        self,
        identity: ModelRuntimeIdentity,
        factory: Callable[[ModelRuntimeIdentity], object],
    ) -> ManagedModelRuntime:
        runtime = self._entries.get(identity)
        if runtime is None:
            runtime = ManagedModelRuntime(identity, lambda: factory(identity))
            self._entries[identity] = runtime
        return runtime

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Model runtime registry is closed")


def _load_sentence_transformer(identity: ModelRuntimeIdentity) -> object:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        identity.model_name,
        revision=identity.revision,
        device=identity.device,
        local_files_only=identity.local_files_only,
        backend=identity.backend,
    )


def _load_cross_encoder(identity: ModelRuntimeIdentity) -> object:
    from sentence_transformers import CrossEncoder

    return CrossEncoder(
        identity.model_name,
        revision=identity.revision,
        device=identity.device,
        local_files_only=identity.local_files_only,
        backend=identity.backend,
    )
