from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from sqlalchemy import select

from alembic import command
from alembic.config import Config
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, normalize_text
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.pdf_processing.ingest import ingest_pdf_scaffold
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import chunks, citation_mappings, evidence_quotes
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from app.backend.summarization.verification import (
    DEFAULT_SUPPORT_THRESHOLD,
    EmbeddingSupportScorer,
    LocalCitationVerifier,
    NLISupportScorer,
    SupportScorer,
    VerificationConfig,
)


@dataclass(frozen=True)
class TopicalFakeEmbeddingModel:
    name: str = "fake-topical-embedding"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [_topical_vector(normalize_text(text, self.normalization)) for text in texts]


@dataclass(frozen=True)
class FakeNLISupportScorer:
    scores: dict[tuple[str, str], float]

    def score(self, *, sentence: str, passage: str) -> float:
        return self.scores[(passage, sentence)]


@dataclass(frozen=True)
class ConstantSupportScorer:
    value: float

    def score(self, *, sentence: str, passage: str) -> float:
        return self.value


@dataclass(frozen=True)
class FakeContradictionScorer:
    """Exposes both `.score` (the Protocol) AND `.support_and_contradiction` (the inc-203 dual read), so the verifier
    can surface the `contradicted` status."""

    support: float
    contradiction: float

    def score(self, *, sentence: str, passage: str) -> float:
        return self.support

    def support_and_contradiction(self, *, sentence: str, passage: str) -> tuple[float, float | None]:
        return self.support, self.contradiction


class UnavailableNLIModel:
    def __call__(self):
        raise OSError("model is not cached")


class CountingEmbeddingModel:
    name = "counting-embedding"
    version = "v1"
    dimension = 2
    normalization = DEFAULT_NORMALIZATION

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[1.0, 0.0] if "alpha" in text else [0.0, 1.0] for text in texts]


def test_nli_support_scorer_satisfies_protocol_without_loading_real_model() -> None:
    scorer: SupportScorer = NLISupportScorer(_loader=lambda: _StubCrossEncoder([[0.05, 0.9, 0.05]]))

    assert scorer.score(sentence="A source entails this.", passage="A source entails this.") == 0.9


def test_verifier_default_uses_nli_with_embedding_fallback() -> None:
    model = TopicalFakeEmbeddingModel()
    verifier = LocalCitationVerifier(model=model, vector_store=InMemoryVectorStore())

    assert VerificationConfig().support_threshold == DEFAULT_SUPPORT_THRESHOLD == 0.55
    assert isinstance(verifier.support_scorer, NLISupportScorer)
    assert isinstance(verifier.support_scorer.fallback_scorer, EmbeddingSupportScorer)
    assert verifier.support_scorer.fallback_scorer.model is model


def test_embedding_support_scorer_batches_all_pairs_in_one_encode_call() -> None:
    model = CountingEmbeddingModel()
    scorer = EmbeddingSupportScorer(model)

    result = scorer.support_and_contradiction_many(
        [("alpha evidence", "alpha claim"), ("beta evidence", "alpha claim")]
    )

    assert model.calls == [["alpha claim", "alpha evidence", "alpha claim", "beta evidence"]]
    assert result == [(1.0, None), (0.0, None)]


def test_topically_similar_unentailed_claim_fails_with_nli_but_passes_embedding(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = TopicalFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    sentence = "Criterion shifts increase with age."
    quote = "Criterion shifts can occur in signal detection tasks."

    with engine.begin() as conn:
        fixture = _ingest_nli_fixture(conn, tmp_path)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=sentence,
                citations=[CandidateCitation(chunk_id=fixture["criterion_chunk_id"], quote=quote)],
            )
        ]
    )
    embedding_result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
        generator=generator,
        model=model,
        vector_store=vector_store,
        support_scorer=EmbeddingSupportScorer(model),
    )
    nli_result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
        generator=generator,
        model=model,
        vector_store=vector_store,
        support_scorer=FakeNLISupportScorer(scores={(quote, sentence): 0.2}),
    )
    with engine.connect() as conn:
        quote_rows = list(conn.execute(select(evidence_quotes).order_by(evidence_quotes.c.id)).mappings())
        mapping_rows = list(conn.execute(select(citation_mappings).order_by(citation_mappings.c.id)).mappings())

    assert embedding_result.sentences[0].citations[0].support_confidence == 1.0
    assert embedding_result.sentences[0].citations[0].status == "verified"
    assert nli_result.sentences[0].citations[0].support_confidence == 0.2
    assert nli_result.sentences[0].citations[0].status == "weak"
    assert nli_result.sentences[0].flagged is True
    assert [row["status"] for row in mapping_rows] == ["verified", "weak"]
    assert [row["support_confidence"] for row in quote_rows] == [1.0, 0.2]


