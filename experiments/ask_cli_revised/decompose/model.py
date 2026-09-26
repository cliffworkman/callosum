"""Swappable JSON-model seam for the decomposition engine.

The engine only ever calls ``model.call(prompt, schema=..., output_cap=...)`` and reads the existing ``SchemaCall``
record, so any local model runtime can be plugged in. Every call site records ``model.label`` so each artifact says
which model produced it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from experiments.ask_cli_revised.calibration.structured_output import SchemaCall, classify, run_schema_call

# Mirrors the bakeoff envelope's generation options (temperature 0, fixed seed) so runs are reproducible.
BASE_OPTIONS = {"num_ctx": 12288, "temperature": 0, "seed": 42, "num_thread": 6, "num_batch": 512}
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = "callosum-managed-local"  # Qwen2.5-1.5B-Instruct-class Q4_K_M, the product's managed Local AI model


@dataclass(frozen=True)
class StopAwareCall(SchemaCall):
    """A call outcome that also carries the provider's own stop reason (``done_reason``), which ``SchemaCall`` does not. It is None
    for scripted and replayed calls, which have no provider to report one."""

    done_reason: str | None = None


class JsonModel(Protocol):
    label: str

    def call(self, prompt: str, *, schema: dict, output_cap: int) -> SchemaCall: ...

    def identity(self) -> dict: ...


class OllamaJsonModel:
    """Any Ollama-served model over a loopback endpoint (the JUNO SSH forwards); native ``format`` schema enforcement."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        client: Any = None,
        think: Any = None,
        wall_timeout: float | None = None,
    ):
        from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient

        self.model = model
        self.endpoint = endpoint
        self.think = think
        self.wall_timeout = wall_timeout  # per-call wall-clock watchdog (seconds); None keeps the client's own default
        self.client = client or OllamaClient(endpoint)
        self.label = f"ollama:{model}@{endpoint}" + ("" if think is None else f"[think={think}]")

    def call(self, prompt: str, *, schema: dict, output_cap: int) -> SchemaCall:
        options = {**BASE_OPTIONS, "num_predict": output_cap}
        extra = {} if self.wall_timeout is None else {"wall_timeout": self.wall_timeout}
        record = self.client.chat(self.model, prompt, schema=schema, options=options, think=self.think, **extra)
        content = record.get("content") or ""
        if record.get("status") != "ok":
            return SchemaCall(
                raw_text=content,
                parsed=None,
                provider_ok=False,
                truncated=False,
                schema_ok=False,
                failure_reason=f"{record.get('status')}: {record.get('error')}",
                elapsed_seconds=record.get("wall_seconds") or 0.0,
                output_cap=output_cap,
                mode="ollama_native_format",
            )
        truncated = record.get("done_reason") == "length"
        parsed, schema_ok, reason = classify(content, truncated)
        return StopAwareCall(
            raw_text=content,
            parsed=parsed,
            provider_ok=True,
            truncated=truncated,
            schema_ok=schema_ok,
            failure_reason=reason,
            elapsed_seconds=record.get("wall_seconds") or 0.0,
            output_cap=output_cap,
            mode="ollama_native_format",
            done_reason=record.get("done_reason"),
        )

    def identity(self) -> dict:
        info: dict = {
            "kind": "ollama",
            "model": self.model,
            "endpoint": self.endpoint,
            "think": self.think,
            "options": dict(BASE_OPTIONS),
            "wall_timeout_seconds": self.wall_timeout,
        }
        try:
            from experiments.ask_cli_revised.supervisor_eval.ollama_client import summarize_show

            shown = self.client.show(self.model)
            info["show"] = summarize_show(shown)
            info["digest"] = shown.get("details", {}).get("parent_model") or shown.get("digest")
        except Exception as exc:  # noqa: BLE001 - identity capture must never abort a run
            info["show_error"] = f"{type(exc).__name__}: {exc}"
        return info


class ManagedLocalJsonModel:
    """The production managed-local descriptor path (llama.cpp), through the existing schema-constrained call."""

    def __init__(self, base_config: Any, mode: str):
        self.base_config = base_config
        self.mode = mode
        self.label = f"managed-local:{mode}"

    def call(self, prompt: str, *, schema: dict, output_cap: int) -> SchemaCall:
        return run_schema_call(self.base_config, prompt, output_cap=output_cap, json_schema=schema, mode=self.mode)

    def identity(self) -> dict:
        return {"kind": "managed_local", "wire_mode": self.mode}


class ScriptedModel:
    """Deterministic test double: ``responder(prompt, schema)`` returns a dict/list (JSON-encoded), a str, or None (failure)."""

    def __init__(self, responder: Callable[[str, dict], Any], label: str = "scripted"):
        self.responder = responder
        self.label = label
        self.calls: list[dict] = []

    def call(self, prompt: str, *, schema: dict, output_cap: int) -> SchemaCall:
        result = self.responder(prompt, schema)
        self.calls.append({"prompt": prompt, "schema": schema, "result": result})
        if result is None:
            return SchemaCall(
                "", None, False, False, False, "provider_error: scripted failure", 0.0, output_cap, "scripted"
            )
        raw = result if isinstance(result, str) else json.dumps(result)
        parsed, schema_ok, reason = classify(raw, False)
        return SchemaCall(raw, parsed, True, False, schema_ok, reason, 0.0, output_cap, "scripted")

    def identity(self) -> dict:
        return {"kind": "scripted", "label": self.label}


class ReplayModel:
    """Re-run the engine over RECORDED outputs: no new model call is ever made. A prompt with no recorded response is
    reported as a provider failure (``replay_miss``) so the engine degrades exactly as it would on a real failure."""

    def __init__(self, records: list[dict], source_label: str):
        import hashlib

        self._hash = lambda prompt: hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self._by_prompt: dict[str, list[str]] = {}
        for rec in records:
            self._by_prompt.setdefault(self._hash(rec["prompt"]), []).append(rec["raw_output"])
        self._used: dict[str, int] = {}
        self.source_label = source_label
        self.label = f"replay[{source_label}]"
        self.misses: list[str] = []

    def call(self, prompt: str, *, schema: dict, output_cap: int) -> SchemaCall:
        key = self._hash(prompt)
        outputs = self._by_prompt.get(key)
        if not outputs:
            self.misses.append(prompt[:120])
            return SchemaCall(
                "",
                None,
                False,
                False,
                False,
                "replay_miss: no recorded response for this prompt",
                0.0,
                output_cap,
                "replay",
            )
        raw = outputs[min(self._used.get(key, 0), len(outputs) - 1)]
        self._used[key] = self._used.get(key, 0) + 1
        parsed, schema_ok, reason = classify(raw, False)
        return SchemaCall(raw, parsed, True, False, schema_ok, reason, 0.0, output_cap, "replay")

    def identity(self) -> dict:
        return {
            "kind": "replay",
            "source_model_label": self.source_label,
            "new_model_calls": 0,
            "replay_misses": len(self.misses),
            "note": "recorded outputs of the source model re-scored by the current code; not a new model run",
        }
