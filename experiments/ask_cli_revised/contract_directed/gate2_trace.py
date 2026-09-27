"""Durable, crash-recoverable tracing for a Gate 2 overview diagnostic call (2026-09-27).

Real incident: a bridge bug (`overview_bridge.real_obligation_states` missing a field) crashed the diagnostic
driver AFTER a live model call had already succeeded and BEFORE anything was written to disk -- the raw
response was lost with the process. This module exists so that specific failure window can never recur: it
wraps `overview.build_overview`'s two additive hooks (`on_prompt_ready`/`on_raw_response`) so the prompt, the
input manifest, and the raw model response are each written to disk the moment they exist -- never only after
`build_overview` returns normally. A caller wraps its own call to `build_overview` in a `try`/`except` and calls
`.exception()` on any failure; every write here is synchronous and immediate, so a crash anywhere downstream of
a hook firing still leaves that hook's data on disk.

**What this cannot cover:** termination before the model call returns at all (the process killed mid-request,
or a hang) -- `on_raw_response` only fires once `supervisor.call(...)` has actually returned an object. In that
window only the prompt (written by `on_prompt_ready`, which fires first) is recoverable; the model's own
response, even if the remote server finished generating it, is not, because this process never received it as
a Python value to persist. This is a fundamentally different failure window from the incident this module
fixes (which crashed strictly after a successful return) and no in-process trace can close it -- recovering
from it would need out-of-process logging on the Ollama server side, which is out of scope here.
"""

from __future__ import annotations

import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class DiagnosticTrace:
    """One attempt's durable trace directory. Every write is complete and self-contained on its own -- reading
    the directory after a crash never needs a later file to interpret an earlier one. `run_dir` must not already
    exist (a fresh attempt directory every time; an attempt is never overwritten or reused)."""

    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self._write_json("00_trace_started.json", {"started_at": _now()})

    def _write_json(self, name: str, payload: dict) -> Path:
        path = self.run_dir / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path

    def manifest_ready(self, manifest_rows: list[dict]) -> None:
        """Optional, and earlier than `prompt_ready`: the contract-directed manifest rows themselves (before
        they are even projected into overview.py's sealed-ledger shape). A caller that has this data before
        building the sealed ledger should write it as soon as it exists, rather than waiting."""
        self._write_json("01_contract_directed_manifest.json", {"written_at": _now(), "manifest_rows": manifest_rows})

    def prompt_ready(self, prompt: str, manifest: dict) -> None:
        """The `on_prompt_ready` hook body: called by `overview.build_overview` before any model call is made."""
        self._write_json(
            "02_prompt_and_manifest.json",
            {"written_at": _now(), "prompt": prompt, "prompt_sha256": _sha256(prompt), "manifest": manifest},
        )

    def raw_response(self, result) -> None:
        """The `on_raw_response` hook body: called by `overview.build_overview` immediately after the model call
        returns, before it parses, screens, or computes `parts_status`."""
        self._write_json(
            "03_raw_response.json",
            {
                "written_at": _now(),
                "record": result.record,
                "raw_text": result.raw_text,
                "raw_text_sha256": _sha256(result.raw_text),
                "thinking": result.thinking,
                "answer_parsed": result.answer is not None,
                "answer": result.answer,
            },
        )

    def final_record(self, record: dict, reasoning: str) -> None:
        """Called by the caller only on a normal, successful return from `build_overview`."""
        self._write_json("04_final_record.json", {"written_at": _now(), "record": record})
        (self.run_dir / "05_reasoning.txt").write_text(reasoning or "", encoding="utf-8")

    def exception(self, exc: BaseException) -> None:
        """Called by the caller's own `try`/`except` wrapping its call to `build_overview` (or to anything
        upstream of it in the same attempt). Whatever was already written by `prompt_ready`/`raw_response`
        stays on disk unchanged; this only adds the failure record alongside it."""
        self._write_json(
            "06_exception_receipt.json",
            {
                "written_at": _now(),
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
