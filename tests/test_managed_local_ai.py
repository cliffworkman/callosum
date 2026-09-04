from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.api.dependencies import resolve_llm_config
from app.backend.api.routers.summary_overview import resolve_overview_generator
from app.backend.llm.managed_local import (
    _PREVIEW_OUTPUT_TOKENS,
    DESCRIPTOR_ENV,
    ENABLE_ENV,
    EXPECTED_PREVIEW_MODEL_DIGEST,
    ManagedLocalTargetError,
    load_preview_target,
    load_target_from_environment,
    resolve_managed_local_overview,
    with_managed_output_contract,
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
                "schema_version": 2,
                "target_id": "llama-cpp-0123456789ab-fedcba987654",
                "kind": "device_local",
                "endpoint": endpoint,
                "wire_format": "chat_completions",
                "credential_ref": str(credential),
                "model_alias": "callosum-managed-local",
                "runtime_family": "llama.cpp",
                "runtime_version": "version 10516 (b95502ba9)",
                "runtime_binary_digest": "a" * 64,
                "runtime_bundle_manifest_digest": "d" * 64,
                "declared_build_backend": "cpu",
                "model_artifact_digest": "b" * 64,
                "chat_template_digest": "c" * 64,
                "context_tokens": 4096,
                "max_output_tokens": 256,
                "temperature": 0.0,
                "seed": 42,
                "requested_execution": {"backend": "cpu", "gpu_layers": 0},
                "observed_execution": {"backend": "cpu", "gpu_layers": 0},
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


def _preview_descriptor(tmp_path: Path) -> Path:
    descriptor = _descriptor(tmp_path)
    payload = json.loads(descriptor.read_text(encoding="utf-8"))
    payload["qualification_state"] = "LOCAL_AI_PREVIEW"
    payload["model_artifact_digest"] = EXPECTED_PREVIEW_MODEL_DIGEST
    payload["context_tokens"] = 12_288
    # Sourced from the module rather than restated, so this fixture cannot silently disagree with the
    # contract it is meant to satisfy when the cap moves (it moved 2048 -> 4096 in inc 575).
    payload["max_output_tokens"] = _PREVIEW_OUTPUT_TOKENS
    descriptor.write_text(json.dumps(payload), encoding="utf-8")
    return descriptor


def test_preview_descriptor_requires_provider_wide_context_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    descriptor = _preview_descriptor(tmp_path)
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(tmp_path))
    assert load_preview_target().context_tokens == 12_288

    payload = json.loads(descriptor.read_text(encoding="utf-8"))
    payload["context_tokens"] = 4096
    descriptor.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManagedLocalTargetError, match="context_tokens"):
        load_preview_target()


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
    assert target.declared_build_backend == "cpu"
    assert target.requested_execution.backend == "cpu"
    assert target.requested_execution.gpu_layers == 0
    assert target.observed_execution == target.requested_execution
    assert config.http_trust_env is False
    assert config.resolved_api_key() == TOKEN
    assert TOKEN not in descriptor.read_text(encoding="utf-8")
    assert TOKEN not in repr(config)
    with pytest.raises(FrozenInstanceError):
        target.endpoint = "http://127.0.0.1:1"  # type: ignore[misc]
    runtime.close()


