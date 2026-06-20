"""Database-backed quote-location helpers."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection, select

from app.backend.pdf_processing.quote_matching import QuoteMatch, locate_quote
from app.backend.persistence.schema import attachments


def locate_quote_for_attachment(conn: Connection, attachment_id: int, quote: str) -> QuoteMatch:
    """Locate a quote using a stored attachment record."""
    row = conn.execute(select(attachments).where(attachments.c.id == attachment_id)).mappings().one()
    path = row["resolved_path"] or row["original_path"]
    if not path:
        return QuoteMatch(found=False, quote=quote)
    return locate_quote(Path(path), quote)
