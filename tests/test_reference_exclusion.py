"""Backlog #82: query-scope synthesis excludes reference-list-section chunks from the claim-evidence
candidate pool by default. A reference-list entry is a pointer to a finding, not a finding, so it can
never be the verbatim evidence for a scientific claim. The exclusion is GROBID-preferred over the
heuristic ``chunks.section`` (the same strict preference ``candidate_section_family`` uses) and KEEPS
unlabelled (``None``-family) chunks -- silence is not a certificate.
"""

from __future__ import annotations

from sqlalchemy import create_engine, select

from app.backend.persistence.repository import create_attachment, create_paper
from app.backend.persistence.schema import chunks
from app.backend.persistence.schema_grobid import paper_sections
from app.backend.summarization.pipeline import SummaryScope, exclude_reference_sections


def _attachment(conn, pid: int) -> int:
    return create_attachment(
        conn,
        paper_id=pid,
        storage_mode="managed",
        availability="available",
        content_type="application/pdf",
        checksum=f"hash-{pid}",
        role="article-fulltext",
    )


def _chunk(conn, pid: int, att: int, *, section: str | None, grobid_section_id: int | None = None) -> int:
    return conn.execute(
        chunks.insert().values(
            paper_id=pid,
            attachment_id=att,
            text="body",
            section=section,
            grobid_section_id=grobid_section_id,
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="deadbeef",
        )
    ).inserted_primary_key[0]


def _grobid_section(conn, pid: int, *, section_kind: str | None, title: str) -> int:
    return conn.execute(
        paper_sections.insert().values(
            paper_id=pid, title=title, section_kind=section_kind, page_start=1, page_end=1, order_index=0
        )
    ).inserted_primary_key[0]


def _surviving_ids(conn) -> set[int]:
    stmt = exclude_reference_sections(select(chunks.c.id))
    return {int(row[0]) for row in conn.execute(stmt)}


def test_excludes_reference_section_chunks_keeps_everything_else(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
        att = _attachment(conn, pid)
        refs = _chunk(conn, pid, att, section="references")
        methods = _chunk(conn, pid, att, section="methods")
        unlabelled = _chunk(conn, pid, att, section=None)
        survivors = _surviving_ids(conn)
    eng.dispose()
    assert refs not in survivors  # the reference list is dropped
    assert methods in survivors  # real body content kept
    assert unlabelled in survivors  # silence is not a certificate -- unlabelled kept


def test_grobid_section_kind_is_preferred_over_the_heuristic(temp_db_url: str) -> None:
    """A chunk the heuristic mislabelled 'methods' but GROBID mapped to a references section is dropped;
    the reverse -- heuristic 'references' but GROBID 'methods' -- is kept. GROBID wins in both directions."""
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
        att = _attachment(conn, pid)
        grobid_refs = _grobid_section(conn, pid, section_kind="references", title="References")
        grobid_methods = _grobid_section(conn, pid, section_kind="methods", title="2. Methods")
        dropped = _chunk(conn, pid, att, section="methods", grobid_section_id=grobid_refs)
        kept = _chunk(conn, pid, att, section="references", grobid_section_id=grobid_methods)
        # A chunk mapped to a GROBID section whose title didn't classify (section_kind NULL) falls back
        # to the heuristic -- a NULL-kind references heuristic is still a reference list, so dropped.
        grobid_unrecognized = _grobid_section(conn, pid, section_kind=None, title="Acknowledgements")
        fallback_dropped = _chunk(conn, pid, att, section="references", grobid_section_id=grobid_unrecognized)
        survivors = _surviving_ids(conn)
    eng.dispose()
    assert dropped not in survivors
    assert kept in survivors
    assert fallback_dropped not in survivors


def test_scope_to_ref_records_only_a_non_default_reference_policy() -> None:
    default = SummaryScope(scope_type="query", query="q").to_ref()
    assert "exclude_references" not in default  # the norm stays unrecorded, so ordinary rows are unchanged
    included = SummaryScope(scope_type="query", query="q", exclude_references=False).to_ref()
    assert included["exclude_references"] is False  # a references-included run is inspectable in its provenance
