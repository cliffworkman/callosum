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
    return pid, result.inserted_primary_key[0]


def test_parse_paper_structure_maps_overlapping_chunk_by_coordinates(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, chunk_id = _seed_paper_with_chunk(conn, page=1, bbox=[{"page": 1, "x0": 10, "y0": 10, "x1": 60, "y1": 30}])
        fake_span = SectionSpan(title="3. Methods", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[fake_span]),
        ):
            result = parse_paper_structure(conn, pid, b"pdf-bytes", "http://127.0.0.1:8070")
        mapped = conn.execute(select(chunks.c.grobid_section_id).where(chunks.c.id == chunk_id)).scalar_one()
        section_row = conn.execute(select(paper_sections.c.title, paper_sections.c.section_kind)).mappings().first()
    eng.dispose()
    assert result == {"sections_found": 1, "chunks_mapped": 1}
    assert mapped is not None
    assert section_row["title"] == "3. Methods" and section_row["section_kind"] == "methods"


def test_parse_paper_structure_non_overlapping_chunk_stays_unmapped(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, chunk_id = _seed_paper_with_chunk(
            conn,
            page=1,
            bbox=[{"page": 1, "x0": 500, "y0": 500, "x1": 510, "y1": 510}],  # far outside
        )
        fake_span = SectionSpan(title="Results", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[fake_span]),
        ):
            parse_paper_structure(conn, pid, b"pdf-bytes", "http://127.0.0.1:8070")
        mapped = conn.execute(select(chunks.c.grobid_section_id).where(chunks.c.id == chunk_id)).scalar_one()
    eng.dispose()
    assert mapped is None


def test_parse_paper_structure_grobid_error_writes_nothing(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, chunk_id = _seed_paper_with_chunk(conn)
        with patch("app.backend.grobid_pipeline.parse_fulltext", side_effect=GrobidError("unreachable")):
            with pytest.raises(GrobidError):
                parse_paper_structure(conn, pid, b"pdf-bytes", "http://127.0.0.1:8070")
        section_count = conn.execute(select(paper_sections.c.id)).fetchall()
    eng.dispose()
    assert section_count == []  # zero partial writes


def test_parse_paper_structure_malformed_tei_writes_nothing(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, chunk_id = _seed_paper_with_chunk(conn)
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"garbage"),
            patch("app.backend.grobid_pipeline.parse_tei", side_effect=GrobidParseError("bad xml")),
        ):
            with pytest.raises(GrobidParseError):
                parse_paper_structure(conn, pid, b"pdf-bytes", "http://127.0.0.1:8070")
        section_count = conn.execute(select(paper_sections.c.id)).fetchall()
    eng.dispose()
    assert section_count == []


def test_parse_paper_structure_zero_sections_is_not_an_error(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, chunk_id = _seed_paper_with_chunk(conn)
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[]),
        ):
            result = parse_paper_structure(conn, pid, b"pdf-bytes", "http://127.0.0.1:8070")
    eng.dispose()
    assert result == {"sections_found": 0, "chunks_mapped": 0}


def test_parse_paper_structure_never_writes_chunks_section(temp_db_url: str) -> None:
    """The provenance-separation invariant, tested not just documented: chunks.section is byte-for-byte
    untouched by this whole pipeline."""
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, chunk_id = _seed_paper_with_chunk(
            conn, section="results", page=1, bbox=[{"page": 1, "x0": 10, "y0": 10, "x1": 60, "y1": 30}]
        )
        fake_span = SectionSpan(title="Methods", page_start=1, page_end=1, bboxes=[(1, 0, 0, 100, 100)])
        with (
            patch("app.backend.grobid_pipeline.parse_fulltext", return_value=b"<TEI/>"),
            patch("app.backend.grobid_pipeline.parse_tei", return_value=[fake_span]),
        ):
            parse_paper_structure(conn, pid, b"pdf-bytes", "http://127.0.0.1:8070")
        section_col = conn.execute(select(chunks.c.section).where(chunks.c.id == chunk_id)).scalar_one()
    eng.dispose()
    assert section_col == "results"  # unchanged, even though GROBID disagreed and said "Methods"
