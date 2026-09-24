"""Qwen3.5 ``think:false`` worker preflight — pass/fail only.

Before a Qwen3.5 worker (T2/T3/T4) is used, confirm three mechanical facts on the isolated Ollama, using the real worker
tasks on neutral synthetic fixtures (no library text): (1) the model accepts ``think:false`` and produces no reasoning;
(2) the four worker schemas hold (gate enum, span-id list, claim string, query string); (3) every bounded call completes
under its own small worker cap (``done_reason == stop``). This is not a worker bakeoff and scores nothing about quality.

    python -m experiments.ask_cli_revised.worker_preflight --out <dir>     # needs the JUNO isolated-Ollama tunnel
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.backends import NativeWorker
from experiments.ask_cli_revised.qwen import QwenTasks

_INFRASTRUCTURE = frozenset({"http_error", "runtime_error", "transport_error", "provider_error"})

_SUBQUESTION = "Does a short nap after learning improve recall the next day?"
_OBLIGATIONS = [{"field_id": "s1-o1", "note": "whether a short nap after learning improves next-day recall"}]
_RESULT = (
    "In a randomized study of 48 adults, participants who napped for 30 minutes after learning word pairs recalled "
    "more pairs the next morning than participants who stayed awake (mean 31.2 versus 26.4 pairs)."
)
_METHODS = "Participants were recruited through university mailing lists and gave written consent."
_NULL = "Nap duration was not associated with recall in the nap group (r = 0.08, p = 0.61)."
_HEADING = "References and acknowledgments"


class _Collector:
    """Keeps only per-call facts (never prompt or output text) for the preflight record."""

    def __init__(self):
        self.calls = []

    def qwen_call(self, *, task, validation_ok, extra=None, **_ignored):
        self.calls.append({"task": task, "validation_ok": validation_ok, **(extra or {})})
        return self.calls[-1]


def run_preflight(client, model: str) -> dict:
    collector = _Collector()
    worker = NativeWorker(client=client, model=model, base_options=topo.SUPERVISOR_BASE_OPTIONS, think=False)
    tasks = QwenTasks(config=worker, trace=collector)
    for packet in (_RESULT, _HEADING):
        tasks.context_gate(packet_text=packet, subquestion=_SUBQUESTION)
    for spans in (
        [{"span_id": "e1", "text": _RESULT}, {"span_id": "e2", "text": _METHODS}],
        [{"span_id": "e1", "text": _NULL}, {"span_id": "e2", "text": _HEADING}],
    ):
        tasks.select_evidence(spans=spans, subquestion=_SUBQUESTION, obligations=_OBLIGATIONS)
    for quote in (_RESULT, _NULL):
        tasks.form_claim(quote=quote, context_text=quote, subquestion=_SUBQUESTION)
    for note in ("whether a short nap improves next-day recall", "how nap length relates to recall"):
        tasks.recovery_query(subquestion=_SUBQUESTION, obligation_note=note)

    calls = [
        {
            "task": c["task"],
            "model": c.get("model", model),
            "status": c.get("status"),
            "outcome": c.get("outcome"),
            "done_reason": c.get("done_reason"),
            "allowance": c.get("allowance"),
            "generated_tokens": c.get("generated_tokens"),
            "thinking_chars": c.get("thinking_chars"),
            "wall_seconds": c.get("wall_seconds"),
        }
        for c in collector.calls
    ]
    criteria = {
        "accepts_think_false": all(c["status"] == "ok" and not c["thinking_chars"] for c in calls),
        "worker_schemas_hold": all(c["outcome"] == "usable" for c in calls),
        "completes_under_caps": all(c["done_reason"] == "stop" for c in calls),
    }
    return {
        "model": model,
        "think": False,
        "pass": all(criteria.values()),
        "criteria": criteria,
        "infrastructure_failures": sum(1 for c in calls if c["status"] in _INFRASTRUCTURE),
        "calls": calls,
    }


def main(argv: list[str] | None = None) -> int:
    from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=topo._QWEN35)
    parser.add_argument("--out", required=True, help="directory for preflight.json (private; never committed)")
    args = parser.parse_args(argv)
    client = OllamaClient(topo.ENDPOINTS["isolated"])
    try:
        result = run_preflight(client, args.model)
        with_version = {**result, "ollama_version": client.version()}
    finally:
        try:
            client.unload(args.model)
        finally:
            client.close()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "preflight.json").write_text(json.dumps(with_version, indent=2), encoding="utf-8")
    print("PREFLIGHT", "PASS" if result["pass"] else "FAIL", json.dumps(result["criteria"]))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
