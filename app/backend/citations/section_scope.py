"""Section-aware retrieval support for Suggest-Citation (Track C section-scoping, backlog #30).

Two existing systems provide everything this module needs: `pdf_processing/sections.py`'s SectionTracker has
already tagged every library chunk's `chunks.section` at ingest time (a canonical family key -- introduction,
methods, results, etc.); the LibreOffice adapter already knows the draft's current heading (inc 380). This
module is the thin, disclosed connector between them: classify a heading into the same family taxonomy, look up
a candidate's own family, and reorder (never filter) a candidate list so matching-family results lead.

`candidate_section_family`'s heuristic-only behavior here is deliberately extended in place by a later task
(Stage 2 / GROBID) to also prefer a richer, GROBID-derived family when a paper has been explicitly parsed -- the
call sites in this module and in `citations/suggest.py` do not change when that lands.
"""

from __future__ import annotations

from sqlalchemy import Connection, select

from app.backend.pdf_processing.sections import detect_section_heading
from app.backend.persistence.schema import chunks
from app.backend.persistence.schema_grobid import paper_sections


def expected_section_family(heading_text: str | None) -> str | None:
    """The canonical section family a draft heading implies, or None if there's no heading context (a
    preamble, the plugin's standalone paste-a-paragraph mode) or the heading doesn't match a recognized alias."""
    if not heading_text:
        return None
    heading = detect_section_heading(heading_text)
    return heading.key if heading is not None else None


def candidate_section_family(conn: Connection, chunk_id: int) -> tuple[str | None, str]:
    """A candidate chunk's own section family and where it came from -- GROBID's data is preferred when the
    chunk has been mapped to one (grobid_section_id set AND that section has a recognized section_kind),
    falling back to the pre-existing heuristic chunks.section column otherwise. GROBID's own bbox-mapping and
    the heuristic never both apply at once for one chunk -- this is a strict preference, not a blend, so the
    disclosed "source" is always accurate."""
    row = conn.execute(
        select(chunks.c.section, paper_sections.c.section_kind)
        .select_from(chunks.outerjoin(paper_sections, paper_sections.c.id == chunks.c.grobid_section_id))
        .where(chunks.c.id == chunk_id)
    ).first()
    if row is None:
        return None, "none"
    heuristic_section, grobid_kind = row
    if grobid_kind:
        return grobid_kind, "grobid"
    if heuristic_section:
        return heuristic_section, "heuristic"
    return None, "none"


def partition_by_phase(candidates: list[dict], expected_family: str | None) -> tuple[list[dict], bool]:
    """Reorder `candidates` (each already carrying a "section_family" key) so matches for `expected_family`
    come first, preserving relative order within each group. Never drops a candidate. Returns the reordered
    list plus whether any reordering happened (False when there's no expected family, or nothing matched --
    in both cases the input order is returned unchanged, which the caller uses to decide whether to disclose a
    search_phase at all)."""
    if not expected_family:
        return candidates, False
    matched = [c for c in candidates if c.get("section_family") == expected_family]
    if not matched:
        return candidates, False
    unmatched = [c for c in candidates if c.get("section_family") != expected_family]
    return matched + unmatched, True
