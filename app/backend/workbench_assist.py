"""Local, deterministic glue for the assisted-extraction funnel (workbench SP2b, inc 259).

The honesty engine: it turns the LLM's untrusted {value, quote, page} proposals into anchored candidates by running
the deterministic local locator (pdf_processing.quote_matching.locate_quote) — the MODEL never asserts a location or a
confidence; the locator decides the anchor state (exact/region/unanchored). It also selects which cells to draft
 (empty structured only — the funnel fills gaps, never contests a human), narrows page-tagged paper text with local
 embedding retrieval, and resolves the paper's PDF path ONLY from its trusted attachment rows (rule #4). No egress here
 (fitz and embeddings are local).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.engine import Connection

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.retrieval import search_similar
from app.backend.embeddings.vector_store import VectorStore
from app.backend.pdf_processing.quote_matching import locate_quote
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import get_attachments_for_paper

MAX_TEXT_CHARS = 50_000  # the paper-text egress cap (resource guard; also bounds the prompt)
# Measured real worst-case input was 50,546 chars -- essentially the full cloud-sized cap above, well past
# the managed Local AI preview's ~10,240-token (~30-40k character) budget. See app/backend/llm/prompt_budget.py.
MAX_TEXT_CHARS_MANAGED_LOCAL = 8_000
MAX_RELEVANT_CHUNKS = 12  # local retrieval budget before the text egress cap is applied
STRUCTURED_TYPES = {"number", "choice"}  # the funnel drafts these; free-text columns stay hand-entered
logger = logging.getLogger(__name__)


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


def field_retrieval_query(fields: list[dict]) -> str:
    """A local retrieval query made only from the empty structured fields' human-readable labels."""
    return "\n".join(f"Extraction field: {field['label']}" for field in fields if str(field.get("label") or "").strip())


def relevant_page_tagged_text(
    conn: Connection,
    chunks,
    *,
    fields: list[dict],
    model: EmbeddingModel,
    vector_store: VectorStore,
    top_k: int = MAX_RELEVANT_CHUNKS,
    cap: int = MAX_TEXT_CHARS,
) -> tuple[str, bool]:
    """Select this paper's top-k chunks against the field labels, then page-tag + cap them.

    The fallback deliberately preserves the previous bounded behavior: local embedding or vector-store trouble may make
    a draft less focused, but must not make an otherwise draftable row unusable.
    """
    rows = list(chunks)
    if not rows:
        return "", False
    if len(rows) <= top_k:
        return page_tagged_text(rows, cap=cap)

    try:
        with conn.begin_nested():
            chunk_ids = [int(row["id"]) for row in rows]
            embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=chunk_ids)
            hits = search_similar(
                conn,
                query=field_retrieval_query(fields),
                model=model,
                vector_store=vector_store,
                top_k=min(top_k, len(chunk_ids)),
                target_types=("chunk",),
                candidate_target_ids=set(chunk_ids),
                document_roles=ARTICLE_DOCUMENT_ROLES,
            )
            by_id = {int(row["id"]): row for row in rows}
            selected = [by_id[hit.chunk_id] for hit in hits if hit.chunk_id in by_id]
            if not selected:
                raise RuntimeError("local retrieval returned no candidate chunks")
        text, capped = page_tagged_text(selected, cap=cap)
        return text, capped or len(selected) < len(rows)
    except Exception as exc:
        logger.warning("Workbench chunk retrieval failed; using bounded document-order text: %s", exc)
        return page_tagged_text(rows, cap=cap)


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
    - quote located AND rectangles present AND value literal in it → `exact` (bbox = union rect on located page).
    - quote located, but rectangles missing OR value not literal   → `region` (no bbox; known page preserved).
      reason is "value_not_in_quote" when rectangles were present, "no_rects" when rectangles were empty.
    - quote not found (or no quote)                                → `unanchored` (keep model's claimed page).
    """
    match = locate_quote(pdf_path, quote) if quote else None
    if match is not None and match.found:
        if match.rectangles and _value_in_quote(value, quote):
            return {
                "anchor_state": "exact",
                "page": match.page_start,
                "bbox_json": json.dumps([_union_rect(match.rectangles)]),
                "reason": None,
            }
        return {
            "anchor_state": "region",
            "page": match.page_start,
            "bbox_json": None,
            "reason": "value_not_in_quote" if match.rectangles else "no_rects",
        }
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
