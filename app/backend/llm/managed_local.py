"""Strict developer-only target descriptor for Tauri-owned local Overview inference.

Normal provider settings never pass through this module. The POC is active only when Tauri launches
the backend with both the explicit developer gate and a private descriptor path.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.backend.provider_runtime import ProviderClientRuntime
from integrations.gemini.generator import LLMConfig

ENABLE_ENV = "CALLOSUM_LOCAL_AI_ENABLED"
DESCRIPTOR_ENV = "CALLOSUM_MANAGED_LOCAL_AI_DESCRIPTOR"
QUALIFICATION_STATE = "DEVELOPER_TEST_ONLY"
MODEL_ALIAS = "callosum-managed-local"
_MAX_DESCRIPTOR_BYTES = 16_384
_MAX_CREDENTIAL_BYTES = 256
_DIGEST = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}")
_TARGET_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}")
_EXECUTION_BACKENDS = {"cpu", "cuda"}
_LOG = logging.getLogger(__name__)


class ManagedLocalTargetError(ValueError):
    """A descriptor is absent, stale, malformed, or outside the POC's strict contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ManagedExecutionState:
    backend: str
    gpu_layers: int


@dataclass(frozen=True)
class ManagedLocalTarget:
    target_id: str
    endpoint: str
    credential_ref: Path
    model_alias: str
    runtime_family: str
    runtime_version: str
    runtime_binary_digest: str
    runtime_bundle_manifest_digest: str
    declared_build_backend: str
    model_artifact_digest: str
    chat_template_digest: str | None
    context_tokens: int
    max_output_tokens: int
    temperature: float
    seed: int
    requested_execution: ManagedExecutionState
    observed_execution: ManagedExecutionState
    qualification_state: str

    def config(self, provider_runtime: ProviderClientRuntime) -> LLMConfig:
        token = _read_credential(self.credential_ref)
        return LLMConfig(
            provider="local",
            wire_format="chat_completions",
            model=self.model_alias,
            api_key=token,
            base_url=self.endpoint,
            data_egress_enabled=False,
            provider_runtime=provider_runtime,
            http_trust_env=False,
        )


@dataclass(frozen=True)
class ManagedLocalOverviewResolution:
    enabled: bool
    target: ManagedLocalTarget | None = None
    config: LLMConfig | None = None


def resolve_managed_local_overview(provider_runtime: ProviderClientRuntime) -> ManagedLocalOverviewResolution:
    """Resolve the Tauri descriptor, or fail closed without consulting any cloud provider."""
    if os.getenv(ENABLE_ENV) != "1":
        return ManagedLocalOverviewResolution(enabled=False)
    try:
        target = load_target_from_environment()
        return ManagedLocalOverviewResolution(
            enabled=True,
            target=target,
            config=target.config(provider_runtime),
        )
    except ManagedLocalTargetError as exc:
        _LOG.warning("Developer managed local AI Overview is unavailable (%s)", exc.code)
        return ManagedLocalOverviewResolution(enabled=True)


def load_target_from_environment() -> ManagedLocalTarget:
    raw_path = os.getenv(DESCRIPTOR_ENV)
    if not raw_path:
        raise ManagedLocalTargetError("descriptor_missing")
    descriptor_path = Path(raw_path)
    if descriptor_path.name != "target.json" or descriptor_path.parent.name != "managed-local-ai":
        raise ManagedLocalTargetError("descriptor_location")
    if descriptor_path.is_symlink():
        raise ManagedLocalTargetError("descriptor_symlink")
    try:
        if descriptor_path.stat().st_size > _MAX_DESCRIPTOR_BYTES:
            raise ManagedLocalTargetError("descriptor_size")
        payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except ManagedLocalTargetError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManagedLocalTargetError("descriptor_unreadable") from exc
    if not isinstance(payload, dict):
        raise ManagedLocalTargetError("descriptor_shape")
    return _target_from_payload(payload, descriptor_path)


