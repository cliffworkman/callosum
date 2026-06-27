"""inc 156 — highlight-to-suggest / evaluate (Track C SP1a).

Engine + endpoint + the NLI stance classifier. Hermetic: a fake embedding model + InMemoryVectorStore (no real
model loads), a fake StanceScorer injected via create_app(stance_scorer=...), and the NLI label-mapping unit
tested with a fake CrossEncoder. The honesty invariant assertions live here too (region-not-exact evidence).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.citations.suggest import suggest_citations
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import soft_delete_paper
from app.backend.summarization.verification import NLIStanceScorer, Stance, _stance_from_scores
from tests.api_helpers import ApiFakeEmbeddingModel, _seed_summarization_library

FACIAL_QUERY = "Facial anomalies influence social judgments in observers."


@dataclass(frozen=True)
class FakeStanceScorer:
    """A deterministic stance, so the engine/endpoint can be tested without loading the NLI model."""

    label: str = "support"
    confidence: float = 0.91

    def classify_stance(self, *, sentence: str, passage: str) -> Stance:
        return Stance(
            label=self.label, confidence=self.confidence, probs={"support": 0.91, "contrast": 0.04, "mention": 0.05}
        )


def _embed_all(db_url: str, model, store) -> None:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        embed_chunks(conn, model=model, vector_store=store, chunk_ids=None)  # all chunks
    engine.dispose()


# ── engine ────────────────────────────────────────────────────────────────────────────────────────────────


def test_suggest_ranks_by_best_chunk_one_per_paper(temp_db_url: str) -> None:
    ids = _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        suggestions = suggest_citations(
            conn, text=FACIAL_QUERY, model=model, vector_store=store, top_k=5, evaluate=False
        )
    engine.dispose()

    # one suggestion per paper; the facial paper (vector match) ranks first.
    assert [s.paper_id for s in suggestions] == [ids["facial_paper_id"], ids["unrelated_paper_id"]]
    assert suggestions[0].match_score > suggestions[1].match_score
    assert "Facial anomalies" in suggestions[0].quote
    assert suggestions[0].title == "API Summarization Facial Paper"


def test_suggest_evidence_is_region_precision_never_exact(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        suggestions = suggest_citations(conn, text=FACIAL_QUERY, model=model, vector_store=store, evaluate=False)
    engine.dispose()

    top = suggestions[0]
    assert top.coordinate_precision == "region"  # a chunk match is region-level, never a fabricated exact rect
    # the stamped bbox carries the same honest precision
    assert all(item.get("coordinate_precision") == "region" for item in top.bbox_json)


def test_suggest_evaluate_attaches_injected_stance_else_none(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        evaluated = suggest_citations(
            conn,
            text=FACIAL_QUERY,
            model=model,
            vector_store=store,
            evaluate=True,
            stance_scorer=FakeStanceScorer("contrast"),
        )
        plain = suggest_citations(conn, text=FACIAL_QUERY, model=model, vector_store=store, evaluate=False)
    engine.dispose()

    assert evaluated[0].stance is not None and evaluated[0].stance.label == "contrast"
    assert plain[0].stance is None


def test_suggest_excludes_trashed_papers(temp_db_url: str) -> None:
    ids = _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        soft_delete_paper(conn, ids["unrelated_paper_id"])
    with engine.begin() as conn:
        suggestions = suggest_citations(conn, text=FACIAL_QUERY, model=model, vector_store=store, evaluate=False)
    engine.dispose()

    assert [s.paper_id for s in suggestions] == [ids["facial_paper_id"]]


def test_suggest_empty_text_returns_nothing(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert suggest_citations(conn, text="   ", model=model, vector_store=store) == []
    engine.dispose()


# ── stance classifier (NLI label mapping) ─────────────────────────────────────────────────────────────────


class _FakeNLIModel:
    """A stand-in for a sentence-transformers CrossEncoder exposing the standard 3-class id2label."""

    def __init__(self, probs: list[float]) -> None:
        self._probs = probs

        class _Config:
            id2label = {0: "contradiction", 1: "entailment", 2: "neutral"}

        class _Inner:
            config = _Config()

        self.model = _Inner()

    def predict(self, _pairs, apply_softmax=True):  # noqa: ANN001
        return [self._probs]


def test_stance_maps_argmax_via_id2label() -> None:
    support = _stance_from_scores([[0.1, 0.7, 0.2]], model=_FakeNLIModel([0.1, 0.7, 0.2]))
    contrast = _stance_from_scores([[0.7, 0.1, 0.2]], model=_FakeNLIModel([0.7, 0.1, 0.2]))
    mention = _stance_from_scores([[0.1, 0.2, 0.7]], model=_FakeNLIModel([0.1, 0.2, 0.7]))

    assert support.label == "support" and abs(support.confidence - 0.7) < 1e-9
    assert contrast.label == "contrast"
    assert mention.label == "mention"
    assert set(support.probs) == {"support", "contrast", "mention"}


def test_nli_stance_scorer_is_graceful_when_model_unavailable() -> None:
    def _boom():
        raise RuntimeError("no model on this box")

    scorer = NLIStanceScorer(_loader=_boom)
    # graceful: no stance rather than a guessed verdict
    assert scorer.classify_stance(sentence="A", passage="B") is None


def test_nli_stance_scorer_classifies_via_loader() -> None:
    scorer = NLIStanceScorer(_loader=lambda: _FakeNLIModel([0.05, 0.8, 0.15]))
    stance = scorer.classify_stance(sentence="claim", passage="passage")
    assert stance is not None and stance.label == "support"


# ── endpoint ──────────────────────────────────────────────────────────────────────────────────────────────


def _suggest_app(db_url: str, *, stance_scorer=None):
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    app = create_app(db_url=db_url, embedding_model=model, vector_store=store, stance_scorer=stance_scorer)
    _embed_all(db_url, model, store)
    return app


def test_suggest_endpoint_returns_suggestions_with_stance(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer("support"))
    client = TestClient(app)

    resp = client.post("/citations/suggest", json={"text": FACIAL_QUERY, "top_k": 5, "evaluate": True})

    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert suggestions
    top = suggestions[0]
    assert top["title"] == "API Summarization Facial Paper"
    assert top["coordinate_precision"] == "region"
    assert top["stance"]["label"] == "support"
    assert "Facial anomalies" in top["quote"]


def test_suggest_endpoint_evaluate_false_omits_stance(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer())
    client = TestClient(app)

    resp = client.post("/citations/suggest", json={"text": FACIAL_QUERY, "evaluate": False})

    assert resp.status_code == 200
    assert resp.json()["suggestions"][0]["stance"] is None


def test_suggest_endpoint_rejects_empty_and_oversized_text(temp_db_url: str) -> None:
    app = _suggest_app(temp_db_url)
    client = TestClient(app)

    assert client.post("/citations/suggest", json={"text": ""}).status_code == 422
    assert client.post("/citations/suggest", json={"text": "   "}).status_code == 422
    assert client.post("/citations/suggest", json={"text": "x" * 4001}).status_code == 422
