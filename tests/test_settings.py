from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend import app_settings
from app.backend.api import create_app
from integrations.gemini.generator import DataEgressDisabledError, GeminiConfig, GeminiSummaryGenerator

# The autouse conftest fixture points CALLOSUM_SETTINGS_PATH at a per-test tmp file and sets
# CALLOSUM_ALLOW_DATA_EGRESS=1, so these tests are hermetic + never touch the real ~/.callosum store.


def test_store_roundtrip_and_clear() -> None:
    assert app_settings.stored_api_key() is None
    assert app_settings.stored_egress() is None  # untouched → None → falls back to env

    app_settings.set_api_key("  sk-secret  ")  # trimmed
    assert app_settings.stored_api_key() == "sk-secret"
    app_settings.set_data_egress(False)
    assert app_settings.stored_egress() is False

    app_settings.set_api_key("")  # clear
    assert app_settings.stored_api_key() is None
    app_settings.set_api_key("   ")  # whitespace also clears
    assert app_settings.stored_api_key() is None


def test_get_settings_never_returns_the_key(temp_db_url: str) -> None:
    app_settings.set_api_key("sk-super-secret-value")
    client = TestClient(create_app(db_url=temp_db_url))

    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key_set"] is True
    assert body["api_key_source"] == "ui"
    # The key value must NEVER appear in the response — status only.
    assert "sk-super-secret-value" not in resp.text
    assert "api_key" not in body


def test_put_sets_clears_key_and_toggles_egress(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    client = TestClient(create_app(db_url=temp_db_url))

    # Set a key.
    body = client.put("/settings", json={"set_api_key": True, "api_key": "sk-abc"}).json()
    assert body["api_key_set"] is True and body["api_key_source"] == "ui"
    assert app_settings.stored_api_key() == "sk-abc"

    # Toggle egress OFF via the UI; it overlays the env default and is reported as ui-sourced.
    body = client.put("/settings", json={"data_egress_enabled": False}).json()
    assert body["data_egress_enabled"] is False and body["egress_source"] == "ui"

    # An egress-only PUT must NOT clear the key (set_api_key was False).
    assert app_settings.stored_api_key() == "sk-abc"

    # Clear the key.
    body = client.put("/settings", json={"set_api_key": True, "api_key": ""}).json()
    assert body["api_key_set"] is False and body["api_key_source"] is None
    assert app_settings.stored_api_key() is None


def test_put_oversized_key_is_rejected_and_nothing_written(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    resp = client.put("/settings", json={"set_api_key": True, "api_key": "x" * 5000})
    assert resp.status_code == 422
    assert app_settings.stored_api_key() is None  # nothing persisted


def test_status_reports_env_sources_when_nothing_stored(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")  # env fallback present, nothing stored
    client = TestClient(create_app(db_url=temp_db_url))
    body = client.get("/settings").json()
    assert body["api_key_set"] is True and body["api_key_source"] == "env"
    assert body["egress_source"] == "env"  # CALLOSUM_ALLOW_DATA_EGRESS=1 (conftest), never toggled in UI


def test_geminiconfig_overlays_stored_key_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")
    # No stored key → env fallback.
    assert GeminiConfig.from_environment().resolved_api_key() == "env-key"
    # Stored key wins.
    app_settings.set_api_key("ui-key")
    assert GeminiConfig.from_environment().resolved_api_key() == "ui-key"


def test_geminiconfig_overlays_stored_egress_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Conftest sets CALLOSUM_ALLOW_DATA_EGRESS=1; with nothing stored that env value wins.
    assert GeminiConfig.from_environment().data_egress_enabled is True
    # A stored OFF overlays the env ON.
    app_settings.set_data_egress(False)
    assert GeminiConfig.from_environment().data_egress_enabled is False


def test_stored_egress_off_still_blocks_generation() -> None:
    """The BYOK toggle feeds the egress gate: stored egress OFF → generation raises before any network."""
    app_settings.set_data_egress(False)
    app_settings.set_api_key("sk-present")  # a key being present must NOT bypass the gate
    gen = GeminiSummaryGenerator(config=GeminiConfig.from_environment())
    with pytest.raises(DataEgressDisabledError):
        gen.generate(source_chunks=[], scope_ref={})


# --- inc 147: "Test this key" (egress-gated ping) ---


def test_test_key_egress_off_does_not_ping(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """With egress OFF, the endpoint must NOT contact Google (the toggle's promise) — _ping_gemini not called."""
    from app.backend.api.routers import settings as settings_router

    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    app_settings.set_api_key("sk-present")  # key present, but egress off
    calls = []
    monkeypatch.setattr(settings_router, "_ping_gemini", lambda *a, **k: (calls.append(1), (True, "x"))[1])

    body = TestClient(create_app(db_url=temp_db_url)).post("/settings/test-key").json()
    assert body["ok"] is False
    assert "Allow AI features" in body["detail"]
    assert calls == []  # no outbound call attempted


def test_test_key_egress_on_no_key(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)  # egress on (conftest), but no key anywhere
    body = TestClient(create_app(db_url=temp_db_url)).post("/settings/test-key").json()
    assert body["ok"] is False
    assert "No API key" in body["detail"]


def test_test_key_egress_on_with_key_pings(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend.api.routers import settings as settings_router

    app_settings.set_api_key("sk-works")  # egress on by conftest
    monkeypatch.setattr(settings_router, "_ping_gemini", lambda model, key: (True, "Key works — Gemini responded."))
    body = TestClient(create_app(db_url=temp_db_url)).post("/settings/test-key").json()
    assert body["ok"] is True and "responded" in body["detail"]


def test_ping_gemini_redacts_the_key_from_errors() -> None:
    """A provider error that echoes the key must be redacted before it reaches `detail`."""
    from app.backend.api.routers import settings as settings_router

    key = "sk-leak-me-1234567890"
    import google.genai as genai_mod  # the SDK is importable in dev/CI

    # Force the genai client path to raise an error containing the key; _ping_gemini must redact it.
    orig = genai_mod.Client

    def _raise(**kw):
        raise RuntimeError(f"401 invalid key {key} rejected")

    try:
        genai_mod.Client = _raise
        ok, detail = settings_router._ping_gemini("gemini-2.5-flash-lite", key)
    finally:
        genai_mod.Client = orig
    assert ok is False
    assert key not in detail and "***" in detail
