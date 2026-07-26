"""Response-layer source anchoring for Methods evidence snippets.

Detectors stay pure text/page producers. Interactive endpoints can call this helper to add optional PDF
coordinates when a snippet is locally locatable on the same page the detector reported.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import Connection, select

from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.persistence.schema import attachments


def pdf_attachment_ids(conn: Connection, values) -> set[int]:
    """Return only attachment ids that the PDF-serving route can safely open."""
    attachment_ids = {int(value) for value in values if value is not None}
    if not attachment_ids:
        return set()
    rows = conn.execute(
        select(attachments.c.id, attachments.c.content_type, attachments.c.attachment_type).where(
            attachments.c.id.in_(attachment_ids)
        )
    ).mappings()
    return {
        int(row["id"])
        for row in rows
        if (row["content_type"] or "").strip().lower() == "application/pdf"
        or (row["attachment_type"] or "").strip().lower() == "pdf"
    }


def pdf_attachment_ids_for_chunks(conn: Connection, chunks: list) -> set[int]:
    return pdf_attachment_ids(conn, (_value(chunk, "attachment_id") for chunk in chunks))


def anchor_evidence(
    conn: Connection,
    chunks: list,
    evidence: str | None,
    page: int | None,
    *,
    pdf_attachment_ids: set[int] | None = None,
) -> dict[str, Any]:
    if not evidence or page is None:
        return {"page_end": page, "coordinate_precision": None, "bbox_json": None, "attachment_id": None}
    chunk = _matching_chunk(chunks, evidence, page)
    if chunk is None:
        return {"page_end": page, "coordinate_precision": "region", "bbox_json": None, "attachment_id": None}

    page_end = _value(chunk, "page_end", page) or page
    bbox_json = _stamp(_value(chunk, "bbox_json"), "region")
    raw_attachment_id = _value(chunk, "attachment_id")
    if pdf_attachment_ids is None:
        pdf_attachment_ids = pdf_attachment_ids_for_chunks(conn, [chunk]) if conn is not None else set()
    attachment_id = (
        int(raw_attachment_id)
        if raw_attachment_id is not None and int(raw_attachment_id) in pdf_attachment_ids
        else None
    )
    if attachment_id is None:
        return {
            "page_end": page_end,
            "coordinate_precision": "region",
            "bbox_json": bbox_json,
            "attachment_id": None,
        }

    try:
        match = locate_quote_for_attachment(conn, int(attachment_id), evidence)
    except Exception:
        match = None
    if not (match and match.found and match.rectangles):
        return {
            "page_end": page_end,
            "coordinate_precision": "region",
            "bbox_json": bbox_json,
            "attachment_id": attachment_id,
        }

    located_pages = {int(rect["page"]) for rect in match.rectangles if isinstance(rect, dict) and rect.get("page")}
    expected_pages = set(range(int(page), int(page_end) + 1))
    if not (located_pages & expected_pages):
        return {
            "page_end": page_end,
            "coordinate_precision": "region",
            "bbox_json": bbox_json,
            "attachment_id": attachment_id,
        }
    return {
        "page_end": match.page_end or page_end,
        "coordinate_precision": "exact",
        "bbox_json": _stamp(list(match.rectangles), "exact"),
        "attachment_id": attachment_id,
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
