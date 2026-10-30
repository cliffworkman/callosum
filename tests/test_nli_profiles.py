"""Verification NLI profiles: the checkpoint contract (label order, architecture, tokenizer) is enforced before any
score is used, the baseline is untouched, selection fails closed, and a synthesis records a non-baseline profile."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.backend.api.dependencies import resolve_support_scorer
from app.backend.model_runtime import ModelRuntimeRegistry
from app.backend.persistence.database import make_engine
from app.backend.summarization.nli_profiles import (
    BASELINE_NLI_PROFILE_KEY,
    DEBERTA_NLI_PROFILE_KEY,
    NLI_PROFILES,
    NliProfileConfigurationError,
    active_nli_profile,
    set_active_nli_profile,
    verification_nli_provenance,
    verify_nli_checkpoint,
)
from app.backend.summarization.verification import VerificationConfig
from tests.api_helpers import _summarization_app

DEBERTA = NLI_PROFILES[DEBERTA_NLI_PROFILE_KEY]


class DebertaV2TokenizerFast:  # name-only stand-in: the contract checks the tokenizer class name
    pass


class BertTokenizerFast:
    pass


def _fake_cross_encoder(id2label=None, model_type="deberta-v2", tokenizer=DebertaV2TokenizerFast):
    labels = {0: "entailment", 1: "neutral", 2: "contradiction"} if id2label is None else id2label
    config = SimpleNamespace(id2label=labels, model_type=model_type)
    return SimpleNamespace(model=SimpleNamespace(config=config), tokenizer=tokenizer())


def test_deberta_profile_pins_revision_and_label_order() -> None:
    assert DEBERTA.model_name == "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    assert DEBERTA.revision == "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
    assert DEBERTA.id2label == {0: "entailment", 1: "neutral", 2: "contradiction"}
    baseline = NLI_PROFILES[BASELINE_NLI_PROFILE_KEY]
    assert baseline.model_name == "cross-encoder/nli-MiniLM2-L6-H768" and not baseline.enforce_contract
    # Thresholds are shared, never re-tuned per profile.
    assert VerificationConfig().support_threshold == 0.55


def test_matching_checkpoint_passes() -> None:
    verify_nli_checkpoint(_fake_cross_encoder(), DEBERTA)


@pytest.mark.parametrize(
    "model",
    [
        _fake_cross_encoder(id2label={0: "contradiction", 1: "entailment", 2: "neutral"}),  # MiniLM2 order
        _fake_cross_encoder(id2label={0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"}),  # names lost → positional guess
        _fake_cross_encoder(id2label={0: "entailment", 1: "not_entailment"}),  # 2-way head
        _fake_cross_encoder(model_type="bert"),
        _fake_cross_encoder(tokenizer=BertTokenizerFast),
        SimpleNamespace(model=SimpleNamespace(config=SimpleNamespace(model_type="deberta-v2")), tokenizer=None),
    ],
)
def test_mismatched_checkpoint_is_refused(model) -> None:
    with pytest.raises(NliProfileConfigurationError):
        verify_nli_checkpoint(model, DEBERTA)


def test_baseline_is_never_contract_checked() -> None:
    verify_nli_checkpoint(object(), NLI_PROFILES[BASELINE_NLI_PROFILE_KEY])  # legacy load path, unchanged


def test_active_profile_defaults_to_baseline_and_ignores_unknown(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert active_nli_profile(conn).key == BASELINE_NLI_PROFILE_KEY
        set_active_nli_profile(conn, DEBERTA_NLI_PROFILE_KEY)
        assert active_nli_profile(conn).key == DEBERTA_NLI_PROFILE_KEY
        from app.backend.persistence.schema import library_settings

        conn.execute(
            library_settings.update().where(library_settings.c.key == "verification_nli_profile").values(value="x")
        )
        assert active_nli_profile(conn).key == BASELINE_NLI_PROFILE_KEY
    engine.dispose()
    # Inc 609: the baseline is recorded too, so an absent record reads as "unknown", never as an assumed MiniLM2.
    baseline = verification_nli_provenance(NLI_PROFILES[BASELINE_NLI_PROFILE_KEY])["verification_nli"]
    assert baseline["profile"] == BASELINE_NLI_PROFILE_KEY and baseline["embedding_fallback"] is False
    assert verification_nli_provenance(DEBERTA)["verification_nli"]["revision"] == DEBERTA.revision


def _app_with_factory(factory):
    return SimpleNamespace(
        state=SimpleNamespace(model_runtime_registry=ModelRuntimeRegistry(cross_encoder_factory=factory))
    )


def test_resolver_loads_the_pinned_profile_and_verifies_it() -> None:
    seen = []

    def factory(identity):
        seen.append((identity.model_name, identity.revision))
        return _fake_cross_encoder()

    scorer = resolve_support_scorer(_app_with_factory(factory), nli_profile=DEBERTA)
    assert seen == [(DEBERTA.model_name, DEBERTA.revision)]
    assert scorer.model_name == DEBERTA.model_name


def test_resolver_refuses_a_mislabelled_checkpoint() -> None:
    factory = lambda identity: _fake_cross_encoder(id2label={0: "contradiction", 1: "entailment", 2: "neutral"})  # noqa: E731
    with pytest.raises(NliProfileConfigurationError):
        resolve_support_scorer(_app_with_factory(factory), nli_profile=DEBERTA)


def test_nli_profile_api(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _summarization_app(temp_db_url)
    app.state.support_scorer = None  # exercise the real verification-on-select path with a fake checkpoint
    good = {"labels": None}
    app.state.model_runtime_registry = ModelRuntimeRegistry(
        cross_encoder_factory=lambda identity: _fake_cross_encoder(id2label=good["labels"])
    )
    client = TestClient(app)
    state = client.get("/verification-nli-profiles").json()
    assert state["active"] == BASELINE_NLI_PROFILE_KEY
    assert state["thresholds_calibrated_on"] == "MiniLM2 NLI (baseline)"
    assert client.put("/verification-nli-profiles/active", json={"key": "nope"}).status_code == 404

    good["labels"] = {0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"}
    refused = client.put("/verification-nli-profiles/active", json={"key": DEBERTA_NLI_PROFILE_KEY})
    assert refused.status_code == 409 and "label order" in refused.json()["detail"]
    assert client.get("/verification-nli-profiles").json()["active"] == BASELINE_NLI_PROFILE_KEY


def test_nli_profile_api_selects_a_verified_checkpoint(temp_db_url: str) -> None:
    app = _summarization_app(temp_db_url)
    app.state.support_scorer = None
    app.state.model_runtime_registry = ModelRuntimeRegistry(
        cross_encoder_factory=lambda identity: _fake_cross_encoder()
    )
    client = TestClient(app)
    selected = client.put("/verification-nli-profiles/active", json={"key": DEBERTA_NLI_PROFILE_KEY})
    assert selected.status_code == 200 and selected.json()["active"] == DEBERTA_NLI_PROFILE_KEY
    assert client.put("/verification-nli-profiles/active", json={"key": BASELINE_NLI_PROFILE_KEY}).json()["active"] == (
        BASELINE_NLI_PROFILE_KEY
    )


def test_profile_dataclass_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEBERTA.revision = "main"  # type: ignore[misc]


def test_ask_verifies_with_the_active_nli_profile_and_records_it(temp_db_url: str) -> None:
    from sqlalchemy import select

    from app.backend.persistence.schema import summaries
    from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
    from tests.api_helpers import _seed_summarization_library

    seeded = _seed_summarization_library(temp_db_url)
    claim = "Facial anomalies influence social judgments."

    def checkpoint(identity):
        model = _fake_cross_encoder()
        # DeBERTa order: entailment is index 0. Read with MiniLM2's positional order this would be 0.005 support.
        model.predict = lambda pairs, apply_softmax=True: [[0.99, 0.005, 0.005] for _ in pairs]
        return model

    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=claim, citations=[CandidateCitation(chunk_id=seeded["facial_chunk_id"], quote=claim)]
            )
        ]
    )
    app = _summarization_app(temp_db_url, generator=generator)
    app.state.support_scorer = None
    app.state.model_runtime_registry = ModelRuntimeRegistry(cross_encoder_factory=checkpoint)
    client = TestClient(app)
    assert client.put("/verification-nli-profiles/active", json={"key": DEBERTA_NLI_PROFILE_KEY}).status_code == 200
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]})
    payload = client.get(f"/summarize/{started.json()['job_id']}").json()
    assert payload["status"] == "done", payload
    citation = payload["sentences"][0]["citations"][0]
    assert citation["support_confidence"] == pytest.approx(0.99) and citation["status"] == "verified"
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        ref = conn.execute(
            select(summaries.c.scope_ref_json).where(summaries.c.id == payload["summary_id"])
        ).scalar_one()
    engine.dispose()
    assert ref["verification_nli"]["profile"] == DEBERTA_NLI_PROFILE_KEY
    assert ref["verification_nli"]["thresholds_calibrated_on"] == "cross-encoder/nli-MiniLM2-L6-H768"


def test_deberta_inference_failure_fails_the_job_instead_of_falling_back_to_embeddings(temp_db_url: str) -> None:
    from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
    from tests.api_helpers import _seed_summarization_library

    seeded = _seed_summarization_library(temp_db_url)
    claim = "Facial anomalies influence social judgments."

    def checkpoint(identity):
        model = _fake_cross_encoder()

        def predict(pairs, apply_softmax=True):
            raise RuntimeError("simulated NLI inference failure")

        model.predict = predict
        return model

    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=claim, citations=[CandidateCitation(chunk_id=seeded["facial_chunk_id"], quote=claim)]
            )
        ]
    )
    app = _summarization_app(temp_db_url, generator=generator)
    app.state.support_scorer = None
    app.state.model_runtime_registry = ModelRuntimeRegistry(cross_encoder_factory=checkpoint)
    client = TestClient(app)
    assert client.put("/verification-nli-profiles/active", json={"key": DEBERTA_NLI_PROFILE_KEY}).status_code == 200
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]})
    payload = client.get(f"/summarize/{started.json()['job_id']}").json()
    assert payload["status"] == "error", payload
    assert "simulated NLI inference failure" in (payload.get("detail") or "")


def test_stance_features_and_reverify_keep_the_baseline_nli(temp_db_url: str) -> None:
    """Scope pin: the profile changes synthesis verification only. Stance features (Suggest-citation, Critical Read,
    citation context) and imported-synthesis re-verification deliberately stay on MiniLM2."""
    import ast
    from pathlib import Path

    from app.backend.api.dependencies import resolve_stance_scorer
    from app.backend.summarization.verification import DEFAULT_NLI_MODEL

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        set_active_nli_profile(conn, DEBERTA_NLI_PROFILE_KEY)
    engine.dispose()
    app = _app_with_factory(lambda identity: _fake_cross_encoder())
    app.state.engine = make_engine(temp_db_url)
    assert resolve_stance_scorer(app).model_name == DEFAULT_NLI_MODEL

    # Only the primary synthesis path passes the active profile; reverify and every stance router do not.
    routers = Path("app/backend/api/routers")
    profile_calls = []
    for path in routers.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in {
                "resolve_support_scorer",
                "resolve_stance_scorer",
            }:
                if any(k.arg == "nli_profile" for k in node.keywords):
                    profile_calls.append((path.name, node.func.id))
    assert profile_calls == [("summaries.py", "resolve_support_scorer")]
