"""Trace writer: one run directory with the 00..15 stage artifacts + a human report.

Every prune/promote decision carries WHY; every Qwen intermediate call persists its raw state so the
postmortem can attribute a lost target to Qwen specifically vs. an upstream deterministic/RAG stage.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _default(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


class TraceWriter:
    """Writes JSON / JSONL artifacts into a run directory. Append-only per artifact."""

    def __init__(self, out_dir: str | Path) -> None:
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._qwen_calls: list[dict] = []
        self._events: list[dict] = []

    def write_json(self, name: str, payload: Any) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(payload, indent=2, default=_default, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def write_jsonl(self, name: str, rows: list[Any]) -> Path:
        path = self.dir / name
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, default=_default, ensure_ascii=False) + "\n")
        return path

    def decision(self, stage: str, reason_code: str, *, kept: bool, **inputs: Any) -> dict:
        """Record and return one prune/promote decision (also mirrored into the human report)."""
        event = {
            "stage": stage,
            "reason_code": reason_code,
            "kept": kept,
            "inputs": inputs,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._events.append(event)
        return event

    def qwen_call(
        self,
        *,
        stage: str,
        task: str,
        input_text: str,
        raw_output: str,
        parse_ok: bool,
        validation_ok: bool,
        failure_reason: str | None = None,
        deterministic_fallback_used: bool = False,
        downstream_consequence: str = "",
        extra: dict | None = None,
    ) -> dict:
        """Preserve one Qwen intermediate call's full raw state (postmortem: model-vs-pipeline failure)."""
        record = {
            "stage": stage,
            "task": task,
            "input_text": input_text,
            "raw_output": raw_output,
            "parse_ok": parse_ok,
            "validation_ok": validation_ok,
            "failure_reason": failure_reason,
            "deterministic_fallback_used": deterministic_fallback_used,
            "downstream_consequence": downstream_consequence,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            record.update(extra)
        self._qwen_calls.append(record)
        return record

    def flush_qwen(self, name: str = "qwen_calls.jsonl") -> Path:
        return self.write_jsonl(name, self._qwen_calls)

    def flush_events(self, name: str = "decisions.jsonl") -> Path:
        return self.write_jsonl(name, self._events)

    def write_report(self, name: str, lines: list[str]) -> Path:
        path = self.dir / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
