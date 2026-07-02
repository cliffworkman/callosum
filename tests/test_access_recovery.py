"""Remote-access lockout recovery (inc 254): the gate-exempt, disable-only ``POST /access/recover``.

When Remote access (inc 168) is on but the browser holds no valid token, every data call 401s — including
``GET /settings`` — so the user can't reach the UI that would fix it. This endpoint is the safe escape hatch:
reachable WITHOUT a token, it proves local-machine possession via a one-time code written to a local file, and
its only privileged effect is turning Remote access OFF. These tests pin the two-phase flow, the honesty
properties (no token/data disclosure), and the negative paths (wrong/expired/oversized code, rate limit).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend import app_settings
from app.backend.api import access_control, access_recovery, create_app


@pytest.fixture(autouse=True)
def _force_file_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the gitignored file store (never the real OS keychain) so the test token/flag stay in the isolated
    per-test ``CALLOSUM_SETTINGS_PATH`` and can't leak into a dev machine's actual vault."""
    monkeypatch.setattr(app_settings, "_keyring", lambda: None)


@pytest.fixture(autouse=True)
def _reset_pending() -> None:
    """The pending recovery code is an in-process module global — reset it around each test."""
    access_recovery.clear_pending()
    yield
    access_recovery.clear_pending()


def _enable_remote(token: str = "s3cret-token") -> None:
    app_settings.set_access_token(token)
    app_settings.set_remote_access_enabled(True)


# ── the module (pure, no HTTP) ────────────────────────────────────────────────────────────────────────────
def test_start_writes_code_to_local_file() -> None:
    path = access_recovery.start_recovery()
    assert path == access_recovery.recovery_file_path()
    assert path.exists()
    assert access_recovery._pending["code"] in path.read_text()  # the code is in the file the local user opens


def test_verify_is_single_use_and_consumes_the_file() -> None:
    access_recovery.start_recovery()
    code = access_recovery._pending["code"]
    assert access_recovery.verify_recovery(code) is True  # first use succeeds
    assert access_recovery.verify_recovery(code) is False  # consumed — a replay fails
    assert not access_recovery.recovery_file_path().exists()  # file removed on success


def test_verify_rejects_expired_code() -> None:
    access_recovery.start_recovery(now=0.0)
    code = access_recovery._pending["code"]
    later = access_recovery.RECOVERY_CODE_TTL_S + 1.0
    assert access_recovery.verify_recovery(code, now=later) is False  # past the TTL
    assert not access_recovery.recovery_file_path().exists()  # expiry also cleans up


def test_start_overwrites_the_previous_code() -> None:
    access_recovery.start_recovery()
    stale = access_recovery._pending["code"]
    access_recovery.start_recovery()  # a fresh code invalidates the old one
    assert access_recovery.verify_recovery(stale) is False


# ── the endpoint (HTTP) ───────────────────────────────────────────────────────────────────────────────────
def test_recover_start_returns_only_the_path_never_the_code(temp_db_url: str) -> None:
    _enable_remote()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/access/recover", json={})  # no token — the user is locked out
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "code_written"
    path = Path(body["code_path"])
    assert path.exists()
    code = access_recovery._pending["code"]
    assert code in path.read_text()  # written to the local file...
    assert code not in r.text  # ...but NEVER returned over the wire


def test_recover_valid_code_disables_remote_access(temp_db_url: str) -> None:
    _enable_remote()
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/access/recover", json={})
    code = access_recovery._pending["code"]
    r = client.post("/access/recover", json={"code": code})
    assert r.status_code == 200
    assert r.json()["status"] == "recovered"
    assert app_settings.stored_remote_access() is False  # the gate is now off — local access restored
    # and the data API is reachable again without a token
    assert client.get("/papers").status_code == 200


def test_recover_wrong_code_leaves_the_gate_on(temp_db_url: str) -> None:
    _enable_remote()
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/access/recover", json={})
    r = client.post("/access/recover", json={"code": "not-the-code"})
    assert r.status_code == 200
    assert r.json()["status"] == "invalid"
    assert app_settings.stored_remote_access() is True  # a bad guess never disables the gate
    assert client.get("/papers").status_code == 401  # still locked


def test_recover_never_reveals_the_token(temp_db_url: str) -> None:
    _enable_remote("super-secret-token-value")
    client = TestClient(create_app(db_url=temp_db_url))
    start = client.post("/access/recover", json={})
    code = access_recovery._pending["code"]
    done = client.post("/access/recover", json={"code": code})
    assert "super-secret-token-value" not in start.text
    assert "super-secret-token-value" not in done.text


def test_recover_oversized_code_is_rejected_at_the_boundary(temp_db_url: str) -> None:
    _enable_remote()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/access/recover", json={"code": "x" * (access_recovery.RECOVERY_CODE_MAX_LEN + 1)})
    assert r.status_code == 422  # capped by the pydantic Field before any comparison


def test_recover_is_rate_limited(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_remote()
    monkeypatch.setattr(access_control, "RATE_LIMIT_MAX", 3)  # tiny limit for the test (read at limiter construction)
    client = TestClient(create_app(db_url=temp_db_url))
    codes = [client.post("/access/recover", json={}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]  # the recovery budget is exhausted — blunts abuse


def test_recover_works_only_matters_when_gate_on_but_is_harmless_off(temp_db_url: str) -> None:
    # With remote access OFF (the default), the endpoint still responds (the middleware is a pass-through) and
    # simply writes a code — no harm, and disabling an already-off gate is a no-op.
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/access/recover", json={}).status_code == 200
    code = access_recovery._pending["code"]
    r = client.post("/access/recover", json={"code": code})
    assert r.json()["status"] == "recovered"
    assert app_settings.stored_remote_access() is False
