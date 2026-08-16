from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select

from app.backend.grobid_pipeline import parse_paper_structure
from app.backend.persistence.repository import create_attachment, create_paper
from app.backend.persistence.schema import chunks
from app.backend.persistence.schema_grobid import paper_sections
from integrations.grobid.client import GrobidError
from integrations.grobid.tei_parse import GrobidParseError, SectionSpan


def _seed_paper_with_chunk(conn, *, section=None, page=1, bbox=None):
    pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
    aid = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum="test-checksum",
        import_source="test",
        attachment_type="pdf",
        role="primary",
    )
    result = conn.execute(
        chunks.insert().values(
            paper_id=pid,
            attachment_id=aid,
            text="chunk body",
            section=section,
            page_start=page,
            page_end=page,
            bbox_json=bbox,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="deadbeef",
        )
    )
    return pid, aid, result.inserted_primary_key[0]


def _add_chunk(conn, *, paper_id, attachment_id, page=1, bbox=None):
    result = conn.execute(
        chunks.insert().values(
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="chunk body",
            section=None,
            page_start=page,
            page_end=page,
            bbox_json=bbox,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="deadbeef",
        )
    )
    return result.inserted_primary_key[0]


def test_parse_paper_structure_maps_overlapping_chunk_by_coordinates(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, aid, chunk_id = _seed_paper_with_chunk(
            conn, page=1, bbox=[{"page": 1, "x0": 10, "y0": 10, "x1": 60, "y1": 30}]
        )
        fake_span = SectionSpan(title="3. Methods", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[fake_span]),
        ):
            result = parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
        mapped = conn.execute(select(chunks.c.grobid_section_id).where(chunks.c.id == chunk_id)).scalar_one()
        section_row = conn.execute(select(paper_sections.c.title, paper_sections.c.section_kind)).mappings().first()
    eng.dispose()
    assert result == {"sections_found": 1, "chunks_mapped": 1}
    assert mapped is not None
    assert section_row["title"] == "3. Methods" and section_row["section_kind"] == "methods"


def test_parse_paper_structure_non_overlapping_chunk_stays_unmapped(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, aid, chunk_id = _seed_paper_with_chunk(
            conn,
            page=1,
            bbox=[{"page": 1, "x0": 500, "y0": 500, "x1": 510, "y1": 510}],  # far outside
        )
        fake_span = SectionSpan(title="Results", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[fake_span]),
        ):
            parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
        mapped = conn.execute(select(chunks.c.grobid_section_id).where(chunks.c.id == chunk_id)).scalar_one()
    eng.dispose()
    assert mapped is None


def test_parse_paper_structure_grobid_error_writes_nothing(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, aid, chunk_id = _seed_paper_with_chunk(conn)
        with patch("app.backend.grobid_pipeline.parse_fulltext", side_effect=GrobidError("unreachable")):
            with pytest.raises(GrobidError):
                parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
        section_count = conn.execute(select(paper_sections.c.id)).fetchall()
    eng.dispose()
    assert section_count == []  # zero partial writes


def test_parse_paper_structure_malformed_tei_writes_nothing(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, aid, chunk_id = _seed_paper_with_chunk(conn)
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"garbage"),
            patch("app.backend.grobid_pipeline.parse_tei", side_effect=GrobidParseError("bad xml")),
        ):
            with pytest.raises(GrobidParseError):
                parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
        section_count = conn.execute(select(paper_sections.c.id)).fetchall()
    eng.dispose()
    assert section_count == []


def test_parse_paper_structure_zero_sections_is_not_an_error(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, aid, chunk_id = _seed_paper_with_chunk(conn)
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[]),
        ):
            result = parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
    eng.dispose()
    assert result == {"sections_found": 0, "chunks_mapped": 0}


def test_parse_paper_structure_never_writes_chunks_section(temp_db_url: str) -> None:
    """The provenance-separation invariant, tested not just documented: chunks.section is byte-for-byte
    untouched by this whole pipeline."""
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, aid, chunk_id = _seed_paper_with_chunk(
            conn, section="results", page=1, bbox=[{"page": 1, "x0": 10, "y0": 10, "x1": 60, "y1": 30}]
        )
        fake_span = SectionSpan(title="Methods", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[fake_span]),
        ):
            parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
        section_col = conn.execute(select(chunks.c.section).where(chunks.c.id == chunk_id)).scalar_one()
    eng.dispose()
    assert section_col == "results"  # unchanged, even though GROBID disagreed and said "Methods"


