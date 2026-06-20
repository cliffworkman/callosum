"""Temporary one-PDF ingest scaffolding for the PDF coordinate slice."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Connection

from app.backend.pdf_processing.extraction import (
    DEFAULT_CHUNKING_STRATEGY,
    extract_pdf,
    file_sha256,
    make_chunk_drafts,
)
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper, refresh_processing_tier


def ingest_pdf_scaffold(
    conn: Connection,
    pdf_path: str | Path,
    *,
    title: str | None = None,
    chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
) -> dict[str, Any]:
    """Create a paper, linked attachment, and chunks for one local PDF.

    This is throwaway scaffolding for the vertical slice. The real Zotero
    importer will replace paper/attachment creation in a later increment.
    """
    path = Path(pdf_path)
    checksum = file_sha256(path)
    paper_title = title or path.stem

    paper_id = create_paper(
        conn,
        title=paper_title,
        csl_json={"id": f"local-{checksum[:12]}", "type": "document", "title": paper_title},
        imported_source="pdf-scaffold",
        processing_tier="metadata-only",
    )
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        original_path=str(path),
        resolved_path=str(path.resolve()),
        checksum=checksum,
        file_size=path.stat().st_size,
        content_type="application/pdf",
        import_source="pdf-scaffold",
        attachment_type="pdf",
        role="primary",
    )

    extraction = extract_pdf(path)
    drafts = make_chunk_drafts(
        extraction,
        source_attachment_checksum=checksum,
        chunking_strategy=chunking_strategy,
    )
    chunk_ids = [
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=draft.text,
            page_start=draft.page_start,
            page_end=draft.page_end,
            bbox_coordinate_system=draft.bbox_coordinate_system,
            extraction_tool=draft.extraction_tool,
            extraction_version=draft.extraction_version,
            chunking_strategy=draft.chunking_strategy,
            chunk_version=draft.chunk_version,
            source_attachment_checksum=draft.source_attachment_checksum,
            section=draft.section,
            char_start=draft.char_start,
            char_end=draft.char_end,
            bbox_json=draft.bbox_json,
        )
        for draft in drafts
    ]
    refresh_processing_tier(conn, paper_id)

    return {
        "paper_id": paper_id,
        "attachment_id": attachment_id,
        "chunk_ids": chunk_ids,
        "checksum": checksum,
        "chunk_version": drafts[0].chunk_version if drafts else None,
    }
