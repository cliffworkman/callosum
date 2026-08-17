"""Section-aware retrieval support for Suggest-Citation (backlog #30)."""

from __future__ import annotations

from sqlalchemy import create_engine

from app.backend.citations.section_scope import (
    candidate_section_family,
    expected_section_family,
    paper_methods_text,
    partition_by_phase,
)
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import chunks


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


def test_candidate_section_family_prefers_grobid_when_present(temp_db_url: str) -> None:
    """A chunk tagged 'results' by the heuristic but mapped to a GROBID paper_sections row classified
    'methods' should report the GROBID value, source='grobid' -- GROBID wins when both exist."""
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
        from app.backend.persistence.schema_grobid import paper_sections

        section_result = conn.execute(
            paper_sections.insert().values(
                paper_id=pid,
                title="3. Methods",
                section_kind="methods",
                page_start=1,
                page_end=1,
                order_index=0,
            )
        )
        section_id = section_result.inserted_primary_key[0]
        chunk_result = conn.execute(
            chunks.insert().values(
                paper_id=pid,
                attachment_id=attachment_id,
                text="body",
                section="results",  # heuristic says results
                grobid_section_id=section_id,  # but GROBID mapped it to methods
                page_start=1,
                page_end=1,
                bbox_coordinate_system="pdf-points-top-left",
                extraction_tool="test",
                extraction_version="1",
                chunking_strategy="test",
                chunk_version="1",
                source_attachment_checksum="deadbeef",
            )
        )
        chunk_id = chunk_result.inserted_primary_key[0]
        family, source = candidate_section_family(conn, chunk_id)
    eng.dispose()
    assert family == "methods" and source == "grobid"


def test_candidate_section_family_falls_back_to_heuristic_when_grobid_kind_unrecognized(temp_db_url: str) -> None:
    """Finding 7 (final-review): a chunk CAN be mapped to a real paper_sections row (grobid_section_id set)
    whose title GROBID extracted verbatim but `classify_section_title` didn't recognize -- an honest
    `section_kind IS NULL`, e.g. a custom subsection title like "Musical activity and late-life cognition"
    (see INCREMENT-479-NOTES.md's live smoke test). That must fall back to the pre-existing heuristic
    `chunks.section` column and report `source="heuristic"` -- not `(None, "grobid")` (silently discarding a
    real heuristic tag) and not silently skipping the heuristic fallback entirely."""
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
        from app.backend.persistence.schema_grobid import paper_sections

        section_result = conn.execute(
            paper_sections.insert().values(
                paper_id=pid,
                title="Musical activity and late-life cognition",  # verbatim GROBID title, unrecognized
                section_kind=None,  # classify_section_title() found no matching alias
                page_start=1,
                page_end=1,
                order_index=0,
            )
        )
        section_id = section_result.inserted_primary_key[0]
        chunk_result = conn.execute(
            chunks.insert().values(
                paper_id=pid,
                attachment_id=attachment_id,
                text="body",
                section="discussion",  # the heuristic DID tag this chunk
                grobid_section_id=section_id,  # mapped, but to an unrecognized GROBID title
                page_start=1,
                page_end=1,
                bbox_coordinate_system="pdf-points-top-left",
                extraction_tool="test",
                extraction_version="1",
                chunking_strategy="test",
                chunk_version="1",
                source_attachment_checksum="deadbeef",
            )
        )
        chunk_id = chunk_result.inserted_primary_key[0]
        family, source = candidate_section_family(conn, chunk_id)
    eng.dispose()
    assert family == "discussion" and source == "heuristic"


def test_paper_methods_text_concatenates_methods_chunks_in_order(temp_db_url: str) -> None:
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
        for section, text in [
            ("intro", "Introduction text."),
            ("methods", "Methods part one."),
            ("methods", "Methods part two."),
            ("results", "Results text."),
        ]:
            create_chunk(
                conn,
                paper_id=pid,
                attachment_id=attachment_id,
                text=text,
                section=section,
                page_start=1,
                page_end=1,
                bbox_coordinate_system="pdf-points-top-left",
                extraction_tool="test",
                extraction_version="1",
                chunking_strategy="test",
                chunk_version="1",
                source_attachment_checksum="deadbeef",
            )
        result = paper_methods_text(conn, pid)
    eng.dispose()
    assert result == "Methods part one.\n\nMethods part two."


def test_paper_methods_text_returns_none_when_no_methods_chunks(temp_db_url: str) -> None:
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
        create_chunk(
            conn,
            paper_id=pid,
            attachment_id=attachment_id,
            text="Only intro.",
            section="intro",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="deadbeef",
        )
        result = paper_methods_text(conn, pid)
    eng.dispose()
    assert result is None


def test_paper_methods_text_caps_length(temp_db_url: str) -> None:
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
        create_chunk(
            conn,
            paper_id=pid,
            attachment_id=attachment_id,
            text="x" * 100,
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
        result = paper_methods_text(conn, pid, max_chars=10)
    eng.dispose()
    assert result is not None and len(result) == 10


def test_paper_methods_text_excludes_preregistration_chunks(temp_db_url: str) -> None:
    """The inc-425 document-scope invariant: paper_methods_text must only read article/supplement-role
    chunks, never registration/preregistration chunks, even if one happened to be tagged "methods"."""
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
        prereg_attachment_id = create_attachment(
            conn,
            paper_id=pid,
            storage_mode="managed",
            availability="available",
            content_type="application/pdf",
            checksum="prereg-hash",
            role="preregistration",
        )
        create_chunk(
            conn,
            paper_id=pid,
            attachment_id=prereg_attachment_id,
            text="Preregistered methods text.",
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
        result = paper_methods_text(conn, pid)
    eng.dispose()
    assert result is None
