"""Turn imported reference-manager folder structure into ordinary Callosum axes.

The operation is an explicit, one-time snapshot. Imported source rows remain provenance; the
resulting axis is user-owned and a later library re-import never silently rewrites it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, insert, select

from app.backend.clustering.axis_assignments import CURATED_KIND, add_manual_assignment, append_member_position
from app.backend.clustering.axis_scoring import create_axis
from app.backend.persistence.schema import (
    axes,
    collection_papers,
    collections,
    imported_collection_axes,
)

SUPPORTED_IMPORT_SOURCES = frozenset({"zotero", "mendeley", "endnote"})
SUPPORTED_AXIS_KINDS = frozenset({CURATED_KIND, "standard"})
MAX_IMPORTED_COLLECTIONS = 2_000
MAX_IMPORTED_MEMBERSHIPS = 100_000
MAX_AXES_PER_ACTION = 100
AXIS_LABEL_MAX = 200


@dataclass(frozen=True)
class ImportedCollectionAxisCandidate:
    collection_id: int
    name: str
    import_source: str
    descendant_count: int
    paper_ids: tuple[int, ...]
    axis_id: int | None
    axis_kind: str | None


@dataclass(frozen=True)
class ImportedCollectionAxesResult:
    created_axis_ids: tuple[int, ...]
    existing_axis_ids: tuple[int, ...]
    skipped_empty_collection_ids: tuple[int, ...]


def list_imported_axis_candidates(
    conn: Connection, *, import_source: str
) -> tuple[ImportedCollectionAxisCandidate, ...]:
    source = _validated_source(import_source)
    rows = list(
        conn.execute(
            select(collections)
            .where(collections.c.import_source == source)
            .order_by(collections.c.id)
            .limit(MAX_IMPORTED_COLLECTIONS + 1)
        ).mappings()
    )
    if len(rows) > MAX_IMPORTED_COLLECTIONS:
        raise ValueError(f"Imported collection count exceeds the {MAX_IMPORTED_COLLECTIONS} safety limit")
    if not rows:
        return ()

    by_id = {int(row["id"]): row for row in rows}
    children: dict[int, list[int]] = {collection_id: [] for collection_id in by_id}
    roots: list[int] = []
    for collection_id, row in by_id.items():
        parent_id = int(row["parent_id"]) if row["parent_id"] is not None else None
        if parent_id is None:
            roots.append(collection_id)
        elif parent_id not in by_id:
            raise ValueError("Imported collection hierarchy points outside its source")
        else:
            children[parent_id].append(collection_id)
    _reject_cycles(by_id, children)
    if not roots:
        raise ValueError("Imported collection hierarchy has no top-level collection")

    membership_rows = list(
        conn.execute(
            select(collection_papers.c.collection_id, collection_papers.c.paper_id)
            .where(collection_papers.c.collection_id.in_(by_id))
            .order_by(collection_papers.c.collection_id, collection_papers.c.paper_id)
            .limit(MAX_IMPORTED_MEMBERSHIPS + 1)
        )
    )
    if len(membership_rows) > MAX_IMPORTED_MEMBERSHIPS:
        raise ValueError(f"Imported membership count exceeds the {MAX_IMPORTED_MEMBERSHIPS} safety limit")
    papers: dict[int, set[int]] = {collection_id: set() for collection_id in by_id}
    for collection_id, paper_id in membership_rows:
        papers[int(collection_id)].add(int(paper_id))

    links = {
        int(row.collection_id): (int(row.axis_id), str(row.kind))
        for row in conn.execute(
            select(imported_collection_axes.c.collection_id, imported_collection_axes.c.axis_id, axes.c.kind).join(
                axes, axes.c.id == imported_collection_axes.c.axis_id
            )
        )
    }
    candidates: list[ImportedCollectionAxisCandidate] = []
    for collection_id in sorted(roots, key=lambda value: (str(by_id[value]["name"]).casefold(), value)):
        descendant_ids = _descendants(collection_id, children)
        paper_ids = tuple(sorted({paper_id for descendant_id in descendant_ids for paper_id in papers[descendant_id]}))
        linked = links.get(collection_id)
        candidates.append(
            ImportedCollectionAxisCandidate(
                collection_id=collection_id,
                name=str(by_id[collection_id]["name"]),
                import_source=source,
                descendant_count=len(descendant_ids) - 1,
                paper_ids=paper_ids,
                axis_id=linked[0] if linked else None,
                axis_kind=linked[1] if linked else None,
            )
        )
    return tuple(candidates)


def create_imported_collection_axes(
    conn: Connection, *, import_source: str, axis_kind: str
) -> ImportedCollectionAxesResult:
    if axis_kind not in SUPPORTED_AXIS_KINDS:
        raise ValueError(f"Unsupported axis kind: {axis_kind}")
    candidates = list_imported_axis_candidates(conn, import_source=import_source)
    pending = [candidate for candidate in candidates if candidate.axis_id is None and candidate.paper_ids]
    if len(pending) > MAX_AXES_PER_ACTION:
        raise ValueError(f"Axis count exceeds the {MAX_AXES_PER_ACTION} per-action safety limit")

    created: list[int] = []
    existing: list[int] = []
    empty: list[int] = []
    for candidate in candidates:
        if candidate.axis_id is not None:
            existing.append(candidate.axis_id)
            continue
        if not candidate.paper_ids:
            empty.append(candidate.collection_id)
            continue
        axis_id = create_axis(conn, label=_axis_label(candidate.name), kind=axis_kind)
        for paper_id in candidate.paper_ids:
            add_manual_assignment(conn, axis_id=axis_id, paper_id=paper_id)
            if axis_kind == CURATED_KIND:
                append_member_position(conn, axis_id=axis_id, paper_id=paper_id)
        conn.execute(insert(imported_collection_axes).values(collection_id=candidate.collection_id, axis_id=axis_id))
        created.append(axis_id)
    return ImportedCollectionAxesResult(tuple(created), tuple(existing), tuple(empty))


def _validated_source(import_source: str) -> str:
    source = import_source.strip().lower()
    if source not in SUPPORTED_IMPORT_SOURCES:
        raise ValueError(f"Unsupported import source: {import_source}")
    return source


def _axis_label(name: str) -> str:
    label = name.strip() or "Imported collection"
    if len(label) <= AXIS_LABEL_MAX:
        return label
    return f"{label[: AXIS_LABEL_MAX - 1].rstrip()}…"


def _reject_cycles(by_id: dict[int, object], children: dict[int, list[int]]) -> None:
    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(collection_id: int) -> None:
        if collection_id in visiting:
            raise ValueError("Imported collection hierarchy contains a cycle")
        if collection_id in visited:
            return
        visiting.add(collection_id)
        for child_id in children[collection_id]:
            visit(child_id)
        visiting.remove(collection_id)
        visited.add(collection_id)

    for collection_id in by_id:
        visit(collection_id)


def _descendants(root_id: int, children: dict[int, list[int]]) -> set[int]:
    found: set[int] = set()
    pending = [root_id]
    while pending:
        collection_id = pending.pop()
        if collection_id in found:
            continue
        found.add(collection_id)
        pending.extend(children[collection_id])
    return found
