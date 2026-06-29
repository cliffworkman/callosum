"""The sync-server's storage logic (pure SQLAlchemy Core, dialect-portable). All rows are scoped by ``user_id`` —
the OIDC ``sub`` — so one user can never read or overwrite another's records.

``push`` is **last-write-wins by version** (a record is stored only if its version exceeds the stored one), and each
stored record is stamped the **next per-user ``seq``** (assigned from the locked ``sync_cursor`` counter row, so
concurrent pushes from one user don't collide). ``pull`` returns the user's records with ``seq > since`` plus the
user's current high seq (the next cursor). Bound params throughout (rule #3); the server never decodes ``ciphertext``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, insert, select, update

from sync_server.schema import sync_cursor, sync_records


@dataclass(frozen=True)
class Record:
    collection: str
    record_id: str
    version: int
    deleted: bool
    ciphertext: str | None  # opaque base64 AES-GCM blob; None iff a tombstone


def _current_seq(conn: Connection, user_id: str, *, lock: bool) -> int:
    stmt = select(sync_cursor.c.seq).where(sync_cursor.c.user_id == user_id)
    if lock and conn.dialect.name != "sqlite":  # SQLite serializes writes; Postgres needs the row lock
        stmt = stmt.with_for_update()
    row = conn.execute(stmt).first()
    return int(row[0]) if row is not None else 0


def _set_seq(conn: Connection, user_id: str, seq: int) -> None:
    updated = conn.execute(update(sync_cursor).where(sync_cursor.c.user_id == user_id).values(seq=seq)).rowcount
    if not updated:
        conn.execute(insert(sync_cursor).values(user_id=user_id, seq=seq))


def push(conn: Connection, user_id: str, records: list[Record]) -> int:
    """Upsert each record (LWW by version), assigning the next per-user seq to each stored one. Returns the new high
    seq. Runs in the caller's transaction."""
    seq = _current_seq(conn, user_id, lock=True)
    for r in records:
        existing = conn.execute(
            select(sync_records.c.version).where(
                sync_records.c.user_id == user_id,
                sync_records.c.collection == r.collection,
                sync_records.c.record_id == r.record_id,
            )
        ).first()
        if existing is not None and r.version <= int(existing[0]):
            continue  # not newer → ignore (LWW)
        seq += 1
        values = dict(
            version=r.version,
            deleted=1 if r.deleted else 0,
            ciphertext=None if r.deleted else r.ciphertext,
            seq=seq,
        )
        if existing is None:
            conn.execute(
                insert(sync_records).values(user_id=user_id, collection=r.collection, record_id=r.record_id, **values)
            )
        else:
            conn.execute(
                update(sync_records)
                .where(
                    sync_records.c.user_id == user_id,
                    sync_records.c.collection == r.collection,
                    sync_records.c.record_id == r.record_id,
                )
                .values(**values)
            )
    _set_seq(conn, user_id, seq)
    return seq


def pull(conn: Connection, user_id: str, since: int) -> tuple[list[Record], int]:
    """The user's records with ``seq > since`` (ordered), plus the user's current high seq."""
    rows = conn.execute(
        select(sync_records)
        .where(sync_records.c.user_id == user_id, sync_records.c.seq > since)
        .order_by(sync_records.c.seq)
    ).mappings()
    records = [
        Record(
            collection=row["collection"],
            record_id=row["record_id"],
            version=int(row["version"]),
            deleted=bool(row["deleted"]),
            ciphertext=row["ciphertext"],
        )
        for row in rows
    ]
    return records, _current_seq(conn, user_id, lock=False)
