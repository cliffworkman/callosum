"""Local, deterministic glue for the assisted-extraction funnel (workbench SP2b, inc 259).

The honesty engine: it turns the LLM's untrusted {value, quote, page} proposals into anchored candidates by running
the deterministic local locator (pdf_processing.quote_matching.locate_quote) — the MODEL never asserts a location or a
confidence; the locator decides the anchor state (exact/region/unanchored). It also selects which cells to draft
(empty structured only — the funnel fills gaps, never contests a human), builds the page-tagged capped paper text, and
resolves the paper's PDF path ONLY from its trusted attachment rows (rule #4). No egress here (fitz is local).
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.engine import Connection

from app.backend.pdf_processing.quote_matching import locate_quote
from app.backend.persistence.repository import get_attachments_for_paper

MAX_TEXT_CHARS = 50_000  # the paper-text egress cap (resource guard; also bounds the prompt)
STRUCTURED_TYPES = {"number", "choice"}  # the funnel drafts these; free-text columns stay hand-entered


def page_tagged_text(chunks, *, cap: int = MAX_TEXT_CHARS) -> tuple[str, bool]:
    """Join a paper's chunks into page-tagged text ("[p.N] …\\n") capped at `cap` chars → (text, truncated)."""
    parts: list[str] = []
    total = 0
    truncated = False
    for c in chunks:
        seg = f"[p.{c['page_start']}] {c['text']}\n"
        if total + len(seg) > cap:
            truncated = True
            break
        parts.append(seg)
        total += len(seg)
    return "".join(parts), truncated


def proposable_fields(template: list[dict], cells: dict) -> list[dict]:
    """The EMPTY STRUCTURED (number/choice) fields — never a filled cell, never a free-text column."""
    out: list[dict] = []
    for f in template:
        if f.get("type") not in STRUCTURED_TYPES:
            continue
        value = (cells.get(f["key"]) or {}).get("value")
        if value is not None and str(value).strip():
            continue
        out.append({"key": f["key"], "label": f["label"], "type": f["type"], "options": f.get("options")})
    return out


def _norm(s: str) -> str:
    return " ".join((s or "").split()).casefold()


def _value_in_quote(value, quote: str) -> bool:
    v = "" if value is None else str(value).strip()
    if not v or not quote:
        return False
    return _norm(v) in _norm(quote) or v in quote


def _union_rect(rectangles) -> dict:
    """One bounding rect on the located quote's first page — matches SP2a-2's single-rect bbox_json (bounded, and the
    exact-highlight renderer already consumes a [rect] list)."""
    page = rectangles[0]["page"]
    same = [r for r in rectangles if r["page"] == page]
    return {
        "page": page,
        "x0": min(r["x0"] for r in same),
        "y0": min(r["y0"] for r in same),
        "x1": max(r["x1"] for r in same),
        "y1": max(r["y1"] for r in same),
    }


def anchor_proposal(pdf_path, value, quote, claimed_page) -> dict:
    """Deterministically anchor one proposal:
    - quote located AND value literal in it → `exact` (bbox = the union rect on the located page).
    - quote located, value not literal      → `region` (no bbox; reason value_not_in_quote).
    - quote not found                        → `unanchored` (keep the model's claimed page; reason quote_not_found).
    """
    match = locate_quote(pdf_path, quote) if quote else None
    if match is not None and match.found and match.rectangles:
        if _value_in_quote(value, quote):
            return {
                "anchor_state": "exact",
                "page": match.page_start,
                "bbox_json": json.dumps([_union_rect(match.rectangles)]),
                "reason": None,
            }
        return {"anchor_state": "region", "page": match.page_start, "bbox_json": None, "reason": "value_not_in_quote"}
    return {"anchor_state": "unanchored", "page": claimed_page, "bbox_json": None, "reason": "quote_not_found"}


def assemble_proposals(pdf_path, raw_proposals: list[dict], allowed_keys: set[str]) -> list[dict]:
    """Anchor each parsed proposal locally → storable proposal dicts (field_key/value/quote + the anchor fields)."""
    out: list[dict] = []
    for rp in raw_proposals:
        if rp["field_key"] not in allowed_keys:
            continue
        anchor = anchor_proposal(pdf_path, rp.get("value"), rp.get("quote"), rp.get("page"))
        out.append({"field_key": rp["field_key"], "value": rp.get("value"), "quote": rp.get("quote"), **anchor})
    return out


def primary_pdf_path(conn: Connection, paper_id: int) -> Path | None:
    """The paper's primary local PDF path, resolved ONLY from its trusted attachment rows (rule #4) — never from a
    request-supplied path. Mirrors routers/paper_files.py's selection (PDF-preferred → role=primary → present on disk).
    """
    rows = get_attachments_for_paper(conn, paper_id)
    if not rows:
        return None
    pdfs = [
        r
        for r in rows
        if (r["content_type"] or "").strip().lower() == "application/pdf"
        or (r["attachment_type"] or "").strip().lower() == "pdf"
    ]
    candidates = pdfs or list(rows)
    primary = [r for r in candidates if (r["role"] or "").strip().lower() == "primary"]
    row = (primary or candidates)[0]
    if row["storage_mode"] == "url" or row["availability"] != "available":
        return None
    raw = row["resolved_path"] or row["original_path"]
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None
