"""Normalize and persist a bounded Mendeley library snapshot.

This module deliberately owns no OAuth, HTTP, token, or file-download behavior. The dormant
transport in ``integrations.mendeley.client`` supplies version-pinned snapshot data; this layer
maps that data into Callosum's existing CSL/paper and imported-collection contracts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, and_, delete, insert, select, update

from app.backend.metadata.citation_import import csl_record_to_paper_fields
from app.backend.persistence.repository import create_paper, find_existing_paper_by_identity
from app.backend.persistence.schema import collection_papers, collections, paper_external_identifiers

MENDELEY_IMPORT_SOURCE = "mendeley"
MENDELEY_ID_PROVIDER = "mendeley-document"
MAX_DOCUMENTS = 50_000
MAX_FOLDERS = 2_000
MAX_MEMBERSHIPS = 100_000
MAX_AUTHORS = 1_000
MAX_ABSTRACT_LENGTH = 1_000_000

_TYPE_TO_CSL = {
    "journal": "article-journal",
    "book": "book",
    "book_section": "chapter",
    "conference_proceedings": "paper-conference",
    "working_paper": "report",
    "report": "report",
    "web_page": "webpage",
    "thesis": "thesis",
    "magazine_article": "article-magazine",
    "newspaper_article": "article-newspaper",
    "patent": "patent",
    "statute": "legislation",
    "computer_program": "software",
    "film": "motion_picture",
}
_BIBLIOGRAPHIC_FIELDS = {
    "volume": ("volume", 20),
    "issue": ("issue", 255),
    "pages": ("page", 50),
    "publisher": ("publisher", 255),
    "language": ("language", 255),
    "citation_key": ("citation-key", 255),
}


class MendeleyImportError(ValueError):
    """A bounded snapshot did not satisfy the version-1 import contract."""


@dataclass(frozen=True)
class MendeleyImportResult:
    papers_created: int
    papers_matched: int
    folders_imported: int
    memberships_imported: int
    created_paper_ids: tuple[int, ...]


@dataclass(frozen=True)
class _Document:
    external_id: str
    csl: dict[str, Any]


@dataclass(frozen=True)
class _Folder:
    external_id: str
    name: str
    parent_external_id: str | None


def import_mendeley_snapshot(
    conn: Connection,
    *,
    documents: Iterable[Mapping[str, Any]],
    folders: Iterable[Mapping[str, Any]],
    folder_document_ids: Mapping[str, Iterable[str]],
) -> MendeleyImportResult:
    """Validate then atomically import one complete, privacy-local Mendeley snapshot.

    The caller is responsible for obtaining the three resources. No malformed or internally
    inconsistent snapshot is partially persisted. Existing paper metadata is never overwritten;
    only source-owned collection names/hierarchy/membership are refreshed.
    """
    normalized_documents = _normalize_documents(documents)
    normalized_folders = _normalize_folders(folders)
    memberships = _normalize_memberships(folder_document_ids, normalized_documents, normalized_folders)

    created_ids: list[int] = []
    matched = 0
    with conn.begin_nested():
        paper_ids: dict[str, int] = {}
        for document in normalized_documents:
            fields = csl_record_to_paper_fields(document.csl)
            fields["citation_key"] = document.csl.get("citation-key")
            fields["language"] = document.csl.get("language")
            source_match = _paper_for_mendeley_id(conn, document.external_id)
            identity_match = find_existing_paper_by_identity(
                conn,
                doi=fields["doi"],
                title=fields["title"],
                year=fields["year"],
                first_author_family_name=fields["first_author_family_name"],
            )
            identity_id = int(identity_match[1]["id"]) if identity_match is not None else None
            if source_match is not None and identity_id is not None and source_match != identity_id:
                raise MendeleyImportError("Mendeley identity conflicts with an existing paper identity")
            if source_match is not None:
                paper_id = source_match
                matched += 1
            elif identity_id is not None:
                paper_id = identity_id
                matched += 1
                _link_mendeley_id(conn, paper_id, document.external_id)
            else:
                paper_id = create_paper(conn, imported_source=MENDELEY_IMPORT_SOURCE, **fields)
                created_ids.append(paper_id)
                _link_mendeley_id(conn, paper_id, document.external_id)
            paper_ids[document.external_id] = paper_id

        collection_ids = _upsert_folders(conn, normalized_folders)
        imported_memberships = 0
        for folder in normalized_folders:
            collection_id = collection_ids[folder.external_id]
            conn.execute(delete(collection_papers).where(collection_papers.c.collection_id == collection_id))
            seen_paper_ids: set[int] = set()
            for document_id in memberships[folder.external_id]:
                paper_id = paper_ids[document_id]
                if paper_id in seen_paper_ids:
                    continue
                seen_paper_ids.add(paper_id)
                conn.execute(
                    insert(collection_papers)
                    .prefix_with("OR IGNORE")
                    .values(collection_id=collection_id, paper_id=paper_id)
                )
                imported_memberships += 1

    return MendeleyImportResult(
        papers_created=len(created_ids),
        papers_matched=matched,
        folders_imported=len(normalized_folders),
        memberships_imported=imported_memberships,
        created_paper_ids=tuple(created_ids),
    )


def normalize_mendeley_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one version-1 Mendeley document response to Callosum's CSL-shaped contract."""
    if not isinstance(document, Mapping):
        raise MendeleyImportError("Mendeley document was not an object")
    external_id = _resource_id(document.get("id"), "document")
    title = _required_string(document.get("title"), "document title", 500)
    document_type = _required_string(document.get("type"), "document type", 64)
    csl: dict[str, Any] = {
        "id": external_id,
        "type": _TYPE_TO_CSL.get(document_type, "document"),
        "title": title,
        "mendeley": {"document_id": external_id, "document_type": document_type},
    }

    authors = document.get("authors")
    if authors is not None:
        if not isinstance(authors, list) or len(authors) > MAX_AUTHORS:
            raise MendeleyImportError("Mendeley document authors exceeded the supported shape")
        normalized_authors: list[dict[str, str]] = []
        for author in authors:
            if not isinstance(author, Mapping):
                raise MendeleyImportError("Mendeley document author was not an object")
            family = _required_string(author.get("last_name"), "author last name", 255)
            given = _optional_string(author.get("first_name"), "author first name", 255)
            normalized_authors.append({"family": family, **({"given": given} if given else {})})
        if normalized_authors:
            csl["author"] = normalized_authors

    year = document.get("year")
    if year is not None:
        if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
            raise MendeleyImportError("Mendeley document year was invalid")
        csl["issued"] = {"date-parts": [[year]]}

    source = _optional_string(document.get("source"), "document source", 500)
    abstract = _optional_string(document.get("abstract"), "document abstract", MAX_ABSTRACT_LENGTH)
    if source:
        csl["container-title"] = source
    if abstract:
        csl["abstract"] = abstract

    identifiers = document.get("identifiers")
    if identifiers is not None:
        if not isinstance(identifiers, Mapping) or len(identifiers) > 32:
            raise MendeleyImportError("Mendeley document identifiers exceeded the supported shape")
        normalized_identifiers: dict[str, str] = {}
        for raw_name, raw_value in identifiers.items():
            name = _required_string(raw_name, "identifier name", 64).lower()
            value = _required_string(raw_value, "identifier value", 500)
            normalized_identifiers[name] = value
        if normalized_identifiers:
            csl["mendeley"]["identifiers"] = normalized_identifiers
        for name, csl_name in (("doi", "DOI"), ("isbn", "ISBN"), ("issn", "ISSN")):
            if normalized_identifiers.get(name):
                csl[csl_name] = normalized_identifiers[name]

    for source_name, (csl_name, limit) in _BIBLIOGRAPHIC_FIELDS.items():
        value = _optional_string(document.get(source_name), f"document {source_name}", limit)
        if value:
            csl[csl_name] = value

    websites = document.get("websites")
    if websites is not None:
        if not isinstance(websites, list) or any(not isinstance(value, str) for value in websites):
            raise MendeleyImportError("Mendeley document websites had an unexpected shape")
        normalized_websites = [value.strip() for value in websites if value.strip()]
        if sum(len(value) for value in normalized_websites) > 5_000:
            raise MendeleyImportError("Mendeley document websites exceeded the supported size")
        if normalized_websites:
            csl["URL"] = normalized_websites[0]
            csl["mendeley"]["websites"] = normalized_websites
    return csl


