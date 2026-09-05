from __future__ import annotations

import unicodedata
from pathlib import Path

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

import app.backend.pdf_processing.quote_matching as quote_matching_module
from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from app.backend.embeddings.models import DEFAULT_NORMALIZATION
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.pdf_processing.extraction import (
    COORDINATE_SYSTEM,
    DEFAULT_CHUNKING_STRATEGY,
    _WordToken,
    canonicalize_quote_text,
    extract_pdf,
    file_sha256,
    make_chunk_drafts,
)
from app.backend.pdf_processing.ingest import ingest_pdf_scaffold
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.pdf_processing.quote_matching import locate_quote
from app.backend.pdf_processing.sections import SectionTracker, detect_section_heading
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper, get_chunks_for_paper
from app.backend.persistence.schema import embeddings, papers
from tests.api_helpers import ApiFakeEmbeddingModel

FIXTURE_QUOTES = [
    {
        "name": "single-page",
        "quote": "Alpha beta gamma appears on page one.",
        "page_start": 1,
        "page_end": 1,
    },
    {
        "name": "two-line",
        "quote": "This two line quote begins on the first row and continues on the second row for testing.",
        "page_start": 1,
        "page_end": 1,
        "min_rectangles": 2,
    },
    {
        "name": "cross-page",
        "quote": "Cross page quote starts before the page break and finishes after the page break.",
        "page_start": 1,
        "page_end": 2,
        "min_rectangles": 2,
    },
    {
        "name": "page-two",
        "quote": "Delta epsilon zeta appears on page two.",
        "page_start": 2,
        "page_end": 2,
    },
]


def test_quote_location_benchmark_for_generated_fixture(tmp_path: Path) -> None:
    pdf_path = _make_fixture_pdf(tmp_path / "quote-fixture.pdf")

    for case in FIXTURE_QUOTES:
        match = locate_quote(pdf_path, case["quote"])

        assert match.found, case["name"]
        assert match.page_start == case["page_start"]
        assert match.page_end == case["page_end"]
        assert len(match.rectangles) >= case.get("min_rectangles", 1)
        assert any(rect["page"] == case["page_start"] for rect in match.rectangles)
        for rect in match.rectangles:
            assert rect["x1"] > rect["x0"]
            assert rect["y1"] > rect["y0"]

    absent = locate_quote(pdf_path, "This sentence is absent from the document.")
    assert absent.found is False
    assert absent.rectangles == ()


def _make_two_column_pdf(path: Path) -> Path:
    # Two clearly separated columns. PyMuPDF's geometric word sort (sort=True) orders top-to-bottom,
    # left-to-right, so it interleaves the two columns row-by-row; reading order (block/line/word)
    # keeps each column contiguous — matching how chunk text is extracted.
    document = fitz.open()
    page = document.new_page(width=612, height=300)
    page.insert_text((50, 80), "The anomalous stereotype was", fontsize=11)
    page.insert_text((50, 100), "clearly measured across trials.", fontsize=11)
    page.insert_text((360, 80), "Sidebar annotation alpha here", fontsize=11)
    page.insert_text((360, 100), "and sidebar annotation beta.", fontsize=11)
    document.save(str(path))
    document.close()
    return path


def test_two_column_quote_locates_in_reading_order_not_geometric(tmp_path: Path) -> None:
    # A single-column passage must locate even though a geometric word sort splices the other column
    # into the middle of it. Regression for the ~47% region-fallback rate measured on the real library.
    pdf_path = _make_two_column_pdf(tmp_path / "two-column.pdf")

    match = locate_quote(pdf_path, "The anomalous stereotype was clearly measured across trials.")
    assert match.found
    assert match.page_start == 1 and match.page_end == 1
    assert len(match.rectangles) >= 2

    # Honesty (#2): a string that only exists by interleaving the two columns must NOT match.
    interleaved = locate_quote(pdf_path, "The anomalous stereotype was Sidebar annotation alpha here")
    assert interleaved.found is False


