"""Section-aware retrieval support for Suggest-Citation (backlog #30)."""

from __future__ import annotations

from sqlalchemy import create_engine

from app.backend.citations.section_scope import (
    candidate_section_family,
    expected_section_family,
    partition_by_phase,
)
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


def test_expected_section_family_recognizes_a_known_heading():
    assert expected_section_family("3. Methods") == "methods"
    assert expected_section_family("Materials and Methods") == "methods"


def test_expected_section_family_none_for_unrecognized_or_missing_heading():
    assert expected_section_family("Some Custom Chapter Title") is None
    assert expected_section_family(None) is None
    assert expected_section_family("") is None


def test_partition_by_phase_moves_matching_candidates_first_without_dropping_any():
    candidates = [
        {"paper_id": 1, "section_family": "results"},
        {"paper_id": 2, "section_family": "methods"},
        {"paper_id": 3, "section_family": None},
        {"paper_id": 4, "section_family": "methods"},
    ]
    reordered, matched_any = partition_by_phase(candidates, "methods")
    assert matched_any is True
    assert [c["paper_id"] for c in reordered] == [2, 4, 1, 3]  # methods first, others keep relative order
    assert len(reordered) == len(candidates)  # nothing dropped


def test_partition_by_phase_no_expected_family_returns_input_order_unchanged():
    candidates = [{"paper_id": 1, "section_family": "methods"}, {"paper_id": 2, "section_family": None}]
    reordered, matched_any = partition_by_phase(candidates, None)
    assert matched_any is False
    assert reordered == candidates


def test_partition_by_phase_no_matches_returns_input_order_unchanged():
    candidates = [{"paper_id": 1, "section_family": "results"}, {"paper_id": 2, "section_family": None}]
    reordered, matched_any = partition_by_phase(candidates, "methods")
    assert matched_any is False
    assert reordered == candidates


def test_candidate_section_family_reads_the_heuristic_column(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
        attachment_id = create_attachment(
            conn,
            paper_id=pid,
            storage_mode="managed",
            availability="available",
            content_type="application/pdf",
            checksum="test-hash",
            role="article-fulltext",
        )
        chunk_id = create_chunk(
            conn,
            paper_id=pid,
            attachment_id=attachment_id,
            text="body text",
            section="methods",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="deadbeef",
        )
        family, source = candidate_section_family(conn, chunk_id)
    eng.dispose()
    assert family == "methods" and source == "heuristic"


def test_candidate_section_family_none_when_heuristic_never_tagged_it(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
        attachment_id = create_attachment(
            conn,
            paper_id=pid,
            storage_mode="managed",
            availability="available",
            content_type="application/pdf",
            checksum="test-hash",
            role="article-fulltext",
        )
        chunk_id = create_chunk(
            conn,
            paper_id=pid,
            attachment_id=attachment_id,
            text="body text",
            section=None,
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="deadbeef",
        )
        family, source = candidate_section_family(conn, chunk_id)
    eng.dispose()
    assert family is None and source == "none"
