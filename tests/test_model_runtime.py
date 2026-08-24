"""Application-scoped transformer runtime ownership, locking, and injection tests."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier, Lock

import pytest

from app.backend.api.app import create_app
from app.backend.api.dependencies import resolve_embedding_model, resolve_stance_scorer, resolve_support_scorer
from app.backend.api.routers.citation_context import _stance_scorer as citation_context_scorer
from app.backend.api.routers.citation_suggest import _suggest_model, _suggest_stance_scorer
from app.backend.api.routers.critical_review import _cr_deps
from app.backend.api.routers.summaries import _embedding_model as summary_embedding_model
from app.backend.embeddings.models import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_NORMALIZATION,
    SentenceTransformerEmbeddingModel,
)
from app.backend.model_runtime import ModelRuntimeIdentity, ModelRuntimeRegistry
from app.backend.summarization.verification import DEFAULT_NLI_MODEL, NLIStanceScorer, NLISupportScorer


class _Vector(list[float]):
    def tolist(self) -> list[float]:
        return list(self)


class _EmbeddingRuntime:
    def get_sentence_embedding_dimension(self) -> int:
        return 2

    def encode(self, texts: list[str], **_: object) -> list[_Vector]:
        return [_Vector([float(len(text)), float(index + 1)]) for index, text in enumerate(texts)]


class _CrossEncoderRuntime:
    def predict(self, pairs: list[tuple[str, str]], **_: object) -> list[list[float]]:
        return [[0.1 + index / 1000, 0.8 - index / 1000, 0.1] for index, _pair in enumerate(pairs)]


def _registry(*, embed_loads: list[object], nli_loads: list[object]) -> ModelRuntimeRegistry:
    def load_embedding(_identity: ModelRuntimeIdentity) -> object:
        model = _EmbeddingRuntime()
        embed_loads.append(model)
        return model

    def load_nli(_identity: ModelRuntimeIdentity) -> object:
        model = _CrossEncoderRuntime()
        nli_loads.append(model)
        return model

    return ModelRuntimeRegistry(
        sentence_transformer_factory=load_embedding,
        cross_encoder_factory=load_nli,
    )


def test_one_load_and_cross_feature_runtime_reuse() -> None:
    embed_loads: list[object] = []
    nli_loads: list[object] = []
    registry = _registry(embed_loads=embed_loads, nli_loads=nli_loads)
    app = create_app(db_url="sqlite://", model_runtime_registry=registry)

    summary_model = summary_embedding_model(app)
    assert summary_model is _suggest_model(_Request(app))
    critical_model, _store, critical_stance = _cr_deps(app)
    assert critical_model is summary_model
    assert critical_stance is citation_context_scorer(app)
    assert critical_stance is _suggest_stance_scorer(_Request(app))

    support = resolve_support_scorer(app, embedding_model=summary_model)
    summary_model.encode_texts(["first"])
    summary_model.encode_texts(["second"])
    critical_stance.classify_stance(sentence="claim", passage="passage")
    support.score(sentence="claim", passage="passage")

    assert len(embed_loads) == 1
    assert len(nli_loads) == 1
    assert critical_stance._runtime is support._runtime  # type: ignore[attr-defined]
    assert critical_stance._runtime.loaded_model is nli_loads[0]  # type: ignore[attr-defined]


def test_distinct_runtime_identities_do_not_collapse() -> None:
    loads: list[object] = []
    registry = ModelRuntimeRegistry(sentence_transformer_factory=lambda _identity: loads.append(object()) or loads[-1])
    common = dict(version="v1", normalization=DEFAULT_NORMALIZATION)
    models = [
        registry.get_embedding_model(name="model-a", device="cpu", **common),
        registry.get_embedding_model(name="model-b", device="cpu", **common),
        registry.get_embedding_model(name="model-a", device="cuda", **common),
        # A local_files_only=True request cannot reuse the local_files_only=False runtime already
        # resident at (model-a, cpu) above — see the asymmetric-reuse tests below — so this is a
        # 4th genuinely distinct runtime, not merely a distinct dataclass identity.
        registry.get_embedding_model(name="model-a", device="cpu", local_files_only=True, **common),
    ]
    runtimes = [model._runtime for model in models]  # type: ignore[attr-defined]
    assert len({id(runtime) for runtime in runtimes}) == 4


def test_local_files_only_true_then_false_reuses_the_offline_safe_runtime() -> None:
    """``local_files_only`` only controls first-load fetch behavior, not what gets loaded. Once a
    local_files_only=True (offline-safe) runtime is resident, a later local_files_only=False request for the
    same weights/device/backend may safely reuse it — no need for a redundant permanently-resident second copy,
    since network access is merely PERMITTED for that caller, not required."""
    loads: list[object] = []
    registry = ModelRuntimeRegistry(cross_encoder_factory=lambda _identity: loads.append(object()) or loads[-1])

    local_only = registry.get_nli_runtime(model_name=DEFAULT_NLI_MODEL, local_files_only=True)
    network_allowed = registry.get_nli_runtime(model_name=DEFAULT_NLI_MODEL, local_files_only=False)

    assert network_allowed is local_only
    assert len(loads) == 0
    network_allowed.get()
    assert local_only.loaded_model is loads[0]
    assert len(loads) == 1


def test_local_files_only_false_then_true_never_downgrades_the_offline_guarantee() -> None:
    """The reverse order is NOT safe to collapse: a local_files_only=False caller may have fetched weights over
    the network, so a LATER local_files_only=True caller — an explicit "must not touch the network" guarantee —
    must never silently inherit that possibly-network-fetched instance. It gets its own separate runtime."""
    loads: list[object] = []
    registry = ModelRuntimeRegistry(cross_encoder_factory=lambda _identity: loads.append(object()) or loads[-1])

    network_allowed = registry.get_nli_runtime(model_name=DEFAULT_NLI_MODEL, local_files_only=False)
    local_only = registry.get_nli_runtime(model_name=DEFAULT_NLI_MODEL, local_files_only=True)

    assert network_allowed is not local_only
    network_allowed.get()
    local_only.get()
    assert len(loads) == 2

    # A subsequent False request may reuse either already-resident runtime (both are safe for it); the
    # implementation prefers the offline-safe slot once one exists, rather than constructing a third copy.
    still_network_allowed = registry.get_nli_runtime(model_name=DEFAULT_NLI_MODEL, local_files_only=False)
    assert still_network_allowed is local_only
    assert len(loads) == 2


def test_explicit_dependency_injection_wins() -> None:
    embed_loads: list[object] = []
    nli_loads: list[object] = []
    registry = _registry(embed_loads=embed_loads, nli_loads=nli_loads)
    fake_embedding = object()
    fake_support = object()
    fake_stance = object()
    app = create_app(
        db_url="sqlite://",
        embedding_model=fake_embedding,  # type: ignore[arg-type]
        support_scorer=fake_support,  # type: ignore[arg-type]
        stance_scorer=fake_stance,  # type: ignore[arg-type]
        model_runtime_registry=registry,
    )

    assert resolve_embedding_model(app) is fake_embedding
    assert resolve_support_scorer(app, embedding_model=fake_embedding) is fake_support  # type: ignore[arg-type]
    assert resolve_stance_scorer(app) is fake_stance
    assert embed_loads == [] and nli_loads == []


def test_simultaneous_first_use_constructs_once() -> None:
    construction_count = 0
    count_lock = Lock()

    def factory(_identity: ModelRuntimeIdentity) -> object:
        nonlocal construction_count
        with count_lock:
            construction_count += 1
        time.sleep(0.05)
        return object()

    registry = ModelRuntimeRegistry(cross_encoder_factory=factory)
    runtime = registry.get_nli_runtime(model_name=DEFAULT_NLI_MODEL)
    with ThreadPoolExecutor(max_workers=8) as pool:
        models = list(pool.map(lambda _index: runtime.get(), range(8)))

    assert construction_count == 1
    assert runtime.load_attempts == runtime.load_count == 1
    assert len({id(model) for model in models}) == 1


def test_failed_load_is_retryable() -> None:
    attempts = 0

    def factory(_identity: ModelRuntimeIdentity) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("first load failed")
        return object()

    runtime = ModelRuntimeRegistry(cross_encoder_factory=factory).get_nli_runtime(model_name=DEFAULT_NLI_MODEL)
    with pytest.raises(RuntimeError, match="first load failed"):
        runtime.get()
    loaded = runtime.get()

    assert loaded is runtime.loaded_model
    assert runtime.load_attempts == 2
    assert runtime.load_count == 1


def test_inference_is_serialized_per_identity_but_not_globally() -> None:
    registry = ModelRuntimeRegistry(cross_encoder_factory=lambda _identity: object())
    same_runtime = registry.get_nli_runtime(model_name="same")
    active = 0
    max_active = 0
    active_lock = Lock()

    def guarded(_model: object) -> None:
        nonlocal active, max_active
        with active_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with active_lock:
            active -= 1

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _index: same_runtime.run(guarded), range(4)))
    assert max_active == 1

    barrier = Barrier(2)
    first = registry.get_nli_runtime(model_name="first")
    second = registry.get_nli_runtime(model_name="second")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(runtime.run, lambda _model: barrier.wait(timeout=1)) for runtime in (first, second)]
        assert [future.result(timeout=2) for future in futures]


def test_separate_apps_own_separate_registries() -> None:
    first = create_app(db_url="sqlite://")
    second = create_app(db_url="sqlite://")
    assert first.state.model_runtime_registry is not second.state.model_runtime_registry
    assert resolve_embedding_model(first) is not resolve_embedding_model(second)


def test_registry_close_releases_models_and_prevents_new_resolution() -> None:
    embed_loads: list[object] = []
    registry = _registry(embed_loads=embed_loads, nli_loads=[])
    model = registry.get_embedding_model(
        name=DEFAULT_EMBEDDING_MODEL,
        normalization=DEFAULT_NORMALIZATION,
    )
    model.encode_texts(["load me"])
    runtime = model._runtime

    registry.close()

    assert runtime.loaded_model is None
    with pytest.raises(RuntimeError, match="closed"):
        registry.get_embedding_model(name=DEFAULT_EMBEDDING_MODEL, normalization=DEFAULT_NORMALIZATION)


def test_managed_and_standalone_scorers_are_semantically_equivalent() -> None:
    runtime_model = _CrossEncoderRuntime()
    registry = ModelRuntimeRegistry(cross_encoder_factory=lambda _identity: runtime_model)
    managed_support = registry.get_support_scorer(
        embedding_model=_FakeEmbeddingModel(),
        model_name=DEFAULT_NLI_MODEL,
    )
    managed_stance = registry.get_stance_scorer(model_name=DEFAULT_NLI_MODEL)
    standalone_support = NLISupportScorer(_loader=lambda: runtime_model)
    standalone_stance = NLIStanceScorer(_loader=lambda: runtime_model)
    pairs = [("passage one", "claim one"), ("passage two", "claim two")]

    assert managed_support.support_and_contradiction_many(pairs) == standalone_support.support_and_contradiction_many(
        pairs
    )
    stance_pairs = [(claim, passage) for passage, claim in pairs]
    assert managed_stance.classify_stances(stance_pairs) == standalone_stance.classify_stances(stance_pairs)


def test_managed_and_standalone_embeddings_are_numerically_equivalent() -> None:
    runtime_model = _EmbeddingRuntime()
    registry = ModelRuntimeRegistry(sentence_transformer_factory=lambda _identity: runtime_model)
    managed = registry.get_embedding_model(
        name=DEFAULT_EMBEDDING_MODEL,
        normalization=DEFAULT_NORMALIZATION,
    )
    standalone = SentenceTransformerEmbeddingModel()
    standalone._model = runtime_model
    texts = ["Repeated text", "Repeated text", "A distinct claim"]

    managed_vectors = managed.encode_texts(texts)
    standalone_vectors = standalone.encode_texts(texts)

    assert managed_vectors == standalone_vectors
    assert (
        max(
            abs(left - right)
            for a, b in zip(managed_vectors, standalone_vectors, strict=True)
            for left, right in zip(a, b, strict=True)
        )
        == 0
    )


@dataclass
class _FakeEmbeddingModel:
    name: str = DEFAULT_EMBEDDING_MODEL
    version: str = DEFAULT_EMBEDDING_MODEL
    normalization: str = DEFAULT_NORMALIZATION
    dimension: int = 2

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]


@dataclass
class _Request:
    app: object
