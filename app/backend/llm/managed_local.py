"""Strict target descriptor for Tauri-owned local generation.

Normal provider settings never pass through this module. The POC is active only when Tauri launches
the backend with both the explicit developer gate and a private descriptor path.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.backend.provider_runtime import ProviderClientRuntime

ENABLE_ENV = "CALLOSUM_LOCAL_AI_ENABLED"
DESCRIPTOR_ENV = "CALLOSUM_MANAGED_LOCAL_AI_DESCRIPTOR"
DEVELOPER_QUALIFICATION_STATE = "DEVELOPER_TEST_ONLY"
PREVIEW_QUALIFICATION_STATE = "LOCAL_AI_PREVIEW"
EXPECTED_PREVIEW_MODEL_DIGEST = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
MODEL_ALIAS = "callosum-managed-local"
_MAX_DESCRIPTOR_BYTES = 16_384
_MAX_CREDENTIAL_BYTES = 256
_DIGEST = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}")
_TARGET_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}")
_EXECUTION_BACKENDS = {"cpu", "cuda"}
_LOG = logging.getLogger(__name__)
_MANAGED_HTTP_TIMEOUT = 600.0
_QUALIFICATION_CONTEXT_TOKENS = 4096
_PREVIEW_CONTEXT_TOKENS = 12_288
_PRIMARY_SYNTHESIS_CONTRACT = "primary_synthesis"
_OVERVIEW_CONTRACT = "synthesis_overview"
AXIS_LABEL_CONTRACT = "axis_cluster_label"
# The managed target is a 1.5B Q4 model: without a grammar it does not reliably emit BARE JSON (it prefixes
# prose, appends commentary, or drifts), and axis labeling's parser then reads an empty object and silently
# keeps the local c-TF-IDF label. Primary synthesis already solved this with a grammar; this is the same
# mechanism for the same reason, mirroring the object the labeler's own prompt asks for.
_AXIS_LABEL_SCHEMA = {
    "type": "object",
    "required": ["label", "terms"],
    "additionalProperties": False,
    "properties": {
        "label": {"type": "string"},
        "terms": {"type": "array", "minItems": 4, "maxItems": 8, "items": {"type": "string"}},
    },
}
_PRIMARY_SYNTHESIS_SCHEMA = {
    "type": "array",
    "minItems": 4,
    "maxItems": 7,
    "items": {
        "type": "object",
        "required": ["text", "citations"],
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "citations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "required": ["chunk_id", "quote"],
                    "additionalProperties": False,
                    "properties": {
                        "chunk_id": {"type": "integer"},
                        "quote": {"type": "string"},
                    },
                },
            },
        },
    },
}


class ManagedLocalTargetError(ValueError):
    """A descriptor is absent, stale, malformed, or outside the POC's strict contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# One honest sentence per failure class, so every surface names the SAME cause rather than inventing
# its own wording (or, as axis-suggest used to, saying nothing at all). The code is always included:
# it is what a bug report needs, and it keeps the sentence checkable against the source.
_UNAVAILABLE_REASONS = {
    "app_data_missing": (
        "Local AI is selected, but this backend was not started by the Callosum desktop app, so it "
        "cannot reach the local model"
    ),
    "descriptor_missing": "Local AI is selected, but no developer descriptor path is configured",
    "descriptor_unreadable": "Local AI is selected, but the local model is not currently running",
}
_MALFORMED_DESCRIPTOR_CODES = {"descriptor_location", "descriptor_symlink", "descriptor_size", "descriptor_shape"}


def unavailable_reason(code: str) -> str:
    """Explain a `ManagedLocalTargetError.code` in one sentence that names the code."""
    if code in _UNAVAILABLE_REASONS:
        sentence = _UNAVAILABLE_REASONS[code]
    elif code in _MALFORMED_DESCRIPTOR_CODES:
        sentence = "Local AI is selected, but its descriptor file is malformed"
    elif code.startswith("credential_"):
        sentence = "Local AI is selected, but its access credential could not be read"
    else:
        sentence = "Local AI is selected, but its descriptor does not match the expected contract"
    return f"{sentence} ({code})."


@dataclass(frozen=True)
class ManagedExecutionState:
    backend: str
    gpu_layers: int


