"""Seam verification: is chunk B really the continuation of chunk A in the source document?

Chunk ids and stream adjacency are NOT evidence of reading order (block order and sorted order disagree on most pages, and a
two-column layout interleaves columns). A seam is `established` only when every deterministic check passes; otherwise it is
`not_established` with the failing reasons, and callers must keep the two halves as separate, unresolved fragments.

Checks (all required): same attachment; same source checksum (and equal to the attachment row's checksum); same extraction
tool/version; a geometry-bearing extractor; contiguous stream offsets; both on the same single page; the right block lies
below the left one in the same column within a bounded gap; no other block sits between them in that column; the text
actually continues (left has no terminal punctuation, right begins lowercase or after a hyphen break).
Pure: geometry is passed in; no connection, no model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from experiments.ask_cli_revised.contract_directed.units import ends_terminal, starts_as_continuation

MAX_STREAM_GAP = 2  # separator characters allowed between chunk A's end offset and chunk B's start offset
MIN_COLUMN_OVERLAP = 0.5  # of the narrower block's width
LEFT_MARGIN_TOLERANCE = 10.0  # points; blocks sharing a left margin count as the same column
MAX_GAP_LINE_HEIGHTS = 4.0  # vertical gap between A's bottom and B's top, in A's line heights
GEOMETRY_EXTRACTORS = frozenset({"pymupdf"})


@dataclass(frozen=True)
class SeamVerdict:
    state: str  # "established" | "not_established"
    reasons: tuple[str, ...]
    checks: dict  # name -> True / False / None (None: could not be evaluated)


@dataclass(frozen=True)
class Box:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    line_height: float
    numeric_only: bool = False  # a bare page number is not body text and must not block a column continuation


def parse_bbox(value) -> list[dict]:
    """`chunks.bbox_json` is a JSON column: a DB read returns a decoded list, a fixture may return a string."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return [s for s in value if isinstance(s, dict)] if isinstance(value, list) else []


def chunk_box(chunk: dict) -> Box | None:
    """The block box of a chunk (union of its span boxes on its page), or None when geometry is missing or ambiguous."""
    spans = parse_bbox(chunk.get("bbox_json"))
    if not spans or chunk.get("page_start") != chunk.get("page_end"):
        return None
    pages = {s.get("page") for s in spans}
    if len(pages) != 1 or None in pages:
        return None
    try:
        x0 = min(float(s["x0"]) for s in spans)
        y0 = min(float(s["y0"]) for s in spans)
        x1 = max(float(s["x1"]) for s in spans)
        y1 = max(float(s["y1"]) for s in spans)
        first = spans[0]
        line_height = max(float(first["y1"]) - float(first["y0"]), 1.0)
    except (KeyError, TypeError, ValueError):
        return None
    numeric = bool(chunk.get("text")) and chunk["text"].strip().replace(" ", "").isdigit()
    return Box(int(pages.pop()), x0, y0, x1, y1, line_height, numeric)


def _x_overlap(a: Box, b: Box) -> float:
    overlap = min(a.x1, b.x1) - max(a.x0, b.x0)
    narrower = min(a.x1 - a.x0, b.x1 - b.x0)
    return overlap / narrower if narrower > 0 and overlap > 0 else 0.0


def _same_column(a: Box, b: Box) -> bool:
    return _x_overlap(a, b) >= MIN_COLUMN_OVERLAP or abs(a.x0 - b.x0) <= LEFT_MARGIN_TOLERANCE


# Column-switch continuation is implemented but DISABLED by default: a spot-check of 12 verified joins found ~4 false positives
# (a footnote joined to a methods sentence, a heading to a footer, a math fragment, "reported at an" to an unrelated line).
# Geometry cannot establish that another column's first block continues this column's last; the honest outcome is an
# unresolved seam with both fragments kept.
ALLOW_COLUMN_SWITCH = False
FULL_WIDTH_SHARE = (
    0.7  # a block at least this share of the page's text width is a header/title/figure, not a column block
)


def _column_switch(a: Box, b: Box, a_id: int, b_id: int, page_boxes: dict[int, "Box"]) -> tuple[bool, dict]:
    """Does `b` continue `a` by leaving the bottom of one column for the top of the NEXT column on the same page?

    Verified, not inferred: the blocks are in horizontally disjoint columns, `b` is to the right of `a`, NOTHING body-like lies
    below `a` in its column, and nothing body-like lies above `b` in its column (full-width blocks and bare page numbers are not
    body). Anything else is refused.
    """
    boxes = list(page_boxes.values())
    if not boxes:
        return False, {"reason": "no_page_geometry"}
    page_width = max(bx.x1 for bx in boxes) - min(bx.x0 for bx in boxes)
    disjoint_right = a.x1 <= b.x0 + LEFT_MARGIN_TOLERANCE
    below_a = [
        cid for cid, bx in page_boxes.items()
        if cid not in (a_id, b_id) and not bx.numeric_only and (bx.x1 - bx.x0) < FULL_WIDTH_SHARE * page_width
        and _x_overlap(bx, a) >= MIN_COLUMN_OVERLAP and bx.y0 >= a.y1 - 1.0
    ]  # fmt: skip
    above_b = [
        cid for cid, bx in page_boxes.items()
        if cid not in (a_id, b_id) and not bx.numeric_only and (bx.x1 - bx.x0) < FULL_WIDTH_SHARE * page_width
        and _x_overlap(bx, b) >= MIN_COLUMN_OVERLAP and bx.y1 <= b.y0 + 1.0
    ]  # fmt: skip
    ok = disjoint_right and not below_a and not above_b
    return ok, {
        "disjoint_columns_b_right_of_a": disjoint_right,
        "body_blocks_below_a_in_its_column": below_a,
        "body_blocks_above_b_in_its_column": above_b,
    }