def test_stable_identity_fingerprint_ignores_endpoint_and_credential_but_not_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fingerprint that drives cache-identity restart-persistence (app/backend/llm/cache.py) must be
    invariant to the per-launch-ephemeral endpoint/token (a fresh random port + bearer token every Tauri
    launch) but MUST change when the actual model/runtime identity changes."""
    _enable(monkeypatch, _descriptor(tmp_path / "launch-1", endpoint="http://127.0.0.1:32123", token=TOKEN))
    launch_one = load_target_from_environment()

    other_token = "b" * 40
    _enable(monkeypatch, _descriptor(tmp_path / "launch-2", endpoint="http://127.0.0.1:60111", token=other_token))
    launch_two = load_target_from_environment()

    assert launch_one.stable_identity_fingerprint() == launch_two.stable_identity_fingerprint()

    runtime = ProviderClientRuntime(http_client_factory=lambda identity: object())
    assert (
        launch_one.config(runtime).stable_identity_fingerprint == launch_two.config(runtime).stable_identity_fingerprint
    )
    runtime.close()

    different_path = _descriptor(tmp_path / "different-model")
    different_payload = json.loads(different_path.read_text(encoding="utf-8"))
    different_payload["model_artifact_digest"] = "f" * 64
    different_path.write_text(json.dumps(different_payload), encoding="utf-8")
    _enable(monkeypatch, different_path)
    different = load_target_from_environment()

    assert different.stable_identity_fingerprint() != launch_one.stable_identity_fingerprint()


def test_managed_output_contract_is_immutable_and_changes_transport_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch, _descriptor(tmp_path))
    runtime = ProviderClientRuntime(http_client_factory=lambda identity: object())
    base = load_target_from_environment().config(runtime)
    synthesis = with_managed_output_contract(base, "primary_synthesis")

    assert base.managed_output_contract is None
    assert synthesis.managed_output_contract == "primary_synthesis"
    assert base.provider_runtime.output_cap == 256
    assert synthesis.provider_runtime.output_cap == 256
    assert synthesis.provider_runtime.contract == "primary_synthesis"
    with pytest.raises(FrozenInstanceError):
        synthesis.managed_output_contract = None  # type: ignore[misc]
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


def test_active_managed_provider_resolves_globally_without_api_key_or_cloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _preview_descriptor(tmp_path)
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(tmp_path))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"provider": "managed_local"}), encoding="utf-8")
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(settings))
    monkeypatch.delenv(ENABLE_ENV, raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    runtime = ProviderClientRuntime(http_client_factory=lambda identity: _ManagedEndpointClient())
    app = create_app(
        db_url=f"sqlite:///{(tmp_path / 'global.sqlite').as_posix()}",
        provider_client_runtime=runtime,
    )
    target = load_preview_target()
    config = resolve_llm_config(app)

    assert target.qualification_state == "LOCAL_AI_PREVIEW"
    assert config.provider == "managed_local"
    assert config.base_url == "http://127.0.0.1:32123"
    assert config.resolved_api_key() == TOKEN
    assert config.data_egress_enabled is False
    assert app.state.provider_client_runtime is runtime
    status = TestClient(app).get("/settings").json()
    assert status["generation_provider_available"] is True
    assert status["api_key_set"] is False
    assert status["provider_evidence"] == {
        "synthesis_overview": "evaluated",
        "other_generative_capabilities": "testing",
    }
    app.state.model_runtime_registry.close()
    app.state.engine.dispose()
    runtime.close()


def test_active_managed_provider_without_ready_descriptor_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"provider": "managed_local", "data_egress_enabled": True}), encoding="utf-8")
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(settings))
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(tmp_path))
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'closed.sqlite').as_posix()}")

    with pytest.raises(ManagedLocalTargetError, match="descriptor_unreadable"):
        resolve_llm_config(app)

    status = TestClient(app).get("/settings").json()
    assert status["generation_provider_available"] is False
    assert status["provider"] == "managed_local"

    app.state.provider_client_runtime.close()
    app.state.model_runtime_registry.close()
    app.state.engine.dispose()


def test_synthesize_job_reports_managed_local_not_ready_with_a_readable_reason_not_a_bare_code(
    temp_db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ManagedLocalTargetError raised inside the synthesize job (Local AI selected but not ready/crashed/
    stale) must not surface as the bare internal code (e.g. "ManagedLocalTargetError: descriptor_unreadable")
    in Status/the Ask panel -- Synthesize's own generic classifier (19_synthesis_failures.jsx) recognizes the
    "Local AI is not ready" wording and routes the user to Settings instead of a dead-end Retry."""
    db_url = temp_db_url
    _seed_summarization_library(db_url)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"provider": "managed_local", "data_egress_enabled": True}), encoding="utf-8")
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(settings))
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(tmp_path))  # no managed-local-ai/target.json written here
    app = create_app(
        db_url=db_url,
        embedding_model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        support_scorer=ConstantSupportScorer(),
    )
    client = TestClient(app)

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial"})
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "error"
    assert "Local AI is not ready (descriptor_unreadable)" in result["detail"]
    assert "Settings" in result["detail"]
    assert "ManagedLocalTargetError" not in result["detail"]
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
    changed = replace(target, runtime_bundle_manifest_digest="e" * 64)
    assert target != changed
    assert {
        target.target_id,
        target.runtime_version,
        target.runtime_binary_digest,
        target.runtime_bundle_manifest_digest,
        target.declared_build_backend,
        target.model_artifact_digest,
        target.chat_template_digest,
        target.requested_execution,
        target.observed_execution,
    }


@pytest.mark.parametrize(
    ("requested", "observed"),
    [
        ({"backend": "cpu", "gpu_layers": 0}, {"backend": "cuda", "gpu_layers": 8}),
        ({"backend": "cuda", "gpu_layers": 8}, {"backend": "cuda", "gpu_layers": 16}),
    ],
)
def test_python_descriptor_validation_rejects_execution_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requested: dict[str, object],
    observed: dict[str, object],
) -> None:
    descriptor = _descriptor(tmp_path)
    payload = json.loads(descriptor.read_text(encoding="utf-8"))
    payload["declared_build_backend"] = "cuda"
    payload["requested_execution"] = requested
    payload["observed_execution"] = observed
    descriptor.write_text(json.dumps(payload), encoding="utf-8")
    _enable(monkeypatch, descriptor)
    with pytest.raises(ManagedLocalTargetError, match="execution_mismatch"):
        load_target_from_environment()
