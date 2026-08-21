"""Translate bounded Zotero text-markup geometry into Callosum PDF coordinates."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from app.backend.pdf_processing.extraction import COORDINATE_SYSTEM

ZOTERO_READER_COORDINATE_SYSTEM = "zotero-reader-json"
# Zotero.Annotations.ANNOTATION_POSITION_MAX_SIZE in Zotero's own annotations.js.
ZOTERO_POSITION_MAX_BYTES = 65_000
# A second structural bound after JSON parsing. The raw-byte cap normally binds first.
ZOTERO_POSITION_MAX_RECTS = 2_048
_TEXT_MARKUP_TYPES = frozenset({1, 5, "1", "5", "highlight", "underline"})
_BOUNDS_TOLERANCE = 1e-4


@dataclass(frozen=True)
class TranslatedZoteroPosition:
    page: int | None
    bboxes_json: list[dict[str, float | int]] | None
    coordinate_system: str | None


def translate_zotero_position(
    position_json: dict[str, Any] | None,
    *,
    annotation_type: str | int | None,
    pdf_path: Path | None,
) -> TranslatedZoteroPosition:
    """Return exact top-left bboxes only when every part of the transform validates.

    Zotero keeps ``position`` as JSON text in SQLite. Its text-markup ``rects`` use
    standard PDF coordinates: points, bottom-left origin, ``[left, bottom, right,
    top]``. PyMuPDF's page transformation matrix converts that space into the same
    unrotated, top-left coordinate basis used by Callosum extraction.
    """
    raw_position = _parse_position(position_json)
    raw_coordinate_system = ZOTERO_READER_COORDINATE_SYSTEM if position_json else None
    if raw_position is None or pdf_path is None or not pdf_path.is_file():
        return TranslatedZoteroPosition(None, None, raw_coordinate_system)

    page_index = raw_position.get("pageIndex")
    if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 0:
        return TranslatedZoteroPosition(None, None, raw_coordinate_system)

    try:
        with fitz.open(pdf_path) as document:
            if page_index >= document.page_count:
                return TranslatedZoteroPosition(None, None, raw_coordinate_system)
            page = document[page_index]
            page_number = page_index + 1
            if page.rotation != 0 or annotation_type not in _TEXT_MARKUP_TYPES:
                return TranslatedZoteroPosition(page_number, None, raw_coordinate_system)

            rects = raw_position.get("rects")
            if not isinstance(rects, list) or not rects or len(rects) > ZOTERO_POSITION_MAX_RECTS:
                return TranslatedZoteroPosition(page_number, None, raw_coordinate_system)

            page_bounds = page.rect
            transformed: list[dict[str, float | int]] = []
            for raw_rect in rects:
                values = _rect_values(raw_rect)
                if values is None:
                    return TranslatedZoteroPosition(page_number, None, raw_coordinate_system)
                rect = fitz.Rect(values) * page.transformation_matrix
                if not _valid_transformed_rect(rect, page_bounds):
                    return TranslatedZoteroPosition(page_number, None, raw_coordinate_system)
                transformed.append(
                    {
                        "page": page_number,
                        "x0": max(page_bounds.x0, rect.x0),
                        "y0": max(page_bounds.y0, rect.y0),
                        "x1": min(page_bounds.x1, rect.x1),
                        "y1": min(page_bounds.y1, rect.y1),
                    }
                )
    except Exception:
        # A malformed/unreadable PDF is already isolated by the importer. Geometry
        # translation must fail closed too, never abort the whole-library import.
        return TranslatedZoteroPosition(None, None, raw_coordinate_system)

    return TranslatedZoteroPosition(page_number, transformed, COORDINATE_SYSTEM)


def _parse_position(position_json: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(position_json, dict):
        return None
    if "raw" not in position_json:
        return position_json
    raw = position_json.get("raw")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > ZOTERO_POSITION_MAX_BYTES:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _rect_values(raw_rect: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(raw_rect, list) or len(raw_rect) != 4:
        return None
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw_rect):
        return None
    values = tuple(float(value) for value in raw_rect)
    if not all(math.isfinite(value) for value in values):
        return None
    x0, y0, x1, y1 = values
    return values if x1 > x0 and y1 > y0 else None


def _valid_transformed_rect(rect: fitz.Rect, bounds: fitz.Rect) -> bool:
    values = (rect.x0, rect.y0, rect.x1, rect.y1)
    if not all(math.isfinite(value) for value in values) or rect.x1 <= rect.x0 or rect.y1 <= rect.y0:
        return False
    return (
        rect.x0 >= bounds.x0 - _BOUNDS_TOLERANCE
        and rect.y0 >= bounds.y0 - _BOUNDS_TOLERANCE
        and rect.x1 <= bounds.x1 + _BOUNDS_TOLERANCE
        and rect.y1 <= bounds.y1 + _BOUNDS_TOLERANCE
    )