def _target_from_payload(payload: dict[str, object], descriptor_path: Path) -> ManagedLocalTarget:
    _require(payload.get("schema_version") == 2, "schema_version")
    _require(payload.get("kind") == "device_local", "target_kind")
    _require(payload.get("wire_format") == "chat_completions", "wire_format")
    _require(payload.get("model_alias") == MODEL_ALIAS, "model_alias")
    _require(payload.get("runtime_family") == "llama.cpp", "runtime_family")
    _require(payload.get("qualification_state") == QUALIFICATION_STATE, "qualification_state")

    target_id = _bounded_string(payload, "target_id", 128)
    _require(bool(_TARGET_ID.fullmatch(target_id)), "target_id")
    endpoint = _strict_endpoint(_bounded_string(payload, "endpoint", 128))
    runtime_version = _bounded_string(payload, "runtime_version", 160)
    runtime_digest = _digest_value(payload, "runtime_binary_digest")
    bundle_digest = _digest_value(payload, "runtime_bundle_manifest_digest")
    declared_build_backend = _bounded_string(payload, "declared_build_backend", 16)
    _require(declared_build_backend in _EXECUTION_BACKENDS, "declared_build_backend")
    model_digest = _digest_value(payload, "model_artifact_digest")
    template_digest_raw = payload.get("chat_template_digest")
    template_digest = None if template_digest_raw is None else _digest_value(payload, "chat_template_digest")
    credential_ref = _credential_path(payload, descriptor_path)
    requested_execution = _execution_state(payload, "requested_execution")
    observed_execution = _execution_state(payload, "observed_execution")
    _require(requested_execution == observed_execution, "execution_mismatch")
    _require(
        declared_build_backend == "cuda" or requested_execution == ManagedExecutionState("cpu", 0),
        "declared_build_backend",
    )
    _require(payload.get("context_tokens") == 4096, "context_tokens")
    _require(payload.get("max_output_tokens") == 256, "max_output_tokens")
    temperature = payload.get("temperature")
    _require(
        isinstance(temperature, (int, float)) and not isinstance(temperature, bool) and temperature == 0, "temperature"
    )
    _require(payload.get("seed") == 42, "seed")
    return ManagedLocalTarget(
        target_id=target_id,
        endpoint=endpoint,
        credential_ref=credential_ref,
        model_alias=MODEL_ALIAS,
        runtime_family="llama.cpp",
        runtime_version=runtime_version,
        runtime_binary_digest=runtime_digest,
        runtime_bundle_manifest_digest=bundle_digest,
        declared_build_backend=declared_build_backend,
        model_artifact_digest=model_digest,
        chat_template_digest=template_digest,
        context_tokens=4096,
        max_output_tokens=256,
        temperature=0.0,
        seed=42,
        requested_execution=requested_execution,
        observed_execution=observed_execution,
        qualification_state=QUALIFICATION_STATE,
    )


def _strict_endpoint(value: str) -> str:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError as exc:
        raise ManagedLocalTargetError("endpoint") from exc
    _require(
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and port is not None
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.params
        and not parsed.query
        and not parsed.fragment,
        "endpoint",
    )
    return f"http://127.0.0.1:{port}"


def _execution_state(payload: dict[str, object], key: str) -> ManagedExecutionState:
    raw = payload.get(key)
    _require(isinstance(raw, dict) and set(raw) == {"backend", "gpu_layers"}, key)
    backend = raw.get("backend")  # type: ignore[union-attr]
    gpu_layers = raw.get("gpu_layers")  # type: ignore[union-attr]
    _require(isinstance(backend, str) and backend in _EXECUTION_BACKENDS, key)
    _require(isinstance(gpu_layers, int) and not isinstance(gpu_layers, bool) and 0 <= gpu_layers <= 999, key)
    _require((backend == "cpu") == (gpu_layers == 0), key)
    return ManagedExecutionState(backend=backend, gpu_layers=gpu_layers)


def _credential_path(payload: dict[str, object], descriptor_path: Path) -> Path:
    raw = _bounded_string(payload, "credential_ref", 1024)
    candidate = Path(raw)
    _require(candidate.name == "auth-token", "credential_location")
    _require(not candidate.is_symlink(), "credential_symlink")
    try:
        resolved_parent = candidate.parent.resolve(strict=True)
        descriptor_parent = descriptor_path.parent.resolve(strict=True)
    except OSError as exc:
        raise ManagedLocalTargetError("credential_location") from exc
    _require(resolved_parent == descriptor_parent, "credential_location")
    return candidate


def _read_credential(path: Path) -> str:
    try:
        if path.stat().st_size > _MAX_CREDENTIAL_BYTES:
            raise ManagedLocalTargetError("credential_size")
        token = path.read_text(encoding="ascii")
    except ManagedLocalTargetError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ManagedLocalTargetError("credential_unreadable") from exc
    _require(bool(_TOKEN.fullmatch(token)), "credential_shape")
    return token


def _bounded_string(payload: dict[str, object], key: str, maximum: int) -> str:
    value = payload.get(key)
    _require(isinstance(value, str) and 0 < len(value) <= maximum, key)
    return value  # type: ignore[return-value]


def _digest_value(payload: dict[str, object], key: str) -> str:
    value = _bounded_string(payload, key, 64)
    _require(bool(_DIGEST.fullmatch(value)), key)
    return value


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ManagedLocalTargetError(code)
