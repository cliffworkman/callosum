"""Inc 609: NLI failure never becomes a cosine "verification", and a synthesis reports the models it actually used.

Before this increment the app-resolved MiniLM2 support scorer silently substituted embedding similarity when NLI
inference raised, read it against the 0.55 NLI threshold and saved it as an ordinary verification. Every
app-resolved support scorer now raises ``NLIInferenceError`` instead: an Ask job fails with nothing saved, and
imported-synthesis re-verification refuses (503) without changing the row. All models here are fakes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from app.backend.api.app import create_app
from app.backend.api.dependencies import resolve_support_scorer
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.model_runtime import ModelRuntimeRegistry
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import summaries
from app.backend.summarization import verification
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from app.backend.summarization.verification import DEFAULT_NLI_MODEL, NLIInferenceError, default_support_scorer
from tests.api_helpers import ApiFakeEmbeddingModel, _seed_summarization_library, _summarization_app
from tests.test_reverify import _blob, _insert_imported, _seed_paper_with_chunk

MINILM2_LABELS = {0: "contradiction", 1: "entailment", 2: "neutral"}


class _Checkpoint:
    """A fake MiniLM2 CrossEncoder: entails everything until ``fail`` is set, then raises like a broken runtime."""

    def __init__(self) -> None:
        self.model = SimpleNamespace(config=SimpleNamespace(id2label=MINILM2_LABELS))
        self.fail = False
        self.calls = 0

    def predict(self, pairs, apply_softmax=True):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated MiniLM2 failure")
        return [[0.02, 0.95, 0.03] for _ in pairs]


def _forbid_cosine(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("embedding similarity was substituted for NLI")

    monkeypatch.setattr(verification.EmbeddingSupportScorer, "score", forbidden)
    monkeypatch.setattr(verification.EmbeddingSupportScorer, "support_and_contradiction_many", forbidden)


def _real_nli_app(temp_db_url: str, factory) -> object:  # type: ignore[no-untyped-def]
    """The production resolution path: no injected support scorer, a registry whose CrossEncoder is a fake."""
    seeded = _seed_summarization_library(temp_db_url)
    claim = "Facial anomalies influence social judgments."
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=claim, citations=[CandidateCitation(chunk_id=seeded["facial_chunk_id"], quote=claim)]
            )
        ]
    )
    app = create_app(
        db_url=temp_db_url,
        summary_generator=generator,
        embedding_model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        model_runtime_registry=ModelRuntimeRegistry(cross_encoder_factory=factory),
    )
    return app, seeded


def _ask(client: TestClient, seeded: dict[str, int]) -> dict:
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]})
    return client.get(f"/summarize/{started.json()['job_id']}").json()


def _summary_count(temp_db_url: str) -> int:
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(summaries)).scalar_one()
    engine.dispose()
    return int(count)


def test_app_resolved_minilm2_scorer_has_no_embedding_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    checkpoint = _Checkpoint()
    app = create_app(
        db_url="sqlite://", model_runtime_registry=ModelRuntimeRegistry(cross_encoder_factory=lambda _i: checkpoint)
    )
    scorer = resolve_support_scorer(app)
    assert scorer.model_name == DEFAULT_NLI_MODEL and scorer.fallback_scorer is None  # type: ignore[attr-defined]
    _forbid_cosine(monkeypatch)
    checkpoint.fail = True
    with pytest.raises(NLIInferenceError, match="simulated MiniLM2 failure"):
        scorer.support_and_contradiction_many([("passage", "claim")])  # type: ignore[attr-defined]


def test_minilm2_unavailable_fails_the_ask_job_and_saves_nothing(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_identity):
        raise OSError("cross-encoder/nli-MiniLM2-L6-H768 is not in the local cache")

    app, seeded = _real_nli_app(temp_db_url, unavailable)
    _forbid_cosine(monkeypatch)
    payload = _ask(TestClient(app), seeded)
    assert payload["status"] == "error", payload
    assert payload["detail"].startswith("Citation verification failed, so no synthesis was saved.")
    assert "not in the local cache" in payload["detail"]
    assert payload["summary_id"] is None and _summary_count(temp_db_url) == 0


def test_minilm2_mid_run_failure_fails_the_job_and_leaves_earlier_results_untouched(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint = _Checkpoint()
    app, seeded = _real_nli_app(temp_db_url, lambda _identity: checkpoint)
    client = TestClient(app)
    first = _ask(client, seeded)
    assert first["status"] == "done" and first["summary_status"] == "verified", first
    _forbid_cosine(monkeypatch)
    checkpoint.fail = True  # the loaded runtime breaks between runs: no reload, no fallback
    second = _ask(client, seeded)
    assert second["status"] == "error" and "simulated MiniLM2 failure" in second["detail"], second
    assert _summary_count(temp_db_url) == 1
    still = client.get(f"/summaries/{first['summary_id']}").json()
    assert still["summary_status"] == "verified"


def test_completed_baseline_run_records_and_returns_both_model_identities(temp_db_url: str) -> None:
    checkpoint = _Checkpoint()
    app, seeded = _real_nli_app(temp_db_url, lambda _identity: checkpoint)
    client = TestClient(app)
    done = _ask(client, seeded)
    assert done["status"] == "done", done
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        ref = conn.execute(select(summaries.c.scope_ref_json).where(summaries.c.id == done["summary_id"])).scalar_one()
    engine.dispose()
    assert ref["retrieval_embedding"]["profile"] == "minilm"
    assert ref["retrieval_embedding"]["model_name"] == "fake-api-embedding"  # the encoder that ran, not Settings
    assert ref["verification_nli"]["profile"] == "minilm2" and ref["verification_nli"]["embedding_fallback"] is False
    provenance = client.get(f"/summaries/{done['summary_id']}").json()["model_provenance"]
    assert provenance["recorded"] is True
    assert provenance["retrieval"]["label"] == "MiniLM (baseline)" and provenance["retrieval"]["experimental"] is False
    assert provenance["verification"]["model_name"] == DEFAULT_NLI_MODEL
    assert provenance["verification"]["experimental"] is False
    assert provenance["verification"]["embedding_fallback"] is False
    assert done["model_provenance"] == provenance  # the job result and a later reload agree


def test_a_row_without_recorded_provenance_reports_unknown_never_a_guessed_minilm(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        summary_id = conn.execute(
            insert(summaries).values(
                scope_type="papers",
                scope_ref_json={"paper_ids": [1]},
                content="An older synthesis.",
                generated_by="fixture",
                chunk_version_verified_against="cv",
                embedding_version_verified_against="ev",
                verification_version="vv",
                status="verified",
            )
        ).inserted_primary_key[0]
    engine.dispose()
    provenance = TestClient(_summarization_app(temp_db_url)).get(f"/summaries/{summary_id}").json()["model_provenance"]
    assert provenance == {"recorded": False, "retrieval": None, "verification": None}


def test_imported_synthesis_has_no_provenance_and_failed_reverify_changes_nothing(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _seed_paper_with_chunk(conn)
        sid = _insert_imported(conn, _blob(paper_id=None, source={"doi": "10.7/rev"}))
    engine.dispose()
    checkpoint = _Checkpoint()
    app = _summarization_app(temp_db_url)
    app.state.support_scorer = None
    app.state.model_runtime_registry = ModelRuntimeRegistry(cross_encoder_factory=lambda _identity: checkpoint)
    client = TestClient(app)
    assert client.get(f"/summaries/{sid}").json()["model_provenance"] is None  # the sender's run is not described

    _forbid_cosine(monkeypatch)
    checkpoint.fail = True
    refused = client.post(f"/summaries/{sid}/reverify")
    assert refused.status_code == 503 and "was not changed" in refused.json()["detail"]
    assert client.get(f"/summaries/{sid}").json()["imported"] is True

    checkpoint.fail = False
    converted = client.post(f"/summaries/{sid}/reverify").json()
    assert converted["imported"] is False
    assert converted["model_provenance"]["verification"]["profile"] == "minilm2"
    assert converted["model_provenance"]["retrieval"]["profile"] == "minilm"


def test_legacy_default_scorer_keeps_its_fallback_for_tools_and_tests() -> None:
    """Scope boundary: only app-resolved scorers lost the fallback. The module default (reached by the validation
    harness and fake-model tests, never by an app route) is unchanged."""
    scorer = default_support_scorer(ApiFakeEmbeddingModel())
    assert isinstance(scorer.fallback_scorer, verification.EmbeddingSupportScorer)  # type: ignore[attr-defined]


def test_result_screens_render_recorded_provenance_never_current_settings() -> None:
    from pathlib import Path

    js = Path("app/frontend/js")
    component = (js / "20e_model_provenance.jsx").read_text(encoding="utf-8")
    assert "/embedding-profiles" not in component and "/verification-nli-profiles" not in component
    assert "not recorded" in component and "experimental" in component
    for screen, prop in (
        ("20_synthesis.jsx", "state.result.model_provenance"),
        ("20d_scoped_ask.jsx", "result.model_provenance"),
    ):
        assert f"<ModelProvenanceLine provenance={{{prop}}} />" in (js / screen).read_text(encoding="utf-8")
    assert "function ModelProvenanceLine" in Path("callosum-app.html").read_text(encoding="utf-8")  # bundle rebuilt