def test_extraction_ingest_writes_chunks_with_provenance(tmp_path: Path) -> None:
    pdf_path = _make_fixture_pdf(tmp_path / "ingest-fixture.pdf")
    db_path = tmp_path / "callosum-pdf.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)

    with engine.begin() as conn:
        result = ingest_pdf_scaffold(conn, pdf_path, title="Generated Quote Fixture")
        chunks = get_chunks_for_paper(conn, result["paper_id"], document_roles=ARTICLE_DOCUMENT_ROLES)
        attachment_match = locate_quote_for_attachment(
            conn,
            result["attachment_id"],
            "Delta epsilon zeta appears on page two.",
        )

    assert chunks
    assert attachment_match.found
    assert attachment_match.page_start == 2
    for chunk in chunks:
        assert chunk["extraction_tool"] == "pymupdf"
        assert chunk["extraction_version"]
        assert chunk["chunking_strategy"] == DEFAULT_CHUNKING_STRATEGY
        assert chunk["chunk_version"]
        assert chunk["source_attachment_checksum"] == result["checksum"]
        assert chunk["bbox_coordinate_system"] == COORDINATE_SYSTEM
        assert chunk["page_start"] >= 1
        assert chunk["page_end"] >= chunk["page_start"]
        assert chunk["bbox_json"]


def test_section_heading_detection_is_conservative() -> None:
    heading = detect_section_heading("1. Methods")
    data_heading = detect_section_heading("Data availability statement")

    assert heading is not None
    assert heading.key == "methods"
    assert data_heading is not None
    assert data_heading.key == "data_availability"
    assert detect_section_heading("The methods were preregistered.") is None
    assert detect_section_heading("Methods, materials, and recruitment") is None

    tracker = SectionTracker()
    assert tracker.observe("Abstract").key == "abstract"
    assert tracker.current_section == "abstract"
    assert tracker.observe("The methods were preregistered.") is None
    assert tracker.current_section == "abstract"


def test_observe_block_labels_merged_heading_and_body() -> None:
    # The common PyMuPDF case: a heading is merged with its following body into one block. The whole
    # block is not heading-shaped, but its first line is — the section must still be picked up, and the
    # block must NOT be skipped (skipping it would drop the body text).
    tracker = SectionTracker()
    skip = tracker.observe_block("Methods\nParticipants were recruited from the community.")
    assert tracker.current_section == "methods"
    assert skip is False

    # A pure single-line heading block is skipped (not emitted as a chunk) and advances the section.
    assert tracker.observe_block("Results") is True
    assert tracker.current_section == "results"

    # A block with no heading leaves the section unchanged and is emitted.
    assert tracker.observe_block("We then computed the correlation between the two measures.") is False
    assert tracker.current_section == "results"

    # A heading that is not the first line (e.g. after a running-header line) is still detected.
    later = SectionTracker()
    assert later.observe_block("Neuropsychopharmacology\nDISCUSSION\nOur findings suggest") is False
    assert later.current_section == "discussion"

    # A body sentence that superficially resembles a heading (trailing period) is not one.
    prose = SectionTracker()
    assert prose.observe_block("The results were analyzed with a mixed-effects model.") is False
    assert prose.current_section is None


def test_default_chunking_strategy_bumped_for_section_detection() -> None:
    # Section detection changed chunk output materially (inc 283); the version bump is what lets
    # text-health flag pre-section chunks as stale instead of masquerading as current.
    assert DEFAULT_CHUNKING_STRATEGY == "pymupdf-block-v2"


def test_section_headings_are_attached_to_following_chunks(tmp_path: Path) -> None:
    pdf_path = _make_sectioned_pdf(tmp_path / "sectioned.pdf")
    chunks = make_chunk_drafts(extract_pdf(pdf_path), source_attachment_checksum=file_sha256(pdf_path))
    sectioned_text = {(chunk.section, chunk.text) for chunk in chunks}

    assert ("abstract", "Data are available at OSF.") in sectioned_text
    assert ("methods", "We recruited participants and analyzed survey responses.") in sectioned_text
    assert ("data_availability", "The analysis code is available at GitHub.") in sectioned_text
    assert "Abstract" not in {chunk.text for chunk in chunks}
    assert "Methods" not in {chunk.text for chunk in chunks}


