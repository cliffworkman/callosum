from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend import app_settings, providers_store
from app.backend.api import create_app
from app.backend.llm.providers import requires_egress
from integrations.gemini.generator import GeminiConfig

# The autouse conftest fixture isolates CALLOSUM_SETTINGS_PATH per test, so the roster + key writes are hermetic.


# --- the synthesized roster (builtins are never persisted; only customs are) ---


def test_roster_synthesizes_managed_and_manual_local_builtins():
    ids = providers_store.provider_ids()
    assert ids[:5] == ["gemini", "openai", "anthropic", "managed_local", "local"]
    assert all(providers_store.is_builtin(p) for p in ("gemini", "openai", "anthropic", "managed_local", "local"))
    assert not providers_store.is_builtin("something-custom")
    # nothing was written to the settings file — the presets are pure synthesis
    assert "custom_providers" not in app_settings.load_settings()


def test_active_defaults_to_gemini():
    assert providers_store.active_provider()["id"] == "gemini"
    assert providers_store.active_model() == "gemini-2.5-flash-lite"


def test_local_base_url_overlays_the_local_preset():
    app_settings.set_local_base_url("http://127.0.0.1:9999")
    local = providers_store.get_provider("local")
    assert local["base_url"] == "http://127.0.0.1:9999" and local["wire_format"] == "chat_completions"


# --- custom-provider CRUD at the store level ---


def test_add_update_delete_custom_roundtrip():
    rec = providers_store.add_custom(
        name="DeepSeek", base_url="https://api.deepseek.com/", wire_format="responses", models=["deepseek-chat", ""]
    )
    assert rec["builtin"] is False and len(rec["id"]) == 32  # server-generated uuid4 hex
    assert rec["base_url"] == "https://api.deepseek.com"  # trailing slash normalised off
    assert rec["models"] == ["deepseek-chat"]  # blank model dropped
    assert providers_store.get_provider(rec["id"])["name"] == "DeepSeek"

    # A pasted documented base ending in /v1 is trimmed — the transports append /v1/... themselves (no double-/v1).
    v1 = providers_store.add_custom(
        name="V1Base", base_url="https://api.example.com/v1", wire_format="chat_completions", models=["m"]
    )
    assert v1["base_url"] == "https://api.example.com"
    providers_store.delete_custom(v1["id"])

    upd = providers_store.update_custom(rec["id"], name="DeepSeek v2", models=["deepseek-reasoner"])
    assert upd["name"] == "DeepSeek v2" and upd["models"] == ["deepseek-reasoner"]
    assert upd["wire_format"] == "responses"  # untouched fields preserved

    assert providers_store.update_custom("no-such-id", name="x") is None  # unknown → None
    assert providers_store.delete_custom(rec["id"]) is True
    assert providers_store.get_provider(rec["id"]) is None
    assert providers_store.delete_custom(rec["id"]) is False  # already gone


def test_deleting_the_active_custom_resets_active_to_gemini():
    rec = providers_store.add_custom(
        name="Acme", base_url="https://api.acme.ai", wire_format="chat_completions", models=[]
    )
    providers_store.set_active(rec["id"], "acme-large")
    assert providers_store.active_provider()["id"] == rec["id"]
    providers_store.delete_custom(rec["id"])
    assert providers_store.active_provider()["id"] == "gemini"
    assert providers_store.active_model() == "gemini-2.5-flash-lite"  # model override cleared too


def test_custom_validation_raises_value_error():
    with pytest.raises(ValueError):
        providers_store.add_custom(name="", base_url="https://x.ai", wire_format="chat_completions", models=[])
    with pytest.raises(ValueError):
        providers_store.add_custom(name="X", base_url="ftp://x.ai", wire_format="chat_completions", models=[])
    with pytest.raises(ValueError):  # gemini SDK is not assignable to a custom provider
        providers_store.add_custom(name="X", base_url="https://x.ai", wire_format="gemini", models=[])
    with pytest.raises(ValueError):
        providers_store.add_custom(name="X", base_url="https://x.ai", wire_format="chat_completions", models=["m"] * 99)


def test_custom_base_url_rejects_embedded_credentials():
    # https://user:pass@host risks a secret landing in stored config/error text -- the key is already collected
    # and stored separately, so a base URL never needs to carry one.
    with pytest.raises(ValueError, match="credentials"):
        providers_store.add_custom(
            name="X", base_url="https://user:pass@x.ai", wire_format="chat_completions", models=[]
        )