def _normalize_documents(documents: Iterable[Mapping[str, Any]]) -> tuple[_Document, ...]:
    normalized: list[_Document] = []
    seen: set[str] = set()
    for document in _bounded(documents, MAX_DOCUMENTS, "documents"):
        csl = normalize_mendeley_document(document)
        external_id = str(csl["id"])
        if external_id in seen:
            raise MendeleyImportError("Mendeley snapshot repeated a document ID")
        seen.add(external_id)
        normalized.append(_Document(external_id, csl))
    return tuple(normalized)


def _normalize_folders(folders: Iterable[Mapping[str, Any]]) -> tuple[_Folder, ...]:
    normalized: list[_Folder] = []
    seen: set[str] = set()
    for folder in _bounded(folders, MAX_FOLDERS, "folders"):
        if not isinstance(folder, Mapping):
            raise MendeleyImportError("Mendeley folder was not an object")
        external_id = _resource_id(folder.get("id"), "folder")
        if external_id in seen:
            raise MendeleyImportError("Mendeley snapshot repeated a folder ID")
        seen.add(external_id)
        parent = folder.get("parent_id")
        parent_id = _resource_id(parent, "parent folder") if parent is not None else None
        normalized.append(_Folder(external_id, _required_string(folder.get("name"), "folder name", 255), parent_id))
    by_id = {folder.external_id: folder for folder in normalized}
    for folder in normalized:
        if folder.parent_external_id is not None and folder.parent_external_id not in by_id:
            raise MendeleyImportError("Mendeley folder referenced a missing parent")
        visited: set[str] = set()
        current: _Folder | None = folder
        while current is not None:
            if current.external_id in visited:
                raise MendeleyImportError("Mendeley folder hierarchy contained a cycle")
            visited.add(current.external_id)
            current = by_id.get(current.parent_external_id) if current.parent_external_id else None
    return tuple(normalized)


