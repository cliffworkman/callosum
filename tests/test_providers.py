from __future__ import annotations

import json

import httpx
import pytest

from app.backend import app_settings
from app.backend.llm import providers
from app.backend.llm.egress import DataEgressDisabledError, EgressGatedSummaryGenerator
from app.backend.llm.managed_local import ManagedProviderRuntime
from app.backend.llm.providers import ProviderError, complete, is_loopback_url, requires_egress
from app.backend.provider_runtime import ProviderClientRuntime
from integrations.gemini.generator import GeminiConfig, GeminiSummaryGenerator

# The autouse conftest fixture isolates CALLOSUM_SETTINGS_PATH per test, so app_settings writes are hermetic.


class _Cfg:
    """A duck-typed config for complete() (avoids constructing a full LLMConfig)."""

    def __init__(self, provider, model="m", api_key="k", base_url=None, wire_format=None):
        self.provider, self.model, self._key, self.base_url = provider, model, api_key, base_url
        self.wire_format = wire_format

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
        self.capture.update(url=url, json=json, headers=headers, timeout=timeout)
        return _FakeResp(self._data)


# --- requires_egress / loopback ---


def test_requires_egress_truth_table():
    assert requires_egress("gemini") and requires_egress("openai") and requires_egress("anthropic")
    assert not requires_egress("local")


def test_is_loopback_url():
    assert is_loopback_url("http://127.0.0.1:11434") and is_loopback_url("http://localhost:1234")
    assert not is_loopback_url("https://api.openai.com") and not is_loopback_url("https://evil.example.com")
    assert not is_loopback_url(None)


def test_is_loopback_url_rejects_bind_all_address():
    # 0.0.0.0 is a bind-all address, not a client-reachable loopback target -- classifying it as loopback would
    # let a custom provider URL skip the egress gate incorrectly.
    assert not is_loopback_url("http://0.0.0.0:11434")


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


def test_complete_responses_flat_output_text(monkeypatch: pytest.MonkeyPatch):
    """The OpenAI Responses wire format (inc 256): POST {base}/v1/responses, body {model, input}, prefer output_text."""
    cap = {}
    client = _FakeClient({"output_text": "hi there", "usage": {"input_tokens": 5, "output_tokens": 2}}, cap)
    cfg = _Cfg(
        "deepseek", model="deepseek-chat", api_key="sk-ds", base_url="https://api.deepseek.com", wire_format="responses"
    )
    res = complete(cfg, "PROMPT", http_client=client)
    assert res.text == "hi there" and res.usage_metadata.total_token_count == 7
    assert cap["url"] == "https://api.deepseek.com/v1/responses"
    assert cap["headers"]["Authorization"] == "Bearer sk-ds"
    assert cap["json"] == {"model": "deepseek-chat", "input": "PROMPT"}  # {model, input}, not messages[]


def test_complete_responses_walks_output_structure():
    """When there's no flat output_text, the parser walks output[].content[].text (raw Responses shape)."""
    cap = {}
    data = {
        "output": [
            {"type": "reasoning", "content": [{"type": "text", "text": "IGNORED"}]},  # non-message item skipped
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "part-1 "},
                    {"type": "output_text", "text": "part-2"},
                ],
            },
        ],
        "usage": {"total_tokens": 9},
    }
    client = _FakeClient(data, cap)
    cfg = _Cfg("custom", base_url="https://api.example.com", wire_format="responses")
    res = complete(cfg, "PROMPT", http_client=client)
    assert res.text == "part-1 part-2" and res.usage_metadata.total_token_count == 9


def test_requires_egress_config_is_endpoint_based():
    """A config arg is decided by endpoint, so a custom CLOUD url is gated exactly like Gemini and a custom
    LOOPBACK url is honestly no-egress — invariant #3 holds for an arbitrary user-supplied provider."""
    assert requires_egress(_Cfg("gemini"))  # the SDK always egresses to Google
    assert requires_egress(_Cfg("acme", base_url="https://api.acme.ai", wire_format="chat_completions"))
    assert not requires_egress(_Cfg("acme", base_url="http://127.0.0.1:1234", wire_format="chat_completions"))
    # No base_url → fall back to the provider name (a bare directly-built config).
    assert requires_egress(_Cfg("openai", base_url=None))
    assert not requires_egress(_Cfg("local", base_url=None))


