from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

import fitz
from sqlalchemy import func, select

from alembic import command
from alembic.config import Config
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, l2_normalize, normalize_text
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, SourceChunk
from integrations.gemini.generator import GeminiConfig
from tests.test_zotero_importer import _make_zotero_fixture
from tools.validation_harness import (
    AxisCalibrationSpec,
    ProgressReporter,
    QuoteCheck,
    SummarizationSpec,
    ValidationReport,
    render_markdown_report,
    run_axis_calibration_probe,
    run_validation,
)


@dataclass(frozen=True)
class HarnessFakeEmbeddingModel:
    name: str = "harness-fake-model"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            normalized = normalize_text(text, self.normalization)
            calibration_vector = _calibration_vector(normalized)
            if calibration_vector is not None:
                vectors.append(calibration_vector)
                continue
            vectors.append(
                l2_normalize(
                    [
                        float(any(word in normalized for word in ("neural", "brain", "cortex"))),
                        float(any(word in normalized for word in ("blank", "empty", "scanned"))),
                        0.1,
                    ]
                )
            )
        return vectors


class HarnessSummaryGenerator:
    name = "harness-summary-generator"

    def generate(
        self,
        *,
        source_chunks: list[SourceChunk],
        scope_ref: dict[str, object],
        conn=None,
    ) -> list[CandidateSummarySentence]:
        cited_chunk = next(chunk for chunk in source_chunks if "Neural brain cortex validation quote." in chunk.text)
        return [
            CandidateSummarySentence(
                text="Neural brain cortex validation quote is documented.",
                citations=[
                    CandidateCitation(
                        chunk_id=cited_chunk.chunk_id,
                        quote="Neural brain cortex validation quote.",
                    )
                ],
            ),
            CandidateSummarySentence(
                text="Neural brain cortex missing quote is documented.",
                citations=[CandidateCitation(chunk_id=cited_chunk.chunk_id, quote="This quote is absent.")],
            ),
            CandidateSummarySentence(
                text="Neural unsupported age effect claim.",
                citations=[
                    CandidateCitation(
                        chunk_id=cited_chunk.chunk_id,
                        quote="Neural brain cortex validation quote.",
                    )
                ],
            ),
        ]


class HarnessSupportScorer:
    def score(self, *, sentence: str, passage: str) -> float:
        if "unsupported" in sentence:
            return 0.2
        if "missing quote" in sentence:
            return 0.88
        return 0.91


