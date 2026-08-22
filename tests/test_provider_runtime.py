"""App-scoped provider-client reuse, rotation, lifecycle, and semantics."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.api.dependencies import resolve_llm_config
from app.backend.llm.providers import ProviderError, complete
from app.backend.provider_runtime import GeminiClientIdentity, HttpClientIdentity, ProviderClientRuntime
from integrations.gemini.generator import LLMConfig


class _FakeHttpClient:
    def __init__(self, response_data: dict | None = None) -> None:
        self.response_data = response_data or {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        }
        self.requests: list[dict[str, object]] = []
        self.close_count = 0
        self.error: Exception | None = None
        self.status_code: int | None = None

    def post(self, url: str, *, json: dict, headers: dict, timeout: float) -> httpx.Response:
        self.requests.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self.error is not None:
            raise self.error
        request = httpx.Request("POST", url)
        if self.status_code is not None:
            return httpx.Response(self.status_code, json={"error": "rejected"}, request=request)
        return httpx.Response(200, json=self.response_data, request=request)

    def close(self) -> None:
        self.close_count += 1


@dataclass
class _GeminiResponse:
    text: str = "gemini-ok"
    usage_metadata: object | None = None


class _FakeGeminiModels:
    def __init__(self, owner: "_FakeGeminiClient") -> None:
        self.owner = owner

    def generate_content(self, *, model: str, contents: str) -> _GeminiResponse:
        self.owner.requests.append((model, contents))
        if self.owner.error is not None:
            raise self.owner.error
        return _GeminiResponse()


class _FakeGeminiClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.close_count = 0
        self.error: Exception | None = None
        self.models = _FakeGeminiModels(self)

    def close(self) -> None:
        self.close_count += 1


def _http_config(
    *,
    runtime: ProviderClientRuntime | None = None,
    base_url: str = "https://api.example.com",
    wire_format: str = "chat_completions",
    api_key: str = "secret-http-key",
) -> LLMConfig:
    return LLMConfig(
        provider="custom",
        model="test-model",
        api_key=api_key,
        base_url=base_url,
        wire_format=wire_format,
        data_egress_enabled=True,
        provider_runtime=runtime,
    )


def test_raw_http_client_is_constructed_once_for_twenty_compatible_acquisitions() -> None:
    constructed: list[_FakeHttpClient] = []
    runtime = ProviderClientRuntime(
        http_client_factory=lambda _identity: constructed.append(_FakeHttpClient()) or constructed[-1]
    )

    clients = [runtime.get_http_client(base_url="https://api.example.com", timeout=60.0) for _ in range(20)]

    assert len(constructed) == 1
    assert len({id(client) for client in clients}) == 1


def test_gemini_client_is_constructed_once_for_twenty_compatible_acquisitions() -> None:
    constructed: list[_FakeGeminiClient] = []
    runtime = ProviderClientRuntime(
        gemini_client_factory=lambda _key: constructed.append(_FakeGeminiClient()) or constructed[-1]
    )

    clients = [runtime.get_gemini_client(api_key="secret-gemini-key") for _ in range(20)]

    assert len(constructed) == 1
    assert len({id(client) for client in clients}) == 1


def test_config_rotation_creates_distinct_compatible_clients_without_key_disclosure() -> None:
    http_clients: list[_FakeHttpClient] = []
    gemini_clients: list[_FakeGeminiClient] = []
    runtime = ProviderClientRuntime(
        http_client_factory=lambda _identity: http_clients.append(_FakeHttpClient()) or http_clients[-1],
        gemini_client_factory=lambda _key: gemini_clients.append(_FakeGeminiClient()) or gemini_clients[-1],
    )

    first_http = runtime.get_http_client(base_url="https://old.example.com", timeout=60.0)
    second_http = runtime.get_http_client(base_url="https://new.example.com", timeout=60.0)
    first_gemini = runtime.get_gemini_client(api_key="old-secret-key")
    second_gemini = runtime.get_gemini_client(api_key="new-secret-key")

    assert first_http is not second_http and len(http_clients) == 2
    assert first_gemini is not second_gemini and len(gemini_clients) == 2
    identities = [identity for identity, _client, _count in runtime.client_entries()]
    assert any(isinstance(identity, HttpClientIdentity) for identity in identities)
    assert any(isinstance(identity, GeminiClientIdentity) for identity in identities)
    identity_text = repr(identities)
    assert "old-secret-key" not in identity_text and "new-secret-key" not in identity_text


def test_explicit_http_injection_wins_without_constructing_runtime_client() -> None:
    def must_not_construct(_identity: HttpClientIdentity) -> object:
        raise AssertionError("app-scoped client must not be constructed when an explicit client is injected")

    runtime = ProviderClientRuntime(http_client_factory=must_not_construct)
    injected = _FakeHttpClient()

    result = complete(_http_config(runtime=runtime), "PROMPT", http_client=injected)

    assert result.text == "ok"
    assert len(injected.requests) == 1
    assert runtime.client_entries() == ()


@pytest.mark.parametrize(
    ("wire_format", "response_data"),
    [
        (
            "chat_completions",
            {
                "choices": [{"message": {"content": "chat-ok"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        ),
        ("messages", {"content": [{"text": "messages-ok"}], "usage": {"input_tokens": 2, "output_tokens": 1}}),
        ("responses", {"output_text": "responses-ok", "usage": {"input_tokens": 2, "output_tokens": 1}}),
    ],
)
def test_runtime_and_explicit_http_paths_have_equivalent_requests(wire_format: str, response_data: dict) -> None:
    explicit = _FakeHttpClient(response_data)
    managed = _FakeHttpClient(response_data)
    runtime = ProviderClientRuntime(http_client_factory=lambda _identity: managed)
    config = _http_config(runtime=runtime, wire_format=wire_format)

    explicit_result = complete(config, "PROMPT", http_client=explicit)
    managed_result = complete(config, "PROMPT")

    assert explicit_result == managed_result
    assert explicit.requests == managed.requests
    assert managed.requests[0]["timeout"] == 60.0


def test_gemini_completion_reuses_client_and_rotates_on_key_change() -> None:
    constructed: list[tuple[str | None, _FakeGeminiClient]] = []

    def factory(key: str | None) -> object:
        client = _FakeGeminiClient()
        constructed.append((key, client))
        return client

    runtime = ProviderClientRuntime(gemini_client_factory=factory)
    old = LLMConfig(api_key="old-key", data_egress_enabled=True, provider_runtime=runtime)
    new = LLMConfig(api_key="new-key", data_egress_enabled=True, provider_runtime=runtime)

    assert complete(old, "one").text == "gemini-ok"
    assert complete(old, "two").text == "gemini-ok"
    assert complete(new, "three").text == "gemini-ok"
    assert complete(new, "four").text == "gemini-ok"

    assert len(constructed) == 2
    assert [len(client.requests) for _key, client in constructed] == [2, 2]
    assert constructed[0][1] is not constructed[1][1]
    assert constructed[0][1].requests == [("gemini-2.5-flash-lite", "one"), ("gemini-2.5-flash-lite", "two")]


def test_raw_http_key_rotation_reuses_safe_pool_but_sends_only_current_header() -> None:
    client = _FakeHttpClient()
    constructor_count = 0

    def factory(_identity: HttpClientIdentity) -> object:
        nonlocal constructor_count
        constructor_count += 1
        return client

    runtime = ProviderClientRuntime(http_client_factory=factory)
    complete(_http_config(runtime=runtime, api_key="old-http-key"), "old prompt")
    complete(_http_config(runtime=runtime, api_key="new-http-key"), "new prompt")

    assert constructor_count == 1
    assert client.requests[0]["headers"]["Authorization"] == "Bearer old-http-key"  # type: ignore[index]
    assert client.requests[1]["headers"]["Authorization"] == "Bearer new-http-key"  # type: ignore[index]
    assert "old-http-key" not in str(client.requests[1])


def test_runtime_preserves_timeout_http_status_and_malformed_response_errors() -> None:
    clients = [_FakeHttpClient(), _FakeHttpClient(), _FakeHttpClient({"unexpected": True})]
    clients[0].error = httpx.TimeoutException("timed out")
    clients[1].status_code = 401
    runtime = ProviderClientRuntime(http_client_factory=lambda _identity: clients.pop(0))

    with pytest.raises(ProviderError, match="timed out"):
        complete(_http_config(runtime=runtime, base_url="https://timeout.example"), "PROMPT")
    with pytest.raises(ProviderError, match="Authentication failed"):
        complete(_http_config(runtime=runtime, base_url="https://auth.example"), "PROMPT")
    with pytest.raises(ProviderError, match="Malformed chat-completions response"):
        complete(_http_config(runtime=runtime, base_url="https://malformed.example"), "PROMPT")


def test_runtime_preserves_gemini_error_redaction() -> None:
    key = "gemini-secret-that-must-not-leak"
    client = _FakeGeminiClient()
    client.error = RuntimeError(f"credential {key} rejected")
    runtime = ProviderClientRuntime(gemini_client_factory=lambda _key: client)
    config = LLMConfig(api_key=key, data_egress_enabled=True, provider_runtime=runtime)

    with pytest.raises(ProviderError) as exc:
        complete(config, "PROMPT")

    assert key not in str(exc.value)
    assert "***" in str(exc.value)


def test_simultaneous_http_first_acquisition_constructs_once_and_failed_load_retries() -> None:
    attempts = 0
    attempts_lock = threading.Lock()

    def factory(_identity: HttpClientIdentity) -> object:
        nonlocal attempts
        with attempts_lock:
            attempts += 1
            current = attempts
        if current == 1:
            raise RuntimeError("first construction failed")
        time.sleep(0.03)
        return _FakeHttpClient()

    runtime = ProviderClientRuntime(http_client_factory=factory)
    with pytest.raises(RuntimeError, match="first construction failed"):
        runtime.get_http_client(base_url="https://api.example.com", timeout=60.0)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [
            pool.submit(runtime.get_http_client, base_url="https://api.example.com", timeout=60.0) for _ in range(6)
        ]
        clients = [future.result(timeout=2) for future in futures]

    assert attempts == 2
    assert len({id(client) for client in clients}) == 1


def test_app_instances_have_isolated_provider_runtimes_and_clients() -> None:
    first_clients: list[_FakeHttpClient] = []
    second_clients: list[_FakeHttpClient] = []
    first_runtime = ProviderClientRuntime(
        http_client_factory=lambda _identity: first_clients.append(_FakeHttpClient()) or first_clients[-1]
    )
    second_runtime = ProviderClientRuntime(
        http_client_factory=lambda _identity: second_clients.append(_FakeHttpClient()) or second_clients[-1]
    )
    first_app = create_app(db_url="sqlite://", provider_client_runtime=first_runtime)
    second_app = create_app(db_url="sqlite://", provider_client_runtime=second_runtime)

    first_client = first_app.state.provider_client_runtime.get_http_client(
        base_url="https://api.example.com", timeout=60.0
    )
    second_client = second_app.state.provider_client_runtime.get_http_client(
        base_url="https://api.example.com", timeout=60.0
    )

    assert first_app.state.provider_client_runtime is not second_app.state.provider_client_runtime
    assert first_client is not second_client


def test_app_shutdown_closes_http_and_gemini_clients_idempotently(temp_db_url: str) -> None:
    http_client = _FakeHttpClient()
    gemini_client = _FakeGeminiClient()
    runtime = ProviderClientRuntime(
        http_client_factory=lambda _identity: http_client,
        gemini_client_factory=lambda _key: gemini_client,
    )
    app = create_app(db_url=temp_db_url, provider_client_runtime=runtime)

    with TestClient(app):
        runtime.get_http_client(base_url="https://api.example.com", timeout=60.0)
        runtime.get_gemini_client(api_key="secret-key")

    assert http_client.close_count == 1
    assert gemini_client.close_count == 1
    runtime.close()
    assert http_client.close_count == 1 and gemini_client.close_count == 1


def test_resolved_config_carries_only_its_apps_runtime() -> None:
    first = create_app(db_url="sqlite://")
    second = create_app(db_url="sqlite://")

    assert resolve_llm_config(first).provider_runtime is first.state.provider_client_runtime
    assert resolve_llm_config(second).provider_runtime is second.state.provider_client_runtime
    assert resolve_llm_config(first).provider_runtime is not resolve_llm_config(second).provider_runtime


def test_gemini_runtime_does_not_serialize_sdk_calls() -> None:
    runtime = ProviderClientRuntime(gemini_client_factory=lambda _key: object())
    active = 0
    max_active = 0
    active_lock = threading.Lock()
    barrier = threading.Barrier(4)

    def guarded(_client: object) -> None:
        nonlocal active, max_active
        with active_lock:
            active += 1
            max_active = max(max_active, active)
        barrier.wait(timeout=1)
        with active_lock:
            active -= 1

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(runtime.run_gemini, api_key="same", operation=guarded) for _ in range(4)]
        for future in futures:
            future.result(timeout=2)
    assert max_active == 4
