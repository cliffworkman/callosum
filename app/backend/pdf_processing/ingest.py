"""One-PDF ingest: create a paper + attachment + chunks for a local PDF, or attach a PDF to an existing paper.

`attach_pdf_to_paper` is the reusable core (create the attachment, extract + chunk, refresh the tier) shared by
the original `ingest_pdf_scaffold` (which also creates the paper) and by OA acquisition (which attaches a
fetched PDF to an already-existing paper).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import Connection, and_, func, select

from app.backend.document_text import (
    DEFAULT_TEXT_CHUNKING_STRATEGY,
    attachment_type_for_document,
    content_type_for_document,
    extract_text_document,
    make_text_chunk_drafts,
)
from app.backend.methods.registration_references import extract_registration_references
from app.backend.pdf_processing.extraction import (
    DEFAULT_CHUNKING_STRATEGY,
    extract_pdf,
    file_sha256,
    make_chunk_drafts,
)
from app.backend.persistence.registration_references_repo import replace_extracted_registration_references
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    delete_chunks_for_attachment,
    refresh_processing_tier,
)
from app.backend.persistence.schema import attachments, chunks
from app.backend.persistence.source_components_repo import (
    record_source_failure,
    replace_attachment_source,
)

if TYPE_CHECKING:
    from app.backend.embeddings.models import EmbeddingModel
    from app.backend.embeddings.vector_store import VectorStore


class PdfReprocessEmptyExtraction(RuntimeError):
    """Raised when reprocessing would replace existing chunks with an empty extraction."""


_REGISTRATION_REFERENCE_SOURCE_ROLES = {
    "article-fulltext",
    "primary",
    "supplement",
    "supplementary",
    "supplementary-text",
}


def _registration_references_for_role(role: str, drafts: list, *, hyperlinks=()) -> list:
    if role.casefold() not in _REGISTRATION_REFERENCE_SOURCE_ROLES:
        return []
    return extract_registration_references(drafts, hyperlinks=hyperlinks)


_log = logging.getLogger(__name__)


def _persist_source_components(conn: Connection, attachment_id: int, extraction: Any, checksum: str) -> None:
    """Record the deterministic source structure this extraction observed (inc 578, H1b).

    **Isolated in a SAVEPOINT on purpose.** These rows are observational substrate that nothing on
    the retrieval path reads, while the chunk writes in the same transaction are authoritative
    product state. A failure here must therefore never roll back the chunks -- ``begin_nested``
    rolls back only to the savepoint and leaves the outer transaction usable. The failure is logged
    at WARNING with the attachment id rather than swallowed silently (inc 577 lost every geometry
    rule to a broad ``except``), and ``tools/backfill_source_components.py`` repairs it later:
    the representation is replace-per-attachment, so a re-run is idempotent.
    """
    source_pages = getattr(extraction, "source_pages", ()) or ()
    if not source_pages:
        return
    try:
        with conn.begin_nested():
            receipt = replace_attachment_source(
                conn,
                attachment_id=attachment_id,
                pages=list(source_pages),
                coordinate_system=extraction.coordinate_system,
                extraction_tool=extraction.extraction_tool,
                extraction_version=extraction.extraction_version,
                source_checksum=checksum,
            )
    except Exception as error:  # noqa: BLE001 - never let observational substrate break a real ingest
        _log.warning(
            "source-component persistence failed for attachment %s; chunks are unaffected and "
            "tools/backfill_source_components.py can repair it",
            attachment_id,
            exc_info=True,
        )
        # A second savepoint, so even the bookkeeping cannot break the authoritative chunk write.
        # `record_source_failure` declines when the rollback restored a still-valid representation:
        # the outcome of this attempt and the state of the persisted graph are different facts, and
        # only the second decides currentness.
        try:
            with conn.begin_nested():
                recorded = record_source_failure(
                    conn,
                    attachment_id=attachment_id,
                    source_checksum=checksum,
                    extraction_tool=extraction.extraction_tool,
                    extraction_version=extraction.extraction_version,
                    reason=f"persistence_error:{type(error).__name__}",
                )
            if not recorded:
                _log.warning(
                    "attachment %s kept its previously complete source representation; only the rebuild attempt failed",
                    attachment_id,
                )
        except Exception:  # noqa: BLE001 - bookkeeping must never escalate into a chunk failure
            _log.warning(
                "could not record the source-representation failure for attachment %s",
                attachment_id,
                exc_info=True,
            )
        return
    if not receipt.is_complete:
        # Honest, non-silent, and non-current: an ordinary backfill rerun will repair it.
        _log.warning(
            "source representation for attachment %s is %s (%s): %d/%d pages, %d components",
            attachment_id,
            receipt.state,
            receipt.state_reason,
            receipt.written_pages,
            receipt.expected_pages,
            receipt.written_components,
        )


def attach_pdf_to_paper(
    conn: Connection,
    paper_id: int,
    pdf_path: str | Path,
    *,
    storage_mode: str = "managed",
    availability: str = "available",
    original_path: str | None = None,
    import_source: str = "pdf-scaffold",
    role: str = "primary",
    chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
) -> dict[str, Any]:
    """Attach a local PDF to an EXISTING paper: create the attachment, extract + chunk, refresh the tier.

    Does NOT create a paper. Returns ``{attachment_id, chunk_ids, checksum, chunk_version}``.
    """
    path = Path(pdf_path)
    checksum = file_sha256(path)
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode=storage_mode,
        availability=availability,
        original_path=original_path if original_path is not None else str(path),
        resolved_path=str(path.resolve()),
        checksum=checksum,
        file_size=path.stat().st_size,
        content_type="application/pdf",
        import_source=import_source,
        attachment_type="pdf",
        role=role,
    )
    extraction = extract_pdf(path)
    drafts = make_chunk_drafts(extraction, source_attachment_checksum=checksum, chunking_strategy=chunking_strategy)
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
    replace_extracted_registration_references(
        conn,
        paper_id,
        attachment_id,
        _registration_references_for_role(role, drafts, hyperlinks=extraction.links),
    )
    _persist_source_components(conn, attachment_id, extraction, checksum)
    refresh_processing_tier(conn, paper_id)
    return {
        "attachment_id": attachment_id,
        "chunk_ids": chunk_ids,
        "checksum": checksum,
        "chunk_version": drafts[0].chunk_version if drafts else None,
    }


def reprocess_pdf_attachment(
    conn: Connection,
    paper_id: int,
    attachment_id: int,
    pdf_path: str | Path,
    *,
    vector_store: "VectorStore",
    embedding_model: "EmbeddingModel",
    chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
) -> dict[str, Any]:
    """Replace extracted chunks for an existing PDF attachment without changing paper metadata or files."""
    path = Path(pdf_path)
    checksum = file_sha256(path)
    extraction = extract_pdf(path)
    drafts = make_chunk_drafts(extraction, source_attachment_checksum=checksum, chunking_strategy=chunking_strategy)
    existing_count = int(
        conn.execute(
            select(func.count())
            .select_from(chunks)
            .where(and_(chunks.c.paper_id == paper_id, chunks.c.attachment_id == attachment_id))
        ).scalar_one()
    )
    if existing_count > 0 and not drafts:
        raise PdfReprocessEmptyExtraction("PDF extraction produced no chunks; existing chunks were preserved.")
    removed_chunk_ids = delete_chunks_for_attachment(conn, paper_id, attachment_id, vector_store=vector_store)
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
    attachment_role = conn.execute(
        select(attachments.c.role).where(attachments.c.id == attachment_id, attachments.c.paper_id == paper_id)
    ).scalar_one_or_none()
    replace_extracted_registration_references(
        conn,
        paper_id,
        attachment_id,
        _registration_references_for_role(attachment_role or "primary", drafts, hyperlinks=extraction.links),
    )
    _persist_source_components(conn, attachment_id, extraction, checksum)
    # Re-embed the fresh chunks: delete_chunks_for_attachment removed the OLD chunks' vector embeddings, so
    # without this the reprocessed paper would silently drop out of vector-search retrieval (find-related,
    # gap-finder, axis scoring, library-wide citation suggest). embed_chunks is idempotent per chunk_version.
    if chunk_ids:
        from app.backend.embeddings.pipeline import embed_chunks

        embed_chunks(conn, model=embedding_model, vector_store=vector_store, chunk_ids=chunk_ids)
    refresh_processing_tier(conn, paper_id)
    return {
        "attachment_id": attachment_id,
        "chunk_ids": chunk_ids,
        "chunks_removed": len(removed_chunk_ids),
        "chunks_created": len(chunk_ids),
        "checksum": checksum,
        "chunk_version": drafts[0].chunk_version if drafts else None,
    }


def attach_text_document_to_paper(
    conn: Connection,
    paper_id: int,
    document_path: str | Path,
    *,
    content_type: str | None = None,
    storage_mode: str = "managed",
    availability: str = "available",
    original_path: str | None = None,
    import_source: str = "document-text",
    role: str = "supplementary-text",
    chunking_strategy: str = DEFAULT_TEXT_CHUNKING_STRATEGY,
) -> dict[str, Any]:
    """Attach a non-PDF text document and feed its extracted text into the normal chunk table.

    This is intentionally separate from PDF ingest: PDF remains the only path with page-coordinate rectangles.
    JATS/XML, DOCX, and HTML chunks carry text-offset provenance so transparency and future registration checks can
    read them, while quote opening degrades to page/region uncertainty instead of pretending exact PDF coordinates.
    """
    path = Path(document_path)
    checksum = file_sha256(path)
    resolved_content_type = content_type_for_document(path, content_type)
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode=storage_mode,
        availability=availability,
        original_path=original_path if original_path is not None else str(path),
        resolved_path=str(path.resolve()),
        checksum=checksum,
        file_size=path.stat().st_size,
        content_type=resolved_content_type,
        import_source=import_source,
        attachment_type=attachment_type_for_document(path, resolved_content_type),
        role=role,
    )
    extraction = extract_text_document(path, resolved_content_type)
    drafts = make_text_chunk_drafts(
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
    replace_extracted_registration_references(
        conn,
        paper_id,
        attachment_id,
        _registration_references_for_role(role, drafts),
    )
    refresh_processing_tier(conn, paper_id)
    return {
        "attachment_id": attachment_id,
        "chunk_ids": chunk_ids,
        "checksum": checksum,
        "chunk_version": drafts[0].chunk_version if drafts else None,
        "extraction_tool": extraction.provider_id,
        "content_type": resolved_content_type,
    }


def ingest_pdf_scaffold(
    conn: Connection,
    pdf_path: str | Path,
    *,
    title: str | None = None,
    chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
) -> dict[str, Any]:
    """Create a paper, linked attachment, and chunks for one local PDF (vertical-slice scaffold)."""
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
    result = attach_pdf_to_paper(
        conn,
        paper_id,
        path,
        storage_mode="linked",
        original_path=str(path),
        import_source="pdf-scaffold",
        role="primary",
        chunking_strategy=chunking_strategy,
    )
    return {"paper_id": paper_id, **result}
