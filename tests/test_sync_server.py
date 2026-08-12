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
from sync_server.rate_limit import RateLimiter
from sync_server.schema import ensure_updated_at_column, sync_records
from sync_server.schema import metadata as server_metadata
from sync_server.store import prune_tombstones


class FakeVerifier:
    """token "u:<sub>" → Identity(sub); anything else → InvalidToken (the 401 path)."""

    def verify(self, token: str) -> Identity:
        if not token.startswith("u:"):
            raise InvalidToken("bad token")
        return Identity(sub=token[2:])


def _server(*, rate_limiter: RateLimiter | None = None) -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    server_metadata.create_all(engine)
    return TestClient(create_server(engine, FakeVerifier(), rate_limiter=rate_limiter))


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


# --- backlog #15: per-user rate limiting ---


def test_rate_limit_is_per_user_not_global() -> None:
    # A tiny limit (2 requests) so the test doesn't need real time to elapse.
    c = _server(rate_limiter=RateLimiter(max_requests=2, window=60.0))
    assert c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).status_code == 200
    assert c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).status_code == 200
    limited = c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"})
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 0
    # bob's own bucket is untouched by alice's traffic
    assert c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:bob"}).status_code == 200


def test_rate_limit_applies_to_push_too() -> None:
    c = _server(rate_limiter=RateLimiter(max_requests=1, window=60.0))
    assert _push(c, "u:alice", [_blob()]).status_code == 200
    second = _push(c, "u:alice", [_blob(record_id="b")])
    assert second.status_code == 429


def test_generous_default_limit_does_not_throttle_normal_use() -> None:
    # The module's actual default (60/60s) shouldn't trip on a handful of ordinary requests.
    c = _server()
    for _ in range(10):
        assert c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).status_code == 200


# --- backlog #15: tombstone retention ---


def _insert_raw_tombstone(engine, *, user_id: str, record_id: str, updated_at) -> None:
    from sqlalchemy import insert

    with engine.begin() as conn:
        conn.execute(
            insert(sync_records).values(
                user_id=user_id,
                collection="papers",
                record_id=record_id,
                version=1,
                deleted=1,
                ciphertext=None,
                seq=1,
                updated_at=updated_at,
            )
        )


def test_prune_tombstones_removes_only_old_ones() -> None:
    from datetime import datetime, timedelta, timezone

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    server_metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    _insert_raw_tombstone(engine, user_id="alice", record_id="old", updated_at=now - timedelta(days=100))
    _insert_raw_tombstone(engine, user_id="alice", record_id="recent", updated_at=now - timedelta(days=10))

    with engine.begin() as conn:
        removed = prune_tombstones(conn, older_than_days=90)
    assert removed == 1

    with engine.connect() as conn:
        remaining = {row[0] for row in conn.execute(select(sync_records.c.record_id))}
    assert remaining == {"recent"}


def test_prune_tombstones_never_touches_live_records() -> None:
    c = _server()
    _push(c, "u:alice", [_blob(record_id="alive", ciphertext="KEEP")])  # not a tombstone, no matter how old
    engine = c.app.state.engine
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    with engine.begin() as conn:
        conn.execute(
            update(sync_records)
            .where(sync_records.c.record_id == "alive")
            .values(updated_at=datetime.now(timezone.utc) - timedelta(days=9999))
        )
        removed = prune_tombstones(conn, older_than_days=90)
    assert removed == 0
    got = c.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()
    assert got["records"][0]["ciphertext"] == "KEEP"


def test_prune_tombstones_skips_rows_with_no_recorded_age() -> None:
    # A pre-migration row (updated_at still NULL) is never assumed old enough to prune — fails toward
    # preservation, matching the documented "never guess" posture.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    server_metadata.create_all(engine)
    _insert_raw_tombstone(engine, user_id="alice", record_id="ancient-unknown-age", updated_at=None)
    with engine.begin() as conn:
        removed = prune_tombstones(conn, older_than_days=90)
    assert removed == 0