def test_complete_local_loopback_uses_openai_shape():
    cap = {}
    client = _FakeClient({"choices": [{"message": {"content": "local-ok"}}], "usage": {}}, cap)
    cfg = _Cfg("local", model="llama3", api_key=None, base_url="http://127.0.0.1:11434")
    res = complete(cfg, "PROMPT", http_client=client)
    assert res.text == "local-ok"
    assert cap["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert "Authorization" not in cap["headers"]  # no key needed for a local server


def test_managed_local_gets_bounded_slow_device_timeout_without_changing_cloud():
    response = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
    local_cap, cloud_cap = {}, {}
    base_runtime = ProviderClientRuntime(http_client_factory=lambda _identity: _FakeClient(response, local_cap))
    local = _Cfg("managed_local", base_url="http://127.0.0.1:1234")
    local.provider_runtime = ManagedProviderRuntime(base_runtime, output_cap=2048)
    complete(local, "PROMPT")
    complete(_Cfg("openai"), "PROMPT", http_client=_FakeClient(response, cloud_cap))
    assert local_cap["timeout"] == 600.0
    assert cloud_cap["timeout"] == 60.0
    base_runtime.close()


class _FakeRuntime:
    """Captures the trust_env kwarg complete() passes to provider_runtime.run_http, bypassing the real
    ProviderClientRuntime's httpx.Client construction plumbing (which doesn't itself expose trust_env)."""

    def __init__(self, capture):
        self.capture = capture

    def run_http(self, *, base_url, timeout, operation, trust_env=True):
        self.capture["trust_env"] = trust_env
        response = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
        return operation(_FakeClient(response, {}))


def test_complete_forces_trust_env_false_for_a_manually_configured_loopback_provider():
    # A manually-configured "local"/custom loopback provider inherits LLMConfig's http_trust_env=True default --
    # without this guard it would honor an ambient HTTP_PROXY/HTTPS_PROXY, silently routing "local, no egress"
    # traffic through a proxy. The complete() dispatch seam must force trust_env=False for any loopback base_url
    # regardless of what the config itself claims.
    cap = {}
    cfg = _Cfg("local", model="llama3", api_key=None, base_url="http://127.0.0.1:11434")
    cfg.http_trust_env = True
    complete(cfg, "PROMPT", provider_runtime=_FakeRuntime(cap))
    assert cap["trust_env"] is False


def test_complete_respects_http_trust_env_for_a_real_cloud_provider():
    cap = {}
    cfg = _Cfg("openai", base_url="https://api.openai.com")
    cfg.http_trust_env = True
    complete(cfg, "PROMPT", provider_runtime=_FakeRuntime(cap))
    assert cap["trust_env"] is True


def test_complete_blocks_before_network_when_no_key_for_cloud_provider():
    """The seam every LLM feature routes through (axis-terms, summaries, help, …) must refuse a cloud call up
    front with a friendly message when no key is resolved, instead of letting a raw provider 401 (e.g.
    Anthropic's "x-api-key header is required" JSON) reach the user — the exact bug an external report
    surfaced via "Search related terms" with no Anthropic key configured."""

    class _Boom:
        def post(self, *a, **kw):
            raise AssertionError("must not reach the network when no API key is resolved")

    with pytest.raises(ProviderError, match="No API key"):
        complete(_Cfg("anthropic", api_key=None), "PROMPT", http_client=_Boom())


class _FakeErrorResp:
    """A response whose raise_for_status() raises like a real httpx.HTTPStatusError (inc 413 — classifying a
    real provider rejection: wrong/expired key, rate limit, outage — as opposed to _FakeResp above, which
    always succeeds)."""

    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text

    def raise_for_status(self):
        raise httpx.HTTPStatusError(f"{self.status_code}", request=None, response=self)

    def json(self):
        return {}


class _FakeErrorClient:
    def __init__(self, status_code, text=""):
        self._resp = _FakeErrorResp(status_code, text)

    def post(self, url, json=None, headers=None, timeout=None):
        return self._resp


def test_complete_gives_friendly_message_for_wrong_key_401():
    """A WRONG (not missing) key still reaches the network and gets a real 401 — the pre-check in complete()
    can't catch this ahead of time, but the response should still lead with a friendly interpretation rather
    than the raw provider JSON, with the raw detail kept (not hidden) after it."""
    raw = '{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}'
    client = _FakeErrorClient(401, raw)
    with pytest.raises(ProviderError) as exc:
        complete(_Cfg("anthropic", api_key="sk-wrong"), "PROMPT", http_client=client)
    msg = str(exc.value)
    assert "Authentication failed" in msg and "check the saved API key" in msg
    assert "HTTP 401" in msg and "authentication_error" in msg  # raw detail still present, not hidden


def test_complete_gives_friendly_message_for_429():
    with pytest.raises(ProviderError, match="Rate limited"):
        complete(_Cfg("openai", api_key="sk-oai"), "PROMPT", http_client=_FakeErrorClient(429, "slow down"))


def test_complete_gives_friendly_message_for_5xx():
    with pytest.raises(ProviderError, match="temporarily unavailable"):
        complete(_Cfg("anthropic", api_key="sk-ant"), "PROMPT", http_client=_FakeErrorClient(503, "overloaded"))


def test_complete_keeps_plain_format_for_an_unclassified_status():
    """No friendly guess for a status we're not confident about — stays the plain, honest raw format."""
    with pytest.raises(ProviderError) as exc:
        complete(_Cfg("openai", api_key="sk-oai"), "PROMPT", http_client=_FakeErrorClient(400, "bad request"))
    assert str(exc.value) == "HTTP 400: bad request"


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


def test_managed_primary_synthesis_contract_adds_llama_schema_at_transport_boundary():
    cap = {}
    response = {"choices": [{"message": {"content": "[]"}}], "usage": {}}
    runtime = ProviderClientRuntime(http_client_factory=lambda _identity: _FakeClient(response, cap))
    cfg = _Cfg("managed_local", api_key="local-token", base_url="http://127.0.0.1:1234")
    cfg.provider_runtime = ManagedProviderRuntime(runtime, output_cap=2048, contract="primary_synthesis")

    complete(cfg, "UNCHANGED PRODUCTION PROMPT")

    schema = cap["json"]["json_schema"]
    citation = schema["items"]["properties"]["citations"]["items"]
    assert citation["required"] == ["chunk_id", "quote"]
    assert cap["json"]["max_tokens"] == 2048
    assert cap["json"]["messages"][0]["content"] == "UNCHANGED PRODUCTION PROMPT"
    runtime.close()


def test_cloud_provider_never_inherits_managed_local_schema():
    cap = {}
    client = _FakeClient({"choices": [{"message": {"content": "[]"}}], "usage": {}}, cap)
    cfg = _Cfg("openai", api_key="sk-oai")
    cfg.managed_output_contract = "primary_synthesis"

    complete(cfg, "PROMPT", http_client=client)

    assert "json_schema" not in cap["json"]
