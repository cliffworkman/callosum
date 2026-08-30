"""Import Zotero records into Callosum's canonical persistence model."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import Connection, and_, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.backend.importers.zotero_annotation_position import translate_zotero_position
from app.backend.pdf_processing.extraction import (
    COORDINATE_SYSTEM,
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
    created_paper_ids: tuple[int, ...] = ()
    # A matched (pre-existing) paper can still gain brand-new chunks this run (e.g. a previously broken local
    # PDF link now resolves) -- that paper needs embed_chunks even though it isn't in created_paper_ids, which
    # only ever gates embed_papers + the retraction check (a matched paper's own metadata didn't change).
    chunk_ids_by_paper: dict[int, tuple[int, ...]] = field(default_factory=dict)


def import_zotero_library(
    conn: Connection,
    zotero_data_dir: str | Path,
    *,
    on_attachment_error: Callable[[ZoteroAttachmentRecord, Exception], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> ZoteroImportResult:
    snapshot = read_zotero_library_copy(zotero_data_dir)
    collection_id_map = _upsert_collections(conn, snapshot.collections)

    papers_created = 0
    papers_matched = 0
    attachments_created = 0
    chunks_created = 0
    created_paper_ids: list[int] = []
    chunk_ids_by_paper: dict[int, list[int]] = {}
    total_items = len(snapshot.items)

    for index, item in enumerate(snapshot.items, start=1):
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
            created_paper_ids.append(paper_id)
        else:
            paper_id = int(existing[1]["id"])
            papers_matched += 1
            _backfill_zotero_identity(conn, paper_id, item)

        _upsert_collection_memberships(conn, paper_id, item.collection_ids, collection_id_map)
        _upsert_tags(conn, paper_id, item.tags)
        _upsert_notes(conn, paper_id, item)
        paper_fully_chunked = False
        attachment_ids_by_zotero_item: dict[int, int] = {}
        for attachment in item.attachments:
            attachment_id, created = _upsert_attachment(conn, paper_id, attachment)
            attachment_ids_by_zotero_item[attachment.item_id] = attachment_id
            attachments_created += int(created)
            if _can_extract_pdf(attachment):
                try:
                    created_ids = _extract_attachment_chunks(conn, paper_id, attachment_id, attachment)
                except Exception as exc:
                    if on_attachment_error is not None:
                        on_attachment_error(attachment, exc)
                    created_ids = []
                if created_ids:
                    chunk_ids_by_paper.setdefault(paper_id, []).extend(created_ids)
                chunks_created += len(created_ids)
                if created_ids or _attachment_has_chunks(conn, attachment_id):
                    paper_fully_chunked = True

        _upsert_annotations(
            conn,
            paper_id,
            item,
            attachment_ids_by_zotero_item=attachment_ids_by_zotero_item,
        )

        if paper_fully_chunked:
            conn.execute(update(papers).where(papers.c.id == paper_id).values(processing_tier="fully-chunked"))

        if on_progress is not None:
            on_progress(index, total_items)

    return ZoteroImportResult(
        papers_created=papers_created,
        papers_matched=papers_matched,
        attachments_created=attachments_created,
        chunks_created=chunks_created,
        created_paper_ids=tuple(created_paper_ids),
        chunk_ids_by_paper={pid: tuple(ids) for pid, ids in chunk_ids_by_paper.items()},
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


# A Zotero word-processor citation URI, e.g. "http://zotero.org/users/123/items/ABCD1234" or
# ".../groups/456/items/ABCD1234" -- the same (library_id, item_key) identity pair `papers.zotero_library_id` /
# `papers.zotero_item_key` already store for the *library* importer above (inc 464, backlog #33/#34 P2 #22).
ZOTERO_ITEM_URI_RE = re.compile(r"zotero\.org/(?:users|groups)/([^/]+)/items/([A-Za-z0-9]+)")


def normalize_zotero_csl_item(item_data: dict[str, Any], uris: Iterable[str] = ()) -> dict[str, Any]:
    """Canonicalize a citation's embedded Zotero ``itemData`` (already CSL-JSON — no ``ZOTERO_TYPE_TO_CSL``
    translation needed, unlike :func:`normalize_zotero_item`'s raw Zotero-field input) into the same
    ``create_paper``-shaped dict. Used only when a document's Zotero-authored citation doesn't match an existing
    library paper (`find_existing_paper_by_identity`) and gets auto-added from its own embedded metadata — same
    ``imported_source``/``processing_tier`` trust posture as the library importer above, not a new judgment.

    Defensive: any missing/malformed field is just absent from the result (never raises) — the embedded JSON
    came from a Writer document's ReferenceMark name, untrusted content per rule #4.
    """
    title = str(item_data.get("title") or "Untitled Zotero Citation")
    year = _year_from_csl_issued(item_data.get("issued"))
    authors = item_data.get("author")
    first_author_family_name = None
    if isinstance(authors, list) and authors and isinstance(authors[0], dict):
        family = authors[0].get("family")
        first_author_family_name = str(family) if family else None

    zotero_library_id: str | None = None
    zotero_item_key: str | None = None
    for uri in uris:
        match = ZOTERO_ITEM_URI_RE.search(str(uri))
        if match:
            zotero_library_id, zotero_item_key = match.group(1), match.group(2)
            break

    doi = item_data.get("DOI")
    item_type = item_data.get("type")
    return {
        "title": title,
        "abstract": item_data.get("abstract") if isinstance(item_data.get("abstract"), str) else None,
        "year": year,
        "doi": str(doi) if doi else None,
        "venue": item_data.get("container-title") if isinstance(item_data.get("container-title"), str) else None,
        "item_type": str(item_type) if item_type else None,
        "language": item_data.get("language") if isinstance(item_data.get("language"), str) else None,
        "publication_date": None,  # CSL `issued` carries no verbatim date string worth preserving separately
        "first_author_family_name": first_author_family_name,
        "imported_source": ZOTERO_IMPORT_SOURCE,
        "zotero_library_id": zotero_library_id,
        "zotero_item_key": zotero_item_key,
        "citation_key": None,
        "csl_json": dict(item_data),
        "processing_tier": "metadata-only",
    }


def _year_from_csl_issued(issued: Any) -> int | None:
    """``issued`` is CSL's ``{"date-parts": [[2020, 5, 1]]}`` shape (or absent). Defensive: any other shape
    (string EDTF dates, missing keys) yields ``None`` rather than guessing."""
    if not isinstance(issued, dict):
        return None
    date_parts = issued.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts or not isinstance(date_parts[0], list) or not date_parts[0]:
        return None
    year = date_parts[0][0]
    try:
        return int(year)
    except (TypeError, ValueError):
        return None


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
) -> list[int]:
    if _attachment_has_chunks(conn, attachment_id):
        return []
    assert attachment.resolved_path is not None
    checksum = file_sha256(attachment.resolved_path)
    extraction = extract_pdf(attachment.resolved_path)
    drafts = make_chunk_drafts(
        extraction,
        source_attachment_checksum=checksum,
        chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
    )
    created_ids: list[int] = []
    for draft in drafts:
        chunk_id = create_chunk(
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
        created_ids.append(chunk_id)
    return created_ids


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
    # First pass establishes every local id. The second can then preserve parent links regardless of source order
    # (and repairs hierarchy for libraries imported before backlog #57 Phase 6C, when parentCollectionID was read
    # by the adapter but accidentally discarded here).
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
    for collection in zotero_collections:
        collection_id = mapping[collection.collection_id]
        parent_id = None
        if collection.parent_collection_id is not None:
            parent_id = mapping.get(collection.parent_collection_id)
            if parent_id is None:
                raise ValueError(
                    f"Zotero collection {collection.collection_id} references missing parent "
                    f"{collection.parent_collection_id}"
                )
        conn.execute(
            update(collections)
            .where(collections.c.id == collection_id)
            .values(name=collection.name, parent_id=parent_id)
        )
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


def _upsert_annotations(
    conn: Connection,
    paper_id: int,
    item: ZoteroItemRecord,
    *,
    attachment_ids_by_zotero_item: dict[int, int] | None = None,
) -> None:
    callosum_attachment_ids = attachment_ids_by_zotero_item or {}
    zotero_attachments = {attachment.item_id: attachment for attachment in item.attachments}
    for annotation in item.annotations:
        external_id = f"{annotation.library_id}:{annotation.key}"
        existing = (
            conn.execute(
                select(annotations).where(
                    and_(
                        annotations.c.import_source == ZOTERO_IMPORT_SOURCE,
                        annotations.c.external_id == external_id,
                    )
                )
            )
            .mappings()
            .first()
        )
        zotero_attachment = zotero_attachments.get(annotation.parent_item_id)
        attachment_id = callosum_attachment_ids.get(annotation.parent_item_id)
        translated = translate_zotero_position(
            annotation.position_json,
            annotation_type=annotation.annotation_type,
            pdf_path=zotero_attachment.resolved_path if zotero_attachment is not None else None,
        )
        location_values = {
            "attachment_id": attachment_id,
            "page": translated.page,
            "bboxes_json": translated.bboxes_json,
            "coordinate_system": translated.coordinate_system,
        }
        if existing is not None:
            # Re-import upgrades legacy raw-only rows once their PDF is available.
            # Once geometry is exact, its attachment identity is part of that proof: a Zotero relink may point
            # the same annotation key at different PDF bytes whose page bounds happen to accept the old rect.
            # Keep that proven location pinned. Raw-only legacy rows can still gain their first exact location.
            has_exact_location = (
                existing["attachment_id"] is not None
                and existing["bboxes_json"] is not None
                and existing["coordinate_system"] == COORDINATE_SYSTEM
            )
            updates = (
                {}
                if has_exact_location
                else {key: value for key, value in location_values.items() if value is not None}
            )
            if existing["anchor_text"] is None and annotation.text:
                updates["anchor_text"] = annotation.text
            if existing["note"] is None and annotation.comment:
                updates["note"] = annotation.comment
            if existing["color"] is None and annotation.color:
                updates["color"] = annotation.color
            if updates:
                conn.execute(update(annotations).where(annotations.c.id == existing["id"]).values(**updates))
            continue
        conn.execute(
            insert(annotations).values(
                paper_id=paper_id,
                annotation_type=annotation.annotation_type,
                body=annotation.comment or annotation.text,
                position_json=annotation.position_json,
                import_source=ZOTERO_IMPORT_SOURCE,
                external_id=external_id,
                color=annotation.color,
                anchor_text=annotation.text,
                note=annotation.comment,
                **location_values,
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
