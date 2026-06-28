"""Remote-access gate (inc 168): the bearer-token requirement + rate-limiting, OFF by default.

The conftest isolates ``CALLOSUM_SETTINGS_PATH`` per test, so remote access is OFF unless a test turns it on —
which is exactly why the gate is a no-op for the rest of the suite. These tests drive both states directly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend import app_settings
from app.backend.api import access_control, create_app
from app.backend.api.access_control import RateLimiter


@pytest.fixture(autouse=True)
def _force_file_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the gitignored file store (never the real OS keychain) so the test token stays in the isolated
    per-test ``CALLOSUM_SETTINGS_PATH`` and can't leak into a dev machine's actual vault."""
    monkeypatch.setattr(app_settings, "_keyring", lambda: None)


# ── the limiter itself (pure) ─────────────────────────────────────────────────────────────────────────────
def test_rate_limiter_allows_then_blocks_within_window() -> None:
    rl = RateLimiter(max_requests=3, window=60.0)
    assert [rl.allow("k", now=t) for t in (0.0, 0.1, 0.2)] == [True, True, True]
    assert rl.allow("k", now=0.3) is False  # 4th in the window → blocked
    assert rl.allow("k", now=61.0) is True  # the window has slid past the first three
    assert rl.allow("other", now=0.3) is True  # a different key has its own budget


# ── the middleware, OFF (the default) ─────────────────────────────────────────────────────────────────────
def test_gate_off_is_a_no_op(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    # No token anywhere, remote access off → the data API behaves exactly as today.
    assert client.get("/papers").status_code == 200
    assert client.get("/settings").json()["remote_access_enabled"] is False


# ── the middleware, ON ────────────────────────────────────────────────────────────────────────────────────
def _enable_remote(token: str = "s3cret-token") -> None:
    app_settings.set_access_token(token)
    app_settings.set_remote_access_enabled(True)


def test_gate_on_requires_a_valid_bearer_token(temp_db_url: str) -> None:
    _enable_remote("right-token")
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers").status_code == 401  # no token
    assert client.get("/papers", headers={"Authorization": "Bearer wrong"}).status_code == 401  # wrong token
    ok = client.get("/papers", headers={"Authorization": "Bearer right-token"})
    assert ok.status_code == 200  # correct token


def test_gate_on_exempts_health_and_shell(temp_db_url: str) -> None:
    _enable_remote()
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/health").status_code == 200  # liveness, no token
    assert client.get("/").status_code == 200  # the static shell carries no library data


def test_disable_env_hatch_forces_off(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_remote()
    monkeypatch.setenv("CALLOSUM_DISABLE_REMOTE_ACCESS", "1")  # local recovery hatch
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers").status_code == 200  # gate forced off → no token needed


def test_rate_limit_returns_429(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_remote("t")
    monkeypatch.setattr(access_control, "RATE_LIMIT_MAX", 3)  # tiny limit for the test (read at limiter construction)
    client = TestClient(create_app(db_url=temp_db_url))
    h = {"Authorization": "Bearer t"}
    codes = [client.get("/papers", headers=h).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]  # the budget is exhausted


# ── the settings surface ──────────────────────────────────────────────────────────────────────────────────
def test_enable_without_a_token_is_422(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.put("/settings", json={"remote_access_enabled": True})  # no token minted yet
    assert r.status_code == 422  # would otherwise lock the local UI out


def test_mint_returns_token_once_then_status_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    minted = client.post("/settings/access-token")
    assert minted.status_code == 200
    token = minted.json()["token"]
    assert token and len(token) >= 20
    # GET /settings reports it's set but NEVER the value.
    body = client.get("/settings").json()
    assert body["access_token_set"] is True
    assert token not in str(body)
    # Now enabling works (a token exists).
    assert (
        client.put(
            "/settings", json={"remote_access_enabled": True}, headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )
