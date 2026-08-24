from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.api.routers.summary_overview import resolve_overview_generator
from app.backend.llm.managed_local import (
    DESCRIPTOR_ENV,
    ENABLE_ENV,
    ManagedLocalTargetError,
    load_target_from_environment,
    resolve_managed_local_overview,
)
from app.backend.provider_runtime import ProviderClientRuntime
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from tests.api_helpers import (
    ApiFakeEmbeddingModel,
    ConstantSupportScorer,
    InMemoryVectorStore,
    _seed_summarization_library,
)

TOKEN = "local-token-abcdefghijklmnopqrstuvwxyz-0123456789"


def _descriptor(tmp_path: Path, *, endpoint: str = "http://127.0.0.1:32123", token: str = TOKEN) -> Path:
    private = tmp_path / "managed-local-ai"
    private.mkdir(parents=True)
    credential = private / "auth-token"
    credential.write_text(token, encoding="ascii")
    descriptor = private / "target.json"
    descriptor.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_id": "llama-cpp-0123456789ab-fedcba987654",
                "kind": "device_local",
                "endpoint": endpoint,
                "wire_format": "chat_completions",
                "credential_ref": str(credential),
                "model_alias": "callosum-managed-local",
                "runtime_family": "llama.cpp",
                "runtime_version": "version 10516 (b95502ba9)",
                "runtime_binary_digest": "a" * 64,
                "model_artifact_digest": "b" * 64,
                "chat_template_digest": "c" * 64,
                "context_tokens": 4096,
                "max_output_tokens": 256,
                "temperature": 0.0,
                "seed": 42,
                "execution_backend": "cpu",
                "qualification_state": "DEVELOPER_TEST_ONLY",
            }
        ),
        encoding="utf-8",
    )
    return descriptor


def _enable(monkeypatch: pytest.MonkeyPatch, descriptor: Path | None) -> None:
    monkeypatch.setenv(ENABLE_ENV, "1")
    if descriptor is None:
        monkeypatch.delenv(DESCRIPTOR_ENV, raising=False)
    else:
        monkeypatch.setenv(DESCRIPTOR_ENV, str(descriptor))


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://0.0.0.0:32123",
        "http://localhost:32123",
        "http://[::1]:32123",
        "https://127.0.0.1:32123",
        "http://127.0.0.1:32123/v1",
        "http://user@127.0.0.1:32123",
        "http://127.0.0.1:32123?next=https://cloud.example",
    ],
)
def test_managed_target_accepts_only_literal_ipv4_loopback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    _enable(monkeypatch, _descriptor(tmp_path, endpoint=endpoint))
    with pytest.raises(ManagedLocalTargetError, match="endpoint"):
        load_target_from_environment()


def test_descriptor_is_immutable_developer_only_and_secret_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor = _descriptor(tmp_path)
    _enable(monkeypatch, descriptor)
    target = load_target_from_environment()
    runtime = ProviderClientRuntime(http_client_factory=lambda identity: object())
    config = target.config(runtime)

    assert target.endpoint == "http://127.0.0.1:32123"
    assert target.qualification_state == "DEVELOPER_TEST_ONLY"
    assert target.model_alias == "callosum-managed-local"
    assert config.http_trust_env is False
    assert config.resolved_api_key() == TOKEN
    assert TOKEN not in descriptor.read_text(encoding="utf-8")
    assert TOKEN not in repr(config)
    with pytest.raises(FrozenInstanceError):
        target.endpoint = "http://127.0.0.1:1"  # type: ignore[misc]
    runtime.close()


def test_descriptor_and_credential_must_share_private_tauri_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor = _descriptor(tmp_path)
    payload = json.loads(descriptor.read_text(encoding="utf-8"))
    outside = tmp_path / "outside-token"
    outside.write_text(TOKEN, encoding="ascii")
    payload["credential_ref"] = str(outside)
    descriptor.write_text(json.dumps(payload), encoding="utf-8")
    _enable(monkeypatch, descriptor)
    with pytest.raises(ManagedLocalTargetError, match="credential_location"):
        load_target_from_environment()


def test_disabled_poc_does_not_read_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor = _descriptor(tmp_path)
    monkeypatch.delenv(ENABLE_ENV, raising=False)
    monkeypatch.setenv(DESCRIPTOR_ENV, str(descriptor))
    runtime = ProviderClientRuntime()
    resolution = resolve_managed_local_overview(runtime)
    assert resolution.enabled is False and resolution.target is None and resolution.config is None
    runtime.close()


