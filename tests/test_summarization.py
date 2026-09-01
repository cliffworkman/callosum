from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
import pytest
from sqlalchemy import select

from alembic import command
from alembic.config import Config
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, normalize_text
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.pdf_processing.extraction import COORDINATE_SYSTEM, DEFAULT_CHUNKING_STRATEGY, file_sha256
from app.backend.pdf_processing.ingest import ingest_pdf_scaffold
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.pdf_processing.quote_matching import QuoteMatch
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import (
    attachments,
    chunks,
    citation_mappings,
    evidence_quotes,
    summaries,
    summary_sentences,
)
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from app.backend.summarization.verification import EmbeddingSupportScorer, LocalCitationVerifier, VerificationConfig
from integrations.gemini import DataEgressDisabledError, GeminiConfig, GeminiSummaryGenerator
from integrations.gemini.generator import SUMMARY_PROMPT_VERSION, _prompt


@dataclass(frozen=True)
class SummaryFakeEmbeddingModel:
    name: str = "fake-summary-embedding"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [_summary_vector(normalize_text(text, self.normalization)) for text in texts]


def test_verified_sentence_persists_full_trust_spine_with_coordinates(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="Alpha beta evidence supports the claim.",
                        )
                    ],
                )
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        summary_row = conn.execute(select(summaries).where(summaries.c.id == result.summary_id)).mappings().one()
        sentence_rows = list(conn.execute(select(summary_sentences)).mappings())
        mapping_row = conn.execute(select(citation_mappings)).mappings().one()
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()

    assert result.status == "verified"
    assert result.flagged_sentences == []
    assert result.sentences[0].citations[0].status == "verified"
    assert summary_row["status"] == "verified"
    assert summary_row["chunk_version_verified_against"]
    assert summary_row["embedding_version_verified_against"] == "fake-summary-embedding:v1"
    assert sentence_rows[0]["ordinal"] == 0
    assert mapping_row["status"] == "verified"
    assert mapping_row["chunk_version_verified_against"] == fixture["chunk_version"]
    assert mapping_row["embedding_version_verified_against"] == "fake-summary-embedding:v1"
    assert quote_row["retrieval_confidence"] >= 0.99
    assert quote_row["quote_confidence"] == 1.0
    assert quote_row["support_confidence"] >= 0.99
    assert quote_row["page_start"] == 1
    assert quote_row["bbox_json"]
    assert quote_row["bbox_json"][0]["x1"] > quote_row["bbox_json"][0]["x0"]
    assert quote_row["bbox_json"][0]["coordinate_precision"] == "exact"
    assert result.sentences[0].citations[0].coordinate_precision == "exact"


def test_missing_claimed_quote_is_flagged_and_not_verified(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="This quote is not in the cited chunk.",
                        )
                    ],
                )
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        mapping_row = conn.execute(select(citation_mappings)).mappings().one()
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()

    assert result.status == "flagged"
    assert result.flagged_sentences[0].text == "Alpha beta evidence supports the claim."
    assert mapping_row["status"] == "weak"
    assert quote_row["retrieval_confidence"] >= 0.99
    assert quote_row["quote_confidence"] == 0.0
    assert quote_row["support_confidence"] == 0.0  # nonexistent claimed evidence cannot support the claim
    assert quote_row["page_start"] is None
    assert quote_row["bbox_json"] is None


def test_quote_present_in_chunk_but_not_exactly_located_verifies_with_region_coordinates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    monkeypatch.setattr(
        "app.backend.summarization.verification.locate_quote_for_attachment",
        lambda conn, attachment_id, quote: QuoteMatch(found=False, quote=quote),
    )

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        chunk_row = conn.execute(select(chunks).where(chunks.c.id == fixture["alpha_chunk_id"])).mappings().one()
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="Alpha beta evidence supports the claim.",
                        )
                    ],
                )
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        mapping_row = conn.execute(select(citation_mappings)).mappings().one()
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()

    assert result.status == "verified"
    assert result.sentences[0].flagged is False
    assert result.sentences[0].citations[0].status == "verified"
    assert result.sentences[0].citations[0].coordinate_precision == "region"
    assert mapping_row["status"] == "verified"
    assert quote_row["quote_confidence"] == 1.0
    assert quote_row["page_start"] == chunk_row["page_start"]
    assert quote_row["page_end"] == chunk_row["page_end"]
    assert quote_row["bbox_json"]
    assert quote_row["bbox_json"][0]["coordinate_precision"] == "region"
    assert quote_row["bbox_json"][0]["page"] == chunk_row["bbox_json"][0]["page"]


