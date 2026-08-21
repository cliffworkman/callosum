"""Binary PDF file-serving for a paper's local attachment.

Split out of `routers/papers.py` (inc 91) to keep that module under the 600-line cap (rule #1) — file
streaming is a cohesive concern distinct from the JSON CRUD in papers.py (route-extraction precedent:
`routers/duplicates.py`, inc 64). Behavior-preserving move; the served path is resolved ONLY from the
trusted attachment row keyed by the integer paper_id — never from client-supplied input (rule #4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.persistence.document_roles import ARTICLE_FULLTEXT, normalized_document_role
from app.backend.persistence.repository import get_attachments_for_paper

router = APIRouter()


@router.get("/papers/{paper_id}/pdf", response_model=None)
def paper_pdf(
    paper_id: int,
    attachment_id: int | None = Query(default=None),  # #5: open a specific (non-primary) attachment, e.g. post-merge
    conn: Connection = Depends(get_connection),
) -> FileResponse:
    # Path is resolved ONLY from an attachment row keyed by the integer
    # paper_id — never from anything else the client supplies. A single DB lookup.
    attachment_rows = get_attachments_for_paper(conn, paper_id)
    if attachment_id is not None:
        # Scoping the match to this paper's own rows makes it ownership-safe by construction: an attachment_id
        # belonging to a different paper (or a stale/nonexistent one) simply isn't found — no cross-paper leak.
        chosen = next((row for row in attachment_rows if row["id"] == attachment_id), None)
        if chosen is None:
            raise HTTPException(status_code=404, detail="Attachment not found for this paper")
        if not _is_pdf_attachment(chosen):
            raise HTTPException(status_code=404, detail="This attachment is not a PDF")
        path = _local_attachment_path(chosen)
        if path is None:
            raise HTTPException(status_code=404, detail="PDF not available locally for this attachment")
    else:
        chosen = _select_primary_pdf_attachment(attachment_rows)
        path = _local_attachment_path(chosen)
        if path is None:
            raise HTTPException(status_code=404, detail="PDF not available locally for this paper")
    return FileResponse(
        path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=path.name,
        headers={"X-Callosum-Attachment-Id": str(chosen["id"])},
    )


def _select_primary_pdf_attachment(rows: list[Any]) -> Any | None:
    """Pick the paper's primary PDF attachment from its attachment rows.

    Only article-fulltext PDFs are eligible. Legacy ``primary`` and null-role attachments normalize into that
    scope; preregistrations, protocols, supplements, and OCR-preserved ``secondary`` originals never become the
    ordinary paper viewer/reprocessing target by fallback.
    """
    if not rows:
        return None
    candidates = [row for row in rows if _is_pdf_attachment(row) and normalized_document_role(row) == ARTICLE_FULLTEXT]
    primary = [row for row in candidates if (row["role"] or "").strip().lower() == "primary"]
    ordered = primary or candidates
    return ordered[0] if ordered else None


def _is_pdf_attachment(row: Any) -> bool:
    content_type = (row["content_type"] or "").strip().lower()
    attachment_type = (row["attachment_type"] or "").strip().lower()
    return content_type == "application/pdf" or attachment_type == "pdf"


def _local_attachment_path(row: Any) -> Path | None:
    """Resolve a streamable local file path from a trusted attachment row.

    The path comes only from the database row (resolved_path, then
    original_path); no client-supplied path is ever followed. Returns None when
    the attachment is URL-only, marked not-present, or missing on disk so the
    endpoint can answer with an honest 404 instead of a 500.
    """
    if row is None:
        return None
    if row["storage_mode"] == "url":
        return None
    if row["availability"] != "available":
        return None
    raw_path = row["resolved_path"] or row["original_path"]
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_file():
        return None
    return path