def test_parse_paper_structure_reparse_is_idempotent_not_additive(temp_db_url: str) -> None:
    """Finding 2 (final-review): a re-parse must REPLACE paper_sections + chunk mappings, not append to them.

    Parse once with one span/chunk overlap, then again with a different span whose bboxes no longer cover the
    first chunk. paper_sections must not grow unboundedly (old rows are gone, not appended alongside the new
    ones), and the chunk that mapped on the first parse must end up back at grobid_section_id IS NULL -- not a
    stale pointer at a section the second parse didn't actually produce.
    """
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, aid, chunk_id = _seed_paper_with_chunk(
            conn, page=1, bbox=[{"page": 1, "x0": 10, "y0": 10, "x1": 60, "y1": 30}]
        )
        span_1 = SectionSpan(title="Methods", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[span_1]),
        ):
            first = parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
        mapped_after_first = conn.execute(
            select(chunks.c.grobid_section_id).where(chunks.c.id == chunk_id)
        ).scalar_one()

        # Second parse: a totally different section that does NOT cover the seeded chunk's bbox at all.
        span_2 = SectionSpan(title="Results", page_start=1, page_end=1, bboxes=[(1, 500, 500, 10, 10)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[span_2]),
        ):
            second = parse_paper_structure(conn, pid, aid, b"pdf-bytes", "http://127.0.0.1:8070")
        mapped_after_second = conn.execute(
            select(chunks.c.grobid_section_id).where(chunks.c.id == chunk_id)
        ).scalar_one()
        section_rows = conn.execute(select(paper_sections.c.id).where(paper_sections.c.paper_id == pid)).fetchall()
    eng.dispose()

    assert first == {"sections_found": 1, "chunks_mapped": 1}
    assert mapped_after_first is not None  # mapped by the first parse's "Methods" span
    assert second == {"sections_found": 1, "chunks_mapped": 0}
    assert mapped_after_second is None  # stale mapping cleared, not left pointing at a deleted section
    assert len(section_rows) == 1  # replaced, not appended -- still exactly the second parse's one section


def test_parse_paper_structure_scopes_mapping_to_parsed_attachment_only(temp_db_url: str) -> None:
    """Finding 3 (final-review, inc-425 document-scope invariant): a supplement's chunk must never be mapped
    just because its bbox happens to overlap a GROBID span belonging to a DIFFERENT attachment (the one
    actually sent to GROBID). Two attachments on the same paper, each with a chunk at the identical overlapping
    bbox; only the primary attachment's chunk may be mapped."""
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, primary_aid, primary_chunk_id = _seed_paper_with_chunk(
            conn, page=1, bbox=[{"page": 1, "x0": 10, "y0": 10, "x1": 60, "y1": 30}]
        )
        supplement_aid = create_attachment(
            conn,
            paper_id=pid,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="supplement-checksum",
            import_source="test",
            attachment_type="pdf",
            role="supplement",
        )
        supplement_chunk_id = _add_chunk(
            conn,
            paper_id=pid,
            attachment_id=supplement_aid,
            page=1,
            bbox=[{"page": 1, "x0": 10, "y0": 10, "x1": 60, "y1": 30}],  # identical overlapping bbox
        )
        fake_span = SectionSpan(title="Methods", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[fake_span]),
        ):
            result = parse_paper_structure(conn, pid, primary_aid, b"pdf-bytes", "http://127.0.0.1:8070")
        primary_mapped = conn.execute(
            select(chunks.c.grobid_section_id).where(chunks.c.id == primary_chunk_id)
        ).scalar_one()
        supplement_mapped = conn.execute(
            select(chunks.c.grobid_section_id).where(chunks.c.id == supplement_chunk_id)
        ).scalar_one()
    eng.dispose()

    assert result == {"sections_found": 1, "chunks_mapped": 1}  # only the primary attachment's chunk counted
    assert primary_mapped is not None
    assert supplement_mapped is None  # never touched, despite the identical overlapping bbox
