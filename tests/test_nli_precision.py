"""Inc 637: DeBERTa is loaded and verified in float32 on every CrossEncoder construction path.

The pinned DeBERTa checkpoint stores float16 weights and transformers 5 loads a checkpoint's own precision by default,
so the packaged runtime ran DeBERTa in float16 (P1b run 41948518913) while G1/G2 measured float32. These tests are
model-free: a recording stand-in replaces ``sentence_transformers.CrossEncoder``, and the one test of the real pinned
constructor builds a tiny random checkpoint in a temporary directory. No real checkpoint is downloaded or loaded.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from app.backend import model_runtime  # noqa: E402
from app.backend.api.dependencies import resolve_support_scorer  # noqa: E402
from app.backend.model_runtime import (  # noqa: E402
    PINNED_MODEL_REVISIONS,
    REQUIRED_INFERENCE_DTYPES,
    ModelPrecisionError,
    ModelRuntimeRegistry,
    floating_point_dtypes,
    load_cross_encoder,
    require_floating_point_dtype,
)
from app.backend.summarization.nli_profiles import (  # noqa: E402
    BASELINE_NLI_PROFILE_KEY,
    DEBERTA_NLI_PROFILE_KEY,
    NLI_PROFILES,
    verification_nli_provenance,
)
from app.backend.summarization.stance import NLIStanceScorer  # noqa: E402
from app.backend.summarization.verification import NLISupportScorer, VerificationConfig  # noqa: E402

DEBERTA = NLI_PROFILES[DEBERTA_NLI_PROFILE_KEY]
MINILM2 = NLI_PROFILES[BASELINE_NLI_PROFILE_KEY]


class DebertaV2TokenizerFast:  # name-only stand-in: the label/architecture/tokenizer contract reads the class name
    pass


class _Weights(torch.nn.Module):
    def __init__(self, dtype, buffer_dtype=torch.int64) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(4, 3).to(dtype)
        self.register_buffer("position_ids", torch.arange(4).to(buffer_dtype), persistent=False)


class FakeCrossEncoder(torch.nn.Module):
    """Stands in for the pinned ``CrossEncoder``: records its arguments and honours ``model_kwargs["dtype"]`` unless
    ``ignore_dtype`` (an installed library that silently drops the argument and keeps the checkpoint's float16)."""

    calls: list[dict] = []
    checkpoint_dtype = torch.float16
    ignore_dtype = False
    buffer_dtype = torch.int64

    def __init__(self, model_name, **kwargs) -> None:
        super().__init__()
        type(self).calls.append({"model_name": model_name, **kwargs})
        requested = (kwargs.get("model_kwargs") or {}).get("dtype")
        dtype = self.checkpoint_dtype if requested is None or self.ignore_dtype else requested
        self.weights = _Weights(dtype, self.buffer_dtype)
        deberta = "DeBERTa" in model_name
        labels = {0: "entailment", 1: "neutral", 2: "contradiction"} if deberta else MINILM2.id2label
        self.config = SimpleNamespace(id2label=labels, model_type="deberta-v2" if deberta else "bert")
        self.tokenizer = DebertaV2TokenizerFast()

    @property
    def model(self):  # the HF model the label contract reads, as CrossEncoder.model is
        return SimpleNamespace(config=self.config)

    def predict(self, pairs, apply_softmax=True):
        return [[0.9, 0.06, 0.04] for _ in pairs]


@pytest.fixture
def fake_ce(monkeypatch: pytest.MonkeyPatch):
    import sentence_transformers

    class Fake(FakeCrossEncoder):
        calls: list[dict] = []

    monkeypatch.setattr(sentence_transformers, "CrossEncoder", Fake)
    return Fake


def _load(name: str, backend: str = "torch"):
    return load_cross_encoder(
        name, revision=PINNED_MODEL_REVISIONS.get(name), device=None, local_files_only=True, backend=backend
    )


# 1-2: float32 is requested explicitly, through the from_pretrained argument of both pinned transformers lines
def test_deberta_requests_float32_through_model_kwargs(fake_ce) -> None:
    assert REQUIRED_INFERENCE_DTYPES == {DEBERTA.model_name: "float32"}
    _load(DEBERTA.model_name)
    (call,) = fake_ce.calls
    assert call["model_kwargs"] == {"use_safetensors": True, "dtype": torch.float32}
    assert "torch_dtype" not in call["model_kwargs"]  # the deprecated alias is never relied on
    assert call["revision"] == DEBERTA.revision and call["local_files_only"] is True and call["backend"] == "torch"


# 3-4: the constructed model is inspected, and float32 is accepted
def test_loaded_float32_parameters_are_accepted(fake_ce) -> None:
    model = _load(DEBERTA.model_name)
    report = floating_point_dtypes(model)
    assert report == {"parameters": {"float32": 2}, "floating_buffers": {}, "other_buffers": {"int64": 1}}


# 5-6: float16 and any other floating dtype are refused
@pytest.mark.parametrize("dtype", [torch.float16, torch.bfloat16, torch.float64])
def test_wrong_parameter_dtype_is_refused(dtype) -> None:
    with pytest.raises(ModelPrecisionError, match=str(dtype).removeprefix("torch.")):
        require_floating_point_dtype(_Weights(dtype), "float32", model_name="m")


def test_float16_floating_buffer_is_refused_while_integer_buffers_are_ignored() -> None:
    require_floating_point_dtype(_Weights(torch.float32, torch.int64), "float32", model_name="m")
    require_floating_point_dtype(_Weights(torch.float32, torch.bool), "float32", model_name="m")
    with pytest.raises(ModelPrecisionError, match="floating_buffers"):
        require_floating_point_dtype(_Weights(torch.float32, torch.float16), "float32", model_name="m")


def test_mixed_parameter_dtypes_are_refused() -> None:
    model = _Weights(torch.float32)
    model.extra = torch.nn.Linear(2, 2).to(torch.float16)
    with pytest.raises(ModelPrecisionError, match="float16"):
        require_floating_point_dtype(model, "float32", model_name="m")


# 7: missing or unreadable dtype information fails closed
class _NoDtype:
    def named_parameters(self):
        return [("w", object())]

    def named_buffers(self):
        return []


class _Raises:
    def named_parameters(self):
        raise RuntimeError("meta device")

    def named_buffers(self):
        return []


@pytest.mark.parametrize(
    "model",
    [object(), SimpleNamespace(predict=lambda pairs: []), _NoDtype(), _Raises(), torch.nn.Module()],
    ids=["no-tensors-api", "predict-only", "tensor-without-dtype", "enumeration-raises", "no-parameters"],
)
def test_unknown_precision_fails_closed(model) -> None:
    with pytest.raises(ModelPrecisionError):
        require_floating_point_dtype(model, "float32", model_name="m")


# 8: an installed library that ignores the argument is caught on the loaded model
def test_ignored_dtype_argument_is_detected(fake_ce) -> None:
    fake_ce.ignore_dtype = True
    with pytest.raises(ModelPrecisionError, match="float16"):
        _load(DEBERTA.model_name)
    assert fake_ce.calls[0]["model_kwargs"]["dtype"] is torch.float32  # it was requested, and still refused


def test_non_torch_backend_is_refused_before_construction(fake_ce) -> None:
    with pytest.raises(ModelPrecisionError, match="torch backend"):
        _load(DEBERTA.model_name, backend="onnx")
    assert fake_ce.calls == []


# 13: MiniLM2 keeps its legacy load, byte for byte
def test_minilm2_load_is_unchanged(fake_ce) -> None:
    model = _load(MINILM2.model_name)
    (call,) = fake_ce.calls
    assert call["model_kwargs"] == {"use_safetensors": True}
    assert floating_point_dtypes(model)["parameters"] == {"float16": 2}  # checkpoint precision, never checked


# 14: the managed runtime and both scorers' direct loaders enforce the same contract
def _registry_load(name):
    return ModelRuntimeRegistry().get_nli_runtime(model_name=name, revision=PINNED_MODEL_REVISIONS.get(name)).get()


def _support_direct(name):
    return NLISupportScorer(model_name=name, revision=PINNED_MODEL_REVISIONS.get(name))._load_model()  # noqa: SLF001


def _stance_direct(name):
    return NLIStanceScorer(model_name=name, revision=PINNED_MODEL_REVISIONS.get(name))._load_model()  # noqa: SLF001


@pytest.mark.parametrize(
    "path", [_registry_load, _support_direct, _stance_direct], ids=["managed", "support", "stance"]
)
def test_every_construction_path_enforces_the_same_precision(fake_ce, path) -> None:
    model = path(DEBERTA.model_name)
    assert floating_point_dtypes(model)["parameters"] == {"float32": 2}
    path(MINILM2.model_name)
    assert [c["model_kwargs"] for c in fake_ce.calls] == [
        {"use_safetensors": True, "dtype": torch.float32},
        {"use_safetensors": True},
    ]
    fake_ce.ignore_dtype = True
    with pytest.raises(ModelPrecisionError):
        path(DEBERTA.model_name)


def test_failed_managed_load_stays_retryable_and_never_resident(fake_ce) -> None:
    fake_ce.ignore_dtype = True
    runtime = ModelRuntimeRegistry().get_nli_runtime(model_name=DEBERTA.model_name, revision=DEBERTA.revision)
    with pytest.raises(ModelPrecisionError):
        runtime.get()
    assert runtime.loaded_model is None and runtime.load_count == 0
    fake_ce.ignore_dtype = False
    assert floating_point_dtypes(runtime.get())["parameters"] == {"float32": 2}


# 12: identity, label order, thresholds and provenance are unchanged; scores are read in DeBERTa's order
def test_identity_labels_thresholds_and_provenance_are_unchanged(fake_ce) -> None:
    assert DEBERTA.revision == "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
    assert DEBERTA.id2label == {0: "entailment", 1: "neutral", 2: "contradiction"}
    config = VerificationConfig()
    assert (config.retrieval_threshold, config.quote_threshold, config.support_threshold) == (0.7, 1.0, 0.55)
    assert config.contradiction_threshold == 0.55
    assert verification_nli_provenance(DEBERTA) == {
        "verification_nli": {
            "profile": DEBERTA_NLI_PROFILE_KEY,
            "model_name": DEBERTA.model_name,
            "revision": DEBERTA.revision,
            "thresholds_calibrated_on": MINILM2.model_name,
            "embedding_fallback": False,
        }
    }
    app = SimpleNamespace(state=SimpleNamespace(model_runtime_registry=ModelRuntimeRegistry()))
    scorer = resolve_support_scorer(app, nli_profile=DEBERTA)  # real registry, real loader, contract checked
    assert scorer.support_and_contradiction_many([("p", "h")]) == [(0.9, 0.04)]  # entailment 0, contradiction 2
    assert fake_ce.calls[0]["model_kwargs"]["dtype"] is torch.float32


# 9-11: through the real synthesis verifier resolution
def _env(db_url: str, gates):
    from tests.test_verifier_resolution import MINILM, Env

    env = Env(db_url, gates=gates)
    env.app.state.nli_support_scorers = {MINILM: env.minilm}  # DeBERTa goes through the real registry and loader
    env.app.state.support_scorer = None
    env.app.state.model_runtime_registry = ModelRuntimeRegistry()
    return env


def test_explicit_deberta_in_wrong_precision_produces_no_result_and_no_substitute(temp_db_url: str, fake_ce) -> None:
    env = _env(temp_db_url, gates=None)
    fake_ce.ignore_dtype = True
    refused = env.client.put("/verification-nli-profiles/active", json={"key": DEBERTA_NLI_PROFILE_KEY})
    assert refused.status_code == 409 and "float32" in refused.json()["detail"]
    env.prefer(DEBERTA_NLI_PROFILE_KEY)  # chosen earlier; the checkpoint now loads in the wrong precision
    before = env.summary_count()
    payload = env.ask()
    assert payload["status"] == "error" and "Choose Automatic or MiniLM2" in payload["detail"]
    assert not env.minilm.calls and env.summary_count() == before


def test_explicit_deberta_in_float32_verifies(temp_db_url: str, fake_ce) -> None:
    env = _env(temp_db_url, gates=None)
    assert env.client.put("/verification-nli-profiles/active", json={"key": DEBERTA_NLI_PROFILE_KEY}).status_code == 200
    payload = env.ask()
    assert payload["status"] == "done", payload
    assert env.nli(payload)["profile"] == DEBERTA_NLI_PROFILE_KEY and not env.minilm.calls


def test_automatic_selection_keeps_its_release_gate_behaviour(temp_db_url: str, fake_ce) -> None:
    from tests.test_verifier_resolution import ARMED

    env = _env(temp_db_url, gates=None)  # production gates: unarmed, DeBERTa is never even constructed
    assert env.nli(env.ask())["fallback_reason"] == "not_qualified" and fake_ce.calls == []
    env.app.state.deberta_release_gates = ARMED  # armed (test only) but wrong precision: MiniLM2, not_verified
    fake_ce.ignore_dtype = True
    payload = env.ask()
    assert payload["status"] == "done" and env.minilm.calls and len(fake_ce.calls) == 1
    assert env.nli(payload)["fallback_reason"] == "not_verified"


# The real pinned constructor (sentence-transformers 5.6.1 / transformers as locked) on a tiny float16 checkpoint
@pytest.fixture(scope="module")
def tiny_float16_checkpoint(tmp_path_factory):
    transformers = pytest.importorskip("transformers")
    pytest.importorskip("sentence_transformers")
    root = tmp_path_factory.mktemp("tiny-fp16-nli")
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "the", "drug", "reduced", "increased", "mortality"]
    (root / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
    labels = {0: "entailment", 1: "neutral", 2: "contradiction"}
    config = transformers.BertConfig(
        vocab_size=len(vocab),
        hidden_size=8,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=16,
        max_position_embeddings=32,
        num_labels=3,
        id2label=labels,
        label2id={v: k for k, v in labels.items()},
    )
    torch.manual_seed(0)
    transformers.BertForSequenceClassification(config).half().save_pretrained(root, safe_serialization=True)
    transformers.BertTokenizerFast(vocab_file=str(root / "vocab.txt")).save_pretrained(root)
    return str(root)


def _fp16_representable(values) -> bool:
    return all(float(torch.tensor(v, dtype=torch.float16)) == v for v in values)


def test_real_constructor_loads_a_float16_checkpoint_in_float32_only_when_required(
    tiny_float16_checkpoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pairs = [("the drug reduced mortality", "the drug increased mortality")]
    legacy = load_cross_encoder(
        tiny_float16_checkpoint, revision=None, device="cpu", local_files_only=True, backend="torch"
    )
    assert floating_point_dtypes(legacy)["parameters"] == {"float16": len(list(legacy.parameters()))}  # the defect
    # predict() hands back float32 arrays even here, so an output dtype is never evidence of float32 inference
    legacy_scores = legacy.predict(pairs, apply_softmax=True)
    assert str(legacy_scores.dtype) == "float32" and _fp16_representable(legacy_scores.ravel().tolist())

    monkeypatch.setitem(model_runtime.REQUIRED_INFERENCE_DTYPES, tiny_float16_checkpoint, "float32")
    fixed = load_cross_encoder(
        tiny_float16_checkpoint, revision=None, device="cpu", local_files_only=True, backend="torch"
    )
    report = require_floating_point_dtype(fixed, "float32", model_name="tiny")
    assert set(report["parameters"]) == {"float32"} and report["floating_buffers"] == {}
    assert set(report["other_buffers"]) == {"int64"}  # position and token-type ids
    assert not _fp16_representable(fixed.predict(pairs, apply_softmax=True).ravel().tolist())