def test_active_custom_cloud_provider_is_egress_gated():
    """A custom provider pointed at a cloud URL resolves through from_environment and is gated exactly like Gemini;
    a custom loopback provider is honestly no-egress (invariant #3 for an arbitrary user URL)."""
    cloud = providers_store.add_custom(
        name="Acme", base_url="https://api.acme.ai", wire_format="chat_completions", models=["big"]
    )
    app_settings.set_provider_key(cloud["id"], "sk-acme")
    providers_store.set_active(cloud["id"], "")
    cfg = GeminiConfig.from_environment()
    assert cfg.provider == cloud["id"] and cfg.base_url == "https://api.acme.ai" and cfg.model == "big"
    assert cfg.resolved_api_key() == "sk-acme" and requires_egress(cfg) is True

    localish = providers_store.add_custom(
        name="LocalLM", base_url="http://127.0.0.1:1234", wire_format="chat_completions", models=["m"]
    )
    providers_store.set_active(localish["id"], "")
    assert requires_egress(GeminiConfig.from_environment()) is False


# --- the roster + CRUD endpoints ---


def _client(temp_db_url: str) -> TestClient:
    return TestClient(create_app(db_url=temp_db_url))


def test_get_providers_roster_shape(temp_db_url: str):
    body = _client(temp_db_url).get("/settings/providers").json()
    assert body["active_provider"] == "gemini"
    assert body["wire_formats"] == ["messages", "chat_completions", "responses"]  # gemini SDK not offered
    ids = [p["id"] for p in body["providers"]]
    assert ids[:5] == ["gemini", "openai", "anthropic", "managed_local", "local"]
    gem = next(p for p in body["providers"] if p["id"] == "gemini")
    assert gem["builtin"] is True and gem["active"] is True and gem["wire_format"] == "gemini"


def test_create_edit_delete_custom_via_api(temp_db_url: str):
    client = _client(temp_db_url)
    created = client.post(
        "/settings/providers",
        json={
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "wire_format": "responses",
            "models": ["deepseek-chat"],
        },
    )
    assert created.status_code == 200
    pid = created.json()["id"]
    assert created.json()["builtin"] is False and created.json()["key_set"] is False

    # it now appears in the roster
    assert pid in [p["id"] for p in client.get("/settings/providers").json()["providers"]]

    # edit it
    edited = client.put(f"/settings/providers/{pid}", json={"name": "DeepSeek Pro", "models": ["deepseek-reasoner"]})
    assert edited.status_code == 200 and edited.json()["name"] == "DeepSeek Pro"

    # delete it
    assert client.delete(f"/settings/providers/{pid}").json() == {"ok": True}
    assert pid not in [p["id"] for p in client.get("/settings/providers").json()["providers"]]


def test_create_validation_422(temp_db_url: str):
    client = _client(temp_db_url)
    assert (
        client.post(
            "/settings/providers", json={"name": "", "base_url": "https://x.ai", "wire_format": "responses"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/settings/providers", json={"name": "X", "base_url": "x.ai", "wire_format": "responses"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/settings/providers", json={"name": "X", "base_url": "https://x.ai", "wire_format": "gemini"}
        ).status_code
        == 422
    )


def test_builtins_cannot_be_edited_or_deleted(temp_db_url: str):
    client = _client(temp_db_url)
    assert client.put("/settings/providers/openai", json={"name": "Nope"}).status_code == 400
    assert client.delete("/settings/providers/gemini").status_code == 400


def test_edit_or_delete_unknown_custom_404(temp_db_url: str):
    client = _client(temp_db_url)
    assert client.put("/settings/providers/deadbeef", json={"name": "x"}).status_code == 404
    assert client.delete("/settings/providers/deadbeef").status_code == 404


def test_custom_key_is_write_only_and_reported_as_set(temp_db_url: str):
    client = _client(temp_db_url)
    pid = client.post(
        "/settings/providers",
        json={"name": "Acme", "base_url": "https://api.acme.ai", "wire_format": "chat_completions", "models": ["big"]},
    ).json()["id"]
    # set a key for the custom provider via the existing PUT /settings channel
    client.put("/settings", json={"set_api_key": True, "api_key": "sk-acme-secret", "api_key_provider": pid})
    resp = client.get("/settings/providers")
    assert "sk-acme-secret" not in resp.text  # NEVER the value
    acme = next(p for p in resp.json()["providers"] if p["id"] == pid)
    assert acme["key_set"] is True

    # activating the custom provider is accepted by PUT /settings (roster is the id allowlist)
    assert client.put("/settings", json={"provider": pid}).status_code == 200
    assert client.get("/settings/providers").json()["active_provider"] == pid
