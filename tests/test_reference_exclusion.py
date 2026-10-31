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
from app.backend.summarization.pipeline import SummaryScope
from app.backend.summarization.reference_rescue import reference_filtered_rows


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
    # inc 611 adds a content rescue for mislabelled prose; fixture text "body" is not prose, so a
    # references-labelled fixture chunk stays excluded exactly as before.
    return {int(row["id"]) for row in reference_filtered_rows(conn, select(chunks).order_by(chunks.c.id))}


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


def _text_chunk(conn, pid: int, att: int, *, text: str, section: str | None) -> int:
    chunk_id = _chunk(conn, pid, att, section=section)
    conn.execute(chunks.update().where(chunks.c.id == chunk_id).values(text=text, chunk_version=f"v-{chunk_id}"))
    return chunk_id


def test_mislabelled_prose_is_rescued_in_chunk_order_and_genuine_entries_stay_out(temp_db_url: str) -> None:
    """inc 611: a ``references`` label no longer suffices on its own. The rescued conclusion re-enters the pool in
    its chunk-id position (what one ordered query would return), and the genuine entry stays excluded -- on the
    first pass and on the memoized second pass alike."""
    conclusion = (
        "In conclusion, reduced transporter availability was observed in patients relative to controls, which may "
        "reflect an early stage of degeneration, and the results support a role for occupancy in treatment response."
    )
    entry = "Smith, J. A., & Jones, B. C. (2019). A study of things. Journal of Results, 12(3), 145-160."
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
        att = _attachment(conn, pid)
        before = _text_chunk(conn, pid, att, text="Body prose before.", section="discussion")
        rescued = _text_chunk(conn, pid, att, text=conclusion, section="references")
        genuine = _text_chunk(conn, pid, att, text=entry, section="references")
        after = _text_chunk(conn, pid, att, text="Body prose after.", section=None)
        stmt = select(chunks).order_by(chunks.c.id)
        first = [int(r["id"]) for r in reference_filtered_rows(conn, stmt)]
        second = [int(r["id"]) for r in reference_filtered_rows(conn, stmt)]
    eng.dispose()
    assert first == second == [before, rescued, after]
    assert genuine not in first
