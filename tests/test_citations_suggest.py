"""inc 156 — highlight-to-suggest / evaluate (Track C SP1a).

Engine + endpoint + the NLI stance classifier. Hermetic: a fake embedding model + InMemoryVectorStore (no real
model loads), a fake StanceScorer injected via create_app(stance_scorer=...), and the NLI label-mapping unit
tested with a fake CrossEncoder. The honesty invariant assertions live here too (region-not-exact evidence).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.backend.api import create_app
from app.backend.citations.suggest import suggest_citations
from app.backend.discovery.providers import Item, SourceRegistry
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper, soft_delete_paper
from app.backend.persistence.schema import attachments, papers
from app.backend.summarization.verification import NLIStanceScorer, Stance, _stance_from_scores
from integrations.semantic_scholar.adapter import RecommendedPaper
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


@dataclass
class _BatchCountingStanceScorer:
    """Proves suggest_citations batches its NLI calls (LATENCY.md) instead of one call per candidate."""

    batch_calls: int = 0
    single_calls: int = 0
    last_pairs: list = field(default_factory=list)

    def classify_stance(self, *, sentence: str, passage: str) -> Stance:
        self.single_calls += 1
        raise AssertionError("suggest_citations must not call classify_stance per-item when a batch API exists")

    def classify_stances(self, pairs: list[tuple[str, str]]) -> list[Stance]:
        self.batch_calls += 1
        self.last_pairs = list(pairs)
        return [
            Stance(label="support", confidence=0.9, probs={"support": 0.9, "contrast": 0.05, "mention": 0.05})
            for _ in pairs
        ]


def _embed_all(db_url: str, model, store) -> None:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        embed_chunks(conn, model=model, vector_store=store, document_roles=ARTICLE_DOCUMENT_ROLES)
    engine.dispose()


def _seed_section_scoped_papers(db_url: str) -> dict[str, int]:
    """Two papers, each with one chunk tagged with a distinct heuristic `chunks.section` -- the fixture the
    section-scoping boost test needs (mirrors `_seed_summarization_library`'s shape, but that shared fixture's
    chunks carry no `section`, so this is a standalone seed rather than a change to shared test infra). The
    "methods" paper's chunk text deliberately does NOT match FACIAL_QUERY (banana/orchard -> a different fixed
    vector under ApiFakeEmbeddingModel), so its raw retrieval score is naturally lower than the "results" paper's
    -- proving search_phase genuinely reorders rather than merely reflecting an already-highest raw score."""
    engine = make_engine(db_url)
    with engine.begin() as conn:
        methods_paper_id = create_paper(
            conn,
            title="Section-Scoped Methods Paper",
            csl_json={
                "type": "article-journal",
                "title": "Section-Scoped Methods Paper",
                "author": [{"given": "Marie", "family": "Curie"}],
            },
            first_author_family_name="Curie",
            processing_tier="fully-chunked",
        )
        other_paper_id = create_paper(
            conn,
            title="Section-Scoped Facial Paper",
            csl_json={
                "type": "article-journal",
                "title": "Section-Scoped Facial Paper",
                "author": [{"given": "Ada", "family": "Lovelace"}],
            },
            first_author_family_name="Lovelace",
            processing_tier="fully-chunked",
        )
        methods_attachment_id = create_attachment(
            conn,
            paper_id=methods_paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="section-methods-checksum",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        other_attachment_id = create_attachment(
            conn,
            paper_id=other_paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="section-other-checksum",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        create_chunk(
            conn,
            paper_id=methods_paper_id,
            attachment_id=methods_attachment_id,
            text="Banana orchard material is unrelated.",
            section="methods",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="section-chunk-v1",
            source_attachment_checksum="section-methods-checksum",
            bbox_json=[{"page": 1, "x0": 10, "y0": 20, "x1": 120, "y1": 40}],
        )
        create_chunk(
            conn,
            paper_id=other_paper_id,
            attachment_id=other_attachment_id,
            text="Facial anomalies influence social judgments.",
            section="results",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="section-chunk-v2",
            source_attachment_checksum="section-other-checksum",
            bbox_json=[{"page": 1, "x0": 11, "y0": 22, "x1": 121, "y1": 42}],
        )
    engine.dispose()
    return {"methods_paper_id": methods_paper_id, "other_paper_id": other_paper_id}


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
    assert suggestions[0].attachment_id == ids["facial_attachment_id"]


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


def test_suggest_omits_non_pdf_attachment_from_source_target(temp_db_url: str) -> None:
    ids = _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            update(attachments)
            .where(attachments.c.id == ids["facial_attachment_id"])
            .values(content_type="text/html", attachment_type="html")
        )
        suggestions = suggest_citations(conn, text=FACIAL_QUERY, model=model, vector_store=store, evaluate=False)
    engine.dispose()

    top = next(item for item in suggestions if item.paper_id == ids["facial_paper_id"])
    assert top.attachment_id is None


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


def test_suggest_citations_batches_stance_scorer_calls(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        second_paper_id = create_paper(
            conn,
            title="API Summarization Facial Paper Two",
            csl_json={"type": "article-journal", "title": "API Summarization Facial Paper Two"},
            first_author_family_name="Lovelace",
            processing_tier="fully-chunked",
        )
        second_attachment_id = create_attachment(
            conn,
            paper_id=second_paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="summary-facial-two-checksum",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        create_chunk(
            conn,
            paper_id=second_paper_id,
            attachment_id=second_attachment_id,
            text="Facial anomalies also influence social judgments in a second paper.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="v1",
            source_attachment_checksum="summary-facial-two-checksum",
        )
    engine.dispose()
    _embed_all(temp_db_url, model, store)

    scorer = _BatchCountingStanceScorer()
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        suggestions = suggest_citations(
            conn, text=FACIAL_QUERY, model=model, vector_store=store, top_k=2, evaluate=True, stance_scorer=scorer
        )
    engine.dispose()

    assert len(suggestions) == 2
    assert scorer.single_calls == 0
    assert scorer.batch_calls == 1  # one NLI call for both candidates, not one per candidate (LATENCY.md)
    assert len(scorer.last_pairs) == 2


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


def test_suggest_citations_boosts_matching_section_without_dropping_others(temp_db_url: str) -> None:
    """Two papers both match the query; the one whose best chunk is heuristic-tagged "methods" should rank
    first when current_heading implies "methods", with search_phase disclosed -- and the other paper must
    still be present in the results, just after it."""
    ids = _seed_section_scoped_papers(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = suggest_citations(
            conn,
            text=FACIAL_QUERY,
            model=model,
            vector_store=store,
            top_k=5,
            evaluate=False,
            current_heading="3. Methods",
        )
    engine.dispose()

    assert result[0].paper_id == ids["methods_paper_id"]
    assert result[0].section_family == "methods"
    assert result[0].search_phase == "expected-sections"
    # Finding 4 (final-review fix): section_source must round-trip too -- these chunks only ever got the
    # pre-existing heuristic chunks.section tag, never a GROBID mapping, so the disclosed source is "heuristic".
    assert result[0].section_source == "heuristic"
    assert {s.paper_id for s in result} == {ids["methods_paper_id"], ids["other_paper_id"]}  # nothing dropped
    # the unmatched paper keeps its own real section tag and an honestly-absent search_phase -- reordering never
    # mislabels a non-match as having matched too
    trailing = next(s for s in result if s.paper_id == ids["other_paper_id"])
    assert trailing.section_family == "results"
    assert trailing.search_phase is None
    assert trailing.section_source == "heuristic"


def test_suggest_citations_discloses_grobid_section_source(temp_db_url: str) -> None:
    """Finding 4 (final-review fix): when a candidate chunk was mapped by an explicit GROBID parse (not just
    the heuristic), section_source must disclose "grobid", not "heuristic" or a silently-discarded value --
    the design doc's "source disclosed" promise, closed end-to-end through the real suggest_citations() engine."""
    ids = _seed_section_scoped_papers(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)

    from app.backend.persistence.schema import chunks
    from app.backend.persistence.schema_grobid import paper_sections

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        # Map the methods paper's chunk to a real GROBID-derived section -- GROBID must now win over the
        # pre-existing heuristic "methods" tag already on this same chunk (candidate_section_family's strict
        # either/or contract).
        section_result = conn.execute(
            paper_sections.insert().values(
                paper_id=ids["methods_paper_id"],
                title="3. Methods",
                section_kind="methods",
                page_start=1,
                page_end=1,
                order_index=0,
            )
        )
        section_id = section_result.inserted_primary_key[0]
        conn.execute(
            chunks.update().where(chunks.c.paper_id == ids["methods_paper_id"]).values(grobid_section_id=section_id)
        )
        result = suggest_citations(
            conn,
            text=FACIAL_QUERY,
            model=model,
            vector_store=store,
            top_k=5,
            evaluate=False,
            current_heading="3. Methods",
        )
    engine.dispose()

    top = next(s for s in result if s.paper_id == ids["methods_paper_id"])
    assert top.section_family == "methods"
    assert top.section_source == "grobid"