def test_missing_attachment_file_does_not_abort_synthesis_verification(tmp_path: Path) -> None:
    """Regression for a live library whose extracted chunks outlived a moved managed PDF.

    The immutable chunk text/page box remains usable evidence; only exact PDF rectangles are unavailable.
    """
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        attachment_path = Path(
            conn.execute(
                select(attachments.c.resolved_path).where(attachments.c.paper_id == fixture["paper_id"])
            ).scalar_one()
        )
        attachment_path.unlink()
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="Alpha beta evidence supports the claim.",
                        )
                    ],
                )
            ]
        )

        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()

    assert result.status == "verified"
    assert result.sentences[0].citations[0].coordinate_precision == "region"
    assert quote_row["quote_confidence"] == 1.0
    assert quote_row["page_start"] == 1
    assert quote_row["bbox_json"][0]["coordinate_precision"] == "region"


def test_tolerant_quote_precheck_still_rejects_altered_quote(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="Alpha beta evidence supports a fabricated claim.",
                        )
                    ],
                )
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()

    assert result.status == "flagged"
    assert result.sentences[0].flagged is True
    assert quote_row["quote_confidence"] == 0.0
    assert quote_row["page_start"] is None
    assert quote_row["bbox_json"] is None


def test_quote_not_in_chunk_still_fails_even_if_pdf_locator_would_find_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    monkeypatch.setattr(
        "app.backend.summarization.verification.locate_quote_for_attachment",
        lambda conn, attachment_id, quote: QuoteMatch(
            found=True,
            quote=quote,
            page_start=1,
            page_end=1,
            rectangles=({"page": 1, "x0": 1.0, "y0": 1.0, "x1": 2.0, "y1": 2.0},),
        ),
    )

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="Alpha beta evidence supports a fabricated claim.",
                        )
                    ],
                )
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()

    assert result.status == "flagged"
    assert result.sentences[0].flagged is True
    assert result.sentences[0].citations[0].coordinate_precision is None
    assert quote_row["quote_confidence"] == 0.0
    assert quote_row["page_start"] is None
    assert quote_row["bbox_json"] is None


def test_hyphenated_faithful_chunk_quote_round_trips_to_pdf_coordinates(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    quote = "brain func- tioning in beau- tiful faces and peo- ple"

    with engine.begin() as conn:
        fixture = _create_hyphenated_round_trip_fixture(conn, tmp_path)
        direct_match = locate_quote_for_attachment(conn, int(fixture["attachment_id"]), quote)
        altered_match = locate_quote_for_attachment(
            conn,
            int(fixture["attachment_id"]),
            "brain func- tioning in beau- tiful hands and peo- ple",
        )
        fabricated_match = locate_quote_for_attachment(
            conn,
            int(fixture["attachment_id"]),
            "this quotation is completely fabricated",
        )
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="The passage describes brain functioning in beautiful faces and people.",
                    citations=[CandidateCitation(chunk_id=int(fixture["chunk_id"]), quote=quote)],
                )
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[int(fixture["paper_id"])]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()
        chunk_text = conn.execute(select(chunks.c.text).where(chunks.c.id == fixture["chunk_id"])).scalar_one()

    assert "brain func- tioning" in chunk_text
    assert "beau- tiful" in chunk_text
    assert "peo- ple" in chunk_text
    assert "brain functioning" not in chunk_text
    assert "beautiful" not in chunk_text
    assert "people" not in chunk_text
    assert direct_match.found
    assert direct_match.page_start == 1
    assert len(direct_match.rectangles) >= 4
    assert {rect["line"] for rect in direct_match.rectangles} == {0, 1, 2, 3}
    assert altered_match.found is False
    assert fabricated_match.found is False
    assert result.status == "verified"
    assert result.sentences[0].flagged is False
    assert quote_row["quote_confidence"] == 1.0
    assert quote_row["page_start"] == 1
    assert quote_row["bbox_json"]
    assert {rect["line"] for rect in quote_row["bbox_json"]} == {0, 1, 2, 3}
    assert {rect["coordinate_precision"] for rect in quote_row["bbox_json"]} == {"exact"}


def test_claim_passes_quote_but_fails_support_and_retrieval(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["banana_chunk_id"],
                            quote="Banana orchard material is unrelated.",
                        )
                    ],
                )
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
        )
        mapping_row = conn.execute(select(citation_mappings)).mappings().one()
        quote_row = conn.execute(select(evidence_quotes)).mappings().one()

    assert result.status == "flagged"
    assert mapping_row["status"] == "unverified"
    assert quote_row["retrieval_confidence"] == 0.0
    assert quote_row["quote_confidence"] == 1.0
    assert quote_row["support_confidence"] == 0.0
    assert result.sentences[0].flagged is True


