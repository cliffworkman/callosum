"""Import Zotero records into Callosum's canonical persistence model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import Connection, and_, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.backend.pdf_processing.extraction import (
    DEFAULT_CHUNKING_STRATEGY,
    extract_pdf,
    file_sha256,
    make_chunk_drafts,
)
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    find_existing_paper_by_identity,
)
from app.backend.persistence.schema import (
    annotations,
    attachments,
    chunks,
    collection_papers,
    collections,
    notes,
    paper_tags,
    papers,
    tags,
)
from integrations.zotero.adapter import (
    LINK_MODE_LINKED_URL,
    ZoteroAttachmentRecord,
    ZoteroItemRecord,
    read_zotero_library_copy,
)

ZOTERO_IMPORT_SOURCE = "zotero"
# Distinct from ZOTERO_IMPORT_SOURCE above: that bare value marks Zotero-origin papers/attachments/collections/
# notes/annotations (five other tables' provenance columns, out of scope here). Tag provenance follows the
# formal `{namespace}:{origin}` contract (backlog #9, `tags_repo.TAG_SOURCE_NAMESPACES`) — only this one column
# gets the namespaced value.
ZOTERO_TAG_SOURCE = "import:zotero"
ZOTERO_TYPE_TO_CSL = {
    "journalArticle": "article-journal",
    "conferencePaper": "paper-conference",
    "book": "book",
    "bookSection": "chapter",
    "thesis": "thesis",
    "report": "report",
    "webpage": "webpage",
}


@dataclass(frozen=True)
class ZoteroImportResult:
    papers_created: int
    papers_matched: int
    attachments_created: int
    chunks_created: int


def import_zotero_library(
    conn: Connection,
    zotero_data_dir: str | Path,
    *,
    on_attachment_error: Callable[[ZoteroAttachmentRecord, Exception], None] | None = None,
) -> ZoteroImportResult:
    snapshot = read_zotero_library_copy(zotero_data_dir)
    collection_id_map = _upsert_collections(conn, snapshot.collections)

    papers_created = 0
    papers_matched = 0
    attachments_created = 0
    chunks_created = 0

    for item in snapshot.items:
        canonical = normalize_zotero_item(item)
        existing = find_existing_paper_by_identity(
            conn,
            doi=canonical["doi"],
            zotero_library_id=item.library_id,
            zotero_item_key=item.key,
            title=canonical["title"],
            year=canonical["year"],
            first_author_family_name=canonical["first_author_family_name"],
        )

        if existing is None:
            paper_id = create_paper(conn, **canonical)
            papers_created += 1
        else:
            paper_id = int(existing[1]["id"])
            papers_matched += 1
            _backfill_zotero_identity(conn, paper_id, item)

        _upsert_collection_memberships(conn, paper_id, item.collection_ids, collection_id_map)
        _upsert_tags(conn, paper_id, item.tags)
        _upsert_notes(conn, paper_id, item)
        _upsert_annotations(conn, paper_id, item)

        paper_fully_chunked = False
        for attachment in item.attachments:
            attachment_id, created = _upsert_attachment(conn, paper_id, attachment)
            attachments_created += int(created)
            if _can_extract_pdf(attachment):
                try:
                    created_chunks = _extract_attachment_chunks(conn, paper_id, attachment_id, attachment)
                except Exception as exc:
                    if on_attachment_error is not None:
                        on_attachment_error(attachment, exc)
                    created_chunks = 0
                chunks_created += created_chunks
                if created_chunks > 0 or _attachment_has_chunks(conn, attachment_id):
                    paper_fully_chunked = True

        if paper_fully_chunked:
            conn.execute(update(papers).where(papers.c.id == paper_id).values(processing_tier="fully-chunked"))

    return ZoteroImportResult(
        papers_created=papers_created,
        papers_matched=papers_matched,
        attachments_created=attachments_created,
        chunks_created=chunks_created,
    )


def normalize_zotero_item(item: ZoteroItemRecord) -> dict[str, Any]:
    fields = item.fields
    title = fields.get("title") or f"Untitled Zotero Item {item.key}"
    creators = [
        {"family": creator.last_name, "given": creator.first_name}
        for creator in item.creators
        if creator.last_name or creator.first_name
    ]
    year = _year_from_fields(fields)
    csl_json: dict[str, Any] = {
        "id": item.key,
        "type": ZOTERO_TYPE_TO_CSL.get(item.item_type, "document"),
        "title": title,
        "zotero": {
            "itemID": item.item_id,
            "key": item.key,
            "libraryID": item.library_id,
            "itemType": item.item_type,
        },
    }
    if creators:
        csl_json["author"] = creators
    if fields.get("DOI"):
        csl_json["DOI"] = fields["DOI"]
    if fields.get("abstractNote"):
        csl_json["abstract"] = fields["abstractNote"]
    if fields.get("publicationTitle"):
        csl_json["container-title"] = fields["publicationTitle"]
    if year is not None:
        csl_json["issued"] = {"date-parts": [[year]]}

    return {
        "title": title,
        "abstract": fields.get("abstractNote"),
        "year": year,
        "doi": fields.get("DOI"),
        "venue": fields.get("publicationTitle") or fields.get("conferenceName"),
        "item_type": item.item_type,
        "language": fields.get("language"),
        "publication_date": fields.get("date"),
        "first_author_family_name": item.creators[0].last_name if item.creators else None,
        "imported_source": ZOTERO_IMPORT_SOURCE,
        "zotero_library_id": item.library_id,
        "zotero_item_key": item.key,
        "citation_key": fields.get("citationKey"),
        "csl_json": csl_json,
        "processing_tier": "metadata-only",
    }


def _upsert_attachment(
    conn: Connection,
    paper_id: int,
    attachment: ZoteroAttachmentRecord,
) -> tuple[int, bool]:
    existing = (
        conn.execute(
            select(attachments).where(
                and_(
                    attachments.c.paper_id == paper_id,
                    attachments.c.import_source == ZOTERO_IMPORT_SOURCE,
                    attachments.c.original_path == attachment.path,
                    attachments.c.role == attachment.role,
                )
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return int(existing["id"]), False

    path = attachment.resolved_path
    checksum = file_sha256(path) if path and path.exists() and path.is_file() else None
    file_size = path.stat().st_size if path and path.exists() and path.is_file() else None
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode=attachment.storage_mode,
        availability=attachment.availability,
        original_path=attachment.path,
        resolved_path=str(path) if path else None,
        checksum=checksum,
        file_size=file_size,
        content_type=attachment.content_type or "application/octet-stream",
        import_source=ZOTERO_IMPORT_SOURCE,
        attachment_type="url" if attachment.link_mode == LINK_MODE_LINKED_URL else "pdf",
        role=attachment.role,
    )
    return attachment_id, True


def _extract_attachment_chunks(
    conn: Connection,
    paper_id: int,
    attachment_id: int,
    attachment: ZoteroAttachmentRecord,
) -> int:
    if _attachment_has_chunks(conn, attachment_id):
        return 0
    assert attachment.resolved_path is not None
    checksum = file_sha256(attachment.resolved_path)
    extraction = extract_pdf(attachment.resolved_path)
    drafts = make_chunk_drafts(
        extraction,
        source_attachment_checksum=checksum,
        chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
    )
    for draft in drafts:
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
    return len(drafts)


def _can_extract_pdf(attachment: ZoteroAttachmentRecord) -> bool:
    return (
        attachment.content_type == "application/pdf"
        and attachment.availability == "available"
        and attachment.resolved_path is not None
        and attachment.resolved_path.exists()
        and attachment.resolved_path.is_file()
    )


def _attachment_has_chunks(conn: Connection, attachment_id: int) -> bool:
    return conn.execute(select(chunks.c.id).where(chunks.c.attachment_id == attachment_id).limit(1)).first() is not None


def _backfill_zotero_identity(conn: Connection, paper_id: int, item: ZoteroItemRecord) -> None:
    existing = conn.execute(select(papers).where(papers.c.id == paper_id)).mappings().one()
    values: dict[str, Any] = {}
    if not existing["zotero_library_id"]:
        values["zotero_library_id"] = item.library_id
    if not existing["zotero_item_key"]:
        values["zotero_item_key"] = item.key
    if values:
        conn.execute(update(papers).where(papers.c.id == paper_id).values(**values))


def _upsert_collections(conn: Connection, zotero_collections: tuple[Any, ...]) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for collection in zotero_collections:
        external_id = collection.key or str(collection.collection_id)
        existing = (
            conn.execute(
                select(collections).where(
                    and_(
                        collections.c.import_source == ZOTERO_IMPORT_SOURCE,
                        collections.c.external_id == external_id,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            mapping[collection.collection_id] = int(existing["id"])
            continue
        collection_id = conn.execute(
            insert(collections).values(
                name=collection.name,
                import_source=ZOTERO_IMPORT_SOURCE,
                external_id=external_id,
            )
        ).inserted_primary_key[0]
        mapping[collection.collection_id] = int(collection_id)
    return mapping


def _upsert_collection_memberships(
    conn: Connection,
    paper_id: int,
    zotero_collection_ids: tuple[int, ...],
    collection_id_map: dict[int, int],
) -> None:
    for zotero_collection_id in zotero_collection_ids:
        collection_id = collection_id_map.get(zotero_collection_id)
        if collection_id is None:
            continue
        _insert_ignore(conn, collection_papers, {"collection_id": collection_id, "paper_id": paper_id})


def _upsert_tags(conn: Connection, paper_id: int, tag_names: tuple[str, ...]) -> None:
    for tag_name in tag_names:
        existing = conn.execute(select(tags).where(tags.c.name == tag_name)).mappings().first()
        if existing is None:
            tag_id = conn.execute(
                insert(tags).values(name=tag_name, import_source=ZOTERO_TAG_SOURCE)
            ).inserted_primary_key[0]
        else:
            tag_id = existing["id"]
        _insert_ignore(conn, paper_tags, {"paper_id": paper_id, "tag_id": tag_id})


def _upsert_notes(conn: Connection, paper_id: int, item: ZoteroItemRecord) -> None:
    for note in item.notes:
        external_id = f"{note.library_id}:{note.key}"
        exists = conn.execute(
            select(notes.c.id).where(
                and_(notes.c.import_source == ZOTERO_IMPORT_SOURCE, notes.c.external_id == external_id)
            )
        ).first()
        if exists:
            continue
        conn.execute(
            insert(notes).values(
                paper_id=paper_id,
                body=note.note,
                import_source=ZOTERO_IMPORT_SOURCE,
                external_id=external_id,
            )
        )


def _upsert_annotations(conn: Connection, paper_id: int, item: ZoteroItemRecord) -> None:
    for annotation in item.annotations:
        external_id = f"{annotation.library_id}:{annotation.key}"
        exists = conn.execute(
            select(annotations.c.id).where(
                and_(annotations.c.import_source == ZOTERO_IMPORT_SOURCE, annotations.c.external_id == external_id)
            )
        ).first()
        if exists:
            continue
        conn.execute(
            insert(annotations).values(
                paper_id=paper_id,
                annotation_type=annotation.annotation_type,
                body=annotation.comment or annotation.text,
                position_json=annotation.position_json,
                coordinate_system="zotero-reader-json" if annotation.position_json else None,
                import_source=ZOTERO_IMPORT_SOURCE,
                external_id=external_id,
            )
        )


def _insert_ignore(conn: Connection, table: Any, values: dict[str, Any]) -> None:
    try:
        conn.execute(insert(table).values(**values))
    except IntegrityError:
        pass


def _year_from_fields(fields: dict[str, str]) -> int | None:
    value = fields.get("date")
    if not value:
        return None
    for token in value.replace("-", " ").replace("/", " ").split():
        if len(token) >= 4 and token[:4].isdigit():
            return int(token[:4])
    return None
