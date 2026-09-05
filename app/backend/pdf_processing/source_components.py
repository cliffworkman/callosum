"""Build the deterministic source-component tree from one PyMuPDF page dict (inc 578, H1b).

**I/O boundary (deliberate and enforced, the H1a contract).** This module opens no database
connection, constructs no client, performs no network call and never opens a PDF. It takes the
``page.get_text("dict", sort=True)`` mapping the extractor has *already* built plus the page
geometry the extractor has *already* measured, and returns records. The caller
(``extraction.extract_pdf``, and through it ingest and the backfill) owns all I/O. That is what
makes this deterministic and testable from literals -- see ``tests/test_source_components.py``,
which builds every case by hand with no PDF and no database.

Why a second walk over the same dict rather than enriching ``extract_pdf``'s own loop: that loop
feeds ``chunks``, and H1b's whole premise is that current chunk behaviour must not change. Keeping
the structural capture in its own pure function means the chunk-producing path is untouched apart
from one call, and a failure here can be isolated without risking the chunk write. The dict is
already materialized, so the extra walk costs a Python traversal, not a re-parse.

**Two orders, and neither is reading order.** ``sorted_order`` is the position in the
geometrically sorted block list -- the same ordinal ``chunks.bbox_json["block"]`` carries, counting
image blocks that ingest then drops. ``native_order`` is MuPDF's own ``block["number"]``, which
``sort=True`` leaves un-renumbered. They disagree on most pages. Neither is a claim about reading
order, and neither establishes that two adjacent components continue one another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.backend.pdf_processing.sections import scan_block_heading

# Component kinds, mirroring persistence.schema_source_components.SOURCE_COMPONENT_KINDS. Kept as
# plain literals here so this module stays importable without touching the persistence package.
TEXT_BLOCK = "text_block"
LINE = "line"
SPAN = "span"
HEADING = "heading"
IMAGE = "image"

# PyMuPDF block types.
_BLOCK_TYPE_TEXT = 0
_BLOCK_TYPE_IMAGE = 1

_VALID_ROTATIONS = (0, 90, 180, 270)

# Geometry validity (inc 579, H1b.1), mirroring persistence.schema_source_components.GEOMETRY_STATES.
GEOMETRY_VALID = "valid"
GEOMETRY_INVALID = "invalid"
GEOMETRY_UNKNOWN = "unknown"

# How far outside the page a bbox may sit and still be usable, in PDF points.
#
# **Frozen before corpus validation, and justified on mechanism rather than on the count it
# produces.** A MediaBox/CropBox difference, a glyph outline overshooting its advance width, and
# float rounding through the coordinate transform all routinely put an edge a fraction of a point
# outside the page rectangle; none of those is a malformed observation. 2.0pt is ~0.7mm -- larger
# than every one of those effects, and far smaller than any region a spatial association could
# meaningfully use. Tuning this after seeing which historical rasters it classifies would be
# choosing a threshold for a desired corpus count, so it is fixed here and reported as measured.
GEOMETRY_PAGE_TOLERANCE_PT = 2.0


def classify_geometry(
    bbox: tuple[float, float, float, float] | None,
    *,
    page_width: float,
    page_height: float,
) -> tuple[str, str | None]:
    """An explicit judgment ABOUT a raw bbox. The bbox itself is never rewritten.

    The independent H1b audit found 363 inverted raster bboxes and one out-of-page bbox faithfully
    preserved. That is fidelity working correctly -- and precisely why a separate validity signal is
    needed: a future association study must be able to fail closed on a region that cannot be
    intersected, without normalizing, clamping or swapping the coordinates the extractor actually
    reported. Returns ``(state, reason)``; the reason is for inspection and reporting and is not
    stored.
    """
    if bbox is None or any(value is None for value in bbox):
        return GEOMETRY_UNKNOWN, "missing"
    x0, y0, x1, y1 = bbox
    if x1 < x0 or y1 < y0:
        return GEOMETRY_INVALID, "inverted"
    tol = GEOMETRY_PAGE_TOLERANCE_PT
    if x0 < -tol or y0 < -tol or x1 > page_width + tol or y1 > page_height + tol:
        return GEOMETRY_INVALID, "out_of_page"
    return GEOMETRY_VALID, None


@dataclass(frozen=True)
class SourceComponent:
    """One node of the extractor's own structural tree. Purely observational."""

    kind: str
    native_order: int | None = None
    sorted_order: int | None = None
    child_order: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    # Exact extractor text, never whitespace-normalized. Only spans and headings carry it: a
    # block's or line's text is reconstructable from its spans, and duplicating it at every
    # level would multiply storage for no new information.
    text: str | None = None
    font: str | None = None
    font_size: float | None = None
    flags: int | None = None
    dir_x: float | None = None
    dir_y: float | None = None
    wmode: int | None = None
    # The stable logical locator path within its page (inc 579, H1b.1):
    # "b{sorted_order}[/l{child_order}[/s{child_order}]]". Durable provenance references a
    # component by this path plus the source/extractor/derivation identity and page number --
    # never by a surrogate row id, which a forced rebuild changes while this path does not.
    component_path: str | None = None
    # An explicit judgment about `bbox`, which is itself never altered. See `classify_geometry`.
    geometry_state: str | None = None
    children: tuple[SourceComponent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SourcePage:
    page_number: int
    width: float
    height: float
    rotation: int
    components: tuple[SourceComponent, ...] = field(default_factory=tuple)


def _rect(value: Any) -> tuple[float, float, float, float] | None:
    """A 4-tuple bbox, or None when the extractor gave something unusable."""
    try:
        x0, y0, x1, y1 = (float(v) for v in tuple(value)[:4])
    except (TypeError, ValueError):
        return None
    return (x0, y0, x1, y1)


def _normalize_rotation(rotation: Any) -> int:
    """PDF rotation is a multiple of 90; anything else is not representable and becomes 0.

    The schema constrains this column, so an odd value from a malformed file must be normalized
    here rather than failing an ingest whose chunks are perfectly fine.
    """
    try:
        value = int(rotation) % 360
    except (TypeError, ValueError):
        return 0
    return value if value in _VALID_ROTATIONS else 0


def _spans_of_line(line: dict[str, Any], prefix: str, width: float, height: float) -> list[SourceComponent]:
    spans: list[SourceComponent] = []
    for span_index, span in enumerate(line.get("spans", []) or []):
        text = span.get("text", "")
        if not text:
            continue
        size = span.get("size")
        bbox = _rect(span.get("bbox"))
        geometry_state, _ = classify_geometry(bbox, page_width=width, page_height=height)
        spans.append(
            SourceComponent(
                kind=SPAN,
                child_order=span_index,
                bbox=bbox,
                text=text,
                font=span.get("font") or None,
                font_size=float(size) if isinstance(size, (int, float)) else None,
                flags=span.get("flags") if isinstance(span.get("flags"), int) else None,
                # Skipped empty-text spans leave gaps in this index, never duplicates, so the path
                # stays unique within its line -- and stable, because the index is the extractor's
                # own ordering rather than an ordinal we re-assign.
                component_path=f"{prefix}/s{span_index}",
                geometry_state=geometry_state,
            )
        )
    return spans


def _lines_of_block(block: dict[str, Any], prefix: str, width: float, height: float) -> list[SourceComponent]:
    lines: list[SourceComponent] = []
    for line_index, line in enumerate(block.get("lines", []) or []):
        line_path = f"{prefix}/l{line_index}"
        spans = _spans_of_line(line, line_path, width, height)
        if not spans:
            continue
        direction = line.get("dir")
        dir_x = dir_y = None
        if isinstance(direction, (list, tuple)) and len(direction) >= 2:
            try:
                dir_x, dir_y = float(direction[0]), float(direction[1])
            except (TypeError, ValueError):
                dir_x = dir_y = None
        line_bbox = _rect(line.get("bbox"))
        line_geometry, _ = classify_geometry(line_bbox, page_width=width, page_height=height)
        lines.append(
            SourceComponent(
                kind=LINE,
                child_order=line_index,
                bbox=line_bbox,
                dir_x=dir_x,
                dir_y=dir_y,
                wmode=line.get("wmode") if isinstance(line.get("wmode"), int) else None,
                component_path=line_path,
                geometry_state=line_geometry,
                children=tuple(spans),
            )
        )
    return lines


def _block_text(lines: list[SourceComponent]) -> str:
    """Newline-joined line text, matching what ``observe_block`` is handed at ingest.

    Deliberately a plain concatenation of span text per line -- NOT ``_line_text_from_spans``'s
    gap-aware spacing. The heading predicate only needs line *count* and heading *shape*, and
    reusing the spacing heuristic here would couple this module to a chunk-text decision.
    """
    return "\n".join("".join(span.text or "" for span in line.children) for line in lines)


def build_page(
    text_dict: dict[str, Any],
    *,
    page_number: int,
    width: float,
    height: float,
    rotation: Any = 0,
) -> SourcePage:
    """Structural records for one page, from the dict the extractor already built.

    Every block in ``text_dict["blocks"]`` is represented, including the image blocks and pure
    headings that ingest discards. ``sorted_order`` is the enumerate ordinal over that same
    (already geometrically sorted) list, so it is directly comparable with the ``"block"`` key in
    ``chunks.bbox_json``; ``native_order`` is MuPDF's own untouched block number.
    """
    width = float(width)
    height = float(height)
    components: list[SourceComponent] = []
    for sorted_index, block in enumerate(text_dict.get("blocks", []) or []):
        native = block.get("number")
        native_order = native if isinstance(native, int) else None
        bbox = _rect(block.get("bbox"))
        # `sorted_order` roots the path because it is the enumerate index over the already-sorted
        # block list: always present at top level and unique per page, where `native_order` may be
        # absent. Skipped blocks leave gaps, never duplicates.
        block_path = f"b{sorted_index}"
        block_geometry, _ = classify_geometry(bbox, page_width=width, page_height=height)

        if block.get("type") == _BLOCK_TYPE_IMAGE:
            # Structural bounds only. No pixels, no interpretation, no figure claim -- a raster
            # block is recorded because ingest drops all 13 of its fields today, not because we
            # know what it depicts.
            components.append(
                SourceComponent(
                    kind=IMAGE,
                    native_order=native_order,
                    sorted_order=sorted_index,
                    bbox=bbox,
                    component_path=block_path,
                    geometry_state=block_geometry,
                )
            )
            continue

        if block.get("type") != _BLOCK_TYPE_TEXT:
            continue

        lines = _lines_of_block(block, block_path, width, height)
        if not lines:
            continue

        heading, line_count = scan_block_heading(_block_text(lines))
        is_pure_heading = heading is not None and line_count == 1
        components.append(
            SourceComponent(
                # A pure heading is recorded as its own kind because ingest emits NO chunk for it
                # -- the text is lost outright today. It is deliberately not bound to neighbouring
                # prose: heading/body scope is an H1c question, not an H1b assertion.
                kind=HEADING if is_pure_heading else TEXT_BLOCK,
                native_order=native_order,
                sorted_order=sorted_index,
                bbox=bbox,
                text=_block_text(lines) if is_pure_heading else None,
                component_path=block_path,
                geometry_state=block_geometry,
                children=tuple(lines),
            )
        )

    return SourcePage(
        page_number=page_number,
        width=width,
        height=height,
        rotation=_normalize_rotation(rotation),
        components=tuple(components),
    )


def component_counts(pages: list[SourcePage]) -> dict[str, int]:
    """Flat per-kind tally over a page list -- for backfill receipts and tests, not for retrieval."""
    counts: dict[str, int] = {}

    def walk(component: SourceComponent) -> None:
        counts[component.kind] = counts.get(component.kind, 0) + 1
        for child in component.children:
            walk(child)

    for page in pages:
        for component in page.components:
            walk(component)
    return counts


__all__ = [
    "GEOMETRY_INVALID",
    "GEOMETRY_PAGE_TOLERANCE_PT",
    "GEOMETRY_UNKNOWN",
    "GEOMETRY_VALID",
    "HEADING",
    "IMAGE",
    "LINE",
    "SPAN",
    "TEXT_BLOCK",
    "SourceComponent",
    "SourcePage",
    "build_page",
    "classify_geometry",
    "component_counts",
]
