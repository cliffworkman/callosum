"""Orchestrates GROBID parsing for one paper (backlog #30 Stage 2): call GROBID, parse its TEI-XML, map its
section boundaries onto callosum's EXISTING PyMuPDF-chunked bboxes by coordinate overlap (never fuzzy text
matching between the two independent parses), write paper_sections + chunks.grobid_section_id.

Provenance rule (see the design doc): chunks.section -- the pre-existing heuristic column -- is NEVER written
here. This pipeline only ever writes to the new, separate paper_sections table and the new grobid_section_id
column. Deleting this whole module would leave the heuristic-only baseline exactly as it was."""

from __future__ import annotations

from sqlalchemy import Connection, select

from app.backend.persistence.schema import chunks
from app.backend.persistence.schema_grobid import paper_sections
from integrations.grobid.client import parse_fulltext
from integrations.grobid.section_classify import classify_section_title
from integrations.grobid.tei_parse import SectionSpan, parse_tei


def _bboxes_overlap(a: tuple[int, float, float, float, float], b: dict) -> bool:
    """`a` is a GROBID span box: (page, x, y, width, height) -- GROBID's own coords format. `b` is one of
    callosum's OWN chunk bbox_json entries: {"page", "x0", "y0", "x1", "y1", ...} -- corner coordinates, a
    DIFFERENT representation (confirmed against pdf_processing/extraction.py's `_rect_to_dict`, which writes
    x0/y0/x1/y1, not x/y/width/height)."""
    a_page, a_x, a_y, a_w, a_h = a
    if a_page != int(b.get("page", -1)):
        return False
    b_x0, b_y0, b_x1, b_y1 = float(b.get("x0", 0)), float(b.get("y0", 0)), float(b.get("x1", 0)), float(b.get("y1", 0))
    a_x1, a_y1 = a_x + a_w, a_y + a_h
    return not (a_x1 < b_x0 or b_x1 < a_x or a_y1 < b_y0 or b_y1 < a_y)


def _chunk_overlaps_span(chunk_row: dict, span: SectionSpan) -> bool:
    chunk_bboxes = chunk_row.get("bbox_json") or []
    if isinstance(chunk_bboxes, dict):
        chunk_bboxes = [chunk_bboxes]
    return any(_bboxes_overlap(span_box, chunk_box) for span_box in span.bboxes for chunk_box in chunk_bboxes)


def parse_paper_structure(conn: Connection, paper_id: int, attachment_id: int, pdf_bytes: bytes, base_url: str) -> dict:
    """Fetch + parse + map GROBID structure for one paper's `attachment_id` (the specific PDF actually sent to
    GROBID -- resolved by the caller, e.g. via `_select_primary_pdf_attachment`). Raises GrobidError/
    GrobidParseError on any failure with zero writes (caller must not commit on exception -- this function
    itself never calls conn.commit(), matching this codebase's run_write convention). Returns
    {"sections_found": int, "chunks_mapped": int}.

    Idempotent re-parse (a re-parse is a REPLACE, not an APPEND): this attachment's prior chunk mappings are
    cleared and this paper's prior paper_sections rows are deleted before writing fresh ones, in the same
    transaction as the inserts below -- otherwise repeated parses would duplicate paper_sections rows without
    bound, and a chunk no longer covered by the new structure would keep pointing at a stale, no-longer-current
    section. Zero-partial-writes still holds: parse_fulltext/parse_tei already raised before either statement
    below would run.
    """
    tei_xml = parse_fulltext(pdf_bytes, base_url)
    spans = parse_tei(tei_xml)

    conn.execute(
        chunks.update()
        .where(chunks.c.paper_id == paper_id, chunks.c.attachment_id == attachment_id)
        .values(grobid_section_id=None)
    )
    conn.execute(paper_sections.delete().where(paper_sections.c.paper_id == paper_id))

    section_ids: list[int] = []
    for order_index, span in enumerate(spans):
        result = conn.execute(
            paper_sections.insert().values(
                paper_id=paper_id,
                title=span.title,
                section_kind=classify_section_title(span.title),
                page_start=span.page_start,
                page_end=span.page_end,
                order_index=order_index,
            )
        )
        section_ids.append(result.inserted_primary_key[0])

    # Scoped to the ATTACHMENT actually sent to GROBID -- a paper can carry supplement/preregistration/protocol
    # attachments under the same paper_id (inc 425's document-scope invariant), and their chunks must never be
    # mapped onto this attachment's GROBID spans just because a bbox happens to overlap.
    paper_chunks = (
        conn.execute(
            select(chunks.c.id, chunks.c.bbox_json).where(
                chunks.c.paper_id == paper_id, chunks.c.attachment_id == attachment_id
            )
        )
        .mappings()
        .all()
    )

    chunks_mapped = 0
    for chunk_row in paper_chunks:
        for span, section_id in zip(spans, section_ids, strict=True):
            if _chunk_overlaps_span(dict(chunk_row), span):
                conn.execute(chunks.update().where(chunks.c.id == chunk_row["id"]).values(grobid_section_id=section_id))
                chunks_mapped += 1
                break  # first overlapping span wins -- spans shouldn't overlap each other in a well-formed TEI

    return {"sections_found": len(spans), "chunks_mapped": chunks_mapped}


def paper_ids_with_sections(conn: Connection) -> set[int]:
    """Paper ids that already have at least one GROBID-mapped section -- lets the bulk parse job offer an
    "unparsed only" mode (backlog #58) without re-parsing papers a prior run already covered."""
    return {int(row[0]) for row in conn.execute(select(paper_sections.c.paper_id).distinct())}