def test_enabled_missing_or_stale_descriptor_fails_closed_without_cloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch, None)
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'missing.sqlite').as_posix()}")
    monkeypatch.setattr(
        "app.backend.api.routers.summary_overview.resolve_llm_config",
        lambda _api: (_ for _ in ()).throw(AssertionError("cloud config must not be resolved")),
    )
    assert resolve_overview_generator(app) is None

    descriptor = _descriptor(tmp_path / "second")
    _enable(monkeypatch, descriptor)
    descriptor.unlink()
    assert resolve_overview_generator(app) is None
    app.state.provider_client_runtime.close()
    app.state.model_runtime_registry.close()
    app.state.engine.dispose()


class _Response:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://127.0.0.1")
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError("failure", request=request, response=response)

    def json(self) -> dict:
        return self.payload


class _ManagedEndpointClient:
    def __init__(self, *, expected_token: str = TOKEN, malformed: bool = False) -> None:
        self.expected_token = expected_token
        self.malformed = malformed
        self.calls: list[dict[str, object]] = []
        self.closed = False

    def post(self, url, json=None, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if headers.get("Authorization") != f"Bearer {self.expected_token}":
            return _Response({"error": "unauthorized"}, 401)
        if self.malformed:
            return _Response({"choices": []})
        content = '[{"text":"Overview from local runtime.","claim_indices":[0]}]'
        return _Response({"choices": [{"message": {"content": content}}], "usage": {}})

    def close(self) -> None:
        self.closed = True


def test_overview_uses_existing_complete_and_parser_with_no_proxy_or_cloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor = _descriptor(tmp_path)
    _enable(monkeypatch, descriptor)
    endpoint_client = _ManagedEndpointClient()
    identities = []

    def factory(identity):  # type: ignore[no-untyped-def]
        identities.append(identity)
        return endpoint_client

    runtime = ProviderClientRuntime(http_client_factory=factory)
    app = create_app(
        db_url=f"sqlite:///{(tmp_path / 'route.sqlite').as_posix()}",
        provider_client_runtime=runtime,
    )
    generator = resolve_overview_generator(app)
    assert generator is not None
    result = generator.generate(verified_claims=["A verified claim."], scope_ref={})

    assert [(item.text, item.claim_indices) for item in result] == [("Overview from local runtime.", [0])]
    assert endpoint_client.calls[0]["url"] == "http://127.0.0.1:32123/v1/chat/completions"
    assert endpoint_client.calls[0]["headers"]["Authorization"] == f"Bearer {TOKEN}"  # type: ignore[index]
    assert "A verified claim." in endpoint_client.calls[0]["json"]["messages"][0]["content"]  # type: ignore[index]
    assert len(identities) == 1 and identities[0].trust_env is False
    runtime.close()
    app.state.model_runtime_registry.close()
    app.state.engine.dispose()


def test_wrong_token_is_rejected_by_inference_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor = _descriptor(tmp_path, token="wrong-token-abcdefghijklmnopqrstuvwxyz-0123456789")
    _enable(monkeypatch, descriptor)
    endpoint_client = _ManagedEndpointClient(expected_token=TOKEN)
    runtime = ProviderClientRuntime(http_client_factory=lambda identity: endpoint_client)
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'auth.sqlite').as_posix()}", provider_client_runtime=runtime)
    generator = resolve_overview_generator(app)
    assert generator is not None
    with pytest.raises(RuntimeError, match="Authentication failed"):
        generator.generate(verified_claims=["A verified claim."], scope_ref={})
    runtime.close()
    app.state.model_runtime_registry.close()
    app.state.engine.dispose()


def test_malformed_local_overview_fails_supplementary_work_without_cloud_or_primary_loss(
    temp_db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor = _descriptor(tmp_path)
    _enable(monkeypatch, descriptor)
    endpoint_client = _ManagedEndpointClient(malformed=True)
    runtime = ProviderClientRuntime(http_client_factory=lambda identity: endpoint_client)
    seeded = _seed_summarization_library(temp_db_url)
    summary = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="Facial anomalies influence social judgments.",
                    )
                ],
            )
        ]
    )
    app = create_app(
        db_url=temp_db_url,
        summary_generator=summary,
        embedding_model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        support_scorer=ConstantSupportScorer(),
        provider_client_runtime=runtime,
    )
    with TestClient(app) as client:
        started = client.post(
            "/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}
        ).json()
        result = client.get(f"/summarize/{started['job_id']}").json()

    assert result["status"] == "done"
    assert result["summary_status"] == "verified"
    assert result["overview_status"] == "failed"
    assert result["overview"] is None
    assert result["sentences"][0]["citations"][0]["status"] == "verified"
    assert len(endpoint_client.calls) == 1


def test_target_identity_distinguishes_runtime_model_template_and_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch, _descriptor(tmp_path))
    target = load_target_from_environment()
    changed = replace(target, execution_backend="gpu-layers:32")
    assert target != changed
    assert {
        target.target_id,
        target.runtime_version,
        target.runtime_binary_digest,
        target.model_artifact_digest,
        target.chat_template_digest,
        target.execution_backend,
    }
