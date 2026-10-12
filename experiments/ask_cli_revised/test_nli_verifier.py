"""The selectable Ask NLI verifier: default untouched, DeBERTa labels/thresholds/device handled explicitly.

No test here loads a real model; the real checkpoint is exercised by the offline integration check recorded
with the DeBERTa E2E run.
"""

from types import SimpleNamespace

import pytest

from app.backend.summarization.verification import LocalCitationVerifier, VerificationConfig
from experiments.ask_cli_revised import nli_verifier as nli
from experiments.ask_cli_revised import overview_guards as guards
from experiments.ask_cli_revised import runtime as runtime_mod


class _Parameter:
    dtype = "torch.float32"
    device = "cpu"


class _StubCrossEncoder:
    """DeBERTa label order: entailment, neutral, contradiction."""

    max_length = 512

    def __init__(self, rows, id2label=None):
        self.rows = rows
        config = SimpleNamespace(id2label=id2label or dict(nli.DEBERTA_ID2LABEL), _commit_hash="stub")
        self.model = SimpleNamespace(config=config, parameters=lambda: iter([_Parameter()]))

    def predict(self, pairs, apply_softmax=True):
        return [self.rows[index % len(self.rows)] for index in range(len(pairs))]


def _scorer(model, *, device="cpu", fallback=None, fail_on=()):
    scorer = nli.DebertaSupportScorer(
        model_name=nli.DEBERTA_NLI_MODEL, revision=nli.DEBERTA_NLI_REVISION, device=device, fallback_scorer=fallback
    )

    def construct(target):
        if target in fail_on:
            raise RuntimeError(f"{target} unavailable")
        return model

    scorer._construct = construct
    return scorer


def test_default_verifier_adds_nothing():
    assert nli.runtime_kwargs("minilm") == {}
    assert nli.screen_config("minilm") is None


def test_deberta_changes_only_the_model_and_the_support_threshold():
    kwargs = nli.runtime_kwargs("deberta")
    config, default = kwargs["verification_config"], VerificationConfig()
    assert kwargs["support_scorer_factory"] is nli.deberta_support_scorer
    assert config.support_threshold == 0.50
    assert (config.retrieval_threshold, config.quote_threshold, config.contradiction_threshold) == (
        default.retrieval_threshold,
        default.quote_threshold,
        default.contradiction_threshold,
    )
    assert nli.screen_config("deberta") is config
    assert default.support_threshold == 0.55


def test_unknown_verifier_is_refused():
    with pytest.raises(ValueError):
        nli.runtime_kwargs("roberta")


def test_entailment_and_contradiction_follow_the_deberta_label_order():
    scorer = _scorer(_StubCrossEncoder([[0.8, 0.15, 0.05], [0.02, 0.08, 0.9]]))
    assert scorer.support_and_contradiction_many([("p", "h"), ("p", "h2")]) == [(0.8, 0.05), (0.02, 0.9)]
    receipt = scorer.receipt()
    assert (receipt["calls"], receipt["pairs_scored"], receipt["embedding_fallback_pairs"]) == (1, 2, 0)
    assert receipt["device"] == "cpu" and receipt["device_fallback_reason"] is None
    assert receipt["support_threshold"] == 0.50


def test_an_unexpected_label_mapping_is_refused_at_construction(monkeypatch):
    import sentence_transformers

    minilm_order = {0: "contradiction", 1: "entailment", 2: "neutral"}
    monkeypatch.setattr(
        sentence_transformers, "CrossEncoder", lambda *a, **k: _StubCrossEncoder([[1, 0, 0]], id2label=minilm_order)
    )
    scorer = nli.DebertaSupportScorer(model_name=nli.DEBERTA_NLI_MODEL, revision=nli.DEBERTA_NLI_REVISION, device="cpu")
    with pytest.raises(ValueError, match="label mapping"):
        scorer._load_model()


