"""SP3b — the client sync engine: the pull → decrypt → merge → apply → push loop over an injectable transport.

The engine is the only place ciphertext meets the local DB. It is deliberately **transport-agnostic** (a
``SyncTransport`` Protocol; a fake drives the tests, the reference server is the next slice) and **cursor-store
agnostic** (``since`` is passed in, the new cursor is returned — the caller persists it). It never sees a passphrase
or recovery code; it holds only the already-unsealed **DEK**, hands the transport **opaque AES-GCM blobs** (the DEK
never leaves), and **fails closed** on any decrypt failure (a tampered/foreign blob raises, never written as garbage).

Apply is keyed on ``sync_uid`` via ``sync_identity`` (changeset.py): a remote record upserts the local row the uid
maps to (UPDATE in place — never INSERT-OR-REPLACE, so no FK-cascade surprise), inserting + binding a new identity if
the uid is unseen; a tombstone deletes the mapped row + forgets the uid (so a later re-create is a clean insert). Only
columns the table actually has are written (rule #4 — a decrypted payload can't inject columns). Conflicts (a remote
winner that also changed locally) are surfaced into ``sync_conflicts`` (A4), never silently merged.

Scope this slice: the top-level, FK-free collections (papers, tags, axes). FK-bearing tables + FK-translation follow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import Connection, DateTime, Integer, and_, insert, select, update

from app.backend.persistence.schema import sync_conflicts as _sync_conflicts
from app.backend.persistence.schema import sync_state as _sync_state
from app.backend.sync.changeset import (
    SYNCABLE,
    RemoteRecord,
    SyncableCollection,
    bind_identity,
    collect_local,
    ensure_identities,
    forget_identity,
    local_changeset,
    local_id_for_uid,
    merge_remote,
    read_sync_state,
    record_hash,
)
from app.backend.sync.crypto import decrypt_payload, encrypt_payload


@dataclass(frozen=True)
class SyncBlob:
    """One record as it crosses the wire: identity + version + an OPAQUE ciphertext (None iff a tombstone). The
    server stores/orders these by an opaque sequence; it never sees plaintext or the DEK."""

    collection: str
    record_id: str  # sync_uid
    version: int
    deleted: bool
    ciphertext: str | None


@dataclass(frozen=True)
class PullResult:
    records: list[SyncBlob]  # blobs with server-sequence > the requested `since`
    seq: int  # the server's current high sequence (the client's next `since`)


class SyncTransport(Protocol):
    """The server contract. Injectable so a fake drives the tests (no egress); the reference server is the next slice."""

    def pull(self, since: int) -> PullResult: ...

    def push(self, records: list[SyncBlob]) -> int: ...


@dataclass
class SyncRunResult:
    new_cursor: int
    pushed: int = 0
    applied: int = 0
    conflicts: int = 0


def _coerce_for_write(table, payload: dict) -> dict:
    """Keep only columns the table actually has (rule #4) and turn decrypted ISO strings back into datetimes for
    DateTime columns (they were serialized via ``default=str`` on the source device)."""
    out: dict = {}
    for k, v in payload.items():
        if k not in table.c:
            continue  # a payload can't inject unknown columns
        col = table.c[k]
        if v is not None and isinstance(col.type, DateTime) and isinstance(v, str):
            try:
                out[k] = datetime.fromisoformat(v)
            except ValueError:
                out[k] = v
        else:
            out[k] = v
    return out


def _json_safe(payload):
    """Make a payload JSON-native (datetimes → ISO strings) for storage in a JSON column (the conflict store)."""
    return None if payload is None else json.loads(json.dumps(payload, default=str))


def _typed_pk(c: SyncableCollection, local_id: str):
    """The map stores local ids as strings; an integer-affinity PK must compare as int in SQLite."""
    if isinstance(c.table.c[c.pk].type, Integer):
        try:
            return int(local_id)
        except (TypeError, ValueError):
            return local_id
    return local_id


def _set_sync_state(conn: Connection, collection: str, record_id: str, version: int, payload, deleted: bool) -> None:
    conn.execute(
        insert(_sync_state)
        .prefix_with("OR REPLACE")
        .values(
            collection=collection,
            record_id=record_id,
            content_hash=None if (deleted or payload is None) else record_hash(payload),
            version=version,
            deleted=1 if deleted else 0,
        )
    )


def _apply_link(conn: Connection, c: SyncableCollection, r: RemoteRecord, by_name: dict) -> bool:
    """Apply a link-table (composite-PK, ``pk is None``) record: its identity is its endpoint uids
    (``record_id`` = the joined uids). Resolve each endpoint uid → this device's local id, then INSERT-OR-IGNORE the
    link / DELETE it (tombstone). Returns False (skip, retry later) iff an endpoint isn't present locally yet."""
    cols = list(c.fks)
    parts = r.record_id.split("|")
    if len(parts) != len(cols):
        return False
    resolved: dict = {}
    for col, uid in zip(cols, parts, strict=False):
        ref_c = by_name.get(c.fks[col])
        local = None if ref_c is None else local_id_for_uid(conn, ref_c, uid)
        if local is None:
            return False  # an endpoint isn't synced here yet
        resolved[col] = _typed_pk(ref_c, local)
    cond = and_(*[c.table.c[col] == v for col, v in resolved.items()])
    if r.deleted:
        conn.execute(c.table.delete().where(cond))
        return True
    if conn.execute(select(c.table).where(cond)).first() is None:  # idempotent (composite PK)
        values = dict(resolved)
        for k, v in _coerce_for_write(c.table, r.payload or {}).items():
            if k not in c.fks:  # any non-FK metadata column (none for paper_tags today)
                values[k] = v
        conn.execute(insert(c.table).values(**values))
    return True


def _apply_record(conn: Connection, c: SyncableCollection, r: RemoteRecord, by_name: dict) -> bool:
    """Write a remote winner into the domain table, by sync_uid (UPDATE-in-place / INSERT-and-bind / DELETE).
    Returns False (skipped, retry later) iff an FK target isn't present locally yet — applied referenced-first, so
    that's rare in practice."""
    if c.pk is None:
        return _apply_link(conn, c, r, by_name)
    local_id = local_id_for_uid(conn, c, r.record_id)
    if r.deleted:
        if local_id is not None:
            conn.execute(c.table.delete().where(c.table.c[c.pk] == _typed_pk(c, local_id)))
            forget_identity(conn, c, r.record_id)
        return True
    values = _coerce_for_write(c.table, r.payload or {})
    for col, ref in c.fks.items():  # referenced sync_uid → this device's local id
        uid = values.get(col)
        if uid is None:
            continue
        ref_c = by_name.get(ref)
        ref_local = None if ref_c is None else local_id_for_uid(conn, ref_c, str(uid))
        if ref_local is None:
            return False  # FK target not synced here yet → skip this record (it retries when the target arrives)
        values[col] = _typed_pk(ref_c, ref_local)
    if local_id is None:
        result = conn.execute(insert(c.table).values(**values))
        bind_identity(conn, c, str(result.inserted_primary_key[0]), r.record_id)
    else:
        conn.execute(update(c.table).where(c.table.c[c.pk] == _typed_pk(c, local_id)).values(**values))
    return True


def run_sync(
    conn: Connection,
    dek: bytes,
    transport: SyncTransport,
    *,
    since: int = 0,
    collections: tuple[SyncableCollection, ...] = SYNCABLE,
) -> SyncRunResult:
    """One full sync pass against ``transport``. Returns the new cursor + counts. Runs inside the caller's
    transaction (the caller commits)."""
    by_name = {c.name: c for c in collections}
    ensure_identities(conn, collections)  # every current row gets its global sync_uid before we collect/diff

    pull = transport.pull(since)
    remote: list[RemoteRecord] = []
    for b in pull.records:
        if b.collection not in by_name:
            continue  # a collection this client doesn't sync (forward-compatible); skip
        if b.deleted:
            remote.append(RemoteRecord(b.collection, b.record_id, b.version, True, None))
        else:
            payload = decrypt_payload(dek, b.ciphertext or "")  # fails closed on a tampered/foreign blob
            remote.append(RemoteRecord(b.collection, b.record_id, b.version, False, payload))

    state = read_sync_state(conn)
    current = collect_local(conn, collections)
    local_versions = {k: st.version for k, st in state.items()}
    locally_changed = {(ch.collection, ch.record_id) for ch in local_changeset(conn, collections)}
    merge = merge_remote(
        local_versions=local_versions,
        local_payloads=dict(current),
        locally_changed=locally_changed,
        remote=remote,
    )

    # Apply referenced-collections-first (SYNCABLE order) so a record's FK targets exist before it is written.
    rank = {c.name: i for i, c in enumerate(collections)}
    applied = 0
    for r in sorted(merge.to_apply, key=lambda r: rank.get(r.collection, len(rank))):
        if _apply_record(conn, by_name[r.collection], r, by_name):
            _set_sync_state(conn, r.collection, r.record_id, r.version, None if r.deleted else r.payload, r.deleted)
            applied += 1
    for cf in merge.conflicts:
        conn.execute(
            insert(_sync_conflicts).values(
                collection=cf.collection,
                record_id=cf.record_id,
                losing_version=cf.losing_version,
                losing_payload=_json_safe(cf.losing_payload),
                resolved=0,
            )
        )

    # Push everything still locally-newer after reconciling remote (a record we just applied now matches → not pushed).
    push_changes = local_changeset(conn, collections)
    blobs = [
        SyncBlob(
            ch.collection,
            ch.record_id,
            ch.new_version,
            ch.deleted,
            None if ch.deleted else encrypt_payload(dek, ch.payload),
        )
        for ch in push_changes
    ]
    if blobs:
        transport.push(blobs)
        for ch in push_changes:
            _set_sync_state(conn, ch.collection, ch.record_id, ch.new_version, ch.payload, ch.deleted)
            if ch.deleted and by_name[ch.collection].pk is not None:  # a link table has no own identity to forget
                forget_identity(conn, by_name[ch.collection], ch.record_id)

    return SyncRunResult(
        new_cursor=pull.seq,
        pushed=len(blobs),
        applied=applied,
        conflicts=len(merge.conflicts),
    )