def test_suggest_citations_no_heading_context_behaves_exactly_as_before(temp_db_url: str) -> None:
    """No current_heading passed (the pre-existing call shape) -- search_phase is None on every result, order
    unaffected by section at all."""
    ids = _seed_summarization_library(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    _embed_all(temp_db_url, model, store)

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = suggest_citations(conn, text=FACIAL_QUERY, model=model, vector_store=store, top_k=5, evaluate=False)
    engine.dispose()

    assert [s.paper_id for s in result] == [ids["facial_paper_id"], ids["unrelated_paper_id"]]
    assert all(s.search_phase is None for s in result)


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


def test_nli_stance_batch_matches_sequential_probabilities_and_order() -> None:
    rows = {
        ("passage-a", "claim-a"): [0.7000001, 0.1999998, 0.1000001],
        ("passage-b", "claim-b"): [0.1000001, 0.7999998, 0.1000001],
        ("passage-a", "claim-a-duplicate"): [0.1000001, 0.1999998, 0.7000001],
    }

    class _PairAwareNLIModel(_FakeNLIModel):
        def __init__(self) -> None:
            super().__init__([0.0, 0.0, 0.0])
            self.calls: list[list[tuple[str, str]]] = []

        def predict(self, pairs, apply_softmax=True):  # noqa: ANN001
            self.calls.append(list(pairs))
            return [rows[tuple(pair)] for pair in pairs]

    pairs = [("claim-a", "passage-a"), ("claim-b", "passage-b"), ("claim-a-duplicate", "passage-a")]
    batch_model = _PairAwareNLIModel()
    batch = NLIStanceScorer(_loader=lambda: batch_model).classify_stances(pairs)
    sequential_model = _PairAwareNLIModel()
    sequential_scorer = NLIStanceScorer(_loader=lambda: sequential_model)
    sequential = [sequential_scorer.classify_stance(sentence=claim, passage=passage) for claim, passage in pairs]

    assert len(batch_model.calls) == 1 and batch_model.calls[0] == [
        ("passage-a", "claim-a"),
        ("passage-b", "claim-b"),
        ("passage-a", "claim-a-duplicate"),
    ]
    assert len(sequential_model.calls) == 3
    assert [stance.label for stance in batch if stance] == ["contrast", "support", "mention"]
    max_difference = max(
        abs(batch_stance.probs[label] - sequential_stance.probs[label])
        for batch_stance, sequential_stance in zip(batch, sequential, strict=True)
        if batch_stance is not None and sequential_stance is not None
        for label in batch_stance.probs
    )
    assert max_difference <= 1e-5


def test_nli_stance_batch_preserves_unavailable_failure_shape() -> None:
    scorer = NLIStanceScorer(_loader=lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    assert scorer.classify_stances([("a", "b"), ("c", "d")]) == [None, None]


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
    assert top["attachment_id"] is not None
    assert top["stance"]["label"] == "support"
    assert "Facial anomalies" in top["quote"]


class _RaisingStanceScorer:
    """A stand-in for a broken/cold local NLI model (corrupted cache, OOM, offline first-use download)."""

    def classify_stance(self, *, sentence: str, passage: str):
        raise RuntimeError("local model failed to load")

    def classify_stances(self, pairs):
        raise RuntimeError("local model failed to load")


def test_suggest_endpoint_returns_clean_error_when_local_model_fails(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    app = _suggest_app(temp_db_url, stance_scorer=_RaisingStanceScorer())
    client = TestClient(app)

    resp = client.post("/citations/suggest", json={"text": FACIAL_QUERY, "top_k": 5, "evaluate": True})

    assert resp.status_code == 503
    assert "could not complete" in resp.json()["detail"]
    assert "RuntimeError" in resp.json()["detail"]  # invariant #4: the real error stays inspectable, not hidden


def test_suggest_endpoint_discloses_section_source(temp_db_url: str) -> None:
    """Finding 4 (final-review fix): section_source must round-trip through the actual HTTP response, for
    both a heuristic-only candidate and a GROBID-mapped one -- the design doc's "source disclosed" promise,
    verified at the wire contract, not just the internal Suggestion dataclass."""
    ids = _seed_section_scoped_papers(temp_db_url)
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer("support"))

    from app.backend.persistence.schema import chunks
    from app.backend.persistence.schema_grobid import paper_sections

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        section_result = conn.execute(
            paper_sections.insert().values(
                paper_id=ids["methods_paper_id"],
                title="3. Methods",
                section_kind="methods",
                page_start=1,
                page_end=1,
                order_index=0,
            )
        )
        section_id = section_result.inserted_primary_key[0]
        conn.execute(
            chunks.update().where(chunks.c.paper_id == ids["methods_paper_id"]).values(grobid_section_id=section_id)
        )
    engine.dispose()

    client = TestClient(app)
    resp = client.post(
        "/citations/suggest",
        json={"text": FACIAL_QUERY, "top_k": 5, "evaluate": False, "current_heading": "3. Methods"},
    )

    assert resp.status_code == 200
    suggestions = {item["paper_id"]: item for item in resp.json()["suggestions"]}
    assert suggestions[ids["methods_paper_id"]]["section_source"] == "grobid"
    assert suggestions[ids["other_paper_id"]]["section_source"] == "heuristic"


def test_suggest_endpoint_evaluate_false_omits_stance(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer())
    client = TestClient(app)

    resp = client.post("/citations/suggest", json={"text": FACIAL_QUERY, "evaluate": False})

    assert resp.status_code == 200
    assert resp.json()["suggestions"][0]["stance"] is None


def test_suggest_endpoint_can_include_beyond_library_candidates(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer("support"))
    app.state.discovery_registry = SourceRegistry()

    class _ExternalProvider:
        name = "fixture-openalex"

        def search(self, query: str, limit: int) -> list[Item]:
            assert "Facial anomalies" in query
            return [
                Item(
                    title="External facial judgment study",
                    sources=("fixture-openalex",),
                    doi="10.1234/external",
                    abstract="Facial anomalies influence social judgments in observers across several tasks.",
                    authors=("Curie, Marie",),
                    journal="Journal of Public Metadata",
                    year=2026,
                    url="https://example.org/external",
                )
            ]

    app.state.citation_openalex_provider = _ExternalProvider()
    client = TestClient(app)

    resp = client.post(
        "/citations/suggest",
        json={"text": FACIAL_QUERY, "top_k": 3, "include_beyond_library": True, "beyond_top_k": 2},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["suggestions"]
    external = body["beyond_library_suggestions"]
    assert external and external[0]["title"] == "External facial judgment study"
    assert external[0]["evidence_kind"] == "abstract"
    assert external[0]["reason_kind"] == "public_metadata_search"
    assert external[0]["stance"]["label"] == "support"
    assert body["source_coverage"][0]["provider_id"] == "fixture-openalex"
    assert body["source_coverage"][0]["status"] == "success"
    assert body["source_coverage"][0]["result_count"] == 1


def test_suggest_endpoint_uses_local_matches_as_openalex_neighborhood_anchors(temp_db_url: str) -> None:
    ids = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(update(papers).where(papers.c.id == ids["facial_paper_id"]).values(doi="10.123/facial"))
    engine.dispose()
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer("support"))
    app.state.discovery_registry = SourceRegistry()

    class _GraphOpenAlex:
        def fetch_work_id(self, conn, ref):  # noqa: ANN001
            assert ref.doi == "10.123/facial"
            return "WLOCAL"

        def fetch_work_meta_for(self, conn, ref):  # noqa: ANN001
            return {"openalex_work_id": "WLOCAL", "related_works": []}

        def fetch_referenced_works(self, conn, ref):  # noqa: ANN001
            return ["WREF"]

        def fetch_citing_works(self, conn, work_id):  # noqa: ANN001
            return []

        def fetch_works_by_ids(self, conn, ids, *, with_abstract=True):  # noqa: ANN001, ARG002
            if ids == ["WREF"]:
                return [
                    {
                        "openalex_work_id": "WREF",
                        "doi": "10.123/ref",
                        "title": "External work cited by local facial paper",
                        "abstract": "Facial anomalies influence social judgments in public metadata.",
                        "authors": ["Graph Author"],
                        "year": 2024,
                        "venue": "Graph Journal",
                    }
                ]
            return []

    app.state.openalex_client = _GraphOpenAlex()
    client = TestClient(app)

    resp = client.post(
        "/citations/suggest",
        json={"text": FACIAL_QUERY, "top_k": 3, "include_beyond_library": True, "beyond_top_k": 5},
    )

    assert resp.status_code == 200
    body = resp.json()
    external = body["beyond_library_suggestions"]
    graph = [item for item in external if item["doi"] == "10.123/ref"]
    assert graph
    assert graph[0]["relationship_kind"] == "cited_by_local_match"
    assert graph[0]["relationship_label"] == "Cited by a locally relevant paper"
    assert graph[0]["anchor_paper_id"] == ids["facial_paper_id"]
    assert graph[0]["anchor_title"] == "API Summarization Facial Paper"
    assert any(row["provider_id"] == "openalex-neighborhood" for row in body["source_coverage"])


def test_suggest_endpoint_includes_semantic_scholar_recommendations(temp_db_url: str) -> None:
    ids = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(update(papers).where(papers.c.id == ids["facial_paper_id"]).values(doi="10.123/facial"))
    engine.dispose()
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer("support"))
    app.state.discovery_registry = SourceRegistry()

    class _S2Recommendations:
        def fetch_recommendations(self, conn, doi, *, limit=10):  # noqa: ANN001
            assert doi == "10.123/facial"
            return [
                RecommendedPaper(
                    title="S2 Recommended Facial Study",
                    doi="10.123/s2-rec",
                    pmid=None,
                    year=2023,
                    authors=["S2 Author"],
                    journal="S2 Journal",
                    url="https://www.semanticscholar.org/paper/s2-rec",
                    abstract="Facial anomalies influence social judgments per Semantic Scholar's recommendation.",
                )
            ]

    app.state.semantic_scholar_client = _S2Recommendations()
    client = TestClient(app)

    resp = client.post(
        "/citations/suggest",
        json={"text": FACIAL_QUERY, "top_k": 3, "include_beyond_library": True, "beyond_top_k": 5},
    )

    assert resp.status_code == 200
    body = resp.json()
    external = body["beyond_library_suggestions"]
    s2 = [item for item in external if item["doi"] == "10.123/s2-rec"]
    assert s2
    assert s2[0]["relationship_kind"] == "recommended_alongside_local_match"
    assert s2[0]["relationship_label"] == "Recommended by Semantic Scholar alongside a locally relevant paper"
    assert s2[0]["anchor_paper_id"] == ids["facial_paper_id"]
    assert s2[0]["anchor_title"] == "API Summarization Facial Paper"
    assert any(row["provider_id"] == "semantic-scholar-recommendations" for row in body["source_coverage"])


def test_suggest_endpoint_openalex_relation_wins_collision_with_s2(temp_db_url: str) -> None:
    """When the same outside paper surfaces from both OpenAlex-neighborhood and S2-recommendations for the same
    anchor, the verifiable graph-fact relation displays — never silently overwritten by S2's opaque algorithmic
    label (commitment #8, inspectability over authority)."""
    ids = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(update(papers).where(papers.c.id == ids["facial_paper_id"]).values(doi="10.123/facial"))
    engine.dispose()
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer("support"))
    app.state.discovery_registry = SourceRegistry()

    class _GraphOpenAlex:
        def fetch_work_id(self, conn, ref):  # noqa: ANN001
            return "WLOCAL"

        def fetch_work_meta_for(self, conn, ref):  # noqa: ANN001
            return {"openalex_work_id": "WLOCAL", "related_works": []}

        def fetch_referenced_works(self, conn, ref):  # noqa: ANN001
            return ["WREF"]

        def fetch_citing_works(self, conn, work_id):  # noqa: ANN001
            return []

        def fetch_works_by_ids(self, conn, ids, *, with_abstract=True):  # noqa: ANN001, ARG002
            if ids == ["WREF"]:
                return [
                    {
                        "openalex_work_id": "WREF",
                        "doi": "10.123/collision",
                        "title": "Collision Candidate",
                        "abstract": "Facial anomalies influence social judgments in shared metadata.",
                        "authors": ["Graph Author"],
                        "year": 2024,
                        "venue": "Graph Journal",
                    }
                ]
            return []

    class _S2Recommendations:
        def fetch_recommendations(self, conn, doi, *, limit=10):  # noqa: ANN001
            return [
                RecommendedPaper(
                    title="Collision Candidate",
                    doi="10.123/collision",
                    pmid=None,
                    year=2024,
                    authors=["Graph Author"],
                    journal="Graph Journal",
                    url=None,
                    abstract="Facial anomalies influence social judgments in shared metadata.",
                )
            ]

    app.state.openalex_client = _GraphOpenAlex()
    app.state.semantic_scholar_client = _S2Recommendations()
    client = TestClient(app)

    resp = client.post(
        "/citations/suggest",
        json={"text": FACIAL_QUERY, "top_k": 3, "include_beyond_library": True, "beyond_top_k": 5},
    )

    assert resp.status_code == 200
    body = resp.json()
    collision = [item for item in body["beyond_library_suggestions"] if item["doi"] == "10.123/collision"]
    assert len(collision) == 1  # deduped to one card, not two
    assert collision[0]["relationship_kind"] == "cited_by_local_match"
    assert collision[0]["relationship_label"] == "Cited by a locally relevant paper"


