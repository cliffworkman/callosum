"""SP3b — the reference sync-server (`sync_server/`) + the client `HttpSyncTransport`, in-process (no socket, no
live Authentik: an injected fake `TokenVerifier`; a SQLite engine via StaticPool so all requests share one DB).

Covers the server contract (round-trip, LWW-by-version, per-user tenant isolation, the `since` cursor, 401 on a bad
token, body caps) AND the full stack end-to-end: two devices converge driven through the **real** HTTP transport →
server → store → back (not the fake transport) — the inc-198..201 scenarios over the wire.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from alembic import command
from alembic.config import Config
from app.backend.persistence import schema
from app.backend.persistence.repository import create_paper
from app.backend.sync.crypto import create_keyring, unlock_with_passphrase
from app.backend.sync.engine import run_sync
from app.backend.sync.transport import HttpSyncTransport, SyncServerError
from sync_server.app import create_server
from sync_server.auth import Identity, InvalidToken
from sync_server.schema import metadata as server_metadata


class FakeVerifier:
    """token "u:<sub>" → Identity(sub); anything else → InvalidToken (the 401 path)."""

    def verify(self, token: str) -> Identity:
        if not token.startswith("u:"):
            raise InvalidToken("bad token")
        return Identity(sub=token[2:])


def _server() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    server_metadata.create_all(engine)
    return TestClient(create_server(engine, FakeVerifier()))


def _push(client: TestClient, token: str, records: list[dict]):
    return client.post("/sync/records", json={"records": records}, headers={"Authorization": f"Bearer {token}"})


def _blob(collection="papers", record_id="u1", version=1, deleted=False, ciphertext="ZW5j"):
    return {
        "collection": collection,
        "record_id": record_id,
        "version": version,
        "deleted": deleted,
        "ciphertext": ciphertext,
    }


# --- server contract ---


def test_push_pull_roundtrip_and_seq() -> None:
    c = _server()
    r = _push(c, "u:alice", [_blob(record_id="a", ciphertext="AAA"), _blob(record_id="b", ciphertext="BBB")])
    assert r.status_code == 200 and r.json()["seq"] == 2
    got = c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()
    assert {x["record_id"]: x["ciphertext"] for x in got["records"]} == {"a": "AAA", "b": "BBB"}
    assert got["seq"] == 2
    assert c.get("/sync/records?since=2", headers={"Authorization": "Bearer u:alice"}).json()["records"] == []


def test_last_write_wins_by_version() -> None:
    c = _server()
    _push(c, "u:alice", [_blob(record_id="a", version=1, ciphertext="V1")])
    _push(c, "u:alice", [_blob(record_id="a", version=2, ciphertext="V2")])
    _push(c, "u:alice", [_blob(record_id="a", version=1, ciphertext="STALE")])  # older → ignored
    got = c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()
    assert len(got["records"]) == 1 and got["records"][0]["ciphertext"] == "V2" and got["records"][0]["version"] == 2


def test_tenant_isolation() -> None:
    c = _server()
    _push(c, "u:alice", [_blob(record_id="secret", ciphertext="ALICE")])
    bob = c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:bob"}).json()
    assert bob["records"] == [] and bob["seq"] == 0  # bob can't see alice's rows
    # bob pushing the same record_id doesn't touch alice's
    _push(c, "u:bob", [_blob(record_id="secret", version=5, ciphertext="BOB")])
    alice = c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()
    assert alice["records"][0]["ciphertext"] == "ALICE"


def test_tombstone_carries_no_ciphertext() -> None:
    c = _server()
    _push(c, "u:alice", [_blob(record_id="a", version=2, deleted=True, ciphertext="should-be-dropped")])
    rec = c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()["records"][0]
    assert rec["deleted"] is True and rec["ciphertext"] is None


def test_auth_required() -> None:
    c = _server()
    assert c.get("/sync/records?since=0").status_code == 401  # no token
    assert c.get("/sync/records?since=0", headers={"Authorization": "Bearer nope"}).status_code == 401  # bad token
    assert _push(c, "nope", [_blob()]).status_code == 401
    assert c.get("/health").json()["status"] == "ok"  # health needs no auth


def test_push_record_cap() -> None:
    c = _server()
    too_many = [_blob(record_id=f"r{i}") for i in range(1001)]
    assert _push(c, "u:alice", too_many).status_code == 422  # MAX_RECORDS_PER_PUSH


def test_unconfigured_server_refuses() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    server_metadata.create_all(engine)
    c = TestClient(create_server(engine, None))  # no verifier → default-closed
    assert c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).status_code == 503


# --- end-to-end: two devices converge through the real HTTP transport → server → store ---


def _fresh_db(path: Path) -> str:
    db_url = f"sqlite:///{path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    return db_url


def _add_paper(db_url: str, title: str) -> int:
    eng = create_engine(db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title=title, csl_json={"title": title, "type": "article-journal"})
    eng.dispose()
    return pid


def test_two_devices_converge_over_http(tmp_path: Path) -> None:
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")  # the same account/vault on both devices
    server = _server()
    transport = HttpSyncTransport(base_url="", token="u:alice", client=server)  # both devices = one account

    db_a, db_b = _fresh_db(tmp_path / "a.sqlite"), _fresh_db(tmp_path / "b.sqlite")
    _add_paper(db_a, "Alpha")
    _add_paper(db_b, "Beta")
    ea, eb = create_engine(db_a), create_engine(db_b)
    ca = cb = 0

    with ea.begin() as conn:
        ca = run_sync(conn, dek, transport, since=ca).new_cursor  # A pushes Alpha to the server
    with eb.begin() as conn:
        rb = run_sync(conn, dek, transport, since=cb)  # B pushes Beta, pulls + applies Alpha
        cb = rb.new_cursor
    with ea.begin() as conn:
        ca = run_sync(conn, dek, transport, since=ca).new_cursor  # A pulls Beta

    def _titles(eng):
        with eng.connect() as conn:
            return set(conn.execute(select(schema.papers.c.title)).scalars())

    assert _titles(ea) == _titles(eb) == {"Alpha", "Beta"}  # converged over the wire
    with eb.begin() as conn:
        again = run_sync(conn, dek, transport, since=cb)
    assert again.pushed == 0 and again.applied == 0  # idempotent through the real transport
    ea.dispose()
    eb.dispose()


def test_transport_fails_closed_on_error() -> None:
    c = _server()
    transport = HttpSyncTransport(base_url="", token="bad", client=c)  # 401 from the server
    with pytest.raises(SyncServerError):
        transport.pull(0)