def test_each_confidence_component_must_pass_for_verified_status(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    config = VerificationConfig(retrieval_threshold=0.7, quote_threshold=1.0, support_threshold=0.7)

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="Alpha beta evidence supports the claim.",
                        )
                    ],
                ),
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"],
                            quote="This quote is not in the cited chunk.",
                        )
                    ],
                ),
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["banana_chunk_id"],
                            quote="Banana orchard material is unrelated.",
                        )
                    ],
                ),
            ]
        )
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            verifier_config=config,
            support_scorer=EmbeddingSupportScorer(model),
        )
        statuses = [
            row["status"] for row in conn.execute(select(citation_mappings).order_by(citation_mappings.c.id)).mappings()
        ]

    assert statuses == ["verified", "weak", "unverified"]
    assert [sentence.flagged for sentence in result.sentences] == [False, True, True]


def test_on_progress_reports_one_call_per_candidate_only_during_verification(tmp_path: Path) -> None:
    """inc 408: retrieval + generation stay un-instrumented (no real sub-progress signal available for a single
    opaque LLM call) — on_progress must fire exactly once per candidate, only once verification starts."""
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    calls: list[tuple[int, int, str]] = []

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text="Alpha beta evidence supports the claim.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["alpha_chunk_id"], quote="Alpha beta evidence supports the claim."
                        )
                    ],
                ),
                CandidateSummarySentence(
                    text="Banana orchard material is unrelated.",
                    citations=[
                        CandidateCitation(
                            chunk_id=fixture["banana_chunk_id"], quote="Banana orchard material is unrelated."
                        )
                    ],
                ),
            ]
        )
        summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
            on_progress=lambda i, n, label: calls.append((i, n, label)),
        )

    assert calls == [(1, 2, "Verifying claim"), (2, 2, "Verifying claim")]


def test_on_progress_is_optional_and_never_called_with_zero_candidates(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = SummaryFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()
    calls: list[tuple[int, int, str]] = []

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        generator = FakeSummaryGenerator(sentences=[])
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[fixture["paper_id"]]),
            generator=generator,
            model=model,
            vector_store=vector_store,
            support_scorer=EmbeddingSupportScorer(model),
            on_progress=lambda i, n, label: calls.append((i, n, label)),
        )

    assert result.sentences == []
    assert calls == []


def test_verify_many_batches_encode_and_nli_calls_instead_of_looping(tmp_path: Path) -> None:
    # inc 418: proves the batching actually happens (call COUNT), not just that outputs are correct — 2
    # (sentence, citation) items must yield ONE encode_texts() call with both sentences and ONE NLI call with
    # both pairs, not 2 calls of each.
    engine = _migrated_engine(tmp_path)
    encode_calls: list[list[str]] = []

    @dataclass(frozen=True)
    class CountingEmbeddingModel:
        name: str = "counting-summary-embedding"
        version: str = "v1"
        dimension: int = 3
        normalization: str = DEFAULT_NORMALIZATION

        def encode_texts(self, texts: list[str]) -> list[list[float]]:
            encode_calls.append(list(texts))
            return [_summary_vector(normalize_text(text, self.normalization)) for text in texts]

    nli_calls: list[list[tuple[str, str]]] = []

    @dataclass(frozen=True)
    class CountingSupportScorer:
        def support_and_contradiction_many(self, pairs: list[tuple[str, str]]) -> list[tuple[float, float | None]]:
            nli_calls.append(list(pairs))
            return [(1.0, None) for _ in pairs]

    model = CountingEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        fixture = _ingest_summary_fixture(conn, tmp_path)
        chunk_ids = [fixture["alpha_chunk_id"], fixture["banana_chunk_id"]]
        embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=chunk_ids)  # pre-embed both chunks
        encode_calls.clear()  # discard the pre-embed call — only verify_many's own calls matter below

        verifier = LocalCitationVerifier(model=model, vector_store=vector_store, support_scorer=CountingSupportScorer())
        items = [
            (
                "Alpha sentence one.",
                CandidateCitation(chunk_id=fixture["alpha_chunk_id"], quote="Alpha beta evidence"),
            ),
            (
                "Banana sentence two.",
                CandidateCitation(chunk_id=fixture["banana_chunk_id"], quote="Banana orchard material"),
            ),
        ]
        results = verifier.verify_many(conn, items=items, source_chunks=[])

    assert len(results) == 2
    assert encode_calls == [["Alpha sentence one.", "Banana sentence two."]]  # ONE call, both sentences together
    assert len(nli_calls) == 1
    assert len(nli_calls[0]) == 2  # ONE call, both pairs together
    assert nli_calls[0] == [
        ("Alpha beta evidence", "Alpha sentence one."),
        ("Banana orchard material", "Banana sentence two."),
    ]  # NLI evaluates the validated evidence quote, not the rest of its page-sized chunk


