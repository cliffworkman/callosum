"""SP3a/SP3b — local change-tracking + the last-write-wins, conflict-surfacing merge core (pure of network/crypto),
keyed on a device-independent ``sync_uid``.

**Identity is global, not local (SP3b):** sync keys every record on a stable ``sync_uid`` (UUID) held in the
``sync_identity`` map (collection, local_id ↔ sync_uid), NOT the device-local auto-increment ``id`` (which differs
across devices). The payload that travels is the row **minus its local PK** — so the same logical record has the same
content on every device. ``ensure_identities`` assigns a uid lazily to any current row lacking one.

**Change-tracking is a hash-diff, not write-hooks:** at sync time, hash each syncable row's canonical payload and
compare to ``sync_state`` (keyed on sync_uid) — rows whose hash differs (or are new) are changes; rows gone from the
domain table but present in ``sync_state`` are deletes (tombstones). No per-write instrumentation.

**Merge is per-record last-write-wins, but conflicts are surfaced:** when a remote record is newer than local AND the
same record was also changed locally since the last sync, remote (the higher version) wins **and** the local losing
payload is returned as a ``Conflict`` so it can be kept + recovered (value A4) — never silently dropped.

The syncable *set* (``SYNCABLE``) here is the **top-level, FK-free** user-authored data (papers, tags, axes); derived
data (embeddings, signals, caches) and PDF bytes are NOT synced (rebuilt/re-linked locally). The FK-bearing tables
(paper_tags, annotations, notes, summaries, manual cluster_node_papers) + an FK-translation layer (resolve a referenced
row's sync_uid ↔ local id, also via ``sync_identity``) are a focused follow-on.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Connection, Table, insert, select

from app.backend.persistence import schema
from app.backend.persistence.schema import sync_identity as _sync_identity
from app.backend.persistence.schema import sync_state as _sync_state

Key = tuple[str, str]  # (collection, sync_uid)


@dataclass(frozen=True)
class SyncableCollection:
    name: str
    table: Table
    pk: str | None = (
        "id"  # the single local-id column → an own sync_uid. None = a LINK table (identity = its endpoints)
    )
    where: Any = None  # optional SQLAlchemy filter (e.g. manual-only); a follow-on uses it
    fks: dict[str, str] = field(default_factory=dict)  # {fk_column: referenced collection} → translated local↔uid
    drop: tuple[str, ...] = ()  # device-local columns omitted from the synced payload (e.g. a per-device attachment id)
    natural_key: str | None = (
        None  # a UNIQUE column whose value derives a DETERMINISTIC sync_uid → cross-device convergence
    )


# The user-authored data, in **referenced-first dependency order** (a row's FK targets sync before it). FK columns are
# translated local-id ↔ a referenced row's sync_uid (changeset.collect_local / engine apply). A LINK table (pk=None,
# e.g. paper_tags) has no own id — its identity is its translated endpoint uids. Derived/un-synced (rebuilt locally):
# PDFs, embeddings, signals, caches, cluster_nodes, AND summaries (a regeneratable synthesis whose verification is
# keyed to device-local chunk/embedding versions). Still a follow-on: manual cluster_node_papers (needs an
# axis-membership identity, since cluster_nodes are derived).
SYNCABLE: tuple[SyncableCollection, ...] = (
    SyncableCollection("papers", schema.papers),
    # a tag IS its (UNIQUE) name — a deterministic name-derived uid lets two devices' identically-named tags converge.
    SyncableCollection("tags", schema.tags, natural_key="name"),
    SyncableCollection("axes", schema.axes),
    SyncableCollection("notes", schema.notes, fks={"paper_id": "papers"}),
    # attachment_id is a per-device pointer (PDFs aren't synced) → dropped; the highlight re-associates by paper+page.
    SyncableCollection("annotations", schema.annotations, fks={"paper_id": "papers"}, drop=("attachment_id",)),
    # a link table: no own id; its sync key is the (paper sync_uid | tag sync_uid) pair → device-independent.
    SyncableCollection("paper_tags", schema.paper_tags, pk=None, fks={"paper_id": "papers", "tag_id": "tags"}),
)


def record_hash(payload: dict) -> str:
    """sha256 of the canonical JSON of a payload (sorted keys; datetimes → str). Stable iff the content is stable
    (a ``datetime`` and the string it round-trips to via ``default=str`` hash identically)."""
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
    record_id: str  # sync_uid
    deleted: bool
    payload: dict | None  # None for a delete; otherwise the row minus its local PK
    new_version: int


@dataclass(frozen=True)
class RemoteRecord:
    collection: str
    record_id: str  # sync_uid
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
    to_apply: list[RemoteRecord] = field(default_factory=list)  # remote wins → write locally
    conflicts: list[Conflict] = field(default_factory=list)


# --- the local↔global identity map (sync_identity) ---


def _new_uid() -> str:
    return uuid.uuid4().hex


def _natural_uid(collection: str, value) -> str:
    """A deterministic sync_uid from a natural key — the SAME on every device, so identically-keyed rows (e.g. two
    devices' tag named "topic") converge instead of colliding. sha256(collection\\0value), hex (fits String(64))."""
    return hashlib.sha256(f"{collection}\x00{value}".encode()).hexdigest()


def uid_map(conn: Connection, collection: SyncableCollection) -> dict[str, str]:
    """{local_id(str): sync_uid} for a collection, from the identity map."""
    rows = conn.execute(
        select(_sync_identity.c.local_id, _sync_identity.c.sync_uid).where(
            _sync_identity.c.collection == collection.name
        )
    ).all()
    return {str(local_id): sync_uid for local_id, sync_uid in rows}


def local_id_for_uid(conn: Connection, collection: SyncableCollection, sync_uid: str) -> str | None:
    """The device-local id a sync_uid currently maps to in this collection, or None (a new record to insert)."""
    row = conn.execute(
        select(_sync_identity.c.local_id).where(
            _sync_identity.c.collection == collection.name, _sync_identity.c.sync_uid == sync_uid
        )
    ).first()
    return None if row is None else str(row[0])


def bind_identity(conn: Connection, collection: SyncableCollection, local_id: str, sync_uid: str) -> None:
    conn.execute(insert(_sync_identity).values(collection=collection.name, local_id=str(local_id), sync_uid=sync_uid))


def forget_identity(conn: Connection, collection: SyncableCollection, sync_uid: str) -> None:
    """Drop a sync_uid's mapping (on a tombstone), so a later re-create of the same uid is treated as an insert."""
    conn.execute(
        _sync_identity.delete().where(
            _sync_identity.c.collection == collection.name, _sync_identity.c.sync_uid == sync_uid
        )
    )


def ensure_identities(conn: Connection, collections: tuple[SyncableCollection, ...] = SYNCABLE) -> None:
    """Assign a ``sync_uid`` to any current row that lacks a ``sync_identity`` entry. Idempotent; the canonical point
    where a device-local row gains its global id. A collection with a ``natural_key`` gets a **deterministic** uid
    derived from that key's value (so two devices independently holding the same logical row — e.g. a tag named
    "topic" — pick the SAME uid and converge instead of colliding on a UNIQUE constraint); others get a random uid.
    Link tables (``pk is None``) are skipped — their identity is their endpoints. Names come from the registry (#3)."""
    for c in collections:
        if c.pk is None:
            continue
        known = set(uid_map(conn, c))
        cols = [c.table.c[c.pk]] + ([c.table.c[c.natural_key]] if c.natural_key else [])
        stmt = select(*cols)
        if c.where is not None:
            stmt = stmt.where(c.where)
        for row in conn.execute(stmt):
            local_id = row[0]
            if str(local_id) in known:
                continue
            uid = _natural_uid(c.name, row[1]) if c.natural_key else _new_uid()
            bind_identity(conn, c, str(local_id), uid)


def _outbound(c: SyncableCollection, row_dict: dict, maps: dict[str, dict[str, str]]) -> tuple[str, dict] | None:
    """(record_id, device-independent payload) for one row, or None to skip. Drops the local PK + ``drop`` columns;
    translates FK columns local-id → the referenced row's sync_uid. record_id = the row's own sync_uid (normal) or
    the joined endpoint uids (a link table, ``pk is None``)."""
    payload = {k: v for k, v in row_dict.items() if k not in c.drop and (c.pk is None or k != c.pk)}
    for col, ref in c.fks.items():
        val = payload.get(col)
        if val is None:
            continue
        ref_uid = maps.get(ref, {}).get(str(val))
        if ref_uid is None:  # the FK target isn't synced/identified yet → can't represent this row portably
            return None
        payload[col] = ref_uid
    if c.pk is None:  # a link table — identity is its (translated) endpoint uids, in fks-declaration order
        if any(payload.get(col) is None for col in c.fks):
            return None
        return "|".join(str(payload[col]) for col in c.fks), payload
    sync_uid = maps[c.name].get(str(row_dict[c.pk]))
    return None if sync_uid is None else (sync_uid, payload)


def collect_local(conn: Connection, collections: tuple[SyncableCollection, ...] = SYNCABLE) -> dict[Key, dict]:
    """{(collection, record_id): payload} over the syncable tables — payload device-independent (FK columns →
    referenced sync_uids; local PK + ``drop`` columns removed). record_id is the row's own sync_uid, or for a link
    table the joined endpoint uids. Rows whose own/FK identity isn't assigned yet are skipped (``ensure_identities``
    runs first in the normal flow)."""
    maps = {c.name: uid_map(conn, c) for c in collections}
    out: dict[Key, dict] = {}
    for c in collections:
        stmt = select(c.table)
        if c.where is not None:
            stmt = stmt.where(c.where)
        for row in conn.execute(stmt).mappings():
            entry = _outbound(c, dict(row), maps)
            if entry is not None:
                out[(c.name, entry[0])] = entry[1]
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
    """The rows changed/added/deleted locally since the last recorded ``sync_state`` (a hash-diff, keyed on sync_uid).
    Ensures identities first so every current row is tracked."""
    ensure_identities(conn, collections)
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
    + recoverable), never silently dropped (A4). A local record that is newer/equal is skipped (it pushes instead)."""
    result = MergeResult()
    for r in remote:
        key = (r.collection, r.record_id)
        local_version = local_versions.get(key, 0)
        if r.version > local_version:
            if key in locally_changed:
                result.conflicts.append(Conflict(r.collection, r.record_id, local_version, local_payloads.get(key)))
            result.to_apply.append(r)
    return result
