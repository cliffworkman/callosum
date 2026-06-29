"""SP3b — the opt-in local `/sync/*` endpoints (setup / settings / status / run): the consent gate + the wiring that
makes E2E sync usable. Hermetic (the autouse conftest isolates CALLOSUM_SETTINGS_PATH per test); the happy path runs
through an injected `HttpSyncTransport` bound to an in-process sync-server (no socket, no live Authentik).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.backend import app_settings
from app.backend.api import create_app
from app.backend.persistence.repository import create_paper
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
    assert c.post("/sync/run", json={"passphrase": "WRONG"}).status_code == 401  # wrong passphrase fails closed


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
    assert c.post("/sync/run", json={"passphrase": "nope"}).status_code == 401
    # nothing reached the server (the bad passphrase fails before the transport is used)
    assert server.get("/sync/records?since=0", headers={"Authorization": "Bearer u:alice"}).json()["records"] == []


@pytest.mark.parametrize("passphrase", ["", " " * 3])
def test_setup_rejects_blank_passphrase(temp_db_url: str, passphrase: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    assert c.post("/sync/setup", json={"passphrase": passphrase}).status_code == 422