def test_section_metadata_survives_pdf_ingest(tmp_path: Path) -> None:
    pdf_path = _make_sectioned_pdf(tmp_path / "sectioned-ingest.pdf")
    db_path = tmp_path / "callosum-sectioned.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)

    with engine.begin() as conn:
        result = ingest_pdf_scaffold(conn, pdf_path, title="Sectioned Fixture")
        chunks = get_chunks_for_paper(conn, result["paper_id"], document_roles=ARTICLE_DOCUMENT_ROLES)

    sections_by_text = {chunk["text"]: chunk["section"] for chunk in chunks}
    assert sections_by_text["Data are available at OSF."] == "abstract"
    assert sections_by_text["We recruited participants and analyzed survey responses."] == "methods"
    assert sections_by_text["The analysis code is available at GitHub."] == "data_availability"


def test_reprocess_pdf_endpoint_replaces_chunks_and_preserves_paper(tmp_path: Path) -> None:
    pdf_path = _make_sectioned_pdf(tmp_path / "sectioned-reprocess.pdf")
    db_path = tmp_path / "callosum-reprocess.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)
    store = InMemoryVectorStore()

    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Keep Metadata", csl_json={"title": "Keep Metadata"}, doi="10.1/keep")
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(pdf_path),
            resolved_path=str(pdf_path),
            checksum="old-checksum",
            file_size=pdf_path.stat().st_size,
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
        old_chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="old extracted text",
            page_start=1,
            page_end=1,
            bbox_coordinate_system=COORDINATE_SYSTEM,
            extraction_tool="old",
            extraction_version="0",
            chunking_strategy="old",
            chunk_version="old",
            source_attachment_checksum="old-checksum",
            bbox_json=[{"page": 1, "x0": 1, "y0": 1, "x1": 2, "y1": 2}],
        )
        old_embedding_id = int(
            conn.execute(
                insert(embeddings).values(
                    target_type="chunk",
                    target_id=old_chunk_id,
                    model_name="m",
                    model_version="v",
                    dimension=2,
                    normalization=DEFAULT_NORMALIZATION,
                    source_text_version="t1",
                    source_chunk_version="old",
                )
            ).inserted_primary_key[0]
        )
        store.add(conn, embedding_id=old_embedding_id, vector=[0.0, 1.0])

    response = TestClient(create_app(db_url=url, vector_store=store, embedding_model=ApiFakeEmbeddingModel())).post(
        f"/papers/{paper_id}/reprocess-pdf"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attachment_id"] == attachment_id
    assert body["chunks_removed"] == 1
    assert body["chunks_created"] == 3
    with engine.begin() as conn:
        saved_paper = conn.execute(select(papers).where(papers.c.id == paper_id)).mappings().one()
        saved_chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES)
        saved_ids = [chunk["id"] for chunk in saved_chunks]
        embedded_current = conn.execute(
            select(func.count())
            .select_from(embeddings)
            .where(embeddings.c.target_type == "chunk", embeddings.c.target_id.in_(saved_ids))
        ).scalar_one()
        orphan_embeddings = conn.execute(
            select(func.count())
            .select_from(embeddings)
            .where(embeddings.c.target_type == "chunk", embeddings.c.target_id.not_in(saved_ids))
        ).scalar_one()
    engine.dispose()

    assert saved_paper["title"] == "Keep Metadata"
    assert saved_paper["doi"] == "10.1/keep"
    # Reprocess replaced the stale embedding: the old chunk (and its embedding) is gone, every new chunk is
    # (re)embedded, no orphaned embedding points at a deleted chunk, and the vector store holds exactly the new set.
    assert embedded_current == len(saved_chunks) == 3
    assert orphan_embeddings == 0
    assert len(store.vectors) == 3
    assert {chunk["text"] for chunk in saved_chunks} == {
        "Data are available at OSF.",
        "We recruited participants and analyzed survey responses.",
        "The analysis code is available at GitHub.",
    }
    assert {chunk["section"] for chunk in saved_chunks} == {"abstract", "methods", "data_availability"}
    assert "old extracted text" not in {chunk["text"] for chunk in saved_chunks}


