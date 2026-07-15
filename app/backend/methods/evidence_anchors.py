"""Response-layer source anchoring for Methods evidence snippets.

Detectors stay pure text/page producers. Interactive endpoints can call this helper to add optional PDF
coordinates when a snippet is locally locatable on the same page the detector reported.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import Connection

from app.backend.pdf_processing.location import locate_quote_for_attachment


def anchor_evidence(conn: Connection, chunks: list, evidence: str | None, page: int | None) -> dict[str, Any]:
    if not evidence or page is None:
        return {"page_end": page, "coordinate_precision": None, "bbox_json": None}
    chunk = _matching_chunk(chunks, evidence, page)
    if chunk is None:
        return {"page_end": page, "coordinate_precision": "region", "bbox_json": None}

    page_end = _value(chunk, "page_end", page) or page
    bbox_json = _stamp(_value(chunk, "bbox_json"), "region")
    attachment_id = _value(chunk, "attachment_id")
    if attachment_id is None:
        return {"page_end": page_end, "coordinate_precision": "region", "bbox_json": bbox_json}

    try:
        match = locate_quote_for_attachment(conn, int(attachment_id), evidence)
    except Exception:
        match = None
    if not (match and match.found and match.rectangles):
        return {"page_end": page_end, "coordinate_precision": "region", "bbox_json": bbox_json}

    located_pages = {int(rect["page"]) for rect in match.rectangles if isinstance(rect, dict) and rect.get("page")}
    expected_pages = set(range(int(page), int(page_end) + 1))
    if not (located_pages & expected_pages):
        return {"page_end": page_end, "coordinate_precision": "region", "bbox_json": bbox_json}
    return {
        "page_end": match.page_end or page_end,
        "coordinate_precision": "exact",
        "bbox_json": _stamp(list(match.rectangles), "exact"),
    }


def _matching_chunk(chunks: list, evidence: str, page: int) -> Any | None:
    evidence_norm = _norm(evidence)
    for chunk in chunks:
        start = _value(chunk, "page_start")
        end = _value(chunk, "page_end", start)
        if start is None or not (int(start) <= int(page) <= int(end or start)):
            continue
        if evidence_norm in _norm(_value(chunk, "text", "")):
            return chunk
    return None


def _value(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def _stamp(bbox_json: Any | None, precision: str) -> Any | None:
    if bbox_json is None:
        return None
    copied = deepcopy(bbox_json)
    if isinstance(copied, list):
        return [{**item, "coordinate_precision": precision} if isinstance(item, dict) else item for item in copied]
    if isinstance(copied, dict):
        return {**copied, "coordinate_precision": precision}
    return copied
