"""SP3b — the client sync engine (pull → decrypt → merge → apply → push) over a fake in-memory transport.

No egress: a ``FakeTransport`` stands in for the (next-slice) server. The headline proof is **two simulated devices
with independent local ids converge via ``sync_uid``** — i.e. the identity layer actually does its job. Plus: a
concurrent edit surfaces a recoverable conflict (A4), a tombstone propagates a delete and re-sync is idempotent, and
a foreign/tampered remote blob fails closed (nothing is written as garbage).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, select, update

from alembic import command
from alembic.config import Config
from app.backend.persistence import schema
from app.backend.persistence.repository import create_paper
from app.backend.sync.crypto import SyncCryptoError, create_keyring, encrypt_payload, unlock_with_passphrase
from app.backend.sync.engine import PullResult, SyncBlob, run_sync


class FakeTransport:
    """An in-memory server: keeps the latest blob per (collection, record_id) at a monotonic sequence, enforcing LWW
    by version (a push of an older/equal version is ignored). pull returns blobs with seq > since + the high seq."""

    def __init__(self) -> None:
        self._seq = 0
        self._store: dict[tuple[str, str], dict] = {}

    def push(self, records: list[SyncBlob]) -> int:
        for b in records:
            cur = self._store.get((b.collection, b.record_id))
            if cur is None or b.version > cur["blob"].version:
                self._seq += 1
                self._store[(b.collection, b.record_id)] = {"blob": b, "seq": self._seq}
        return self._seq

    def pull(self, since: int) -> PullResult:
        entries = sorted(self._store.values(), key=lambda e: e["seq"])
        return PullResult(records=[e["blob"] for e in entries if e["seq"] > since], seq=self._seq)


def _fresh_db(path: Path) -> str:
    db_url = f"sqlite:///{path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    return db_url


def _add_paper(db_url: str, title: str, year: int) -> int:
    eng = create_engine(db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title=title, year=year, csl_json={"title": title, "type": "article-journal"})
    eng.dispose()
    return pid


def _sync(eng, dek, server, since: int):
    with eng.begin() as conn:
        return run_sync(conn, dek, server, since=since)


def _uid_to_title(eng) -> dict[str, str]:
    with eng.connect() as conn:
        rows = conn.execute(
            select(schema.sync_identity.c.sync_uid, schema.sync_identity.c.local_id).where(
                schema.sync_identity.c.collection == "papers"
            )
        ).all()
        out: dict[str, str] = {}
        for uid, local_id in rows:
            title = conn.execute(select(schema.papers.c.title).where(schema.papers.c.id == int(local_id))).scalar()
            if title is not None:  # skip a forgotten/stale mapping
                out[uid] = title
        return out


def _uid_to_localid(eng) -> dict[str, str]:
    with eng.connect() as conn:
        return {
            uid: str(local_id)
            for uid, local_id in conn.execute(
                select(schema.sync_identity.c.sync_uid, schema.sync_identity.c.local_id).where(
                    schema.sync_identity.c.collection == "papers"
                )
            )
        }


def _titles(eng) -> set[str]:
    with eng.connect() as conn:
        return set(conn.execute(select(schema.papers.c.title)).scalars())


def test_two_devices_converge_via_sync_uid(tmp_path: Path) -> None:
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")  # same vault unlocked on both devices
    server = FakeTransport()

    db_a, db_b = _fresh_db(tmp_path / "a.sqlite"), _fresh_db(tmp_path / "b.sqlite")
    _add_paper(db_a, "Alpha", 2020)
    _add_paper(db_a, "Beta", 2021)
    _add_paper(db_b, "Gamma", 2022)  # B's own paper gets local id 1 — same int A's "Alpha" uses
    ea, eb = create_engine(db_a), create_engine(db_b)
    ca = cb = 0

    ca = _sync(ea, dek, server, ca).new_cursor  # A pushes Alpha, Beta
    rb = _sync(eb, dek, server, cb)  # B pushes Gamma, pulls + applies Alpha, Beta
    cb = rb.new_cursor
    assert rb.pushed == 1 and rb.applied == 2
    ca = _sync(ea, dek, server, ca).new_cursor  # A pulls + applies Gamma

    assert _titles(ea) == _titles(eb) == {"Alpha", "Beta", "Gamma"}
    # same GLOBAL identity set + same content per uid, but DIFFERENT local ids → the identity layer earns its keep
    assert _uid_to_title(ea) == _uid_to_title(eb)
    assert _uid_to_localid(ea) != _uid_to_localid(eb)

    # converged → another round on each side pushes nothing + applies nothing (proves the content-hash round-trip
    # through encrypt/decrypt + the datetime coercion is stable — no phantom re-sync)
    again = _sync(eb, dek, server, cb)
    assert again.pushed == 0 and again.applied == 0 and again.conflicts == 0

    ea.dispose()
    eb.dispose()


def test_concurrent_edit_surfaces_conflict(tmp_path: Path) -> None:
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")
    server = FakeTransport()
    db_a, db_b = _fresh_db(tmp_path / "a.sqlite"), _fresh_db(tmp_path / "b.sqlite")
    _add_paper(db_a, "Original", 2020)
    ea, eb = create_engine(db_a), create_engine(db_b)
    ca = cb = 0

    ca = _sync(ea, dek, server, ca).new_cursor  # A pushes Original
    cb = _sync(eb, dek, server, cb).new_cursor  # B pulls it → both share the paper (same uid) at v1

    with ea.begin() as conn:  # A edits + syncs (server now has v2 = "A-edit")
        conn.execute(update(schema.papers).values(title="A-edit"))
    ca = _sync(ea, dek, server, ca).new_cursor

    with eb.begin() as conn:  # B edits the SAME paper locally, NOT yet synced
        conn.execute(update(schema.papers).values(title="B-edit"))
    rb = _sync(eb, dek, server, cb)  # B pulls A's v2 → conflict; remote wins, B's edit kept for recovery

    assert rb.conflicts == 1
    with eb.connect() as conn:
        assert conn.execute(select(schema.papers.c.title)).scalar() == "A-edit"  # remote (higher version) wins
        losing = conn.execute(select(schema.sync_conflicts.c.losing_payload)).scalar()
        assert losing is not None and losing.get("title") == "B-edit"  # the local loser is recoverable (A4)
    ea.dispose()
    eb.dispose()


def test_tombstone_propagates_and_resync_is_idempotent(tmp_path: Path) -> None:
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")
    server = FakeTransport()
    db_a, db_b = _fresh_db(tmp_path / "a.sqlite"), _fresh_db(tmp_path / "b.sqlite")
    _add_paper(db_a, "Doomed", 2020)
    ea, eb = create_engine(db_a), create_engine(db_b)
    ca = cb = 0

    ca = _sync(ea, dek, server, ca).new_cursor
    cb = _sync(eb, dek, server, cb).new_cursor  # B has the paper
    assert _titles(eb) == {"Doomed"}

    with ea.begin() as conn:  # A deletes it locally, then syncs → a tombstone goes to the server
        conn.execute(delete(schema.papers))
    ca = _sync(ea, dek, server, ca).new_cursor

    rb = _sync(eb, dek, server, cb)  # B pulls the tombstone → its row is deleted
    cb = rb.new_cursor
    assert rb.applied == 1 and _titles(eb) == set()

    again = _sync(eb, dek, server, cb)  # re-sync: no resurrection, no duplicate, no error
    assert again.applied == 0 and again.pushed == 0 and _titles(eb) == set()
    ea.dispose()
    eb.dispose()


def test_foreign_remote_blob_fails_closed(tmp_path: Path) -> None:
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")
    other, _ = create_keyring("pw")
    foreign_dek = unlock_with_passphrase(other, "pw")  # a different vault's DEK

    server = FakeTransport()
    server.push([SyncBlob("papers", "uid-x", 1, False, encrypt_payload(foreign_dek, {"title": "x"}))])
    eng = create_engine(_fresh_db(tmp_path / "d.sqlite"))
    with pytest.raises(SyncCryptoError):  # can't open a blob sealed under a key we don't hold → never written
        with eng.begin() as conn:
            run_sync(conn, dek, server)
    with eng.connect() as conn:
        assert conn.execute(select(schema.papers.c.id)).first() is None  # nothing written
    eng.dispose()
