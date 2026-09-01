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


def test_agent_writes_toggle_defaults_off_and_round_trips(temp_db_url: str) -> None:
    # B1 SP2: the MCP agent-writes opt-in. Default OFF; PUT toggles it (the conftest isolates the settings store).
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/settings").json()["agent_writes_enabled"] is False
    assert client.put("/settings", json={"agent_writes_enabled": True}).json()["agent_writes_enabled"] is True
    assert client.get("/settings").json()["agent_writes_enabled"] is True
    client.put("/settings", json={"agent_writes_enabled": False})
    assert client.get("/settings").json()["agent_writes_enabled"] is False


def test_onboarding_completed_defaults_false_and_round_trips(temp_db_url: str) -> None:
    # inc 416/553: completion and the wizard-contract version are one atomic settings update.
    client = TestClient(create_app(db_url=temp_db_url))
    initial = client.get("/settings").json()
    assert initial["onboarding_completed"] is False
    assert initial["onboarding_version"] == 0
    updated = client.put(
        "/settings",
        json={"onboarding_completed": True, "onboarding_version": app_settings.ONBOARDING_CURRENT_VERSION},
    ).json()
    assert updated["onboarding_completed"] is True
    assert updated["onboarding_version"] == app_settings.ONBOARDING_CURRENT_VERSION
    assert client.get("/settings").json()["onboarding_version"] == app_settings.ONBOARDING_CURRENT_VERSION


def test_onboarding_completed_store_roundtrip() -> None:
    assert app_settings.stored_onboarding_completed() is False
    assert app_settings.stored_onboarding_version() == 0
    app_settings.set_onboarding_completed(True, version=app_settings.ONBOARDING_CURRENT_VERSION)
    assert app_settings.stored_onboarding_completed() is True
    assert app_settings.stored_onboarding_version() == app_settings.ONBOARDING_CURRENT_VERSION
    app_settings.set_onboarding_completed(False)
    assert app_settings.stored_onboarding_completed() is False


