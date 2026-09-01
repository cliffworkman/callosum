"""Database-backed quote-location helpers."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection, select

from app.backend.pdf_processing.quote_matching import QuoteMatch, locate_quote
from app.backend.persistence.schema import attachments


def locate_quote_for_attachment(conn: Connection, attachment_id: int, quote: str) -> QuoteMatch:
    """Locate a quote using an available path from a stored attachment record.

    Exact PDF rectangles are an enrichment of the already-persisted chunk provenance. A linked
    file may be moved or a managed file may be temporarily unavailable after its text was
    extracted; that must degrade to the caller's honest page/region fallback rather than abort
    synthesis verification. Prefer the resolved path, but retain the original-path fallback used
    by the paper-file API when a stale resolved path no longer exists.
    """
    row = conn.execute(select(attachments).where(attachments.c.id == attachment_id)).mappings().one()
    seen: set[Path] = set()
    for raw_path in (row["resolved_path"], row["original_path"]):
        if not raw_path:
            continue
        path = Path(raw_path)
        if path in seen:
            continue
        seen.add(path)
        try:
            if path.is_file():
                return locate_quote(path, quote)
        except OSError:
            # The file can disappear between is_file() and open(), or be temporarily inaccessible.
            # The caller still has immutable extracted chunk/page provenance for a region fallback.
            continue
    return QuoteMatch(found=False, quote=quote)
