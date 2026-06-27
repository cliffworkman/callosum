from __future__ import annotations

import json

import pytest

from app.backend import app_settings
from app.backend.llm import providers
from app.backend.llm.egress import DataEgressDisabledError, EgressGatedSummaryGenerator
from app.backend.llm.providers import ProviderError, complete, is_loopback_url, requires_egress
from integrations.gemini.generator import GeminiConfig, GeminiSummaryGenerator

# The autouse conftest fixture isolates CALLOSUM_SETTINGS_PATH per test, so app_settings writes are hermetic.


class _Cfg:
    """A duck-typed config for complete() (avoids constructing a full LLMConfig)."""

    def __init__(self, provider, model="m", api_key="k", base_url=None):
        self.provider, self.model, self._key, self.base_url = provider, model, api_key, base_url

    def resolved_api_key(self):
        return self._key


class _FakeResp:
    def __init__(self, data):
        self._data, self.status_code, self.text = data, 200, json.dumps(data)

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, data, capture):
        self._data, self.capture = data, capture

    def post(self, url, json=None, headers=None, timeout=None):
        self.capture.update(url=url, json=json, headers=headers)
        return _FakeResp(self._data)


# --- requires_egress / loopback ---


def test_requires_egress_truth_table():
    assert requires_egress("gemini") and requires_egress("openai") and requires_egress("anthropic")
    assert not requires_egress("local")


def test_is_loopback_url():
    assert is_loopback_url("http://127.0.0.1:11434") and is_loopback_url("http://localhost:1234")
    assert not is_loopback_url("https://api.openai.com") and not is_loopback_url("https://evil.example.com")
    assert not is_loopback_url(None)


# --- complete() per provider (no network — injected client) ---


def test_complete_openai_request_and_parse():
    cap = {}
    client = _FakeClient(
        {
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        },
        cap,
    )
    res = complete(_Cfg("openai", model="gpt-4o-mini", api_key="sk-oai"), "PROMPT", http_client=client)
    assert res.text == "hi"
    assert res.usage_metadata.total_token_count == 4
    assert cap["url"].endswith("/v1/chat/completions") and cap["url"].startswith("https://api.openai.com")
    assert cap["headers"]["Authorization"] == "Bearer sk-oai"
    assert cap["json"]["messages"][0]["content"] == "PROMPT"


def test_complete_anthropic_request_and_parse():
    cap = {}
    client = _FakeClient({"content": [{"text": "hi"}], "usage": {"input_tokens": 3, "output_tokens": 1}}, cap)
    res = complete(_Cfg("anthropic", model="claude-3-5-haiku-latest", api_key="sk-ant"), "PROMPT", http_client=client)
    assert res.text == "hi" and res.usage_metadata.total_token_count == 4
    assert cap["url"] == "https://api.anthropic.com/v1/messages"
    assert cap["headers"]["x-api-key"] == "sk-ant" and "anthropic-version" in cap["headers"]
    assert cap["json"]["max_tokens"] >= 1


def test_complete_local_loopback_uses_openai_shape():
    cap = {}
    client = _FakeClient({"choices": [{"message": {"content": "local-ok"}}], "usage": {}}, cap)
    cfg = _Cfg("local", model="llama3", api_key=None, base_url="http://127.0.0.1:11434")
    res = complete(cfg, "PROMPT", http_client=client)
    assert res.text == "local-ok"
    assert cap["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert "Authorization" not in cap["headers"]  # no key needed for a local server


def test_complete_local_nonloopback_is_rejected():
    cfg = _Cfg("local", base_url="https://evil.example.com")
    with pytest.raises(ProviderError):
        complete(cfg, "PROMPT", http_client=_FakeClient({}, {}))


def test_complete_redacts_the_key_from_provider_errors(monkeypatch: pytest.MonkeyPatch):
    """A provider error that echoes the key must be redacted before it surfaces in a ProviderError."""
    key = "sk-leak-me-1234567890"
    import google.genai as genai_mod

    def _raise(**kw):
        raise RuntimeError(f"401 invalid key {key} rejected")

    monkeypatch.setattr(genai_mod, "Client", _raise)
    with pytest.raises(ProviderError) as exc:
        complete(_Cfg("gemini", api_key=key), "PROMPT")
    assert key not in str(exc.value) and "***" in str(exc.value)


# --- the gate: local skips egress; cloud still blocks ---


class _FakeSum:
    name = "fake"

    def generate(self, *, source_chunks, scope_ref, conn=None):
        return ["delegated"]


def test_gate_allows_local_with_egress_off():
    gen = EgressGatedSummaryGenerator(inner=_FakeSum(), data_egress_enabled=False, provider="local")
    assert gen.generate(source_chunks=[], scope_ref={}) == ["delegated"]  # no raise — local needs no consent


def test_gate_blocks_cloud_with_egress_off():
    gen = EgressGatedSummaryGenerator(inner=_FakeSum(), data_egress_enabled=False, provider="openai")
    with pytest.raises(DataEgressDisabledError):
        gen.generate(source_chunks=[], scope_ref={})


# --- config resolution + the headline guarantee ---


def test_from_environment_resolves_per_provider_key_and_default_model():
    app_settings.set_provider("openai")
    app_settings.set_provider_key("openai", "sk-oai")
    cfg = GeminiConfig.from_environment()
    assert cfg.provider == "openai" and cfg.model == "gpt-4o-mini"
    assert cfg.resolved_api_key() == "sk-oai"


def test_local_summary_generates_with_egress_off(monkeypatch: pytest.MonkeyPatch):
    """Headline: a loopback local provider generates a summary with the egress toggle OFF (zero egress)."""
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    app_settings.set_provider("local")
    app_settings.set_local_base_url("http://127.0.0.1:11434")
    app_settings.set_model("llama3")
    app_settings.set_data_egress(False)
    cfg = GeminiConfig.from_environment()
    assert cfg.provider == "local" and not cfg.data_egress_enabled

    # Stub the provider call (the SDK/httpx layer is tested above); the point here is the generator's gate.
    monkeypatch.setattr(
        providers, "complete", lambda config, prompt, **kw: providers.CompletionResult(text="[]", usage_metadata=None)
    )
    gen = GeminiSummaryGenerator(config=cfg)
    # Must NOT raise DataEgressDisabledError — local keeps text on the machine.
    assert gen.generate(source_chunks=[], scope_ref={}) == []