def verify_seam(
    a: dict,
    b: dict,
    *,
    attachment_checksum: str | None,
    page_boxes: dict[int, Box],
    allow_column_switch: bool = ALLOW_COLUMN_SWITCH,
) -> SeamVerdict:
    """Verify that chunk `b` continues chunk `a`.

    `a`/`b` need: chunk_id, attachment_id, source_attachment_checksum, extraction_tool, extraction_version, page_start,
    page_end, char_start, char_end, bbox_json, text. `page_boxes` maps chunk_id -> Box for EVERY chunk on their page in this
    attachment (used to detect an intervening block).
    """
    checks: dict = {}
    checks["same_attachment"] = a.get("attachment_id") == b.get("attachment_id")
    checks["same_source_checksum"] = (
        a.get("source_attachment_checksum") == b.get("source_attachment_checksum") is not None
    )
    checks["checksum_matches_attachment_row"] = (
        None if attachment_checksum is None else a.get("source_attachment_checksum") == attachment_checksum
    )
    checks["same_extraction"] = (a.get("extraction_tool"), a.get("extraction_version")) == (
        b.get("extraction_tool"),
        b.get("extraction_version"),
    )
    checks["geometry_extractor"] = a.get("extraction_tool") in GEOMETRY_EXTRACTORS
    gap = None
    if a.get("char_end") is not None and b.get("char_start") is not None:
        gap = b["char_start"] - a["char_end"]
    checks["contiguous_stream_offsets"] = None if gap is None else 0 <= gap <= MAX_STREAM_GAP
    checks["same_single_page"] = (
        a.get("page_start") == a.get("page_end") == b.get("page_start") == b.get("page_end")
        and a.get("page_start") is not None
    )
    box_a, box_b = chunk_box(a), chunk_box(b)
    checks["geometry_available"] = box_a is not None and box_b is not None
    checks["same_column_right_below_left"] = None
    checks["gap_within_line_heights"] = None
    checks["no_intervening_block"] = None
    checks["column_switch_verified"] = None
    if box_a is not None and box_b is not None and box_a.page == box_b.page:
        same_col = _same_column(box_a, box_b) and box_b.y0 >= box_a.y0
        if not same_col and allow_column_switch:
            switched, detail = _column_switch(box_a, box_b, a["chunk_id"], b["chunk_id"], page_boxes)
            checks["column_switch_verified"] = switched
            checks["column_switch_detail"] = detail
        checks["same_column_right_below_left"] = True if checks["column_switch_verified"] else same_col
        vertical_gap = box_b.y0 - box_a.y1
        checks["gap_within_line_heights"] = (
            True if checks["column_switch_verified"] else vertical_gap <= MAX_GAP_LINE_HEIGHTS * box_a.line_height
        )
        between = [
            cid
            for cid, box in page_boxes.items()
            if cid not in (a["chunk_id"], b["chunk_id"])
            and box.page == box_a.page
            and _x_overlap(box, Box(box_a.page, min(box_a.x0, box_b.x0), 0, max(box_a.x1, box_b.x1), 0, 1))
            >= MIN_COLUMN_OVERLAP
            and box.y0 >= box_a.y1 - 1.0
            and box.y1 <= box_b.y0 + 1.0
        ]
        checks["no_intervening_block"] = True if checks["column_switch_verified"] else not between
    checks["left_open"] = not ends_terminal(a.get("text", ""))
    hyphen_break = a.get("text", "").rstrip().endswith("-")
    checks["right_continues"] = starts_as_continuation(b.get("text", "")) or (
        hyphen_break and not ends_terminal(a.get("text", ""))
    )

    informational = {"column_switch_verified", "column_switch_detail"}
    reasons = tuple(
        name
        for name, ok in checks.items()
        if name not in informational and (ok is False or (ok is None and name in _REQUIRED_KNOWN))
    )
    return SeamVerdict("not_established" if reasons else "established", reasons, checks)


# Checks that must be evaluable (True), not merely "not False": an unevaluable one is a reason to refuse.
_REQUIRED_KNOWN = frozenset(
    {
        "contiguous_stream_offsets",
        "same_column_right_below_left",
        "gap_within_line_heights",
        "no_intervening_block",
        "checksum_matches_attachment_row",
    }
)
