"""SP3a — local change-tracking + the last-write-wins, conflict-surfacing merge core (pure of network/crypto).

**Change-tracking is a hash-diff, not write-hooks:** at sync time, hash each syncable row's canonical payload and
compare to ``sync_state`` — rows whose hash differs (or are new) are changes; rows gone from the domain table but
present in ``sync_state`` are deletes (tombstones). No per-write instrumentation.

**Merge is per-record last-write-wins, but conflicts are surfaced:** when a remote record is newer than local AND
the same record was also changed locally since the last sync, remote (the higher version) wins **and** the local
losing payload is returned as a ``Conflict`` so it can be kept + recovered (value A4) — never silently dropped.

The syncable *set* (``SYNCABLE``) is the user-authored + bibliographic data; derived data (embeddings, signals,
caches) and PDF bytes are NOT here — they're rebuilt/re-linked locally. Manual axis assignments + the profile are
finalized in SP3b (they need a filtered/field-selected collection).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Connection, Table, select

from app.backend.persistence import schema
from app.backend.persistence.schema import sync_state as _sync_state

Key = tuple[str, str]  # (collection, record_id)


@dataclass(frozen=True)
class SyncableCollection:
    name: str
    table: Table
    where: Any = None  # optional SQLAlchemy filter (e.g. manual-only); SP3b uses it

    def record_id(self, row: dict) -> str:
        # Composite-PK-safe (e.g. paper_tags) — join the primary-key columns.
        return ":".join(str(row[c.name]) for c in self.table.primary_key.columns)


# The user-authored + bibliographic data. (cluster_node_papers-manual + profile → SP3b; PDFs/embeddings/signals are
# rebuilt locally, never synced.)
SYNCABLE: tuple[SyncableCollection, ...] = (
    SyncableCollection("papers", schema.papers),
    SyncableCollection("tags", schema.tags),
    SyncableCollection("paper_tags", schema.paper_tags),
    SyncableCollection("notes", schema.notes),
    SyncableCollection("annotations", schema.annotations),
    SyncableCollection("axes", schema.axes),
    SyncableCollection("summaries", schema.summaries),
)


def record_hash(payload: dict) -> str:
    """sha256 of the canonical JSON of a payload (sorted keys; datetimes → str). Stable iff the content is stable."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass(frozen=True)
class SyncStateRow:
    version: int
    content_hash: str | None
    deleted: bool


@dataclass(frozen=True)
class LocalChange:
    collection: str
    record_id: str
    deleted: bool
    payload: dict | None  # None for a delete
    new_version: int


@dataclass(frozen=True)
class RemoteRecord:
    collection: str
    record_id: str
    version: int
    deleted: bool
    payload: dict | None


@dataclass(frozen=True)
class Conflict:
    collection: str
    record_id: str
    losing_version: int
    losing_payload: dict | None  # the LOCAL side that lost the LWW — kept for recovery (A4)


@dataclass
class MergeResult:
    to_apply: list[RemoteRecord] = field(default_factory=list)  # remote wins → write locally (SP3b)
    conflicts: list[Conflict] = field(default_factory=list)


def collect_local(conn: Connection, collections: tuple[SyncableCollection, ...] = SYNCABLE) -> dict[Key, dict]:
    """{(collection, record_id): payload} over the syncable tables. Table/column names come from the registry
    (constants → rule #3), never request data."""
    out: dict[Key, dict] = {}
    for c in collections:
        stmt = select(c.table)
        if c.where is not None:
            stmt = stmt.where(c.where)
        for row in conn.execute(stmt).mappings():
            row_dict = dict(row)
            out[(c.name, c.record_id(row_dict))] = row_dict
    return out


def read_sync_state(conn: Connection) -> dict[Key, SyncStateRow]:
    out: dict[Key, SyncStateRow] = {}
    for row in conn.execute(select(_sync_state)).mappings():
        out[(row["collection"], row["record_id"])] = SyncStateRow(
            version=int(row["version"]),
            content_hash=row["content_hash"],
            deleted=bool(row["deleted"]),
        )
    return out


def local_changeset(conn: Connection, collections: tuple[SyncableCollection, ...] = SYNCABLE) -> list[LocalChange]:
    """The rows changed/added/deleted locally since the last recorded ``sync_state`` (a hash-diff)."""
    current = collect_local(conn, collections)
    state = read_sync_state(conn)
    changes: list[LocalChange] = []

    for key, payload in current.items():
        st = state.get(key)
        h = record_hash(payload)
        if st is None or st.deleted or st.content_hash != h:
            new_version = (st.version + 1) if st is not None else 1
            changes.append(LocalChange(key[0], key[1], False, payload, new_version))

    for key, st in state.items():
        if not st.deleted and key not in current:  # gone from the domain table → a tombstone
            changes.append(LocalChange(key[0], key[1], True, None, st.version + 1))

    return changes


def merge_remote(
    *,
    local_versions: dict[Key, int],
    local_payloads: dict[Key, dict | None],
    locally_changed: set[Key],
    remote: list[RemoteRecord],
) -> MergeResult:
    """Per-record last-write-wins by version, surfacing conflicts. Remote wins when strictly newer; if the record
    was ALSO changed locally since the last sync, the overwritten local payload is returned as a ``Conflict`` (kept
    + recoverable), never silently dropped (A4). A local record that is newer/equal is skipped (it pushes in SP3b)."""
    result = MergeResult()
    for r in remote:
        key = (r.collection, r.record_id)
        local_version = local_versions.get(key, 0)
        if r.version > local_version:
            if key in locally_changed:
                result.conflicts.append(Conflict(r.collection, r.record_id, local_version, local_payloads.get(key)))
            result.to_apply.append(r)
    return result
