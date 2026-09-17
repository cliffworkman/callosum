"""Schema-constrained managed-local calls for Run 0.5, plus the pre-calibration enforcement smoke test.

This mirrors the *mechanism* production already uses for primary-synthesis / axis-labeling — one field
injected into the OpenAI-compatible chat/completions payload that constrains the decode to a JSON schema
(`app/backend/llm/managed_local.py::_ManagedHttpClient`). It is NOT a parallel grammar subsystem: it is
the same one-field injection, parameterized by a caller-supplied schema, built entirely in experiment
code so no production module is touched.

Two wire modes are supported because the Juno replay runtime is *ollama*, not the shipping llama.cpp
`b10516`:
  - ``top_level``      : ``payload["json_schema"] = <schema>`` (what production sends; native to
                          llama.cpp's own server).
  - ``response_format``: ``payload["response_format"] = {"type":"json_schema","json_schema":{...}}``
                          (the OpenAI-standard shape ollama documents).
The smoke test decides empirically which the live topology actually enforces; if neither does, Run 0.5
STOPS rather than silently accepting unconstrained JSON.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from typing import Any

from app.backend.llm.providers import ProviderError, complete
from app.backend.provider_runtime import ProviderClientRuntime

_MANAGED_HTTP_TIMEOUT = 600.0

TOP_LEVEL = "top_level"
RESPONSE_FORMAT = "response_format"
WIRE_MODES = (TOP_LEVEL, RESPONSE_FORMAT)


@dataclass(frozen=True)
class _SchemaHttpClient:
    """Wraps the app-owned httpx client; injects the output cap + one schema field per request."""

    inner: Any = field(repr=False)
    output_cap: int
    json_schema: dict | None
    mode: str

    def post(self, url, json=None, headers=None, timeout=None):  # type: ignore[no-untyped-def]
        payload = dict(json or {})
        payload["max_tokens"] = self.output_cap
        if self.json_schema is not None:
            if self.mode == RESPONSE_FORMAT:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "calibration", "schema": self.json_schema, "strict": True},
                }
            else:
                payload["json_schema"] = self.json_schema
        return self.inner.post(url, json=payload, headers=headers, timeout=_MANAGED_HTTP_TIMEOUT)


@dataclass(frozen=True)
class _SchemaProviderRuntime:
    """A ManagedProviderRuntime-shaped adapter that injects a caller-supplied schema (not the two fixed
    production contracts). Reuses the same app-scoped connection pool."""

    base_runtime: ProviderClientRuntime = field(repr=False, compare=False)
    output_cap: int
    json_schema: dict | None
    mode: str

    def run_http(self, *, base_url, timeout, trust_env, operation):  # type: ignore[no-untyped-def]
        return self.base_runtime.run_http(
            base_url=base_url,
            timeout=_MANAGED_HTTP_TIMEOUT,
            trust_env=False,
            operation=lambda client: operation(_SchemaHttpClient(client, self.output_cap, self.json_schema, self.mode)),
        )


def schema_config(base_config, *, output_cap: int, json_schema: dict | None, mode: str):
    """Return a managed-local config that injects ``json_schema`` at ``output_cap`` via ``mode``.

    ``base_config`` is the ManagedProviderConfig from ``resolve_managed_local_provider``; its
    ``provider_runtime.base_runtime`` is the shared ``ProviderClientRuntime`` pool (the same access
    ``experiments.ask_cli_revised.qwen._with_output_cap`` uses).
    """
    base_runtime = base_config.provider_runtime.base_runtime
    runtime = _SchemaProviderRuntime(base_runtime, output_cap=output_cap, json_schema=json_schema, mode=mode)
    return replace(
        base_config,
        provider_runtime=runtime,
        max_output_tokens=output_cap,
        managed_output_contract=None,
    )


def extract_json(text: str):
    """First balanced JSON value embedded in model text (mirrors qwen._extract_json)."""
    if not text:
        return None
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(text, index)
        except ValueError:
            continue
        return payload
    return None


def classify(raw_text: str, truncated: bool) -> tuple[Any, bool, str | None]:
    """Keep the three failure classes separable: truncation vs no-structured-output vs (parsed) semantic.

    Truncation is reported even when partial JSON parsed, because a capped decode is not a clean success.
    """
    parsed = extract_json(raw_text)
    schema_ok = isinstance(parsed, (dict, list))
    if truncated:
        return parsed, schema_ok, "truncated_at_output_cap"
    if not schema_ok:
        return parsed, schema_ok, "no_structured_output"
    return parsed, schema_ok, None


@dataclass(frozen=True)
class SchemaCall:
    """One schema-constrained call outcome, keeping the three failure classes separable."""

    raw_text: str
    parsed: Any
    provider_ok: bool
    truncated: bool
    schema_ok: bool  # parsed to a JSON object/array (grammar produced structured output)
    failure_reason: str | None
    elapsed_seconds: float
    output_cap: int
    mode: str


def run_schema_call(base_config, prompt: str, *, output_cap: int, json_schema: dict, mode: str) -> SchemaCall:
    config = schema_config(base_config, output_cap=output_cap, json_schema=json_schema, mode=mode)
    started = time.monotonic()
    try:
        result = complete(config, prompt)
    except ProviderError as exc:
        return SchemaCall(
            raw_text="",
            parsed=None,
            provider_ok=False,
            truncated=False,
            schema_ok=False,
            failure_reason=f"provider_error: {exc}",
            elapsed_seconds=time.monotonic() - started,
            output_cap=output_cap,
            mode=mode,
        )
    elapsed = time.monotonic() - started
    raw = result.text or ""
    truncated = bool(getattr(result, "truncated", False))
    parsed, schema_ok, reason = classify(raw, truncated)
    return SchemaCall(
        raw_text=raw,
        parsed=parsed,
        provider_ok=True,
        truncated=truncated,
        schema_ok=schema_ok,
        failure_reason=reason,
        elapsed_seconds=elapsed,
        output_cap=output_cap,
        mode=mode,
    )


# ---- pre-calibration enforcement smoke test ----------------------------------------------------------

# A neutral schema whose only valid answers are five letters; a prompt whose *natural* answer is prose.
# If the runtime enforces the grammar, the output is a bare object with a single-letter `window`; if it
# ignores the grammar, the model answers in prose and `schema_ok`/enum-membership fails. No AIB content.
_SMOKE_SCHEMA = {
    "type": "object",
    "required": ["window"],
    "additionalProperties": False,
    "properties": {"window": {"type": "string", "enum": ["A", "B", "C", "D", "E"]}},
}
_SMOKE_PROMPTS = (
    "Greet me warmly in one friendly sentence.",
    "Pick a letter for this made-up label and return it as window: A, B, C, D, or E.",
    "Describe the color blue to someone who has never seen it.",
)


@dataclass(frozen=True)
class SmokeResult:
    mode: str
    enforced: bool
    calls: tuple[dict, ...]


def smoke_test_mode(base_config, mode: str, *, output_cap: int = 64) -> SmokeResult:
    """Return whether ``mode`` actually constrains output to the enum schema across the neutral prompts."""
    calls: list[dict] = []
    enforced = True
    for prompt in _SMOKE_PROMPTS:
        call = run_schema_call(base_config, prompt, output_cap=output_cap, json_schema=_SMOKE_SCHEMA, mode=mode)
        window = call.parsed.get("window") if isinstance(call.parsed, dict) else None
        ok = call.schema_ok and isinstance(window, str) and window in {"A", "B", "C", "D", "E"}
        enforced = enforced and ok
        calls.append(
            {
                "prompt": prompt,
                "raw_output": call.raw_text[:400],
                "parsed": call.parsed,
                "schema_ok": call.schema_ok,
                "enum_ok": ok,
                "truncated": call.truncated,
                "elapsed_seconds": round(call.elapsed_seconds, 3),
            }
        )
    return SmokeResult(mode=mode, enforced=enforced, calls=tuple(calls))


def choose_enforcing_mode(base_config) -> tuple[str | None, list[SmokeResult]]:
    """Try each wire mode; return the first that enforces the schema (or None → STOP), with all results."""
    results: list[SmokeResult] = []
    for mode in WIRE_MODES:
        result = smoke_test_mode(base_config, mode)
        results.append(result)
        if result.enforced:
            return mode, results
    return None, results
