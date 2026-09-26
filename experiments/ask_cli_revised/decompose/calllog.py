"""One place that records every model call (full prompt and raw output, unedited) and which model made it.

A hard call cap is part of the log: once ``max_calls`` calls have been made the next call raises ``CallCapReached``
instead of reaching the model, so a run can never quietly exceed its authorization.

Two further bounds exist for a run that must end COMPLETE or visibly INCOMPLETE, never quietly partial:

* ``max_seconds`` is a wall-clock budget for the whole run: a call that would START after it is refused with ``RunHalted``;
* ``halt_on(result)`` inspects each finished call (after it is recorded) and, when it names a reason (a provider failure, an
  unparseable or truncated output, a stop reason that is not a confirmed stop), raises ``RunHalted``: no further call is made.

``RunHalted`` deliberately is NOT a ``CallCapReached``: the engine's degrade-to-fallback paths never swallow it, so a halted run
stops instead of continuing with an empty inventory or fallback children that look like results.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from experiments.ask_cli_revised.decompose.model import JsonModel


class CallCapReached(RuntimeError):
    pass


class RunHalted(RuntimeError):
    """The run was stopped on a pre-declared condition. The offending call (if any) is already recorded."""

    def __init__(self, reason: str, *, seq: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.seq = seq


def strict_live_halt(result) -> str | None:
    """The pre-declared stop conditions for a LIVE provider call: anything but a clean, parsed, confirmed ``stop``."""
    if not result.provider_ok:
        return f"provider_failure: {result.failure_reason}"
    if result.truncated:
        return "truncated_at_output_cap"
    if not result.schema_ok:
        return f"unparseable_output: {result.failure_reason}"
    stop = getattr(result, "done_reason", None)
    if stop != "stop":
        return f"stop_reason_not_confirmed: {stop!r}"
    return None


class CallLog:
    def __init__(
        self,
        model: JsonModel,
        max_calls: int | None = None,
        sink: Path | None = None,
        *,
        max_seconds: float | None = None,
        halt_on=None,
        clock=time.monotonic,
    ):
        self.model = model
        self.max_calls = max_calls
        self.records: list[dict] = []
        self.cap_hit = False
        self.halted: str | None = None
        self.sink = sink  # every record is appended here as it is made, so a crash never loses recorded model output
        self.max_seconds = max_seconds
        self.halt_on = halt_on
        self._clock = clock
        self._started = clock()

    def remaining(self) -> int | None:
        return None if self.max_calls is None else self.max_calls - len(self.records)

    def elapsed(self) -> float:
        return self._clock() - self._started

    def call(self, task: str, prompt: str, schema: dict, output_cap: int, *, unit_id: str | None = None):
        if self.max_calls is not None and len(self.records) >= self.max_calls:
            self.cap_hit = True
            raise CallCapReached(f"call cap of {self.max_calls} reached before task {task!r}")
        if self.max_seconds is not None and self.elapsed() > self.max_seconds:
            self.halted = f"time_cap: {self.max_seconds:.0f}s exhausted before task {task!r}"
            raise RunHalted(self.halted)
        result = self.model.call(prompt, schema=schema, output_cap=output_cap)
        self.records.append(
            {
                "seq": len(self.records) + 1,
                "task": task,
                "unit_id": unit_id,
                "produced_by": self.model.label,
                "prompt": prompt,
                "raw_output": result.raw_text,
                "parsed": result.parsed,
                "provider_ok": result.provider_ok,
                "schema_ok": result.schema_ok,
                "truncated": result.truncated,
                "stop_reason": getattr(result, "done_reason", None),
                "failure_reason": result.failure_reason,
                "elapsed_seconds": round(result.elapsed_seconds, 3),
                "mode": result.mode,
                "output_cap": output_cap,
            }
        )
        if self.sink is not None:
            with self.sink.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(self.records[-1], ensure_ascii=False, default=str) + "\n")
        reason = self.halt_on(result) if self.halt_on is not None else None
        if reason:
            self.halted = reason
            raise RunHalted(reason, seq=len(self.records))
        return result

    def summary(self) -> dict:
        return {
            "calls": len(self.records),
            "max_calls": self.max_calls,
            "max_seconds": self.max_seconds,
            "provider_failures": sum(1 for r in self.records if not r["provider_ok"]),
            "schema_failures": sum(1 for r in self.records if not r["schema_ok"]),
            "truncations": sum(1 for r in self.records if r["truncated"]),
            "stop_reasons": {
                str(k): sum(1 for r in self.records if r["stop_reason"] == k)
                for k in sorted({r["stop_reason"] for r in self.records}, key=str)
            },
            "elapsed_seconds_total": round(sum(r["elapsed_seconds"] for r in self.records), 2),
            "halted": self.halted,
        }