def _normalize_memberships(
    source: Mapping[str, Iterable[str]],
    documents: tuple[_Document, ...],
    folders: tuple[_Folder, ...],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(source, Mapping):
        raise MendeleyImportError("Mendeley folder memberships were not an object")
    document_ids = {document.external_id for document in documents}
    folder_ids = {folder.external_id for folder in folders}
    normalized: dict[str, tuple[str, ...]] = {folder_id: () for folder_id in folder_ids}
    count = 0
    for raw_folder_id, raw_document_ids in source.items():
        folder_id = _resource_id(raw_folder_id, "membership folder")
        if folder_id not in folder_ids:
            raise MendeleyImportError("Mendeley membership referenced an unknown folder")
        if isinstance(raw_document_ids, (str, bytes)) or not isinstance(raw_document_ids, Iterable):
            raise MendeleyImportError("Mendeley folder membership was not a document-ID collection")
        unique: list[str] = []
        seen: set[str] = set()
        for raw_document_id in raw_document_ids:
            document_id = _resource_id(raw_document_id, "membership document")
            if document_id not in document_ids:
                raise MendeleyImportError("Mendeley membership referenced an unknown document")
            if document_id not in seen:
                seen.add(document_id)
                unique.append(document_id)
                count += 1
                if count > MAX_MEMBERSHIPS:
                    raise MendeleyImportError("Mendeley memberships exceeded the supported limit")
        normalized[folder_id] = tuple(unique)
    return normalized


def _upsert_folders(conn: Connection, folders: tuple[_Folder, ...]) -> dict[str, int]:
    local_ids: dict[str, int] = {}
    for folder in folders:
        existing = conn.execute(
            select(collections.c.id).where(
                and_(
                    collections.c.import_source == MENDELEY_IMPORT_SOURCE,
                    collections.c.external_id == folder.external_id,
                )
            )
        ).first()
        if existing is None:
            local_id = conn.execute(
                insert(collections).values(
                    name=folder.name,
                    import_source=MENDELEY_IMPORT_SOURCE,
                    external_id=folder.external_id,
                )
            ).inserted_primary_key[0]
        else:
            local_id = existing[0]
        local_ids[folder.external_id] = int(local_id)
    for folder in folders:
        parent_id = local_ids.get(folder.parent_external_id) if folder.parent_external_id else None
        conn.execute(
            update(collections)
            .where(collections.c.id == local_ids[folder.external_id])
            .values(name=folder.name, parent_id=parent_id)
        )
    return local_ids


def _paper_for_mendeley_id(conn: Connection, external_id: str) -> int | None:
    row = conn.execute(
        select(paper_external_identifiers.c.paper_id).where(
            and_(
                paper_external_identifiers.c.provider == MENDELEY_ID_PROVIDER,
                paper_external_identifiers.c.identifier == external_id,
            )
        )
    ).first()
    return int(row[0]) if row is not None else None


def _link_mendeley_id(conn: Connection, paper_id: int, external_id: str) -> None:
    conn.execute(
        insert(paper_external_identifiers).values(
            paper_id=paper_id,
            provider=MENDELEY_ID_PROVIDER,
            identifier=external_id,
        )
    )


def _bounded(items: Iterable[Any], limit: int, label: str) -> tuple[Any, ...]:
    bounded: list[Any] = []
    for item in items:
        bounded.append(item)
        if len(bounded) > limit:
            raise MendeleyImportError(f"Mendeley {label} exceeded the supported limit")
    return tuple(bounded)


def _resource_id(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise MendeleyImportError(f"Mendeley {label} ID was invalid")
    normalized = value.strip()
    if not normalized or len(normalized) > 64 or any(ch not in "0123456789abcdefABCDEF-" for ch in normalized):
        raise MendeleyImportError(f"Mendeley {label} ID was invalid")
    return normalized


def _required_string(value: object, label: str, limit: int) -> str:
    normalized = _optional_string(value, label, limit)
    if normalized is None:
        raise MendeleyImportError(f"Mendeley {label} was missing")
    return normalized


def _optional_string(value: object, label: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MendeleyImportError(f"Mendeley {label} was not text")
    normalized = value.strip()
    if len(normalized) > limit:
        raise MendeleyImportError(f"Mendeley {label} exceeded the supported size")
    return normalized or None