def test_an_accelerator_that_cannot_load_falls_back_to_cpu():
    scorer = _scorer(_StubCrossEncoder([[0.7, 0.2, 0.1]]), device="cuda", fail_on=("cuda",))
    assert scorer.support_and_contradiction_many([("p", "h")]) == [(0.7, 0.1)]
    receipt = scorer.receipt()
    assert receipt["device_requested"] == "cuda"
    assert "cuda unavailable" in receipt["device_fallback_reason"]
    assert receipt["embedding_fallback_pairs"] == 0


def test_embedding_substitution_is_counted_not_hidden():
    class Broken(_StubCrossEncoder):
        calls = 0

        def predict(self, pairs, apply_softmax=True):
            Broken.calls += 1
            if Broken.calls > 1:  # the load probe succeeds; real inference then fails
                raise RuntimeError("inference failed")
            return super().predict(pairs, apply_softmax)

    scorer = _scorer(Broken([[0.7, 0.2, 0.1]]), fallback=SimpleNamespace(score=lambda sentence, passage: 0.6))
    assert scorer.support_and_contradiction_many([("p", "h")]) == [(0.6, None)]
    assert scorer.receipt()["embedding_fallback_pairs"] == 1


def test_device_resolution(monkeypatch):
    assert nli.resolve_device("cpu") == "cpu"
    monkeypatch.setenv(nli.DEVICE_ENV, "cpu")
    assert nli.resolve_device() == "cpu"
    with pytest.raises(ValueError):
        nli.resolve_device("tpu")


def test_threshold_applies_at_the_verifier_and_at_the_screens():
    verifier = LocalCitationVerifier(
        model=None, vector_store=None, config=nli.DEBERTA_VERIFICATION_CONFIG, support_scorer=object()
    )

    def status(support, contradiction=0.05, retrieval=0.9):
        return verifier._status(
            retrieval_confidence=retrieval,
            quote_confidence=1.0,
            support_confidence=support,
            contradiction_confidence=contradiction,
        )

    assert status(0.52) == "verified"
    assert status(0.49) == "weak"
    assert status(0.52, retrieval=0.69) == "weak"  # the similarity gate is unchanged
    assert status(0.2, contradiction=0.9) == "contradicted"
    assert guards.nli_reasons(0.52, 0.05) == ["nli_low_support:0.52"]
    with guards.nli_screen_config(nli.screen_config("deberta")):
        assert guards.nli_reasons(0.52, 0.05) == []
        assert guards.nli_reasons(0.49, 0.05) == ["nli_low_support:0.49"]
        assert guards.nli_reasons(0.2, 0.9) == ["nli_contradicted:0.90"]
        assert guards.nli_reasons(0.9, None) == ["nli_unavailable"]
    assert guards.nli_reasons(0.52, 0.05) == ["nli_low_support:0.52"]
    with guards.nli_screen_config(None):
        assert guards.nli_reasons(0.52, 0.05) == ["nli_low_support:0.52"]


def test_runtime_uses_the_selected_scorer_for_every_nli_consumer(monkeypatch):
    built = {}

    def factory(model):
        built["scorer"] = SimpleNamespace(support_and_contradiction_many=lambda pairs: [], embedding=model)
        return built["scorer"]

    monkeypatch.setattr(runtime_mod, "ModelRuntimeRegistry", lambda: SimpleNamespace(get_embedding_model=lambda **k: 1))
    monkeypatch.setattr(runtime_mod, "ProviderClientRuntime", lambda: object())
    monkeypatch.setattr(runtime_mod, "make_engine", lambda url: object())
    monkeypatch.setattr(runtime_mod, "SQLiteVecVectorStore", lambda: object())
    rt = runtime_mod.build_runtime(
        "unused.sqlite",
        want_qwen=False,
        verification_config=nli.DEBERTA_VERIFICATION_CONFIG,
        support_scorer_factory=factory,
    )
    # e2e hands exactly this attribute to the child-overview and parent-synthesis screens.
    assert rt.verifier.support_scorer is built["scorer"]
    assert rt.verifier.config.support_threshold == 0.50