def test_reprocess_pdf_endpoint_rejects_paper_without_local_pdf(tmp_path: Path) -> None:
    db_path = tmp_path / "callosum-reprocess-missing.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="No PDF", csl_json={"title": "No PDF"})
    engine.dispose()

    response = TestClient(create_app(db_url=url)).post(f"/papers/{paper_id}/reprocess-pdf")

    assert response.status_code == 422
    assert "no local PDF" in response.json()["detail"]


def test_changed_chunking_strategy_changes_chunk_version(tmp_path: Path) -> None:
    pdf_path = _make_fixture_pdf(tmp_path / "version-fixture.pdf")
    checksum = file_sha256(pdf_path)
    extraction = extract_pdf(pdf_path)

    default_chunks = make_chunk_drafts(
        extraction,
        source_attachment_checksum=checksum,
        chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
    )
    alternate_chunks = make_chunk_drafts(
        extraction,
        source_attachment_checksum=checksum,
        chunking_strategy="pymupdf-block-alt",
    )

    assert default_chunks
    assert alternate_chunks
    assert default_chunks[0].chunk_version != alternate_chunks[0].chunk_version


def test_span_boundary_preserves_word_space_in_chunk_text(tmp_path: Path) -> None:
    pdf_path = _make_span_boundary_pdf(tmp_path / "span-boundary.pdf")
    extraction = extract_pdf(pdf_path)
    chunks = make_chunk_drafts(extraction, source_attachment_checksum=file_sha256(pdf_path))

    assert chunks
    assert "we tested the hypothesis" in chunks[0].text
    assert "testedthe" not in chunks[0].text


def test_text_from_extracted_chunk_is_locatable(tmp_path: Path) -> None:
    pdf_path = _make_span_boundary_pdf(tmp_path / "locatable-span-boundary.pdf")
    extraction = extract_pdf(pdf_path)
    chunks = make_chunk_drafts(extraction, source_attachment_checksum=file_sha256(pdf_path))
    quote = "we tested the hypothesis"

    assert quote in chunks[0].text
    match = locate_quote(pdf_path, quote)

    assert match.found
    assert match.page_start == 1
    assert match.rectangles
    assert match.rectangles[0]["x1"] > match.rectangles[0]["x0"]


def test_mid_word_span_boundary_does_not_insert_space(tmp_path: Path) -> None:
    pdf_path = _make_span_boundary_pdf(tmp_path / "mid-word-boundary.pdf")
    extraction = extract_pdf(pdf_path)
    chunks = make_chunk_drafts(extraction, source_attachment_checksum=file_sha256(pdf_path))
    combined_text = " ".join(chunk.text for chunk in chunks)

    assert "anomalous" in combined_text
    assert "anom alous" not in combined_text


def test_hyphenated_line_break_quote_locates_with_real_coordinates(tmp_path: Path) -> None:
    pdf_path = _make_hyphenated_line_break_pdf(tmp_path / "hyphenated-line-break.pdf")

    match = locate_quote(pdf_path, "beautiful faces")
    faithful_match = locate_quote(pdf_path, "beau- tiful faces")

    assert match.found
    assert match.page_start == 1
    assert match.page_end == 1
    assert len(match.rectangles) >= 2
    assert {rect["line"] for rect in match.rectangles} == {0, 1}
    assert all(rect["page"] == 1 for rect in match.rectangles)
    assert all(rect["x1"] > rect["x0"] and rect["y1"] > rect["y0"] for rect in match.rectangles)
    assert faithful_match.found


def test_partial_compound_line_break_quote_locates(tmp_path: Path) -> None:
    pdf_path = _make_partial_compound_break_pdf(tmp_path / "partial-compound-break.pdf")

    broken_quote = locate_quote(pdf_path, "beauty-is- good stereotype")
    unbroken_quote = locate_quote(pdf_path, "beauty-is-good stereotype")

    assert broken_quote.found
    assert broken_quote.page_start == 1
    assert broken_quote.page_end == 1
    assert len(broken_quote.rectangles) >= 2
    assert {rect["line"] for rect in broken_quote.rectangles} == {0, 1}
    assert unbroken_quote.found