def test_suggest_endpoint_s2_recommendation_failure_on_one_anchor_does_not_drop_others(temp_db_url: str) -> None:
    ids = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(update(papers).where(papers.c.id == ids["facial_paper_id"]).values(doi="10.123/facial"))
        conn.execute(update(papers).where(papers.c.id == ids["unrelated_paper_id"]).values(doi="10.123/banana"))
    engine.dispose()
    app = _suggest_app(temp_db_url, stance_scorer=FakeStanceScorer("support"))
    app.state.discovery_registry = SourceRegistry()

    class _FlakyS2:
        def fetch_recommendations(self, conn, doi, *, limit=10):  # noqa: ANN001
            if doi == "10.123/facial":
                raise ConnectionError("simulated S2 outage for this anchor")
            return [
                RecommendedPaper(
                    title="Recovered From Second Anchor",
                    doi="10.123/second-anchor-rec",
                    pmid=None,
                    year=2022,
                    authors=["Recovered Author"],
                    journal="Recovered Journal",
                    url=None,
                    abstract=None,
                )
            ]

    app.state.semantic_scholar_client = _FlakyS2()
    client = TestClient(app)

    resp = client.post(
        "/citations/suggest",
        json={"text": FACIAL_QUERY, "top_k": 5, "include_beyond_library": True, "beyond_top_k": 10},
    )

    assert resp.status_code == 200
    body = resp.json()
    coverage = next(row for row in body["source_coverage"] if row["provider_id"] == "semantic-scholar-recommendations")
    # the failing anchor is honestly reflected ("partial", not silently "success")...
    assert coverage["status"] == "partial"
    assert coverage["warning"] and "ConnectionError" in coverage["warning"]
    # ...but the *other* anchor's legitimate results still made it through — proves per-anchor isolation, not an
    # early-return-on-first-failure that would silently cost every anchor after the failing one
    recovered = [item for item in body["beyond_library_suggestions"] if item["doi"] == "10.123/second-anchor-rec"]
    assert recovered


def test_suggest_endpoint_rejects_empty_and_oversized_text(temp_db_url: str) -> None:
    app = _suggest_app(temp_db_url)
    client = TestClient(app)

    assert client.post("/citations/suggest", json={"text": ""}).status_code == 422
    assert client.post("/citations/suggest", json={"text": "   "}).status_code == 422
    assert client.post("/citations/suggest", json={"text": "x" * 4001}).status_code == 422