def test_validation_harness_reports_pdf_fidelity_quotes_zotero_and_retrieval(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    text_pdf = _make_text_pdf(pdf_dir / "text.pdf")
    _make_blank_pdf(pdf_dir / "blank.pdf")
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    output_dir = tmp_path / "validation-output"

    report = run_validation(
        pdf_dir=pdf_dir,
        zotero_dir=zotero_dir,
        output_dir=output_dir,
        quote_checks=[QuoteCheck(pdf_name=text_pdf.name, quote="Neural brain cortex validation quote.")],
        queries=["neural cortex"],
        top_k=2,
        embedding_model=HarnessFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
    )
    markdown = render_markdown_report(report)

    assert (output_dir / "validation.sqlite").exists()
    assert (output_dir / "validation-report.md").exists()
    assert "Callosum Validation Report" in markdown

    reports_by_name = {Path(pdf.path).name: pdf for pdf in report.pdf_reports}
    assert reports_by_name["text.pdf"].chunk_count > 0
    assert reports_by_name["text.pdf"].pages_with_text == 1
    assert reports_by_name["text.pdf"].quote_results[0]["found"] is True
    assert reports_by_name["text.pdf"].quote_results[0]["page_start"] == 1
    assert reports_by_name["blank.pdf"].page_count == 1
    assert reports_by_name["blank.pdf"].chunk_count == 0
    assert reports_by_name["blank.pdf"].zero_text is True

    assert report.zotero_schema is not None
    assert report.zotero_schema.read_only_unchanged is True
    assert "items" in report.zotero_schema.present_tables
    assert report.zotero_import is not None
    assert report.zotero_import.imported_items >= 3
    assert report.zotero_import.missing_attachments >= 1

    assert report.retrieval.embedding_error is None
    assert report.retrieval.chunk_embeddings > 0
    assert "neural cortex" in report.retrieval.query_results
    assert report.retrieval.query_results["neural cortex"][0]["snippet"]


def test_validation_harness_summarization_report_marks_verified_and_flagged_sentences(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_text_pdf(pdf_dir / "text.pdf")
    output_dir = tmp_path / "validation-output"

    report = run_validation(
        pdf_dir=pdf_dir,
        output_dir=output_dir,
        summarization=SummarizationSpec(query="neural cortex"),
        top_k=3,
        embedding_model=HarnessFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        summary_generator=HarnessSummaryGenerator(),
        support_scorer_name="fake-nli",
        support_threshold=0.7,
        support_scorer=HarnessSupportScorer(),
    )
    markdown = render_markdown_report(report)

    assert (output_dir / "validation-report.md").exists()
    assert report.summarization is not None
    assert report.summarization.summary_id is not None
    assert report.summarization.status == "flagged"
    assert report.summarization.verified_sentences == 1
    assert report.summarization.flagged_sentences == 2
    assert [sentence.flagged for sentence in report.summarization.sentences] == [False, True, True]

    statuses = [citation.status for sentence in report.summarization.sentences for citation in sentence.citations]
    assert statuses == ["verified", "weak", "weak"]
    assert [
        (item.rank, item.sentence_ordinal, round(item.score, 2), item.status)
        for item in report.summarization.support_scores
    ] == [
        (1, 0, 0.91, "verified"),
        (2, 1, 0.88, "weak"),
        (3, 2, 0.2, "weak"),
    ]
    assert report.summarization.sentences[0].citations[0].quote_located is True
    assert report.summarization.sentences[1].citations[0].quote_located is False
    assert "## Summarization Probe" in markdown
    assert "Sentence 1: VERIFIED" in markdown
    assert "Sentence 2: FLAGGED" in markdown
    assert "| 3 | 0.200 | weak | 3 |" in markdown


def test_validation_harness_summarization_egress_disabled_skips_generation(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_text_pdf(pdf_dir / "text.pdf")
    output_dir = tmp_path / "validation-output"

    report = run_validation(
        pdf_dir=pdf_dir,
        output_dir=output_dir,
        summarization=SummarizationSpec(query="neural cortex"),
        embedding_model=HarnessFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        gemini_config=GeminiConfig(data_egress_enabled=False),
    )
    markdown = (output_dir / "validation-report.md").read_text(encoding="utf-8")

    assert report.summarization is not None
    assert report.summarization.summary_id is None
    assert report.summarization.skipped_reason == "CALLOSUM_ALLOW_DATA_EGRESS is not enabled"
    assert "Generation skipped: CALLOSUM_ALLOW_DATA_EGRESS is not enabled" in markdown


def test_validation_harness_reuse_db_reuses_existing_chunks_without_duplication(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_text_pdf(pdf_dir / "text.pdf")
    output_dir = tmp_path / "validation-output"

    first = run_validation(pdf_dir=pdf_dir, output_dir=output_dir, queries=[])
    first_counts = _scratch_counts(output_dir)

    second = run_validation(pdf_dir=pdf_dir, output_dir=output_dir, queries=[], reuse_db=True)
    second_counts = _scratch_counts(output_dir)

    assert first.database_reused is False
    assert first_counts["papers"] == 1
    assert first_counts["attachments"] == 1
    assert first_counts["chunks"] > 0
    assert second.database_reused is True
    assert second.pdf_reports[0].reused_existing is True
    assert second.pdf_reports[0].chunk_count == first_counts["chunks"]
    assert second_counts == first_counts


def test_validation_harness_default_fresh_db_wipes_previous_run(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_text_pdf(pdf_dir / "text.pdf")
    output_dir = tmp_path / "validation-output"

    run_validation(pdf_dir=pdf_dir, output_dir=output_dir, queries=[])
    assert _scratch_counts(output_dir)["chunks"] > 0

    report = run_validation(output_dir=output_dir, queries=[])

    assert report.database_reused is False
    assert report.database_migrated is True
    assert _scratch_counts(output_dir) == {"papers": 0, "attachments": 0, "chunks": 0}


def test_validation_harness_reuse_missing_db_creates_without_error(tmp_path: Path) -> None:
    output_dir = tmp_path / "validation-output"

    report = run_validation(output_dir=output_dir, queries=[], reuse_db=True)

    assert (output_dir / "validation.sqlite").exists()
    assert report.database_reused is False
    assert report.database_created is True
    assert report.database_migrated is True
    assert _scratch_counts(output_dir) == {"papers": 0, "attachments": 0, "chunks": 0}


def test_validation_harness_reingesting_same_pdfs_with_reuse_is_idempotent(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_text_pdf(pdf_dir / "text.pdf")
    _make_text_pdf(pdf_dir / "second.pdf")
    output_dir = tmp_path / "validation-output"

    run_validation(pdf_dir=pdf_dir, output_dir=output_dir, queries=[])
    first_counts = _scratch_counts(output_dir)
    run_validation(pdf_dir=pdf_dir, output_dir=output_dir, queries=[], reuse_db=True)
    second_counts = _scratch_counts(output_dir)
    third = run_validation(pdf_dir=pdf_dir, output_dir=output_dir, queries=[], reuse_db=True)
    third_counts = _scratch_counts(output_dir)

    assert first_counts["papers"] == 2
    assert first_counts["attachments"] == 2
    assert first_counts["chunks"] > 0
    assert second_counts == first_counts
    assert third_counts == first_counts
    assert [pdf.reused_existing for pdf in third.pdf_reports] == [True, True]


def test_validation_harness_zero_chunk_summarization_warns_loudly(tmp_path: Path) -> None:
    output_dir = tmp_path / "validation-output"

    report = run_validation(
        output_dir=output_dir,
        summarization=SummarizationSpec(query="neural cortex"),
        embedding_model=HarnessFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        summary_generator=HarnessSummaryGenerator(),
    )
    markdown = (output_dir / "validation-report.md").read_text(encoding="utf-8")

    assert report.summarization is not None
    assert report.summarization.support_scorer == "nli"
    assert report.summarization.support_threshold == 0.55
    assert report.summarization.source_chunk_count == 0
    assert report.summarization.skipped_reason == "no source chunks available"
    assert report.summarization.zero_chunk_message is not None
    assert "No source chunks were available for this summarization scope." in markdown
    assert "Run with --pdf-dir first, or pass --reuse-db with a populated --output-dir." in markdown


def test_validation_harness_reports_corrupt_pdf_without_failing(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "corrupt.pdf").write_bytes(b"not a real pdf")

    report = run_validation(
        pdf_dir=pdf_dir,
        output_dir=tmp_path / "validation-output",
        queries=[],
    )

    assert len(report.pdf_reports) == 1
    assert report.pdf_reports[0].error is not None
    assert report.pdf_reports[0].chunk_count == 0


def test_validation_harness_progress_reports_visible_phases(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_text_pdf(pdf_dir / "text.pdf")
    stream = io.StringIO()

    run_validation(
        pdf_dir=pdf_dir,
        output_dir=tmp_path / "validation-output",
        progress=ProgressReporter(stream=stream),
    )

    output = stream.getvalue()
    assert "Preparing scratch database" in output
    assert "Validating PDFs" in output
    assert "[############################] 1/1" in output
    assert "Writing validation report" in output


def _make_text_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=420, height=420)
    page.insert_text((50, 70), "Neural brain cortex validation quote.", fontsize=12)
    page.insert_text((50, 110), "Another paragraph for extraction.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _make_blank_pdf(path: Path) -> Path:
    document = fitz.open()
    document.new_page(width=420, height=420)
    document.save(path)
    document.close()
    return path


def test_validation_harness_per_page_reporting(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_mixed_pdf(pdf_dir / "mixed.pdf")
    output_dir = tmp_path / "validation-output"

    report = run_validation(
        pdf_dir=pdf_dir,
        output_dir=output_dir,
        queries=[],
    )
    markdown = render_markdown_report(report)

    mixed_report = report.pdf_reports[0]
    assert mixed_report.page_count == 4
    assert mixed_report.pages_with_text == 1
    assert mixed_report.pages_without_text == [2, 3, 4]

    details = {pd.page_number: pd for pd in mixed_report.page_details}
    assert details[1].has_text is True
    assert details[1].hint is None

    assert details[2].has_text is False
    assert "drawing" in details[2].hint

    assert details[3].has_text is False
    assert "image" in details[3].hint

    assert details[4].has_text is False
    assert "empty" in details[4].hint

    # Check markdown content
    assert "Pages without text: 2, 3, 4" in markdown
    assert "Page 2: likely graphic/drawing page" in markdown
    assert "Page 3: likely image/figure page" in markdown
    assert "Page 4: empty page" in markdown

    # Check optional debug images
    debug_dir = output_dir / "debug-images" / "mixed.pdf"
    assert debug_dir.exists()
    assert (debug_dir / "page_2.png").exists()
    assert (debug_dir / "page_3.png").exists()
    assert (debug_dir / "page_4.png").exists()
    assert not (debug_dir / "page_1.png").exists()


def test_axis_calibration_probe_reports_exact_score_distribution(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    model = HarnessFakeEmbeddingModel()
    vector_store = InMemoryVectorStore()

    with engine.begin() as conn:
        first = create_paper(
            conn,
            title="Calibration Strong A",
            abstract="Synthetic calibration paper.",
            csl_json={"id": "cal-a", "type": "article-journal", "title": "Calibration Strong A"},
            processing_tier="abstract-embedded",
        )
        second = create_paper(
            conn,
            title="Calibration Strong B",
            abstract="Synthetic calibration paper.",
            csl_json={"id": "cal-b", "type": "article-journal", "title": "Calibration Strong B"},
            processing_tier="abstract-embedded",
        )
        third = create_paper(
            conn,
            title="Calibration Weak Tail",
            abstract="Synthetic calibration paper.",
            csl_json={"id": "cal-tail", "type": "article-journal", "title": "Calibration Weak Tail"},
            processing_tier="abstract-embedded",
        )
        reports = run_axis_calibration_probe(
            conn,
            axes=[AxisCalibrationSpec(label="Calibration Axis")],
            embedding_model=model,
            vector_store=vector_store,
        )

    axis_report = reports[0]
    assert axis_report.error is None
    assert [(score.rank, score.paper_id, round(score.score, 2)) for score in axis_report.scores] == [
        (1, first, 1.0),
        (2, second, 0.9),
        (3, third, 0.63),
    ]
    assert [None if score.gap_to_next is None else round(score.gap_to_next, 2) for score in axis_report.scores] == [
        0.1,
        0.27,
        None,
    ]
    assert axis_report.largest_gap_rank == 2
    assert round(axis_report.largest_gap, 2) == 0.27

    markdown = render_markdown_report(
        ValidationReport(
            output_dir=str(tmp_path),
            database_path=str(tmp_path / "validation.sqlite"),
            axis_calibration=reports,
        )
    )
    assert "## Axis Calibration" in markdown
    assert "Largest adjacent score gap: rank 2 gap=0.270" in markdown
    assert "| 3 | 0.630 |  |" in markdown


def _make_mixed_pdf(path: Path) -> Path:
    document = fitz.open()
    # Page 1: Text
    page1 = document.new_page(width=400, height=400)
    page1.insert_text((50, 50), "Page 1 text")

    # Page 2: Drawing only
    page2 = document.new_page(width=400, height=400)
    page2.draw_rect((50, 50, 150, 150), color=(1, 0, 0), fill=(0, 1, 0))

    # Page 3: Image only
    page3 = document.new_page(width=400, height=400)
    img = fitz.Pixmap(fitz.csRGB, (0, 0, 10, 10), False)
    img.clear_with(255)
    page3.insert_image((50, 50, 150, 150), pixmap=img)

    # Page 4: Wholly empty
    document.new_page(width=400, height=400)

    document.save(path)
    document.close()
    return path


def _migrated_engine(tmp_path: Path):
    db_path = tmp_path / "callosum-validation-harness.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _scratch_counts(output_dir: Path) -> dict[str, int]:
    engine = make_engine(f"sqlite:///{(output_dir / 'validation.sqlite').as_posix()}")
    try:
        with engine.begin() as conn:
            return {
                "papers": int(conn.execute(select(func.count()).select_from(papers)).scalar_one()),
                "attachments": int(conn.execute(select(func.count()).select_from(attachments)).scalar_one()),
                "chunks": int(conn.execute(select(func.count()).select_from(chunks)).scalar_one()),
            }
    finally:
        engine.dispose()


def _calibration_vector(text: str) -> list[float] | None:
    if "calibration axis" in text:
        return [1.0, 0.0, 0.0]
    if "calibration strong a" in text:
        return [1.0, 0.0, 0.0]
    if "calibration strong b" in text:
        return [0.9, math.sqrt(1 - 0.9**2), 0.0]
    if "calibration weak tail" in text:
        return [0.63, math.sqrt(1 - 0.63**2), 0.0]
    return None