def test_same_line_compound_hyphen_is_preserved(tmp_path: Path) -> None:
    pdf_path = _make_same_line_compound_pdf(tmp_path / "same-line-compound.pdf")

    exact = locate_quote(pdf_path, "anomalous-is-bad stereotype")
    dropped_hyphen = locate_quote(pdf_path, "anomalous-isbad stereotype")

    assert exact.found
    assert exact.page_start == 1
    assert len(exact.rectangles) == 1
    assert dropped_hyphen.found is False


def test_digit_adjacent_line_break_hyphens_are_kept(monkeypatch) -> None:
    words = [
        ("α2-", 0),
        ("integrin", 1),
        ("and", 1),
        ("5-", 2),
        ("HT", 3),
        ("signaling", 3),
    ]
    tokens, document_text = _fake_word_tokens_with_lines(words)
    monkeypatch.setattr(quote_matching_module, "_word_tokens_for_pdf", lambda pdf_path: (tokens, document_text))

    exact = locate_quote("unused.pdf", "α2-integrin and 5-HT")
    dropped = locate_quote("unused.pdf", "α2integrin and 5HT")

    assert exact.found
    assert exact.page_start == 1
    assert len(exact.rectangles) >= 4
    assert dropped.found is False


def test_prefix_allow_list_line_break_hyphen_is_kept(monkeypatch) -> None:
    tokens, document_text = _fake_word_tokens_with_lines(
        [
            ("anti-", 0),
            ("inflammatory", 1),
            ("response", 1),
        ]
    )
    monkeypatch.setattr(quote_matching_module, "_word_tokens_for_pdf", lambda pdf_path: (tokens, document_text))

    exact = locate_quote("unused.pdf", "anti-inflammatory response")
    dropped = locate_quote("unused.pdf", "antiinflammatory response")

    assert exact.found
    assert {rect["line"] for rect in exact.rectangles} == {0, 1}
    assert dropped.found is False


def test_multiple_line_break_hyphens_canonicalize_without_recursive_suffix_work() -> None:
    text = " ".join(["unusu-\nal"] * 12)

    assert canonicalize_quote_text(text) == " ".join(["unusual"] * 12)


def test_ligature_quote_location_uses_canonical_text_without_losing_coordinates(monkeypatch) -> None:
    document_text = "The di\ufb03cult \ufb01nd appears here."
    words = ["The", "di\ufb03cult", "\ufb01nd", "appears", "here."]
    tokens = _fake_word_tokens(words)

    monkeypatch.setattr(quote_matching_module, "_word_tokens_for_pdf", lambda pdf_path: (tokens, document_text))

    match = locate_quote("unused.pdf", "difficult find appears")

    assert match.found
    assert match.page_start == 1
    assert len(match.rectangles) == 1
    assert match.rectangles[0]["x0"] == 55.0
    assert match.rectangles[0]["x1"] == 155.0


def test_canonicalization_uses_nfc_without_nfkc_loss(monkeypatch) -> None:
    text = "The ½ dose and p² marker remained."
    tokens, document_text = _fake_word_tokens_with_lines(
        [
            ("The", 0),
            ("½", 0),
            ("dose", 0),
            ("and", 0),
            ("p²", 0),
            ("marker", 0),
            ("remained.", 0),
        ]
    )
    monkeypatch.setattr(quote_matching_module, "_word_tokens_for_pdf", lambda pdf_path: (tokens, document_text))

    canonical = canonicalize_quote_text(text)
    match = locate_quote("unused.pdf", "½ dose and p² marker")

    assert unicodedata.normalize("NFKC", text) != canonical
    assert canonical == text
    assert match.found
    assert match.page_start == 1


def test_tolerant_quote_location_still_rejects_altered_quote(tmp_path: Path) -> None:
    pdf_path = _make_hyphenated_line_break_pdf(tmp_path / "altered-quote.pdf")

    altered = locate_quote(pdf_path, "beautiful hands")
    fabricated = locate_quote(pdf_path, "totally fabricated quote")

    assert altered.found is False
    assert altered.rectangles == ()
    assert fabricated.found is False
    assert fabricated.rectangles == ()


