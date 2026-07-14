from __future__ import annotations

import unicodedata
from pathlib import Path

import fitz

import app.backend.pdf_processing.quote_matching as quote_matching_module
from alembic import command
from alembic.config import Config
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
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import get_chunks_for_paper

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
        chunks = get_chunks_for_paper(conn, result["paper_id"])
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
        chunking_strategy="pymupdf-block-v2",
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