@dataclass(frozen=True)
class ManagedProviderConfig:
    """Provider-neutral fields consumed by ``complete`` for the managed target.

    This deliberately does not extend the historical ``LLMConfig`` record: the frozen qualification
    contracts import that class, while the managed preview needs additional request identity (an output cap
    and, for selected feature contracts, a llama.cpp grammar). Both remain transport/config concerns.
    """

    provider: str
    wire_format: str
    model: str
    api_key: str = field(repr=False)
    base_url: str
    data_egress_enabled: bool
    provider_runtime: "ManagedProviderRuntime"
    http_trust_env: bool
    max_output_tokens: int
    help_assistant_enabled: bool = False
    managed_output_contract: str | None = None
    # Restart-persistent cache identity (inc 558): the transport credential/base_url are per-launch-ephemeral
    # (a fresh random bearer token + port every Tauri launch, by design -- security, not scientific identity),
    # so app/backend/llm/cache.py's GenerationCacheIdentity keys on THIS instead for managed_local, letting a
    # semantically-identical request hit cache across a restart. Empty string (never used for anything else)
    # when unset, so directly-constructed test fixtures stay backward compatible.
    stable_identity_fingerprint: str = ""

    def resolved_api_key(self) -> str:
        return self.api_key


def with_managed_output_contract(config, contract: str):  # type: ignore[no-untyped-def]
    """Attach a managed-only transport contract without changing cloud/manual provider semantics."""
    if isinstance(config, ManagedProviderConfig):
        cap = 256 if contract == _OVERVIEW_CONTRACT else config.max_output_tokens
        runtime = ManagedProviderRuntime(config.provider_runtime.base_runtime, output_cap=cap, contract=contract)
        return replace(config, provider_runtime=runtime, max_output_tokens=cap, managed_output_contract=contract)
    return config


@dataclass(frozen=True)
class ManagedProviderRuntime:
    """Narrow request adapter around the app-owned client pool.

    The historical provider transport remains byte-for-byte frozen. This adapter changes only requests for the
    authenticated managed target: it supplies the explicit output cap and the one llama.cpp grammar required by
    primary synthesis, while retaining the underlying app-scoped connection pool.
    """

    base_runtime: ProviderClientRuntime = field(repr=False, compare=False)
    output_cap: int
    contract: str | None = None

    def run_http(self, *, base_url: str, timeout: float, trust_env: bool, operation):  # type: ignore[no-untyped-def]
        return self.base_runtime.run_http(
            base_url=base_url,
            timeout=_MANAGED_HTTP_TIMEOUT,
            trust_env=False,
            operation=lambda client: operation(_ManagedHttpClient(client, self.output_cap, self.contract)),
        )


