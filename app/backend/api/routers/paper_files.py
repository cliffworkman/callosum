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

from app.backend.acquisition.fetch import library_dir
from app.backend.api.dependencies import get_connection
from app.backend.api.routers.health import reported_app_version
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
            _raise_pdf_error(None, "Attachment not found for this paper", "PDF_ATTACHMENT_NOT_FOUND")
        if not _is_pdf_attachment(chosen):
            _raise_pdf_error(chosen, "This attachment is not a PDF", "PDF_ATTACHMENT_NOT_PDF")
        path = _local_attachment_path(chosen)
        if path is None:
            _raise_pdf_error(chosen, "PDF not available locally for this attachment")
    else:
        chosen = _select_primary_pdf_attachment(attachment_rows)
        path = _local_attachment_path(chosen)
        if path is None:
            _raise_pdf_error(chosen, "PDF not available locally for this paper")
    try:
        # Cloud-backed placeholders and disconnected volumes can look like files to ``is_file`` yet fail on the
        # first read. Catch that here so the UI gets a stable, actionable 404 instead of FileResponse's opaque 500.
        with path.open("rb") as stream:
            stream.read(1)
    except OSError:
        _raise_pdf_error(chosen, "PDF file exists but could not be read", "PDF_ATTACHMENT_UNREADABLE")
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


def _raise_pdf_error(row: Any | None, detail: str, code: str | None = None) -> None:
    """Raise a privacy-safe PDF failure with stable diagnostic headers.

    Paths stay server-side: the browser gets only attachment state needed to distinguish an absent library folder,
    a moved file, a URL-only record, and a generic missing attachment.
    """
    error_code = code or _attachment_failure_code(row)
    headers = {"X-Callosum-Error-Code": error_code}
    app_version = reported_app_version()
    if app_version:
        headers["X-Callosum-App-Version"] = app_version
    if row is not None:
        headers.update(
            {
                "X-Callosum-Attachment-Id": str(row["id"]),
                "X-Callosum-Storage-Mode": str(row["storage_mode"]),
                "X-Callosum-Attachment-Availability": str(row["availability"]),
            }
        )
    raise HTTPException(status_code=404, detail=detail, headers=headers)


def _attachment_failure_code(row: Any | None) -> str:
    if row is None:
        return "PDF_ATTACHMENT_NOT_FOUND"
    if row["storage_mode"] == "url":
        return "PDF_REMOTE_ONLY"
    if row["availability"] == "missing":
        return "PDF_ATTACHMENT_MARKED_MISSING"
    if row["availability"] != "available":
        return "PDF_ATTACHMENT_NOT_AVAILABLE"
    raw_path = row["resolved_path"] or row["original_path"]
    if not raw_path:
        return "PDF_ATTACHMENT_PATH_MISSING"
    if row["storage_mode"] == "managed" and not library_dir().is_dir():
        return "PDF_LIBRARY_FOLDER_MISSING"
    return "PDF_ATTACHMENT_FILE_MISSING"
