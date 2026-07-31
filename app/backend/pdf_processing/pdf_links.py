"""URI annotation extraction for PDFs, separate from block/chunk construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import fitz


@dataclass(frozen=True)
class PdfLinkAnnotation:
    """A URI annotation plus the visible/nearby page text used to interpret it."""

    page_number: int
    uri: str
    bbox: dict[str, float]
    visible_text: str | None
    nearby_text: str | None
    association: str


def extract_page_link_annotations(page: Any, page_number: int, blocks: list[Any]) -> list[PdfLinkAnnotation]:
    annotations: list[PdfLinkAnnotation] = []
    page_words = page.get_text("words", sort=True)
    for raw in page.get_links():
        uri = str(raw.get("uri") or "").strip()
        source_rect = raw.get("from")
        if not uri or source_rect is None:
            continue
        rect = fitz.Rect(source_rect)
        words = [word for word in page_words if not (fitz.Rect(word[:4]) & rect).is_empty and str(word[4]).strip()]
        clipped = _normalize_space(page.get_textbox(rect))
        visible = clipped or " ".join(str(word[4]).strip() for word in words) or None
        containing = [block for block in blocks if not (_block_rect(block) & rect).is_empty]
        if containing:
            nearby = min(containing, key=lambda block: _rect_distance(rect, _block_rect(block))).text
            association = "overlapping-text" if visible else "nearby-block"
        else:
            nearby_block = min(blocks, key=lambda block: _rect_distance(rect, _block_rect(block)), default=None)
            nearby = (
                nearby_block.text if nearby_block and _rect_distance(rect, _block_rect(nearby_block)) <= 36 else None
            )
            association = "nearby-block" if nearby else "unpaired"
        annotations.append(
            PdfLinkAnnotation(
                page_number=page_number,
                uri=uri,
                bbox={"x0": float(rect.x0), "y0": float(rect.y0), "x1": float(rect.x1), "y1": float(rect.y1)},
                visible_text=visible,
                nearby_text=_normalize_space(nearby)[:500] if nearby else None,
                association=association,
            )
        )
    return annotations


def _block_rect(block: Any) -> fitz.Rect:
    return fitz.Rect(tuple(block.bbox.values()))


def _rect_distance(left: Any, right: Any) -> float:
    dx = max(float(right.x0) - float(left.x1), float(left.x0) - float(right.x1), 0.0)
    dy = max(float(right.y0) - float(left.y1), float(left.y0) - float(right.y1), 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _normalize_space(text: str) -> str:
    return " ".join(text.split())
