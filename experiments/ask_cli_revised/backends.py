"""Model backends for role binding: one call-record shape, and the residency guard for a single small GPU.

Every supervisory call and every native worker call goes through ``execution_policy.run_stage_call``, which expects the
record shape ``OllamaClient.chat`` returns. The Qwen2.5 worker on the shared Ollama is reached through the managed-local
completion path instead, so ``ManagedLocalChat`` adapts it to that same shape; the seam then classifies both identically
(NO ANSWER on a capped, unparseable, or schema-invalid call).

JUNO has one 8 GB GPU with ``OLLAMA_MAX_LOADED_MODELS=1`` per Ollama, and two Ollama processes (the shared one hosting the
Q2.5 worker, the isolated one hosting every candidate). ``ResidencyGuard`` therefore unloads the previous phase's model
before the next phase loads its own, and unloads only models this run loaded.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.backend.llm.providers import ProviderError, complete
from experiments.ask_cli_revised.calibration.structured_output import RESPONSE_FORMAT, schema_config


class ManagedLocalChat:
    """``OllamaClient.chat``-shaped adapter over the managed-local completion path (Qwen2.5 on the shared Ollama)."""

    def __init__(self, config, *, clock=time.monotonic):
        self.config = config
        self._clock = clock

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive=None, wall_timeout=None):
        started = self._clock()
        config = schema_config(self.config, output_cap=options["num_predict"], json_schema=schema, mode=RESPONSE_FORMAT)
        try:
            result = complete(config, prompt)
        except ProviderError as exc:
            return {
                "status": "provider_error",
                "error": str(exc),
                "content": "",
                "thinking": "",
                "done_reason": None,
                "timings": {},
                "wall_seconds": self._clock() - started,
            }
        usage = result.usage_metadata
        return {
            "status": "ok",
            "error": None,
            "content": result.text or "",
            "thinking": "",
            "done_reason": "length" if getattr(result, "truncated", False) else "stop",
            "timings": {
                "prompt_eval_count": getattr(usage, "prompt_token_count", None),
                "eval_count": getattr(usage, "candidates_token_count", None),
                "load_duration": None,
            },
            "wall_seconds": self._clock() - started,
        }


@dataclass(frozen=True)
class NativeWorker:
    """A worker bound to an Ollama-native model. ``QwenTasks`` routes its calls through the execution-policy seam."""

    client: object
    model: str
    base_options: dict
    think: bool | str | None = False  # workers run with thinking off: their caps are 48-512 tokens


@dataclass
class ResidencyGuard:
    """Keep one model resident per phase; unload only what this run loaded; record what was resident."""

    clients: dict
    events: list = field(default_factory=list)
    observations: list = field(default_factory=list)  # what was resident after a phase ran (its model's real footprint)
    _touched: list = field(default_factory=list)

    def _resident(self) -> dict:
        return {
            endpoint: [
                {"name": m.get("name") or m.get("model"), "size": m.get("size"), "size_vram": m.get("size_vram")}
                for m in client.ps()
            ]
            for endpoint, client in self.clients.items()
        }

    def enter(self, endpoint: str, model: str, *, phase: str) -> dict:
        started = time.monotonic()
        unloaded = []
        for touched in list(self._touched):
            if touched != (endpoint, model):
                self.clients[touched[0]].unload(touched[1])
                self._touched.remove(touched)
                unloaded.append(list(touched))
        if (endpoint, model) not in self._touched:
            self._touched.append((endpoint, model))
        event = {
            "phase": phase,
            "endpoint": endpoint,
            "model": model,
            "unloaded": unloaded,
            "resident": self._resident(),
            "wall_seconds": time.monotonic() - started,
        }
        self.events.append(event)
        return event

    def observe(self, phase: str) -> dict:
        """Record what is resident now. Entry snapshots precede the load; this one shows the model's real footprint."""
        try:
            observation = {"phase": phase, "resident": self._resident()}
        except Exception as exc:  # noqa: BLE001 - telemetry must never abort a run
            observation = {"phase": phase, "error": f"{type(exc).__name__}: {exc}"}
        self.observations.append(observation)
        return observation

    def release_all(self) -> None:
        for endpoint, model in list(self._touched):
            self.clients[endpoint].unload(model)
        self._touched.clear()
