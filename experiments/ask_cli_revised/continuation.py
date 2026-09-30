"""Stage A (plural evidence anchors, 2026-09-29 authorization): is chunk B really the textual
continuation of chunk A -- one sentence the chunker split at an arbitrary boundary -- and is that
provable, not merely plausible?

Two independent, required checks, both computed deterministically (no model call):

1. `contract_directed/seams.py::verify_seam` (reused unmodified, not reimplemented -- the Phase 2
   Section 5 precedent for reusing contract_directed's own tested primitives): same attachment/
   checksum/extraction identity, contiguous stream offsets, same page, same column, a bounded
   vertical gap, no OTHER PERSISTED CHUNK sitting between them by real page geometry, and the
   linguistic check (A's text is not terminal, B's text begins as a continuation).

2. `section_unchanged` -- closes a real, empirically-confirmed gap `verify_seam` does NOT close on
   its own. `pdf_processing/extraction.py::make_chunk_drafts` silently skips a text block that is
   PURELY one recognized section heading (e.g. a bare "Methods" line) -- the cursor never advances
   for it and it produces no chunk row at all, so it can never appear in ANY chunk-table-sourced
   geometry index, including `verify_seam`'s own `page_boxes` (also chunk-table-sourced, confirmed
   by reading `contract_directed/store.py::page_boxes`). Two otherwise-adjacent, offset-contiguous
   chunks straddling such a skipped heading would pass every one of `verify_seam`'s own checks.
   `pdf_processing/sections.py::SectionTracker.current_section` still advances across the skipped
   block (it observes the heading before deciding to skip it), so comparing `chunks.section` across
   the candidate pair catches exactly this case -- confirmed empirically (see
   `test_continuation.py`'s reproduction of the real extraction behavior).

A join is made only when BOTH checks pass. Neither check alone is trusted as sufficient.
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import seams

SECTION_CHANGED_REASON = "section_changed_between_chunks"


def section_unchanged(chunk_a: dict, chunk_b: dict) -> bool:
    """True only when both chunks carry the same (possibly None) section label. `None == None` is
    treated as unchanged -- neither chunk has ever seen a recognized heading, so there is nothing to
    have skipped between them on this signal; `verify_seam`'s own checks still apply."""
    return chunk_a.get("section") == chunk_b.get("section")


def page_boxes_for(chunks_on_attachment: list[dict], page: int) -> dict[int, seams.Box]:
    """`chunk_id -> Box` for every geometry-bearing chunk on one page, from an already-fetched chunk
    list (avoids a second query when the caller already has the attachment's full chunk list)."""
    boxes: dict[int, seams.Box] = {}
    for chunk in chunks_on_attachment:
        if chunk.get("page_start") == page:
            box = seams.chunk_box(chunk)
            if box is not None:
                boxes[chunk["chunk_id"]] = box
    return boxes


def detect_continuation(
    chunk_a: dict, chunk_b: dict, *, attachment_checksum: str | None, chunks_on_attachment: list[dict]
) -> dict:
    """`chunk_a`/`chunk_b` need every field `seams.verify_seam` needs (see its own docstring) plus
    `section`. `chunks_on_attachment`: every chunk of the shared attachment, used to build
    `page_boxes` for `chunk_a`'s page (mirrors `contract_directed/store.py::seam_verifier`'s own
    binding, without adopting its heavier `LibraryStore` caching abstraction).

    Returns a full, inspectable verdict -- never just a boolean -- so a refused join's reason is
    always recoverable for provenance/audit, matching this codebase's own decision-logging norm."""
    page = chunk_a.get("page_start")
    boxes = page_boxes_for(chunks_on_attachment, page) if page is not None else {}
    verdict = seams.verify_seam(chunk_a, chunk_b, attachment_checksum=attachment_checksum, page_boxes=boxes)
    sec_ok = section_unchanged(chunk_a, chunk_b)
    reasons = list(verdict.reasons)
    if not sec_ok:
        reasons.append(SECTION_CHANGED_REASON)
    return {
        "is_continuation": verdict.state == "established" and sec_ok,
        "seam_state": verdict.state,
        "seam_reasons": reasons,
        "seam_checks": verdict.checks,
        "section_unchanged": sec_ok,
    }