def test_gemini_generator_refuses_data_egress_before_sdk_call() -> None:
    generator = GeminiSummaryGenerator(config=GeminiConfig(data_egress_enabled=False))

    with pytest.raises(DataEgressDisabledError):
        generator.generate(source_chunks=[], scope_ref={"paper_ids": [1]})


def test_summary_prompt_requests_concise_cross_paper_answer_and_bounded_evidence() -> None:
    prompt = _prompt(source_chunks=[], scope_ref={"paper_ids": [1, 2, 3], "query": "What is the bias?"})

    assert SUMMARY_PROMPT_VERSION == "summary-v4"
    assert "MUST contain 4 to 7" in prompt
    assert "MUST be exactly one complete standalone sentence" in prompt
    assert "qualifications or null findings" in prompt
    assert "across those papers" in prompt
    assert "contain 1 to 3 citations" in prompt
    assert "No quote may exceed 80 words" in prompt


def _migrated_engine(tmp_path: Path):
    db_path = tmp_path / "callosum-summarization.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _ingest_summary_fixture(conn, tmp_path: Path) -> dict[str, int | str]:
    pdf_path = _make_summary_pdf(tmp_path / "summary-fixture.pdf")
    ingest = ingest_pdf_scaffold(conn, pdf_path, title="Summary Fixture")
    chunk_rows = list(conn.execute(select(chunks).where(chunks.c.paper_id == ingest["paper_id"])).mappings())
    by_text = {row["text"]: row for row in chunk_rows}
    alpha_chunk = by_text["Alpha beta evidence supports the claim."]
    banana_chunk = by_text["Banana orchard material is unrelated."]
    return {
        "paper_id": ingest["paper_id"],
        "alpha_chunk_id": int(alpha_chunk["id"]),
        "banana_chunk_id": int(banana_chunk["id"]),
        "chunk_version": str(alpha_chunk["chunk_version"]),
    }


def _create_hyphenated_round_trip_fixture(conn, tmp_path: Path) -> dict[str, int | str]:
    pdf_path = _make_hyphenated_round_trip_pdf(tmp_path / "hyphenated-round-trip.pdf")
    checksum = file_sha256(pdf_path)
    paper_id = create_paper(
        conn,
        title="Hyphenated Round Trip Fixture",
        csl_json={"id": "hyphenated-round-trip", "type": "document", "title": "Hyphenated Round Trip Fixture"},
        processing_tier="fully-chunked",
    )
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        original_path=str(pdf_path),
        resolved_path=str(pdf_path.resolve()),
        checksum=checksum,
        file_size=pdf_path.stat().st_size,
        content_type="application/pdf",
        import_source="test",
        attachment_type="pdf",
        role="primary",
    )
    chunk_text = (
        "The cited sentence describes brain func- tioning in beau- tiful faces and peo- ple with facial anomalies."
    )
    chunk_id = create_chunk(
        conn,
        paper_id=paper_id,
        attachment_id=attachment_id,
        text=chunk_text,
        page_start=1,
        page_end=1,
        bbox_coordinate_system=COORDINATE_SYSTEM,
        extraction_tool="pymupdf",
        extraction_version="test",
        chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
        chunk_version="hyphenated-round-trip-v1",
        source_attachment_checksum=checksum,
        char_start=0,
        char_end=len(chunk_text),
        bbox_json=[{"page": 1, "x0": 50, "y0": 50, "x1": 300, "y1": 130}],
    )
    return {"paper_id": paper_id, "attachment_id": attachment_id, "chunk_id": chunk_id}


def _make_summary_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=460, height=420)
    page.insert_text((50, 70), "Alpha beta evidence supports the claim.", fontsize=12)
    page.insert_text((50, 115), "Banana orchard material is unrelated.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _make_hyphenated_round_trip_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=560, height=320)
    page.insert_text((50, 70), "The cited sentence describes brain func-", fontsize=12)
    page.insert_text((50, 88), "tioning in beau-", fontsize=12)
    page.insert_text((50, 106), "tiful faces and peo-", fontsize=12)
    page.insert_text((50, 124), "ple with facial anomalies.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _summary_vector(text: str) -> list[float]:
    if any(token in text for token in ("alpha", "beta", "evidence", "claim")):
        return [1.0, 0.0, 0.0]
    if any(token in text for token in ("banana", "orchard", "unrelated")):
        return [0.0, 1.0, 0.0]
    return [0.0, 0.0, 1.0]