def test_genuinely_entailed_sentence_passes_with_nli_scorer(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = TopicalFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    sentence = "Criterion shifts can occur in signal detection tasks."
    quote = "Criterion shifts can occur in signal detection tasks."

    with engine.begin() as conn:
        fixture = _ingest_nli_fixture(conn, tmp_path)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=sentence,
                citations=[CandidateCitation(chunk_id=fixture["criterion_chunk_id"], quote=quote)],
            )
        ]
    )
    result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
        generator=generator,
        model=model,
        vector_store=vector_store,
        support_scorer=FakeNLISupportScorer(scores={(quote, sentence): 0.92}),
    )

    assert result.status == "verified"
    assert result.sentences[0].citations[0].support_confidence == 0.92
    assert result.sentences[0].citations[0].status == "verified"


def test_nli_support_scorer_falls_back_when_model_unavailable() -> None:
    scorer = NLISupportScorer(
        local_files_only=True,
        fallback_scorer=ConstantSupportScorer(0.73),
        _loader=UnavailableNLIModel(),
    )

    assert scorer.score(sentence="Any sentence.", passage="Any passage.") == 0.73


def test_default_nli_path_falls_back_without_crashing_when_model_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _migrated_engine(tmp_path)
    model = TopicalFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    sentence = "Criterion shifts can occur in signal detection tasks."
    quote = "Criterion shifts can occur in signal detection tasks."

    def unavailable(self: NLISupportScorer) -> object:
        raise OSError("model is not cached")

    monkeypatch.setattr(NLISupportScorer, "_load_model", unavailable)

    with engine.begin() as conn:
        fixture = _ingest_nli_fixture(conn, tmp_path)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=sentence,
                citations=[CandidateCitation(chunk_id=fixture["criterion_chunk_id"], quote=quote)],
            )
        ]
    )
    result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
        generator=generator,
        model=model,
        vector_store=vector_store,
    )

    assert result.status == "verified"
    assert result.sentences[0].citations[0].support_confidence == 1.0
    assert result.sentences[0].citations[0].status == "verified"


def test_default_support_threshold_boundary_is_inclusive(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = TopicalFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    sentence = "Criterion shifts can occur in signal detection tasks."
    quote = "Criterion shifts can occur in signal detection tasks."

    with engine.begin() as conn:
        fixture = _ingest_nli_fixture(conn, tmp_path)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=sentence,
                citations=[CandidateCitation(chunk_id=fixture["criterion_chunk_id"], quote=quote)],
            )
        ]
    )
    pass_result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
        generator=generator,
        model=model,
        vector_store=vector_store,
        support_scorer=ConstantSupportScorer(0.55),
    )
    fail_result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
        generator=generator,
        model=model,
        vector_store=vector_store,
        support_scorer=ConstantSupportScorer(0.54),
    )

    assert VerificationConfig().support_threshold == 0.55
    assert pass_result.sentences[0].citations[0].support_confidence == 0.55
    assert pass_result.sentences[0].citations[0].status == "verified"
    assert fail_result.sentences[0].citations[0].support_confidence == 0.54
    assert fail_result.sentences[0].citations[0].status == "weak"


# --- inc 203 (A9): the dormant `contradicted` status — the source actively disagrees ---


def test_nli_scorer_reads_both_entailment_and_contradiction_from_one_softmax() -> None:
    # standard NLI order [contradiction, entailment, neutral]: this row says contradiction 0.85, entailment 0.10
    scorer = NLISupportScorer(_loader=lambda: _StubCrossEncoder([[0.85, 0.10, 0.05]]))
    support, contradiction = scorer.support_and_contradiction(sentence="X.", passage="not X.")
    assert support == pytest.approx(0.10) and contradiction == pytest.approx(0.85)
    assert scorer.score(sentence="X.", passage="not X.") == pytest.approx(0.10)  # .score() still = entailment