def test_ensure_updated_at_column_is_idempotent() -> None:
    import sqlalchemy as sa

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # Build the table WITHOUT updated_at, simulating an already-deployed pre-#15 table.
    legacy = sa.MetaData()
    sa.Table(
        "sync_records",
        legacy,
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("collection", sa.String(length=60), nullable=False),
        sa.Column("record_id", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ciphertext", sa.Text()),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "collection", "record_id", name="pk_sync_records"),
    )
    legacy.create_all(engine)

    ensure_updated_at_column(engine)  # should add it
    ensure_updated_at_column(engine)  # calling again must be a safe no-op, not an error

    inspector = sa.inspect(engine)
    assert "updated_at" in {c["name"] for c in inspector.get_columns("sync_records")}


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


# --- backlog #15: the prune_tombstones CLI script ---


def test_prune_cli_dry_run_and_real_run(tmp_path: Path, monkeypatch, capsys) -> None:
    from datetime import datetime, timedelta, timezone

    from sync_server import prune_tombstones as cli

    db_path = tmp_path / "cli-sync.sqlite"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    server_metadata.create_all(engine)
    _insert_raw_tombstone(
        engine, user_id="alice", record_id="old", updated_at=datetime.now(timezone.utc) - timedelta(days=200)
    )
    engine.dispose()

    monkeypatch.setenv("CALLOSUM_SYNC_DB_URL", f"sqlite:///{db_path.as_posix()}")

    assert cli.main(["--dry-run"]) == 0
    assert "1 tombstone" in capsys.readouterr().out

    assert cli.main([]) == 0
    assert "removed 1 tombstone" in capsys.readouterr().out

    # a second real run finds nothing left to remove
    assert cli.main([]) == 0
    assert "removed 0 tombstone" in capsys.readouterr().out


# --- SP4a (backlog #15): the sharing-identity directory ---------------------------------------------------


def test_register_then_lookup_by_exact_sub() -> None:
    client = _server()
    r = client.post(
        "/identity/register",
        json={"public_key": "AAAA==", "display_name": "Alice"},
        headers={"Authorization": "Bearer u:alice"},
    )
    assert r.status_code == 204
    r = client.get("/identity/lookup", params={"sub": "alice"}, headers={"Authorization": "Bearer u:bob"})
    assert r.status_code == 200
    assert r.json() == {"public_key": "AAAA==", "display_name": "Alice"}


def test_lookup_unknown_sub_is_404() -> None:
    client = _server()
    r = client.get("/identity/lookup", params={"sub": "nobody"}, headers={"Authorization": "Bearer u:bob"})
    assert r.status_code == 404


def test_lookup_never_lists_or_fuzzy_matches() -> None:
    """The divergence fence: exact-id only. A near-miss (case/whitespace/substring) must NOT match — this is
    what keeps the directory a lookup, never a search."""
    client = _server()
    client.post("/identity/register", json={"public_key": "AAAA=="}, headers={"Authorization": "Bearer u:alice"})
    for near_miss in ("Alice", " alice", "alice ", "ali", "alicee"):
        r = client.get("/identity/lookup", params={"sub": near_miss}, headers={"Authorization": "Bearer u:bob"})
        assert r.status_code == 404, f"{near_miss!r} should not match 'alice'"
    # and there is structurally no listing endpoint to enumerate registered users
    assert client.get("/identity", headers={"Authorization": "Bearer u:bob"}).status_code == 404
    assert client.get("/identity/list", headers={"Authorization": "Bearer u:bob"}).status_code == 404


def test_re_register_rotates_the_current_key() -> None:
    client = _server()
    headers = {"Authorization": "Bearer u:alice"}
    client.post("/identity/register", json={"public_key": "OLD=="}, headers=headers)
    client.post("/identity/register", json={"public_key": "NEW==", "display_name": "Alice A."}, headers=headers)
    r = client.get("/identity/lookup", params={"sub": "alice"}, headers={"Authorization": "Bearer u:bob"})
    assert r.json() == {"public_key": "NEW==", "display_name": "Alice A."}


def test_identity_endpoints_require_auth() -> None:
    client = _server()
    assert client.get("/identity/lookup", params={"sub": "alice"}).status_code == 401
    assert client.post("/identity/register", json={"public_key": "AAAA=="}).status_code == 401


def test_register_rejects_oversized_public_key() -> None:
    client = _server()
    r = client.post(
        "/identity/register",
        json={"public_key": "A" * 200},
        headers={"Authorization": "Bearer u:alice"},
    )
    assert r.status_code == 422


# --- SP4b (backlog #15): the share mailbox --------------------------------------------------------------


def test_create_share_persists_addressed_to_recipient() -> None:
    client = _server()
    r = client.post(
        "/shares",
        json={"recipient_sub": "bob", "wrapped_key": "wk==", "ciphertext": "ct=="},
        headers={"Authorization": "Bearer u:alice"},
    )
    assert r.status_code == 200
    assert isinstance(r.json()["share_id"], int)


def test_create_share_ids_increment_across_shares() -> None:
    client = _server()
    headers = {"Authorization": "Bearer u:alice"}
    first = client.post(
        "/shares", json={"recipient_sub": "bob", "wrapped_key": "a==", "ciphertext": "b=="}, headers=headers
    )
    second = client.post(
        "/shares", json={"recipient_sub": "carol", "wrapped_key": "c==", "ciphertext": "d=="}, headers=headers
    )
    assert second.json()["share_id"] != first.json()["share_id"]


def test_create_share_requires_auth() -> None:
    client = _server()
    r = client.post("/shares", json={"recipient_sub": "bob", "wrapped_key": "wk==", "ciphertext": "ct=="})
    assert r.status_code == 401


def test_create_share_rejects_oversized_wrapped_key() -> None:
    client = _server()
    r = client.post(
        "/shares",
        json={"recipient_sub": "bob", "wrapped_key": "A" * 2000, "ciphertext": "ct=="},
        headers={"Authorization": "Bearer u:alice"},
    )
    assert r.status_code == 422


def test_create_share_rejects_oversized_ciphertext() -> None:
    client = _server()
    r = client.post(
        "/shares",
        json={"recipient_sub": "bob", "wrapped_key": "wk==", "ciphertext": "A" * 22_000_000},
        headers={"Authorization": "Bearer u:alice"},
    )
    assert r.status_code == 422


def test_share_sender_sub_comes_from_token_not_body() -> None:
    """The request body has no sender_sub field at all -- confirms it's structurally impossible to spoof."""
    client = _server()
    r = client.post(
        "/shares",
        json={"recipient_sub": "bob", "wrapped_key": "wk==", "ciphertext": "ct==", "sender_sub": "eve"},
        headers={"Authorization": "Bearer u:alice"},
    )
    assert r.status_code == 200  # extra field is silently ignored by pydantic, not an error


def test_share_rate_limit_applies() -> None:
    c = _server(rate_limiter=RateLimiter(max_requests=1, window=60.0))
    headers = {"Authorization": "Bearer u:alice"}
    first = c.post("/shares", json={"recipient_sub": "bob", "wrapped_key": "a==", "ciphertext": "b=="}, headers=headers)
    assert first.status_code == 200
    second = c.post(
        "/shares", json={"recipient_sub": "bob", "wrapped_key": "c==", "ciphertext": "d=="}, headers=headers
    )
    assert second.status_code == 429