def test_onboarding_version_requires_completion_and_is_bounded(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.put("/settings", json={"onboarding_version": 2}).status_code == 422
    assert client.put("/settings", json={"onboarding_completed": True, "onboarding_version": 3}).status_code == 422


def test_publisher_prefs_gate_and_roundtrip(temp_db_url: str) -> None:
    # #40 SP1b: the first-use choice gate is satisfied only when BOTH consequential defaults are set — neither is
    # pre-selected, so the weighting is one forced choice among peers (never the lone spotlighted one).
    client = TestClient(create_app(db_url=temp_db_url))
    s = client.get("/settings").json()
    assert s["publisher_defaults_set"] is False and s["publisher_weighting"] is None and s["publisher_breadth"] is None

    # setting only the weighting does NOT satisfy the gate (both are required together)
    client.put("/settings", json={"set_publisher_weighting": True, "publisher_weighting": 0.5})
    assert client.get("/settings").json()["publisher_defaults_set"] is False

    # setting the breadth too flips the gate
    client.put("/settings", json={"set_publisher_breadth": True, "publisher_breadth": "focused"})
    s = client.get("/settings").json()
    assert s["publisher_defaults_set"] is True
    assert s["publisher_weighting"] == 0.5 and s["publisher_breadth"] == "focused"

    # clearing one re-gates
    client.put("/settings", json={"set_publisher_breadth": True, "publisher_breadth": ""})
    assert client.get("/settings").json()["publisher_defaults_set"] is False


def test_publisher_prefs_validation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    # weighting must be 0..1
    assert (
        client.put("/settings", json={"set_publisher_weighting": True, "publisher_weighting": 5.0}).status_code == 422
    )
    assert (
        client.put("/settings", json={"set_publisher_weighting": True, "publisher_weighting": -0.1}).status_code == 422
    )
    # breadth is allowlisted
    assert (
        client.put("/settings", json={"set_publisher_breadth": True, "publisher_breadth": "enormous"}).status_code
        == 422
    )
    # a rejected PUT leaves the store unset (nothing partially written)
    assert client.get("/settings").json()["publisher_weighting"] is None


def test_get_settings_never_returns_the_key(temp_db_url: str) -> None:
    app_settings.set_api_key("sk-super-secret-value")
    client = TestClient(create_app(db_url=temp_db_url))

    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key_set"] is True
    assert body["api_key_source"] == "ui"
    assert body["generation_provider_available"] is True
    assert body["provider_evidence"] == {
        "synthesis_overview": "evaluated",
        "other_generative_capabilities": "testing",
    }
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


# --- contact email / polite-pool mailto (inc 158) ---


def test_contact_email_store_roundtrip_and_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CALLOSUM_CROSSREF_MAILTO", raising=False)
    monkeypatch.delenv("CALLOSUM_OPENALEX_MAILTO", raising=False)
    assert app_settings.stored_contact_email() is None
    assert app_settings.resolved_mailto("CALLOSUM_CROSSREF_MAILTO") is None

    app_settings.set_contact_email("  me@uni.edu  ")  # trimmed
    assert app_settings.stored_contact_email() == "me@uni.edu"
    # one stored email overlays BOTH polite-pool env vars
    assert app_settings.resolved_mailto("CALLOSUM_CROSSREF_MAILTO") == "me@uni.edu"
    assert app_settings.resolved_mailto("CALLOSUM_OPENALEX_MAILTO") == "me@uni.edu"

    app_settings.set_contact_email("")  # clears
    assert app_settings.stored_contact_email() is None


def test_resolved_mailto_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALLOSUM_CROSSREF_MAILTO", "env@lab.org")
    assert app_settings.stored_contact_email() is None
    assert app_settings.resolved_mailto("CALLOSUM_CROSSREF_MAILTO") == "env@lab.org"
    # the stored value wins over the env var when both are present
    app_settings.set_contact_email("ui@lab.org")
    assert app_settings.resolved_mailto("CALLOSUM_CROSSREF_MAILTO") == "ui@lab.org"


def test_put_and_get_contact_email(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CALLOSUM_CROSSREF_MAILTO", raising=False)
    monkeypatch.delenv("CALLOSUM_OPENALEX_MAILTO", raising=False)
    client = TestClient(create_app(db_url=temp_db_url))

    body = client.put("/settings", json={"set_contact_email": True, "contact_email": "you@example.com"}).json()
    assert body["contact_email"] == "you@example.com" and body["contact_email_source"] == "ui"
    assert client.get("/settings").json()["contact_email"] == "you@example.com"

    body = client.put("/settings", json={"set_contact_email": True, "contact_email": ""}).json()
    assert body["contact_email"] == "" and body["contact_email_source"] is None


def test_get_contact_email_reports_env_source(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALLOSUM_CROSSREF_MAILTO", "env@lab.org")
    body = TestClient(create_app(db_url=temp_db_url)).get("/settings").json()
    # the input field stays empty (env isn't a UI value) but the source is reported so the UI can say so
    assert body["contact_email"] == "" and body["contact_email_source"] == "env"


def test_put_rejects_invalid_contact_email(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    resp = client.put("/settings", json={"set_contact_email": True, "contact_email": "not-an-email"})
    assert resp.status_code == 422
    assert app_settings.stored_contact_email() is None  # nothing persisted


def test_retraction_watch_client_uses_stored_contact_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CALLOSUM_CROSSREF_MAILTO", raising=False)
    from integrations.retraction_watch import RetractionWatchClient

    app_settings.set_contact_email("rw@uni.edu")
    assert RetractionWatchClient().mailto == "rw@uni.edu"  # picks up the UI contact email, no env var needed


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
    """With egress OFF (cloud provider), the endpoint must NOT contact a provider — complete() not called."""
    from app.backend.llm import providers

    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    app_settings.set_api_key("sk-present")  # key present, but egress off; default provider = gemini
    calls = []
    monkeypatch.setattr(providers, "complete", lambda *a, **k: calls.append(1))

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
    from app.backend.llm import providers

    app_settings.set_api_key("sk-works")  # egress on by conftest; default provider = gemini
    monkeypatch.setattr(
        providers, "complete", lambda config, prompt, **kw: providers.CompletionResult(text="OK", usage_metadata=None)
    )
    body = TestClient(create_app(db_url=temp_db_url)).post("/settings/test-key").json()
    assert body["ok"] is True and "responded" in body["detail"]


# --- inc 150: multi-provider Settings UI (PUT extension) ---


def test_put_sets_provider_and_rejects_unknown(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    body = client.put("/settings", json={"provider": "openai"}).json()
    assert body["provider"] == "openai"
    assert client.put("/settings", json={"provider": "bogus"}).status_code == 422


def test_put_local_base_url_loopback_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    ok = client.put("/settings", json={"set_local_base_url": True, "local_base_url": "http://127.0.0.1:11434"})
    assert ok.status_code == 200 and ok.json()["local_base_url"] == "http://127.0.0.1:11434"
    # A non-loopback endpoint is refused (so "local = no egress" stays honest).
    assert (
        client.put(
            "/settings", json={"set_local_base_url": True, "local_base_url": "https://evil.example.com"}
        ).status_code
        == 422
    )


def test_put_per_provider_key_isolated(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    client.put("/settings", json={"set_api_key": True, "api_key": "sk-oai", "api_key_provider": "openai"})
    body = client.put("/settings", json={"provider": "openai"}).json()
    assert body["provider_keys_set"]["openai"] is True
    assert body["provider_keys_set"]["gemini"] is False  # writing openai's key left gemini's untouched
    assert app_settings.stored_api_key() is None  # the gemini "api_key" field was not written


def test_put_toggles_help_assistant(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    body = client.put("/settings", json={"help_assistant_enabled": False}).json()
    assert body["help_assistant_enabled"] is False and body["help_source"] == "ui"
    body = client.put("/settings", json={"help_assistant_enabled": True}).json()
    assert body["help_assistant_enabled"] is True and body["help_source"] == "ui"


def test_geminiconfig_overlays_stored_help_over_env() -> None:
    # Conftest sets CALLOSUM_HELP_ASSISTANT_ENABLED=1; a stored OFF overlays it (independent of egress).
    assert GeminiConfig.from_environment().help_assistant_enabled is True
    app_settings.set_help_assistant_enabled(False)
    assert GeminiConfig.from_environment().help_assistant_enabled is False


def test_test_key_local_works_without_egress(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A loopback local provider validates without egress consent (it makes no cloud call)."""
    from app.backend.llm import providers

    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    app_settings.set_provider("local")
    app_settings.set_local_base_url("http://127.0.0.1:11434")
    app_settings.set_data_egress(False)
    monkeypatch.setattr(
        providers, "complete", lambda config, prompt, **kw: providers.CompletionResult(text="OK", usage_metadata=None)
    )
    body = TestClient(create_app(db_url=temp_db_url)).post("/settings/test-key").json()
    assert body["ok"] is True  # not gated on egress — local makes no cloud call


# --- inc 152: OS-keychain storage (optional keyring, file fallback) ---


class _FakeKeyring:
    """An in-memory stand-in for the `keyring` module (so the keychain path is tested without installing keyring)."""

    def __init__(self):
        self.store: dict[tuple, str] = {}

    def set_password(self, service, user, pw):
        self.store[(service, user)] = pw

    def get_password(self, service, user):
        return self.store.get((service, user))

    def delete_password(self, service, user):
        if (service, user) in self.store:
            del self.store[(service, user)]
        else:
            raise RuntimeError("no such password")


def test_keychain_stores_in_vault_not_file(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeKeyring()
    monkeypatch.setattr(app_settings, "_keyring", lambda: fake)
    app_settings.set_provider_key("openai", "sk-vault")
    assert app_settings.get_provider_key("openai") == "sk-vault"
    assert fake.store[("callosum", "openai_api_key")] == "sk-vault"
    assert "openai_api_key" not in app_settings.load_settings()  # never written to the plaintext file


def test_keychain_migrates_file_key_on_resave(monkeypatch: pytest.MonkeyPatch) -> None:
    # A key written before keyring was available lands in the file.
    monkeypatch.setattr(app_settings, "_keyring", lambda: None)
    app_settings.set_provider_key("gemini", "sk-file")
    assert app_settings.load_settings().get("api_key") == "sk-file"
    # keyring now available → the file key is still found (fallback)…
    fake = _FakeKeyring()
    monkeypatch.setattr(app_settings, "_keyring", lambda: fake)
    assert app_settings.get_provider_key("gemini") == "sk-file"
    # …and re-saving migrates it to the vault + drops the plaintext file copy.
    app_settings.set_provider_key("gemini", "sk-file2")
    assert fake.store[("callosum", "api_key")] == "sk-file2"
    assert "api_key" not in app_settings.load_settings()
    assert app_settings.get_provider_key("gemini") == "sk-file2"


def test_keychain_error_falls_back_to_file(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        def set_password(self, *a):
            raise RuntimeError("vault locked")

        def get_password(self, *a):
            raise RuntimeError("vault locked")

        def delete_password(self, *a):
            raise RuntimeError("vault locked")

    monkeypatch.setattr(app_settings, "_keyring", lambda: _Boom())
    app_settings.set_provider_key("anthropic", "sk-fallback")  # set raises → file fallback
    assert app_settings.load_settings().get("anthropic_api_key") == "sk-fallback"
    assert app_settings.get_provider_key("anthropic") == "sk-fallback"  # get raises → file fallback


def test_status_reports_keychain_storage(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_settings, "_keyring", lambda: _FakeKeyring())
    body = TestClient(create_app(db_url=temp_db_url)).get("/settings").json()
    assert body["key_storage"] == "keychain"
    monkeypatch.setattr(app_settings, "_keyring", lambda: None)
    body = TestClient(create_app(db_url=temp_db_url)).get("/settings").json()
    assert body["key_storage"] == "file"


def test_plugins_enabled_defaults_false_and_round_trips(temp_db_url: str) -> None:
    # backlog #41: the admin-gated plugins foundation toggle. Default OFF; PUT toggles it. Enabling
    # it does not cause any other behavior to change -- there is no loader wired to it yet.
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/settings").json()["plugins_enabled"] is False
    assert client.put("/settings", json={"plugins_enabled": True}).json()["plugins_enabled"] is True
    assert client.get("/settings").json()["plugins_enabled"] is True
    client.put("/settings", json={"plugins_enabled": False})
    assert client.get("/settings").json()["plugins_enabled"] is False


def test_plugins_disable_env_hatch_forces_off(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # The CALLOSUM_DISABLE_PLUGINS recovery hatch, mirroring CALLOSUM_DISABLE_AGENT_WRITES: forces the
    # stored value to False regardless of what was saved.
    client = TestClient(create_app(db_url=temp_db_url))
    client.put("/settings", json={"plugins_enabled": True})
    assert client.get("/settings").json()["plugins_enabled"] is True
    monkeypatch.setenv("CALLOSUM_DISABLE_PLUGINS", "1")
    assert client.get("/settings").json()["plugins_enabled"] is False
