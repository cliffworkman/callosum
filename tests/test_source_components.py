"""Regression coverage for deterministic source-component preservation (inc 578, H1b).

The structural failures the two evidence-unit studies established are promoted here as explicit
cases. ``build_page`` performs no I/O by design, so most tests build a PyMuPDF page dict from
literals and never need a PDF, a database or a network call.

The load-bearing properties are NEGATIVE and they matter more than the positive ones:

* a preserved heading must NOT become retrievable evidence,
* a vector drawing must NOT become a figure,
* the post-sort ordinal must NOT be mistaken for MuPDF's native block number,
* and the whole representation must NOT be visible to retrieval, embeddings, prompts or the
  verifier. H1b is observational substrate; if any of those start reading it, H1b has failed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.backend.pdf_processing.source_components import (
    HEADING,
    IMAGE,
    LINE,
    SPAN,
    TEXT_BLOCK,
    build_page,
    component_counts,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import chunks, papers
from app.backend.persistence.schema_source_components import (
    SOURCE_DERIVATION_VERSION,
    source_components,
    source_pages,
)
from app.backend.persistence.source_components_repo import (
    attachments_with_current_source,
    components_for_page,
    replace_attachment_source,
    source_page_for,
)

# --- literal page-dict builders (no PDF, no database) ---


def _span(text: str, bbox, *, font="Times", size=10.0, flags=0) -> dict:
    return {"text": text, "bbox": bbox, "font": font, "size": size, "flags": flags}


def _line(spans: list[dict], bbox, *, direction=(1.0, 0.0), wmode=0) -> dict:
    return {"spans": spans, "bbox": bbox, "dir": direction, "wmode": wmode}


def _text_block(number: int, bbox, lines: list[dict]) -> dict:
    return {"type": 0, "number": number, "bbox": bbox, "lines": lines}


def _image_block(number: int, bbox) -> dict:
    # PyMuPDF image blocks carry 13 fields; ingest drops all of them today. Only the geometry is
    # preserved by H1b -- deliberately no pixels, no colorspace, no interpretation.
    return {"type": 1, "number": number, "bbox": bbox, "width": 100, "height": 50, "ext": "png"}


def _simple_page(blocks: list[dict]) -> dict:
    return {"width": 612.0, "height": 792.0, "blocks": blocks}


def _prose_block(number: int, y: float, text: str = "Participants completed the task in one session.") -> dict:
    return _text_block(
        number,
        (72.0, y, 400.0, y + 12.0),
        [_line([_span(text, (72.0, y, 400.0, y + 12.0))], (72.0, y, 400.0, y + 12.0))],
    )


# --- 1-5: page geometry and the two orders ---


def test_page_dimensions_and_rotation_are_preserved() -> None:
    page = build_page(_simple_page([_prose_block(0, 100.0)]), page_number=3, width=612.0, height=792.0, rotation=90)
    assert (page.width, page.height) == (612.0, 792.0)
    assert page.rotation == 90
    assert page.page_number == 3


@pytest.mark.parametrize(
    "raw,expected", [(0, 0), (90, 90), (180, 180), (270, 270), (360, 0), (-90, 270), (45, 0), (None, 0)]
)
def test_rotation_is_normalized_to_a_representable_value(raw, expected) -> None:
    """A malformed rotation must not fail an ingest whose chunks are perfectly fine."""
    page = build_page(_simple_page([_prose_block(0, 100.0)]), page_number=1, width=612.0, height=792.0, rotation=raw)
    assert page.rotation == expected


def test_block_bbox_is_preserved() -> None:
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (10.0, 20.0, 30.0, 40.0),
                    [_line([_span("x", (10.0, 20.0, 30.0, 40.0))], (10.0, 20.0, 30.0, 40.0))],
                )
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    assert page.components[0].bbox == (10.0, 20.0, 30.0, 40.0)


def test_native_and_sorted_order_are_separate_fields() -> None:
    page = build_page(_simple_page([_prose_block(7, 100.0)]), page_number=1, width=612.0, height=792.0)
    block = page.components[0]
    assert block.native_order == 7, "native_order must be MuPDF's own block['number']"
    assert block.sorted_order == 0, "sorted_order must be the position in the sorted list"


def test_the_two_orders_can_demonstrably_disagree() -> None:
    """The central trap: sort=True reorders blocks WITHOUT renumbering them.

    Measured on real PDFs this happens on most pages (117 of 184 on a 12-PDF probe). If these ever
    became one field, every future reconstruction would silently inherit the wrong reading order.
    """
    # As MuPDF would hand them back after sort=True: geometrically ordered, natively numbered 14/0/1.
    page = build_page(
        _simple_page([_image_block(14, (25.0, 5.0, 89.0, 18.0)), _prose_block(0, 35.0), _prose_block(1, 70.0)]),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    natives = [c.native_order for c in page.components]
    sorteds = [c.sorted_order for c in page.components]
    assert natives == [14, 0, 1]
    assert sorteds == [0, 1, 2]
    assert natives != sorteds
    assert natives != sorted(natives), "this fixture must actually exercise the disagreement"


def test_sorted_order_counts_image_blocks_like_the_bbox_json_ordinal_does() -> None:
    """`chunks.bbox_json["block"]` counts image blocks that are then dropped, so it has gaps.

    `sorted_order` reproduces that ordinal exactly -- which is what makes the two comparable --
    while `native_order` remains a different numbering space that must never be conflated with it.
    """
    page = build_page(
        _simple_page([_prose_block(0, 35.0), _image_block(9, (25.0, 50.0, 89.0, 70.0)), _prose_block(1, 100.0)]),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    text_blocks = [c for c in page.components if c.kind == TEXT_BLOCK]
    assert [c.sorted_order for c in text_blocks] == [0, 2], "the image consumed ordinal 1"
    assert [c.native_order for c in text_blocks] == [0, 1], "native numbering is unaffected by that gap"


# --- 7-8: hierarchy and per-span geometry ---


def test_line_and_span_hierarchy_survives() -> None:
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (72.0, 100.0, 400.0, 130.0),
                    [
                        _line(
                            [_span("first ", (72.0, 100.0, 120.0, 112.0)), _span("line", (120.0, 100.0, 160.0, 112.0))],
                            (72.0, 100.0, 160.0, 112.0),
                        ),
                        _line([_span("second line", (72.0, 118.0, 200.0, 130.0))], (72.0, 118.0, 200.0, 130.0)),
                    ],
                )
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    block = page.components[0]
    assert block.kind == TEXT_BLOCK
    assert [line.kind for line in block.children] == [LINE, LINE]
    assert [len(line.children) for line in block.children] == [2, 1]
    assert all(span.kind == SPAN for line in block.children for span in line.children)
    assert [line.child_order for line in block.children] == [0, 1]
    assert [s.child_order for s in block.children[0].children] == [0, 1]


def test_each_span_keeps_its_own_text_geometry_and_style() -> None:
    """Mapping a value like "p = .761" back to its own rectangle is exactly what H1c needs."""
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (72.0, 100.0, 300.0, 112.0),
                    [
                        _line(
                            [
                                _span("Cohen's d = ", (72.0, 100.0, 140.0, 112.0), font="Times", size=10.0, flags=0),
                                _span("p = .761", (140.0, 100.0, 200.0, 112.0), font="Times-Bold", size=9.5, flags=16),
                            ],
                            (72.0, 100.0, 200.0, 112.0),
                        )
                    ],
                )
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    spans = page.components[0].children[0].children
    assert spans[1].text == "p = .761"
    assert spans[1].bbox == (140.0, 100.0, 200.0, 112.0)
    assert spans[1].font == "Times-Bold"
    assert spans[1].font_size == 9.5
    assert spans[1].flags == 16
    assert spans[0].bbox != spans[1].bbox, "sibling spans must not share one rectangle"


def test_exact_span_text_is_not_whitespace_normalized() -> None:
    """chunks.text is whitespace-collapsed; source components are structural provenance instead."""
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (0.0, 0.0, 10.0, 10.0),
                    [_line([_span("  double  spaced  ", (0.0, 0.0, 10.0, 10.0))], (0.0, 0.0, 10.0, 10.0))],
                )
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    assert page.components[0].children[0].children[0].text == "  double  spaced  "


def test_line_direction_and_wmode_are_preserved() -> None:
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (0.0, 0.0, 10.0, 10.0),
                    [
                        _line(
                            [_span("x", (0.0, 0.0, 10.0, 10.0))], (0.0, 0.0, 10.0, 10.0), direction=(0.0, -1.0), wmode=1
                        )
                    ],
                )
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    line = page.components[0].children[0]
    assert (line.dir_x, line.dir_y, line.wmode) == (0.0, -1.0, 1)


# --- 9-12: headings, evidence boundary, images, vector drawings ---


def test_pure_headings_survive_as_components() -> None:
    """Ingest recognizes a pure heading, advances the section tracker, and emits NO chunk -- the
    text is lost outright today. H1b preserves it."""
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (72.0, 100.0, 140.0, 112.0),
                    [_line([_span("Methods", (72.0, 100.0, 140.0, 112.0))], (72.0, 100.0, 140.0, 112.0))],
                )
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    assert page.components[0].kind == HEADING
    assert page.components[0].text == "Methods"


def test_a_heading_merged_with_body_prose_is_not_a_pure_heading() -> None:
    """PyMuPDF often merges heading + body into one block; that block still becomes a chunk."""
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (72.0, 100.0, 400.0, 130.0),
                    [
                        _line([_span("Methods", (72.0, 100.0, 140.0, 112.0))], (72.0, 100.0, 140.0, 112.0)),
                        _line(
                            [_span("Participants were recruited online.", (72.0, 118.0, 400.0, 130.0))],
                            (72.0, 118.0, 400.0, 130.0),
                        ),
                    ],
                )
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    assert page.components[0].kind == TEXT_BLOCK


def test_a_heading_is_not_bound_to_neighbouring_prose() -> None:
    """Heading/body scope is an H1c question. H1b must not assert the association."""
    page = build_page(
        _simple_page(
            [
                _text_block(
                    0,
                    (72.0, 100.0, 140.0, 112.0),
                    [_line([_span("Results", (72.0, 100.0, 140.0, 112.0))], (72.0, 100.0, 140.0, 112.0))],
                ),
                _prose_block(1, 130.0),
            ]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    heading, prose = page.components
    assert heading.kind == HEADING
    assert prose.kind == TEXT_BLOCK
    assert heading.children != prose.children
    # The heading owns only its own lines; it never adopts the following block.
    assert all(child.kind == LINE for child in heading.children)
    assert prose not in heading.children


def test_image_bounds_survive_without_any_figure_claim() -> None:
    page = build_page(
        _simple_page([_image_block(3, (25.0, 5.0, 89.0, 18.0))]), page_number=1, width=612.0, height=792.0
    )
    image = page.components[0]
    assert image.kind == IMAGE
    assert image.bbox == (25.0, 5.0, 89.0, 18.0)
    assert image.text is None, "an image block carries no text and must not invent any"
    assert image.children == (), "a raster block has no line/span structure"


def test_raw_vector_drawings_do_not_become_components() -> None:
    """Vector drawing groups were measured as extremely noisy (43,837 groups over 161 pages) and
    are deliberately out of scope. Only PyMuPDF block types 0 and 1 are represented; a page's
    `drawings` are never consulted, so no rule line or axis tick can become an automatic figure."""
    page = build_page(
        {
            "width": 612.0,
            "height": 792.0,
            "blocks": [_prose_block(0, 100.0), {"type": 2, "number": 1, "bbox": (0.0, 0.0, 5.0, 5.0)}],
            "drawings": [{"rect": (0.0, 0.0, 100.0, 100.0), "type": "s"}],
        },
        page_number=1,
        width=612.0,
        height=792.0,
    )
    assert [c.kind for c in page.components] == [TEXT_BLOCK]
    assert component_counts([page]).get(IMAGE, 0) == 0


def test_empty_and_whitespace_only_blocks_produce_no_component() -> None:
    page = build_page(
        _simple_page(
            [_text_block(0, (0.0, 0.0, 10.0, 10.0), [_line([_span("", (0.0, 0.0, 1.0, 1.0))], (0.0, 0.0, 1.0, 1.0))])]
        ),
        page_number=1,
        width=612.0,
        height=792.0,
    )
    assert page.components == ()


def test_build_page_never_mutates_its_input() -> None:
    page_dict = _simple_page([_prose_block(0, 100.0), _image_block(1, (0.0, 0.0, 5.0, 5.0))])
    before = json.dumps(page_dict, sort_keys=True)
    build_page(page_dict, page_number=1, width=612.0, height=792.0)
    assert json.dumps(page_dict, sort_keys=True) == before


# --- persistence: hierarchy, identity, staleness, idempotence ---


def _seed_attachment(db_url: str, *, checksum: str = "abc123", deleted: bool = False):
    engine = make_engine(db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Source component fixture", csl_json={"title": "Source component fixture"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            original_path="/tmp/x.pdf",
            resolved_path="/tmp/x.pdf",
            checksum=checksum,
            file_size=100,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="article-fulltext",
        )
        if deleted:
            conn.execute(papers.update().where(papers.c.id == paper_id).values(deleted_at=func.current_timestamp()))
    return engine, paper_id, attachment_id


def _store(engine, attachment_id: int, pages: list, *, checksum: str = "abc123") -> dict:
    with engine.begin() as conn:
        return replace_attachment_source(
            conn,
            attachment_id=attachment_id,
            pages=pages,
            coordinate_system="pdf-points-top-left",
            extraction_tool="pymupdf",
            extraction_version="1.27.2",
            source_checksum=checksum,
        )


def _sample_pages() -> list:
    return [
        build_page(
            _simple_page(
                [
                    _image_block(14, (25.0, 5.0, 89.0, 18.0)),
                    _text_block(
                        0,
                        (72.0, 35.0, 400.0, 60.0),
                        [_line([_span("Methods", (72.0, 35.0, 140.0, 47.0))], (72.0, 35.0, 140.0, 47.0))],
                    ),
                    _prose_block(1, 100.0),
                ]
            ),
            page_number=1,
            width=612.0,
            height=792.0,
            rotation=90,
        )
    ]


def test_persisted_page_geometry_and_hierarchy_round_trip(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed_attachment(temp_db_url)
    written = _store(engine, attachment_id, _sample_pages())
    assert written.written_pages == 1
    assert written.state == "complete"

    with engine.begin() as conn:
        page = source_page_for(conn, attachment_id, 1)
        assert page is not None
        assert (page.width, page.height, page.rotation) == (612.0, 792.0, 90)
        assert page.coordinate_system == "pdf-points-top-left"
        assert page.derivation_version == SOURCE_DERIVATION_VERSION
        assert page.is_stale is False

        rows = components_for_page(conn, page.id)
        by_id = {row["id"]: row for row in rows}
        kinds = {row["kind"] for row in rows}
        assert {IMAGE, HEADING, TEXT_BLOCK, LINE, SPAN} <= kinds

        image = next(r for r in rows if r["kind"] == IMAGE)
        assert (image["native_order"], image["sorted_order"]) == (14, 0)
        assert (image["x0"], image["y0"], image["x1"], image["y1"]) == (25.0, 5.0, 89.0, 18.0)

        # every span resolves to a line, and every line to a block -- the hierarchy survived
        for span in (r for r in rows if r["kind"] == SPAN):
            line = by_id[span["parent_id"]]
            assert line["kind"] == LINE
            assert by_id[line["parent_id"]]["kind"] in (TEXT_BLOCK, HEADING)

        heading = next(r for r in rows if r["kind"] == HEADING)
        assert heading["text"] == "Methods"


def test_source_checksum_and_derivation_version_bind_the_representation(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed_attachment(temp_db_url, checksum="live-sha")
    _store(engine, attachment_id, _sample_pages(), checksum="live-sha")
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == {attachment_id}
        assert source_page_for(conn, attachment_id, 1).is_stale is False


def test_a_replaced_pdf_makes_the_representation_detectably_stale(temp_db_url: str) -> None:
    """A re-ingest changes the attachment checksum; derived rows must not masquerade as current."""
    engine, _, attachment_id = _seed_attachment(temp_db_url, checksum="live-sha")
    _store(engine, attachment_id, _sample_pages(), checksum="an-older-sha")
    with engine.begin() as conn:
        assert source_page_for(conn, attachment_id, 1).is_stale is True
        assert attachments_with_current_source(conn) == set(), "stale rows must drop out of the resume set"


def test_an_older_derivation_version_drops_out_of_coverage(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed_attachment(temp_db_url)
    _store(engine, attachment_id, _sample_pages())
    with engine.begin() as conn:
        assert attachments_with_current_source(conn, "source-components-v99") == set()


def test_replace_is_idempotent(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed_attachment(temp_db_url)
    first = _store(engine, attachment_id, _sample_pages())
    second = _store(engine, attachment_id, _sample_pages())
    assert first == second
    with engine.begin() as conn:
        assert conn.execute(select(func.count()).select_from(source_pages)).scalar_one() == 1
        assert (
            conn.execute(select(func.count()).select_from(source_components)).scalar_one() == first.written_components
        )


def test_trashed_papers_are_outside_live_coverage_by_design(temp_db_url: str) -> None:
    """A soft-deleted paper keeps its chunk rows physically, but the app treats it as deleted.

    This is the diagnosis of H1a's 93 "unclassified" chunks: correct behaviour, not a defect. A
    trashed paper without source rows must never be reported as a coverage failure.
    """
    import tools.backfill_source_components as backfill_tool

    engine, _, attachment_id = _seed_attachment(temp_db_url, deleted=True)
    with engine.begin() as conn:
        live = backfill_tool._pdf_targets(conn, paper_id=None, attachment_id=None, include_trashed=False)
        debug = backfill_tool._pdf_targets(conn, paper_id=None, attachment_id=None, include_trashed=True)
    assert [t["id"] for t in live] == [], "a trashed paper is not live coverage"
    assert [t["id"] for t in debug] == [attachment_id], "--include-trashed is the explicit debugging opt-in"


# --- the no-behaviour-change invariant ---


def test_chunk_text_is_untouched_by_source_component_persistence(temp_db_url: str) -> None:
    engine, paper_id, attachment_id = _seed_attachment(temp_db_url)
    original = "  Participants  completed  the task.  "
    with engine.begin() as conn:
        chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=original,
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="pymupdf",
            extraction_version="1.27.2",
            chunking_strategy="pymupdf-block-v2",
            chunk_version="v",
            source_attachment_checksum="abc123",
            bbox_json=[{"page": 1, "block": 0, "line": 0, "span": 0, "x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0}],
        )
    _store(engine, attachment_id, _sample_pages())
    with engine.begin() as conn:
        row = conn.execute(select(chunks).where(chunks.c.id == chunk_id)).mappings().one()
    assert row["text"] == original, "chunk text must be byte-for-byte unchanged"
    assert row["bbox_json"] == [
        {"page": 1, "block": 0, "line": 0, "span": 0, "x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0}
    ]
    assert row["chunk_version"] == "v"


_RETRIEVAL_MODULES = (
    "app/backend/summarization/pipeline.py",
    "app/backend/summarization/chunk_filtering.py",
    "app/backend/summarization/generators.py",
    "app/backend/summarization/verification.py",
    "app/backend/embeddings/pipeline.py",
    "app/backend/embeddings/retrieval.py",
    "app/backend/embeddings/vector_store.py",
    "app/backend/citations/suggest.py",
    "app/backend/citations/section_scope.py",
    "app/backend/persistence/fulltext_repo.py",
    "app/backend/llm/providers.py",
)

_H1B_NAMES = ("source_pages", "source_components", "paper_figures", "source_components_repo", "build_page")


@pytest.mark.parametrize("module_path", _RETRIEVAL_MODULES)
def test_retrieval_and_generation_never_read_the_source_component_tables(module_path: str) -> None:
    """H1b is observational substrate. The moment retrieval, embedding, the verifier or the
    provider seam consults it, it has become load-bearing and this increment's central claim is
    void. Ask's chunk query joins `chunks` to `attachments` and nothing else.
    """
    source = Path(module_path).read_text(encoding="utf-8")
    for name in _H1B_NAMES:
        assert name not in source, f"{module_path} must not reference the H1b substrate ({name})"


def test_the_production_boilerplate_key_is_unchanged_and_the_experimental_one_is_offline() -> None:
    """The guarded digit-masked key stays a research helper until it clears a held-out gate."""
    production = Path("app/backend/summarization/chunk_filtering.py").read_text(encoding="utf-8")
    assert "guarded_digit_masked_key" not in production
    assert "evidence_hygiene" not in production

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.evidence_hygiene.structure import guarded_digit_masked_key

    # It must decline rather than collapse a real reported result into a shared key.
    assert guarded_digit_masked_key("M = 3.41, SD = 1.02") is None
    assert guarded_digit_masked_key("p = .761") is None
    assert guarded_digit_masked_key("t(48) = 2.31") is None
    # Two issues of one running head share a masked key.
    assert guarded_digit_masked_key("Journal of Cognition, Vol 12, No 3, 2021") == guarded_digit_masked_key(
        "Journal of Cognition, Vol 12, No 7, 2021"
    )


def test_a_source_component_failure_never_rolls_back_the_chunk_write(temp_db_url: str, monkeypatch, caplog) -> None:
    """The safeguard that lets H1b write on the production ingest path at all.

    Source components are observational substrate; the chunks written in the same transaction are
    authoritative product state. The write is wrapped in a SAVEPOINT so a failure rolls back only
    to that savepoint. The failure is logged rather than swallowed (inc 577 lost every geometry
    rule to a broad `except`), and the backfill repairs it later.
    """
    import logging

    from app.backend.pdf_processing import ingest as ingest_module

    def boom(*args, **kwargs):
        raise RuntimeError("simulated source-component failure")

    monkeypatch.setattr(ingest_module, "replace_attachment_source", boom)

    engine = make_engine(temp_db_url)
    with caplog.at_level(logging.WARNING):
        with engine.begin() as conn:
            paper_id = create_paper(conn, title="Isolation fixture", csl_json={"title": "Isolation fixture"})
            result = ingest_module.attach_pdf_to_paper(conn, paper_id, str(Path("tests/fixtures/seed.pdf").resolve()))

    assert result["chunk_ids"], "the chunk write must survive a source-component failure"
    with engine.begin() as conn:
        assert conn.execute(
            select(func.count()).select_from(chunks).where(chunks.c.paper_id == paper_id)
        ).scalar_one() == len(result["chunk_ids"])
        assert conn.execute(select(func.count()).select_from(source_pages)).scalar_one() == 0
    assert any("source-component persistence failed" in r.message for r in caplog.records), (
        "the failure must be reported, never silently swallowed"
    )


def test_a_normal_ingest_records_source_components_alongside_its_chunks(temp_db_url: str) -> None:
    from app.backend.pdf_processing.ingest import attach_pdf_to_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Ingest fixture", csl_json={"title": "Ingest fixture"})
        result = attach_pdf_to_paper(conn, paper_id, str(Path("tests/fixtures/seed.pdf").resolve()))

    with engine.begin() as conn:
        assert conn.execute(select(func.count()).select_from(source_pages)).scalar_one() > 0
        assert conn.execute(select(func.count()).select_from(source_components)).scalar_one() > 0
        assert attachments_with_current_source(conn) == {result["attachment_id"]}
        # the chunk rows are unaffected in shape
        assert conn.execute(
            select(func.count()).select_from(chunks).where(chunks.c.paper_id == paper_id)
        ).scalar_one() == len(result["chunk_ids"])