def test_status_contradicted_only_when_a_confident_contradiction_dominates_support() -> None:
    v = LocalCitationVerifier(model=TopicalFakeEmbeddingModel(), vector_store=InMemoryVectorStore())
    # a confident contradiction that exceeds support → contradicted, even with high retrieval+quote (overrides verified)
    assert (
        v._status(retrieval_confidence=0.9, quote_confidence=1.0, support_confidence=0.1, contradiction_confidence=0.85)
        == "contradicted"
    )
    # contradiction present but NOT exceeding support → not contradicted (here: verified)
    assert (
        v._status(retrieval_confidence=0.9, quote_confidence=1.0, support_confidence=0.9, contradiction_confidence=0.85)
        == "verified"
    )
    # contradiction below the threshold → not contradicted
    assert (
        v._status(retrieval_confidence=0.2, quote_confidence=0.0, support_confidence=0.1, contradiction_confidence=0.40)
        == "unverified"
    )
    # no contradiction signal (embedding fallback) → never contradicted
    assert (
        v._status(retrieval_confidence=0.9, quote_confidence=1.0, support_confidence=0.1, contradiction_confidence=None)
        == "weak"
    )


def test_contradicting_source_resolves_to_contradicted_and_persists(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = TopicalFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    sentence = "Criterion shifts can occur in signal detection tasks."
    quote = "Criterion shifts can occur in signal detection tasks."  # quote matches + topically retrieved
    with engine.begin() as conn:
        fixture = _ingest_nli_fixture(conn, tmp_path)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text=sentence,
                citations=[CandidateCitation(chunk_id=fixture["criterion_chunk_id"], quote=quote)],
            )
        ]
    )
    result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
        generator=generator,
        model=model,
        vector_store=vector_store,
        support_scorer=FakeContradictionScorer(support=0.1, contradiction=0.85),
    )
    with engine.connect() as conn:
        mapping_rows = list(conn.execute(select(citation_mappings).order_by(citation_mappings.c.id)).mappings())

    # the cited source contradicts the claim → contradicted (overriding what would otherwise be verified), flagged, persisted
    assert result.sentences[0].citations[0].status == "contradicted"
    assert result.sentences[0].flagged is True
    assert [row["status"] for row in mapping_rows] == ["contradicted"]


def _migrated_engine(tmp_path: Path):
    db_path = tmp_path / "callosum-nli-support.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _ingest_nli_fixture(conn, tmp_path: Path) -> dict[str, int]:
    pdf_path = _make_nli_pdf(tmp_path / "nli-fixture.pdf")
    ingest = ingest_pdf_scaffold(conn, pdf_path, title="NLI Fixture")
    row = (
        conn.execute(
            select(chunks).where(
                chunks.c.paper_id == ingest["paper_id"],
                chunks.c.text == "Criterion shifts can occur in signal detection tasks.",
            )
        )
        .mappings()
        .one()
    )
    return {"paper_id": int(ingest["paper_id"]), "criterion_chunk_id": int(row["id"])}


def _make_nli_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=500, height=420)
    page.insert_text((50, 70), "Criterion shifts can occur in signal detection tasks.", fontsize=12)
    page.insert_text((50, 115), "Unrelated control material appears here.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _topical_vector(text: str) -> list[float]:
    if any(token in text for token in ("criterion", "shift", "signal", "detection", "age")):
        return [1.0, 0.0, 0.0]
    if "unrelated" in text:
        return [0.0, 1.0, 0.0]
    return [0.0, 0.0, 1.0]


class _StubCrossEncoder:
    def __init__(self, scores: list[list[float]]) -> None:
        self.scores = scores
        self.model = SimpleNamespace(
            config=SimpleNamespace(id2label={0: "contradiction", 1: "entailment", 2: "neutral"})
        )

    def predict(self, pairs, apply_softmax: bool):  # type: ignore[no-untyped-def]
        assert apply_softmax is True
        return self.scores