def _make_fixture_pdf(path: Path) -> Path:
    document = fitz.open()
    page_one = document.new_page(width=420, height=420)
    page_one.insert_text((50, 70), "Alpha beta gamma appears on page one.", fontsize=12)
    page_one.insert_text((50, 105), "This two line quote begins on the first row", fontsize=12)
    page_one.insert_text((50, 122), "and continues on the second row for testing.", fontsize=12)
    page_one.insert_text((50, 360), "Cross page quote starts before the page break", fontsize=12)

    page_two = document.new_page(width=420, height=420)
    page_two.insert_text((50, 70), "and finishes after the page break.", fontsize=12)
    page_two.insert_text((50, 115), "Delta epsilon zeta appears on page two.", fontsize=12)

    document.save(path)
    document.close()
    return path


def _make_sectioned_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=560, height=360)
    page.insert_text((50, 45), "Abstract", fontsize=16)
    page.insert_text((50, 85), "Data are available at OSF.", fontsize=12)
    page.insert_text((50, 135), "Methods", fontsize=16)
    page.insert_text((50, 175), "We recruited participants and analyzed survey responses.", fontsize=12)
    page.insert_text((50, 225), "Data availability statement", fontsize=16)
    page.insert_text((50, 265), "The analysis code is available at GitHub.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _make_span_boundary_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=500, height=200)
    page.insert_text((50, 70), "we tested", fontsize=12)
    page.insert_text((105, 70), "the hypothesis", fontsize=12)
    page.insert_text((50, 105), "anom", fontsize=12)
    page.insert_text((79, 105), "alous", fontsize=12, fontname="tiro")
    document.save(path)
    document.close()
    return path


def _make_hyphenated_line_break_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=500, height=220)
    page.insert_text((50, 70), "The study described beau-", fontsize=12)
    page.insert_text((50, 88), "tiful faces in the condition.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _make_partial_compound_break_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=520, height=220)
    page.insert_text((50, 70), "The result supported a beauty-is-", fontsize=12)
    page.insert_text((50, 88), "good stereotype in the sample.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _make_same_line_compound_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=520, height=220)
    page.insert_text((50, 70), "The anomalous-is-bad stereotype was tested.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _fake_word_tokens(words: list[str]) -> list[_WordToken]:
    tokens, _ = _fake_word_tokens_with_lines([(word, 0) for word in words])
    return tokens


def _fake_word_tokens_with_lines(words: list[tuple[str, int]]) -> tuple[list[_WordToken], str]:
    tokens = []
    pieces = []
    cursor = 0
    word_indexes_by_line: dict[int, int] = {}
    for index, (word, line_number) in enumerate(words):
        if index:
            pieces.append(" ")
            cursor += 1
        pieces.append(word)
        start = cursor
        cursor += len(word)
        word_number = word_indexes_by_line.get(line_number, 0)
        word_indexes_by_line[line_number] = word_number + 1
        tokens.append(
            _WordToken(
                text=word,
                page_number=1,
                block_number=0,
                line_number=line_number,
                word_number=word_number,
                bbox={
                    "x0": 20.0 + word_number * 35.0,
                    "y0": 40.0 + line_number * 16.0,
                    "x1": 50.0 + word_number * 35.0,
                    "y1": 52.0 + line_number * 16.0,
                },
                start=start,
                end=cursor,
            )
        )
    return tokens, "".join(pieces)


# --- exact-anchor regression, through the REAL locator (inc 577) --------------------------------
#
# The evidence-hygiene study found this failure class INVISIBLE to the existing suite:
# tests/test_quote_matching.py monkeypatches `locate_quote` away, so a change that improved
# retrieval while silently degrading in-PDF highlighting would pass everything. These cases run
# `locate_quote_for_attachment` for real, against real PDFs, through a real attachment row.
#
# The distinction being protected is the one production already makes and must keep making:
#
#   semantic quote verification  !=  PDF coordinate localization
#
# Failing to recover a rectangle degrades PRECISION to region; it must never retroactively make an
# already-verified quote semantically false (see pdf_processing/location.py's own docstring).

EXACT_ANCHOR_CASES = [
    {
        "name": "ordinary-exact",
        "pdf": "_make_fixture_pdf",
        "quote": "Alpha beta gamma appears on page one.",
        "expect_exact": True,
    },
    {
        # A discretionary hyphen split across a line break: the canonicalizer's own reason for being.
        "name": "line-break-hyphen",
        "pdf": "_make_hyphenated_line_break_pdf",
        "quote": "The study described beautiful faces in the condition.",
        "expect_exact": True,
    },
    {
        # A genuine compound must survive as a compound, not be silently joined.
        "name": "genuine-compound",
        "pdf": "_make_same_line_compound_pdf",
        "quote": None,  # resolved from the fixture's own text below
        "expect_exact": True,
    },
    {
        "name": "absent-quote-is-not-anchored",
        "pdf": "_make_fixture_pdf",
        "quote": "This sentence is absent from the document entirely.",
        "expect_exact": False,
    },
]


def _attach_pdf(conn, pdf_path: Path) -> int:
    paper_id = create_paper(conn, title="Anchor Fixture", csl_json={"title": "Anchor Fixture"})
    return create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        original_path=str(pdf_path),
        resolved_path=str(pdf_path),
        checksum="anchor-fixture",
        file_size=pdf_path.stat().st_size,
        content_type="application/pdf",
        attachment_type="pdf",
        role="primary",
    )


def test_exact_anchor_rate_through_the_real_locator(tmp_path: Path) -> None:
    """Locks the exact-anchor rate in. No monkeypatching: this is the real PDF path."""
    from app.backend.pdf_processing.location import locate_quote_for_attachment

    url = f"sqlite:///{tmp_path / 'anchors.sqlite'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)

    generators = {
        "_make_fixture_pdf": _make_fixture_pdf,
        "_make_hyphenated_line_break_pdf": _make_hyphenated_line_break_pdf,
        "_make_same_line_compound_pdf": _make_same_line_compound_pdf,
    }
    exact = 0
    expected_exact = 0
    for case in EXACT_ANCHOR_CASES:
        pdf_path = generators[case["pdf"]](tmp_path / f"{case['name']}.pdf")
        quote = case["quote"]
        if quote is None:
            page_text = fitz.open(pdf_path)[0].get_text().split("\n")
            quote = " ".join(line.strip() for line in page_text if line.strip())
        with engine.begin() as conn:
            attachment_id = _attach_pdf(conn, pdf_path)
            match = locate_quote_for_attachment(conn, attachment_id, quote)

        got_exact = bool(match.found and match.rectangles)
        assert got_exact == case["expect_exact"], f"{case['name']}: exact={got_exact}"
        exact += int(got_exact)
        expected_exact += int(case["expect_exact"])
        if got_exact:
            for rect in match.rectangles:
                assert rect["x1"] > rect["x0"] and rect["y1"] > rect["y0"], case["name"]

    assert exact == expected_exact


def test_a_missing_pdf_degrades_precision_without_falsifying_the_quote(tmp_path: Path) -> None:
    """The production invariant, pinned: an unlocatable rectangle is a PRECISION fact, not a
    semantic one. `_quote_confidence` establishes verbatim-in-chunk BEFORE any PDF access, so a
    moved file must degrade exact -> region rather than make a verified quote false."""
    from app.backend.pdf_processing.extraction import canonical_text_contains
    from app.backend.pdf_processing.location import locate_quote_for_attachment

    url = f"sqlite:///{tmp_path / 'missing.sqlite'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)

    pdf_path = _make_fixture_pdf(tmp_path / "will-move.pdf")
    quote = "Alpha beta gamma appears on page one."
    chunk_text = f"Preamble. {quote} Trailing sentence."
    with engine.begin() as conn:
        attachment_id = _attach_pdf(conn, pdf_path)
    pdf_path.unlink()  # the file moves after extraction, as linked files do

    with engine.begin() as conn:
        match = locate_quote_for_attachment(conn, attachment_id, quote)

    assert match.found is False  # no rectangle: coordinate localization failed
    # ...but the SEMANTIC question is answered from the stored chunk text and is unaffected.
    assert canonical_text_contains(needle=quote, haystack=chunk_text) is True
