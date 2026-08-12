"""SP3b — the opt-in local `/sync/*` endpoints (setup / settings / status / run): the consent gate + the wiring that
makes E2E sync usable. Hermetic (the autouse conftest isolates CALLOSUM_SETTINGS_PATH per test); the happy path runs
through an injected `HttpSyncTransport` bound to an in-process sync-server (no socket, no live Authentik).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.pool import StaticPool

from alembic import command
from alembic.config import Config
from app.backend import app_settings
from app.backend.api import create_app
from app.backend.persistence import schema
from app.backend.persistence.repository import create_paper
from app.backend.sync.crypto import create_keyring, unlock_with_passphrase
from app.backend.sync.engine import PullResult, SyncBlob, run_sync
from app.backend.sync.transport import HttpSyncTransport
from sync_server.app import create_server
from sync_server.auth import Identity, InvalidToken
from sync_server.schema import metadata as server_metadata


class _FakeVerifier:
    def verify(self, token: str) -> Identity:
        if not token.startswith("u:"):
            raise InvalidToken("bad token")
        return Identity(sub=token[2:])


def _sync_server() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    server_metadata.create_all(engine)
    return TestClient(create_server(engine, _FakeVerifier()))


def _add_paper(db_url: str, title: str) -> None:
    eng = create_engine(db_url)
    with eng.begin() as conn:
        create_paper(conn, title=title, csl_json={"title": title, "type": "article-journal"})
    eng.dispose()


def _sign_in() -> None:
    app_settings.set_oauth_session({"access_token": "u:alice", "sub": "alice"})


def test_status_defaults_off(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    s = c.get("/sync/status").json()
    assert s == {"enabled": False, "configured": False, "signed_in": False, "server_url": None, "last_cursor": 0}


def test_setup_returns_recovery_once_then_409(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    r = c.post("/sync/setup", json={"passphrase": "correct horse"})
    assert r.status_code == 200 and r.json()["recovery_code"]  # shown once
    assert c.get("/sync/status").json()["configured"] is True
    assert "recovery_code" not in c.get("/sync/status").json()  # never via status
    assert c.post("/sync/setup", json={"passphrase": "again"}).status_code == 409  # don't silently re-key


def test_enable_requires_setup_signin_and_url(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    # not configured / not signed-in / no url → each fails closed
    assert c.put("/sync/settings", json={"enabled": True, "server_url": "https://s"}).status_code == 422
    c.post("/sync/setup", json={"passphrase": "pw"})
    assert (
        c.put("/sync/settings", json={"enabled": True, "server_url": "https://s"}).status_code == 422
    )  # not signed in
    _sign_in()
    assert c.put("/sync/settings", json={"enabled": True, "server_url": ""}).status_code == 422  # no url
    ok = c.put("/sync/settings", json={"enabled": True, "server_url": "https://s"})
    assert ok.status_code == 200 and ok.json()["enabled"] is True


def test_run_refused_when_off_or_wrong_passphrase(temp_db_url: str) -> None:
    c = TestClient(
        create_app(db_url=temp_db_url, sync_transport=HttpSyncTransport("", "u:alice", client=_sync_server()))
    )
    assert c.post("/sync/run", json={"passphrase": "pw"}).status_code == 409  # off
    c.post("/sync/setup", json={"passphrase": "pw"})
    _sign_in()
    c.put("/sync/settings", json={"enabled": True, "server_url": "https://s"})
    # 422, not 401 — the frontend's api* helpers treat any 401 as the unrelated remote-access lockout (inc 254)
    assert c.post("/sync/run", json={"passphrase": "WRONG"}).status_code == 422  # wrong passphrase fails closed


def test_run_happy_path_syncs_and_advances_cursor(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _add_paper(temp_db_url, "Solo")
    _sign_in()
    c.post("/sync/setup", json={"passphrase": "pw"})
    c.put("/sync/settings", json={"enabled": True, "server_url": "https://s"})

    r = c.post("/sync/run", json={"passphrase": "pw"})
    assert r.status_code == 200
    body = r.json()
    assert body["pushed"] >= 1  # the paper actually pushed
    # it really reached the server (real egress over the transport) — as opaque ciphertext
    stored = server.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()["records"]
    assert len(stored) >= 1 and stored[0]["ciphertext"]
    assert c.get("/sync/status").json()["last_cursor"] == body["cursor"]  # cursor persisted (mirrors the run)

    again = c.post("/sync/run", json={"passphrase": "pw"}).json()  # converged → idempotent; cursor catches up
    assert again["pushed"] == 0 and again["applied"] == 0
    assert again["cursor"] > body["cursor"]  # the cursor advances past our own first-round pushes


def test_run_with_wrong_passphrase_does_not_egress(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _add_paper(temp_db_url, "Secret")
    _sign_in()
    c.post("/sync/setup", json={"passphrase": "pw"})
    c.put("/sync/settings", json={"enabled": True, "server_url": "https://s"})
    assert c.post("/sync/run", json={"passphrase": "nope"}).status_code == 422
    # nothing reached the server (the bad passphrase fails before the transport is used)
    assert server.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()["records"] == []


# --- token refresh: a sync run can happen well after the original sign-in, so a near/past-expiry access token
# must be refreshed via the stored refresh_token before it's used against the sync server ---


class _FakeRefreshClient:
    """No network — records each refresh call so tests can assert it happened (or didn't)."""

    def __init__(self) -> None:
        self.refreshed_with: list[str] = []

    def refresh_access_token(self, refresh_token: str) -> dict:
        self.refreshed_with.append(refresh_token)
        return {"access_token": "u:alice-refreshed", "refresh_token": "new-refresh", "expires_in": 300}


def test_run_refreshes_a_near_expired_access_token(temp_db_url: str) -> None:
    fake = _FakeRefreshClient()
    c = TestClient(create_app(db_url=temp_db_url, oidc_client=fake))
    app_settings.set_oauth_session(
        {"access_token": "u:alice", "refresh_token": "old-refresh", "sub": "alice", "expires_at": 1}
    )
    c.post("/sync/run", json={"passphrase": "pw"})  # 409 (sync off) — refresh already ran before that gate
    assert fake.refreshed_with == ["old-refresh"]
    session = app_settings.stored_oauth_session()
    assert session["access_token"] == "u:alice-refreshed" and session["refresh_token"] == "new-refresh"
    assert session["expires_at"] > time.time()


def test_run_does_not_refresh_a_still_valid_token(temp_db_url: str) -> None:
    fake = _FakeRefreshClient()
    c = TestClient(create_app(db_url=temp_db_url, oidc_client=fake))
    app_settings.set_oauth_session(
        {"access_token": "u:alice", "refresh_token": "old-refresh", "sub": "alice", "expires_at": time.time() + 3600}
    )
    c.post("/sync/run", json={"passphrase": "pw"})
    assert fake.refreshed_with == []  # comfortably valid — no needless refresh call
    assert app_settings.stored_oauth_session()["access_token"] == "u:alice"


@pytest.mark.parametrize("passphrase", ["", " " * 3])
def test_setup_rejects_blank_passphrase(temp_db_url: str, passphrase: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    assert c.post("/sync/setup", json={"passphrase": passphrase}).status_code == 422


# --- SP3c: /sync/conflicts (list + resolve) --------------------------------------------------------------------
# These two endpoints are deliberately NOT gated on enabled/signed-in/configured (a conflict is local data from a
# past sync run), so the tests below hit them directly against a database that already has one — produced via the
# same two-simulated-devices recipe as tests/test_sync_engine.py, but through engine.run_sync directly (bypassing
# app_settings/API-layer sign-in state, which — unlike the db — is a single shared store per test process, not
# something that can represent two independent "devices" the way two separate sqlite files can).


class _FakeTransport:
    """A minimal in-memory server for engine.run_sync: latest blob per (collection, record_id) at a monotonic
    sequence, LWW by version. Mirrors test_sync_engine.py's FakeTransport."""

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


def _make_conflict(tmp_path: Path) -> str:
    """Two simulated devices edit the same paper concurrently; B's edit loses (A syncs first) and is surfaced as
    a conflict in B's database. Returns db_b's URL, which now holds exactly one unresolved conflict."""
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")
    server = _FakeTransport()
    db_a, db_b = _fresh_db(tmp_path / "a.sqlite"), _fresh_db(tmp_path / "b.sqlite")
    _add_paper(db_a, "Original")
    ea, eb = create_engine(db_a), create_engine(db_b)

    def _run(eng, since: int) -> int:
        with eng.begin() as conn:
            return run_sync(conn, dek, server, since=since).new_cursor

    ca, cb = _run(ea, 0), _run(eb, 0)  # B pulls A's "Original" → both share the paper at v1
    with ea.begin() as conn:
        conn.execute(update(schema.papers).values(title="A-edit"))
    ca = _run(ea, ca)  # server now has v2 = "A-edit"
    with eb.begin() as conn:
        conn.execute(update(schema.papers).values(title="B-edit"))  # B's own, not-yet-synced edit
    with eb.begin() as conn:
        result = run_sync(conn, dek, server, since=cb)  # B pulls A's v2 → conflict; remote wins, B's edit kept
    assert result.conflicts == 1
    ea.dispose()
    eb.dispose()
    return db_b


def test_list_conflicts_shows_mine_and_current(tmp_path: Path) -> None:
    db_b = _make_conflict(tmp_path)
    c = TestClient(create_app(db_url=db_b))
    listed = c.get("/sync/conflicts").json()
    assert len(listed) == 1
    conflict = listed[0]
    assert conflict["collection"] == "papers"
    assert conflict["losing_payload"]["title"] == "B-edit"  # mine
    assert conflict["current"]["title"] == "A-edit"  # theirs (already applied to the domain row)


def test_resolve_theirs_just_marks_resolved(tmp_path: Path) -> None:
    db_b = _make_conflict(tmp_path)
    c = TestClient(create_app(db_url=db_b))
    conflict_id = c.get("/sync/conflicts").json()[0]["id"]
    r = c.post(f"/sync/conflicts/{conflict_id}/resolve", json={"side": "theirs"})
    assert r.status_code == 200 and r.json() == {"resolved": True}
    assert c.get("/sync/conflicts").json() == []  # no longer listed
    eng = create_engine(db_b)
    with eng.connect() as conn:
        assert conn.execute(select(schema.papers.c.title)).scalar() == "A-edit"  # untouched — theirs already won
    eng.dispose()


def test_resolve_mine_restores_the_losing_value(tmp_path: Path) -> None:
    db_b = _make_conflict(tmp_path)
    c = TestClient(create_app(db_url=db_b))
    conflict_id = c.get("/sync/conflicts").json()[0]["id"]
    r = c.post(f"/sync/conflicts/{conflict_id}/resolve", json={"side": "mine"})
    assert r.status_code == 200 and r.json() == {"resolved": True}
    assert c.get("/sync/conflicts").json() == []
    eng = create_engine(db_b)
    with eng.connect() as conn:
        assert conn.execute(select(schema.papers.c.title)).scalar() == "B-edit"  # restored
    eng.dispose()


def test_resolve_unknown_or_already_resolved_conflict_fails_closed(tmp_path: Path) -> None:
    db_b = _make_conflict(tmp_path)
    c = TestClient(create_app(db_url=db_b))
    assert c.post("/sync/conflicts/999/resolve", json={"side": "theirs"}).status_code == 409
    conflict_id = c.get("/sync/conflicts").json()[0]["id"]
    c.post(f"/sync/conflicts/{conflict_id}/resolve", json={"side": "theirs"})
    assert c.post(f"/sync/conflicts/{conflict_id}/resolve", json={"side": "mine"}).status_code == 409


# --- SP4a (backlog #15): sharing identity ------------------------------------------------------------------


def _sync_ready(c: TestClient, *, passphrase: str = "pw") -> None:
    """Setup + sign-in + enable — the shared precondition every identity endpoint (like /sync/run) requires."""
    c.post("/sync/setup", json={"passphrase": passphrase})
    _sign_in()
    c.put("/sync/settings", json={"enabled": True, "server_url": "https://s"})


def test_identity_status_defaults_to_no_identity(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    assert c.get("/sync/identity/status").json() == {"has_identity": False, "fingerprint": None, "own_sub": None}


def test_identity_setup_happy_path_registers_and_returns_fingerprint(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _sync_ready(c)

    r = c.post("/sync/identity/setup", json={"passphrase": "pw"})
    assert r.status_code == 200
    body = r.json()
    assert body["own_sub"] == "alice" and body["fingerprint"]
    assert set(body) == {"fingerprint", "own_sub"}  # never the private key, never the raw public key either

    status = c.get("/sync/identity/status").json()
    assert status == {"has_identity": True, "fingerprint": body["fingerprint"], "own_sub": "alice"}

    # it really registered with the server (real egress over the transport)
    look = server.get("/identity/lookup", params={"sub": "alice"}, headers={"Authorization": "Bearer u:alice"})
    assert look.status_code == 200 and look.json()["public_key"]


def test_identity_setup_refused_when_sync_not_ready(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    assert c.post("/sync/identity/setup", json={"passphrase": "pw"}).status_code == 409  # sync off/unconfigured


def test_identity_setup_wrong_passphrase_fails_closed_no_egress(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _sync_ready(c)
    assert c.post("/sync/identity/setup", json={"passphrase": "WRONG"}).status_code == 422
    assert c.get("/sync/identity/status").json()["has_identity"] is False
    # nothing registered server-side
    look = server.get("/identity/lookup", params={"sub": "alice"}, headers={"Authorization": "Bearer u:alice"})
    assert look.status_code == 404


def test_identity_setup_twice_is_409_no_silent_rekey(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _sync_ready(c)
    assert c.post("/sync/identity/setup", json={"passphrase": "pw"}).status_code == 200
    assert c.post("/sync/identity/setup", json={"passphrase": "pw"}).status_code == 409


def test_identity_lookup_proxies_and_computes_fingerprint_locally(temp_db_url: str) -> None:
    server = _sync_server()
    # a second, independent identity ("bob") registered directly against the server, to be looked up by alice
    import base64

    server.post(
        "/identity/register",
        json={"public_key": base64.b64encode(bytes(32)).decode("ascii"), "display_name": "Bob"},
        headers={"Authorization": "Bearer u:bob"},
    )
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _sync_ready(c)

    r = c.get("/sync/identity/lookup", params={"sub": "bob"})
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Bob" and body["fingerprint"]  # computed locally, not asserted by the server


def test_identity_lookup_unknown_sub_is_404(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _sync_ready(c)
    assert c.get("/sync/identity/lookup", params={"sub": "nobody"}).status_code == 404


def test_identity_lookup_refused_when_sync_not_ready(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    assert c.get("/sync/identity/lookup", params={"sub": "alice"}).status_code == 409


# --- SP4b (backlog #15): share -----------------------------------------------------------------------------


def _register_real_identity(server: TestClient, sub: str, *, display_name: str | None = None):
    """Register a REAL X25519 keypair for `sub` directly against the fake server (bypassing SP4a's own local
    setup flow, which this file already covers) -- returns the private key + its base64 public key, so a share
    addressed to `sub` can be genuinely decrypted in the test, not just proven to exist."""
    import base64

    from cryptography.hazmat.primitives.asymmetric import x25519

    private_key = x25519.X25519PrivateKey.generate()
    public_b64 = base64.b64encode(private_key.public_key().public_bytes_raw()).decode("ascii")
    server.post(
        "/identity/register",
        json={"public_key": public_b64, "display_name": display_name},
        headers={"Authorization": f"Bearer u:{sub}"},
    )
    return private_key, public_b64


def test_share_happy_path_creates_a_decryptable_share(temp_db_url: str) -> None:
    import json

    from sync_server.schema import shares as shares_table

    server = _sync_server()
    bob_priv, _bob_pub = _register_real_identity(server, "bob", display_name="Bob")
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _add_paper(temp_db_url, "Attention Is All You Need")
    _sync_ready(c)
    c.post("/sync/identity/setup", json={"passphrase": "pw"})

    eng = create_engine(temp_db_url)
    with eng.connect() as conn:
        pid = conn.execute(select(schema.papers.c.id)).scalar_one()
    eng.dispose()

    r = c.post("/sync/share", json={"recipient_sub": "bob", "paper_ids": [pid], "passphrase": "pw"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["share_id"], int) and body["recipient_fingerprint"]

    # confirm it really reached the server, addressed to bob, and bob's REAL private key decrypts it -- read
    # the row back via the fake server's own ASGI app state (the engine `_sync_server()` built internally)
    with server.app.state.engine.begin() as conn:  # type: ignore[attr-defined]
        row = conn.execute(select(shares_table)).mappings().first()
    assert row is not None and row["recipient_sub"] == "bob" and row["sender_sub"] == "alice"

    from app.backend.sync.crypto import decrypt_payload
    from app.backend.sync.sharing import WrappedKey, unwrap_content_key

    wrapped = WrappedKey.from_dict(json.loads(row["wrapped_key"]))
    content_key = unwrap_content_key(wrapped, bob_priv)
    bundle = decrypt_payload(content_key, row["ciphertext"])
    assert bundle["papers"][0]["csl_json"]["title"] == "Attention Is All You Need"


def test_share_refused_when_sync_not_ready(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    r = c.post("/sync/share", json={"recipient_sub": "bob", "paper_ids": [1], "passphrase": "pw"})
    assert r.status_code == 409


def test_share_refused_without_sharing_identity(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _add_paper(temp_db_url, "Solo")
    _sync_ready(c)  # sync ready, but alice never ran /sync/identity/setup
    r = c.post("/sync/share", json={"recipient_sub": "bob", "paper_ids": [1], "passphrase": "pw"})
    assert r.status_code == 409


def test_share_wrong_passphrase_fails_closed_no_egress(temp_db_url: str) -> None:
    server = _sync_server()
    _register_real_identity(server, "bob")
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _add_paper(temp_db_url, "Solo")
    _sync_ready(c)
    c.post("/sync/identity/setup", json={"passphrase": "pw"})
    eng = create_engine(temp_db_url)
    with eng.connect() as conn:
        pid = conn.execute(select(schema.papers.c.id)).scalar_one()
    eng.dispose()

    r = c.post("/sync/share", json={"recipient_sub": "bob", "paper_ids": [pid], "passphrase": "WRONG"})
    assert r.status_code == 422
    # nothing reached the server -- confirmed by the sync-server's own health of having zero shares
    from sync_server.schema import shares as shares_table

    with server.app.state.engine.begin() as conn:  # type: ignore[attr-defined]
        assert conn.execute(select(shares_table)).first() is None


def test_share_unknown_recipient_is_404(temp_db_url: str) -> None:
    server = _sync_server()
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _add_paper(temp_db_url, "Solo")
    _sync_ready(c)
    c.post("/sync/identity/setup", json={"passphrase": "pw"})
    eng = create_engine(temp_db_url)
    with eng.connect() as conn:
        pid = conn.execute(select(schema.papers.c.id)).scalar_one()
    eng.dispose()

    r = c.post("/sync/share", json={"recipient_sub": "nobody", "paper_ids": [pid], "passphrase": "pw"})
    assert r.status_code == 404


def test_share_empty_or_oversized_paper_ids_is_422(temp_db_url: str) -> None:
    server = _sync_server()
    _register_real_identity(server, "bob")
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _sync_ready(c)
    c.post("/sync/identity/setup", json={"passphrase": "pw"})

    assert c.post("/sync/share", json={"recipient_sub": "bob", "paper_ids": [], "passphrase": "pw"}).status_code == 422
    too_many = list(range(1, 202))
    assert (
        c.post("/sync/share", json={"recipient_sub": "bob", "paper_ids": too_many, "passphrase": "pw"}).status_code
        == 422
    )


def test_share_nonexistent_papers_produce_no_shareable_content_422(temp_db_url: str) -> None:
    server = _sync_server()
    _register_real_identity(server, "bob")
    transport = HttpSyncTransport("", "u:alice", client=server)
    c = TestClient(create_app(db_url=temp_db_url, sync_transport=transport))
    _sync_ready(c)
    c.post("/sync/identity/setup", json={"passphrase": "pw"})

    r = c.post("/sync/share", json={"recipient_sub": "bob", "paper_ids": [999999], "passphrase": "pw"})
    assert r.status_code == 422
