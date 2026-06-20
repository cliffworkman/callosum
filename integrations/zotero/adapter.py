"""Read-only Zotero SQLite adapter.

The adapter copies `zotero.sqlite` to a temporary file and reads that copy.
It does not open the user's live database.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LINK_MODE_IMPORTED_FILE = 0
LINK_MODE_IMPORTED_URL = 1
LINK_MODE_LINKED_FILE = 2
LINK_MODE_LINKED_URL = 3


@dataclass(frozen=True)
class ZoteroCreatorRecord:
    first_name: str | None
    last_name: str | None
    order_index: int


@dataclass(frozen=True)
class ZoteroAttachmentRecord:
    item_id: int
    key: str
    parent_item_id: int
    library_id: str
    link_mode: int
    content_type: str | None
    path: str | None
    resolved_path: Path | None
    availability: str
    storage_mode: str
    role: str


@dataclass(frozen=True)
class ZoteroCollectionRecord:
    collection_id: int
    key: str | None
    name: str
    parent_collection_id: int | None


@dataclass(frozen=True)
class ZoteroNoteRecord:
    item_id: int
    key: str
    parent_item_id: int
    library_id: str
    note: str


@dataclass(frozen=True)
class ZoteroAnnotationRecord:
    item_id: int
    key: str
    parent_item_id: int
    library_id: str
    annotation_type: str | None
    text: str | None
    comment: str | None
    position_json: dict[str, Any] | None


@dataclass(frozen=True)
class ZoteroItemRecord:
    item_id: int
    key: str
    library_id: str
    item_type: str
    fields: dict[str, str]
    creators: tuple[ZoteroCreatorRecord, ...] = ()
    tags: tuple[str, ...] = ()
    collection_ids: tuple[int, ...] = ()
    attachments: tuple[ZoteroAttachmentRecord, ...] = ()
    notes: tuple[ZoteroNoteRecord, ...] = ()
    annotations: tuple[ZoteroAnnotationRecord, ...] = ()


@dataclass(frozen=True)
class ZoteroLibrarySnapshot:
    data_dir: Path
    items: tuple[ZoteroItemRecord, ...]
    collections: tuple[ZoteroCollectionRecord, ...] = ()


def read_zotero_library_copy(zotero_data_dir: str | Path) -> ZoteroLibrarySnapshot:
    data_dir = Path(zotero_data_dir)
    source_db = data_dir / "zotero.sqlite"
    if not source_db.exists():
        raise FileNotFoundError(f"Zotero database not found: {source_db}")

    with tempfile.TemporaryDirectory(prefix="callosum-zotero-") as temp_dir:
        copied_db = Path(temp_dir) / "zotero.sqlite"
        shutil.copy2(source_db, copied_db)
        conn = sqlite3.connect(f"file:{copied_db.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return _read_snapshot(conn, data_dir)
        finally:
            conn.close()


def _read_snapshot(conn: sqlite3.Connection, data_dir: Path) -> ZoteroLibrarySnapshot:
    collections = _read_collections(conn)
    attachments_by_parent = _read_attachments(conn, data_dir)
    notes_by_parent = _read_notes(conn)
    annotations_by_parent = _read_annotations(conn)
    tags_by_item = _read_tags(conn)
    collection_ids_by_item = _read_collection_membership(conn)
    creators_by_item = _read_creators(conn)

    item_rows = conn.execute(
        """
        SELECT i.itemID, i.key, COALESCE(CAST(i.libraryID AS TEXT), 'local') AS libraryID, it.typeName
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
        ORDER BY i.itemID
        """
    ).fetchall()
    fields_by_item = _read_item_fields(conn)
    items: list[ZoteroItemRecord] = []

    for row in item_rows:
        item_id = int(row["itemID"])
        items.append(
            ZoteroItemRecord(
                item_id=item_id,
                key=str(row["key"]),
                library_id=str(row["libraryID"]),
                item_type=str(row["typeName"]),
                fields=fields_by_item.get(item_id, {}),
                creators=tuple(creators_by_item.get(item_id, [])),
                tags=tuple(tags_by_item.get(item_id, [])),
                collection_ids=tuple(collection_ids_by_item.get(item_id, [])),
                attachments=tuple(attachments_by_parent.get(item_id, [])),
                notes=tuple(notes_by_parent.get(item_id, [])),
                annotations=tuple(annotations_by_parent.get(item_id, [])),
            )
        )

    return ZoteroLibrarySnapshot(data_dir=data_dir, items=tuple(items), collections=tuple(collections))


def _read_item_fields(conn: sqlite3.Connection) -> dict[int, dict[str, str]]:
    rows = conn.execute(
        """
        SELECT id.itemID, f.fieldName, idv.value
        FROM itemData id
        JOIN fields f ON f.fieldID = id.fieldID
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        ORDER BY id.itemID
        """
    ).fetchall()
    fields_by_item: dict[int, dict[str, str]] = {}
    for row in rows:
        fields_by_item.setdefault(int(row["itemID"]), {})[str(row["fieldName"])] = str(row["value"])
    return fields_by_item


def _read_creators(conn: sqlite3.Connection) -> dict[int, list[ZoteroCreatorRecord]]:
    if not _table_exists(conn, "itemCreators"):
        return {}
    rows = conn.execute(
        """
        SELECT ic.itemID, c.firstName, c.lastName, COALESCE(ic.orderIndex, 0) AS orderIndex
        FROM itemCreators ic
        JOIN creators c ON c.creatorID = ic.creatorID
        ORDER BY ic.itemID, ic.orderIndex
        """
    ).fetchall()
    creators_by_item: dict[int, list[ZoteroCreatorRecord]] = {}
    for row in rows:
        creators_by_item.setdefault(int(row["itemID"]), []).append(
            ZoteroCreatorRecord(
                first_name=row["firstName"],
                last_name=row["lastName"],
                order_index=int(row["orderIndex"]),
            )
        )
    return creators_by_item


def _read_attachments(conn: sqlite3.Connection, data_dir: Path) -> dict[int, list[ZoteroAttachmentRecord]]:
    rows = conn.execute(
        """
        SELECT ia.itemID, ia.parentItemID, ia.linkMode, ia.contentType, ia.path,
               i.key, COALESCE(CAST(i.libraryID AS TEXT), 'local') AS libraryID
        FROM itemAttachments ia
        JOIN items i ON i.itemID = ia.itemID
        WHERE ia.parentItemID IS NOT NULL
        ORDER BY ia.parentItemID, ia.itemID
        """
    ).fetchall()
    attachments_by_parent: dict[int, list[ZoteroAttachmentRecord]] = {}
    for row in rows:
        record = _attachment_record_from_row(row, data_dir)
        attachments_by_parent.setdefault(record.parent_item_id, []).append(record)
    return attachments_by_parent


def _attachment_record_from_row(row: sqlite3.Row, data_dir: Path) -> ZoteroAttachmentRecord:
    item_id = int(row["itemID"])
    key = str(row["key"])
    link_mode = int(row["linkMode"])
    raw_path = row["path"]
    content_type = row["contentType"]
    resolved_path: Path | None = None
    availability = "unresolved"
    storage_mode = "linked"

    if link_mode in (LINK_MODE_IMPORTED_FILE, LINK_MODE_IMPORTED_URL):
        storage_mode = "linked"
        filename = _stored_filename(raw_path)
        if filename:
            resolved_path = data_dir / "storage" / key / filename
            availability = "available" if resolved_path.exists() else "missing"
        else:
            availability = "unresolved"
    elif link_mode == LINK_MODE_LINKED_FILE:
        storage_mode = "linked"
        if raw_path:
            resolved_path = Path(str(raw_path))
            availability = "available" if resolved_path.exists() else "missing"
        else:
            availability = "unresolved"
    elif link_mode == LINK_MODE_LINKED_URL:
        storage_mode = "url"
        availability = "available" if raw_path else "unresolved"

    return ZoteroAttachmentRecord(
        item_id=item_id,
        key=key,
        parent_item_id=int(row["parentItemID"]),
        library_id=str(row["libraryID"]),
        link_mode=link_mode,
        content_type=content_type,
        path=raw_path,
        resolved_path=resolved_path,
        availability=availability,
        storage_mode=storage_mode,
        role="primary" if content_type == "application/pdf" else "attachment",
    )


def _stored_filename(path: str | None) -> str | None:
    if not path:
        return None
    value = str(path)
    if value.startswith("storage:"):
        return value.split(":", 1)[1]
    return Path(value).name


def _read_collections(conn: sqlite3.Connection) -> list[ZoteroCollectionRecord]:
    if not _table_exists(conn, "collections"):
        return []
    rows = conn.execute(
        """
        SELECT collectionID, key, collectionName, parentCollectionID
        FROM collections
        ORDER BY collectionID
        """
    ).fetchall()
    return [
        ZoteroCollectionRecord(
            collection_id=int(row["collectionID"]),
            key=row["key"],
            name=str(row["collectionName"]),
            parent_collection_id=row["parentCollectionID"],
        )
        for row in rows
    ]


def _read_collection_membership(conn: sqlite3.Connection) -> dict[int, list[int]]:
    if not _table_exists(conn, "collectionItems"):
        return {}
    rows = conn.execute("SELECT collectionID, itemID FROM collectionItems ORDER BY itemID").fetchall()
    memberships: dict[int, list[int]] = {}
    for row in rows:
        memberships.setdefault(int(row["itemID"]), []).append(int(row["collectionID"]))
    return memberships


def _read_tags(conn: sqlite3.Connection) -> dict[int, list[str]]:
    if not _table_exists(conn, "itemTags"):
        return {}
    rows = conn.execute(
        """
        SELECT it.itemID, t.name
        FROM itemTags it
        JOIN tags t ON t.tagID = it.tagID
        ORDER BY it.itemID, t.name
        """
    ).fetchall()
    tags_by_item: dict[int, list[str]] = {}
    for row in rows:
        tags_by_item.setdefault(int(row["itemID"]), []).append(str(row["name"]))
    return tags_by_item


def _read_notes(conn: sqlite3.Connection) -> dict[int, list[ZoteroNoteRecord]]:
    if not _table_exists(conn, "itemNotes"):
        return {}
    rows = conn.execute(
        """
        SELECT n.itemID, n.parentItemID, n.note, i.key,
               COALESCE(CAST(i.libraryID AS TEXT), 'local') AS libraryID
        FROM itemNotes n
        JOIN items i ON i.itemID = n.itemID
        WHERE n.parentItemID IS NOT NULL
        ORDER BY n.parentItemID, n.itemID
        """
    ).fetchall()
    notes_by_parent: dict[int, list[ZoteroNoteRecord]] = {}
    for row in rows:
        record = ZoteroNoteRecord(
            item_id=int(row["itemID"]),
            key=str(row["key"]),
            parent_item_id=int(row["parentItemID"]),
            library_id=str(row["libraryID"]),
            note=str(row["note"] or ""),
        )
        notes_by_parent.setdefault(record.parent_item_id, []).append(record)
    return notes_by_parent


def _read_annotations(conn: sqlite3.Connection) -> dict[int, list[ZoteroAnnotationRecord]]:
    if not _table_exists(conn, "itemAnnotations"):
        return {}
    rows = conn.execute(
        """
        SELECT a.itemID, a.parentItemID, a.type, a.text, a.comment, a.position,
               i.key, COALESCE(CAST(i.libraryID AS TEXT), 'local') AS libraryID
        FROM itemAnnotations a
        JOIN items i ON i.itemID = a.itemID
        WHERE a.parentItemID IS NOT NULL
        ORDER BY a.parentItemID, a.itemID
        """
    ).fetchall()
    annotations_by_parent: dict[int, list[ZoteroAnnotationRecord]] = {}
    for row in rows:
        position = row["position"]
        record = ZoteroAnnotationRecord(
            item_id=int(row["itemID"]),
            key=str(row["key"]),
            parent_item_id=int(row["parentItemID"]),
            library_id=str(row["libraryID"]),
            annotation_type=row["type"],
            text=row["text"],
            comment=row["comment"],
            position_json={"raw": position} if position else None,
        )
        annotations_by_parent.setdefault(record.parent_item_id, []).append(record)
    return annotations_by_parent


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None