@dataclass(frozen=True)
class _ManagedHttpClient:
    inner: Any = field(repr=False)
    output_cap: int
    contract: str | None

    def post(self, url, json=None, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        payload = dict(json or {})
        payload["max_tokens"] = self.output_cap
        if self.contract == _PRIMARY_SYNTHESIS_CONTRACT:
            payload["json_schema"] = _PRIMARY_SYNTHESIS_SCHEMA
        elif self.contract == AXIS_LABEL_CONTRACT:
            payload["json_schema"] = _AXIS_LABEL_SCHEMA
        return self.inner.post(
            url,
            json=payload,
            headers=headers,
            timeout=_MANAGED_HTTP_TIMEOUT,
        )


@dataclass(frozen=True)
class ManagedContractSummaryGenerator:
    """Give the managed request contract a distinct synthesis-cache identity."""

    inner: Any
    contract: str = _PRIMARY_SYNTHESIS_CONTRACT
    name: str = "managed-local-summary-contract"

    @property
    def cache_signature(self) -> str:
        return f"{self.inner.cache_signature}|{self.contract}|max-output-2048|schema-v1"

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.inner.generate(**kwargs)


def managed_summary_generator(config):  # type: ignore[no-untyped-def]
    """Build the unchanged production generator with a managed-only request/cache adapter."""
    from integrations.gemini import GeminiSummaryGenerator

    configured = with_managed_output_contract(config, _PRIMARY_SYNTHESIS_CONTRACT)
    inner = GeminiSummaryGenerator(config=configured)
    return ManagedContractSummaryGenerator(inner=inner) if configured is not config else inner


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

    def stable_identity_fingerprint(self) -> str:
        """A sha256 of everything that determines WHAT this target generates -- model/runtime/chat-template
        digests, context/output size, and the fixed sampling parameters -- deliberately excluding the
        per-launch-ephemeral endpoint/credential (security material, re-randomized every Tauri launch, never a
        scientific identity) and the observed/requested execution backend (a performance detail, not an
        output-determining one given generation is already fixed-temperature/fixed-seed deterministic)."""
        payload = {
            "model_alias": self.model_alias,
            "runtime_family": self.runtime_family,
            "runtime_version": self.runtime_version,
            "runtime_binary_digest": self.runtime_binary_digest,
            "runtime_bundle_manifest_digest": self.runtime_bundle_manifest_digest,
            "declared_build_backend": self.declared_build_backend,
            "model_artifact_digest": self.model_artifact_digest,
            "chat_template_digest": self.chat_template_digest,
            "context_tokens": self.context_tokens,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "seed": self.seed,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def config(self, provider_runtime: ProviderClientRuntime) -> ManagedProviderConfig:
        token = _read_credential(self.credential_ref)
        return ManagedProviderConfig(
            provider="managed_local",
            wire_format="chat_completions",
            model=self.model_alias,
            api_key=token,
            base_url=self.endpoint,
            data_egress_enabled=False,
            provider_runtime=ManagedProviderRuntime(
                provider_runtime,
                output_cap=self.max_output_tokens,
            ),
            http_trust_env=False,
            max_output_tokens=self.max_output_tokens,
            stable_identity_fingerprint=self.stable_identity_fingerprint(),
        )


@dataclass(frozen=True)
class ManagedLocalOverviewResolution:
    enabled: bool
    target: ManagedLocalTarget | None = None
    config: ManagedProviderConfig | None = None


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


def resolve_managed_local_provider(provider_runtime: ProviderClientRuntime) -> ManagedProviderConfig:
    """Resolve the production managed provider or fail closed without consulting another provider."""
    from app.backend.app_settings import load_settings

    target = load_preview_target()
    stored = load_settings().get("help_assistant_enabled")
    env_enabled = os.getenv("CALLOSUM_HELP_ASSISTANT_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    return replace(
        target.config(provider_runtime),
        help_assistant_enabled=stored if isinstance(stored, bool) else env_enabled,
    )


def load_preview_target() -> ManagedLocalTarget:
    descriptor_path = _preview_descriptor_path()
    target = _load_target(descriptor_path, {PREVIEW_QUALIFICATION_STATE})
    _require(target.model_artifact_digest == EXPECTED_PREVIEW_MODEL_DIGEST, "model_artifact_digest")
    return target


def _preview_descriptor_path() -> Path:
    root = os.getenv("CALLOSUM_APP_DATA_DIR")
    if not root:
        raise ManagedLocalTargetError("app_data_missing")
    return Path(root) / "managed-local-ai" / "target.json"


def load_target_from_environment() -> ManagedLocalTarget:
    raw_path = os.getenv(DESCRIPTOR_ENV)
    if not raw_path:
        raise ManagedLocalTargetError("descriptor_missing")
    return _load_target(Path(raw_path), {DEVELOPER_QUALIFICATION_STATE, PREVIEW_QUALIFICATION_STATE})


def _load_target(descriptor_path: Path, qualification_states: set[str]) -> ManagedLocalTarget:
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
    return _target_from_payload(payload, descriptor_path, qualification_states)


def _target_from_payload(
    payload: dict[str, object], descriptor_path: Path, qualification_states: set[str]
) -> ManagedLocalTarget:
    _require(payload.get("schema_version") == 2, "schema_version")
    _require(payload.get("kind") == "device_local", "target_kind")
    _require(payload.get("wire_format") == "chat_completions", "wire_format")
    _require(payload.get("model_alias") == MODEL_ALIAS, "model_alias")
    _require(payload.get("runtime_family") == "llama.cpp", "runtime_family")
    qualification_state = _bounded_string(payload, "qualification_state", 32)
    _require(qualification_state in qualification_states, "qualification_state")

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
    expected_context_tokens = (
        _QUALIFICATION_CONTEXT_TOKENS
        if qualification_state == DEVELOPER_QUALIFICATION_STATE
        else _PREVIEW_CONTEXT_TOKENS
    )
    _require(payload.get("context_tokens") == expected_context_tokens, "context_tokens")
    expected_output_tokens = 256 if qualification_state == DEVELOPER_QUALIFICATION_STATE else 2048
    _require(payload.get("max_output_tokens") == expected_output_tokens, "max_output_tokens")
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
        context_tokens=expected_context_tokens,
        max_output_tokens=expected_output_tokens,
        temperature=0.0,
        seed=42,
        requested_execution=requested_execution,
        observed_execution=observed_execution,
        qualification_state=qualification_state,
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
