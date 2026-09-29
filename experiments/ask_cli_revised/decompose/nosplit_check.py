"""Gate B of the closure pass: one bounded run of the INTENDED live control path for a single simple question, to see which route the engine takes.

The request is fixed; the inventory is live (one unit call, one whole-request call, one ambiguity call); the engine then decides. If it takes the
no-split route the writer is never called (3 calls in all); otherwise exactly one writer call follows (4 calls, the hard cap). Nothing is repaired,
retried, retrieved or answered. Every raw response is compared with what the frozen v6 control run recorded for the SAME prompts, so the result says
plainly whether the live model reproduced that record (temperature 0 and a fixed seed make an exact repeat the expected outcome).

It shows the route the live model takes for this ONE request with the prompt-echo correction in place. It does not show that any other simple
question is routed the same way, and a scripted test elsewhere shows only a decision path, never what a real inventory model returns.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from experiments.ask_cli_revised.decompose import ENGINE_VERSION, integrated, prompts, views
from experiments.ask_cli_revised.decompose.calllog import RunHalted, strict_live_halt
from experiments.ask_cli_revised.decompose.engine import code_hashes, run_engine
from experiments.ask_cli_revised.decompose.model import BASE_OPTIONS

CONFIG_B = {
    "artifact": "nosplit_check_closure_b",
    "request": "What is a placebo effect?",
    "variant": "prepared",
    "model": integrated.CONFIG["model"],
    "endpoint": integrated.CONFIG["endpoint"],
    "think": integrated.CONFIG["think"],
    "options": dict(BASE_OPTIONS),
    "repair": False,
    "automatic_retries": False,
    "inventory_calls_known_in_advance": 3,
    "max_calls": 4,
    "total_time_cap_seconds": 180,
    "per_call_wall_timeout_seconds": 120,
    "expected_model_digest": integrated.CONFIG["expected_model_digest"],
    "expected_model_family": integrated.CONFIG["expected_model_family"],
}


def _dump(path: Path, payload) -> None:
    integrated._dump(path, payload)


def _same_as_recorded(calls: list[dict], recorded: list[dict] | None) -> list[dict]:
    """For each call made now, was its prompt the recorded one, and was the raw response byte-identical to the recorded one?"""
    if recorded is None:
        return []
    by_task = {r["task"]: r for r in recorded}
    out = []
    for c in calls:
        r = by_task.get(c["task"])
        out.append(
            {
                "task": c["task"],
                "prompt_identical_to_recorded": bool(r) and r["prompt"] == c["prompt"],
                "raw_response_identical_to_recorded": bool(r) and r["raw_output"] == c["raw_output"],
            }
        )
    return out


def run_check(
    root: Path, model_factory, *, live: bool, identity_check=None, recorded: list[dict] | None = None
) -> dict:
    """Identity first, then the bounded run. Never retries. Returns the summary (also written to CHECK_SUMMARY.json)."""
    from experiments.ask_cli_revised.decompose.__main__ import write_artifacts

    config = CONFIG_B
    root.mkdir(parents=True, exist_ok=True)
    started = time.time()
    model = model_factory()
    identity = integrated.capture_identity(model)
    problems = identity_check(identity) if identity_check else []
    if problems:
        summary = {
            "outcome": "not_started",
            "reason": problems,
            "note": "a precondition failed before any generation call",
        }
        _dump(root / "CHECK_SUMMARY.json", summary)
        return summary
    sink = root / "model_calls.jsonl"
    sink.write_text("", encoding="utf-8")
    try:
        result = run_engine(
            config["request"],
            model,
            repair=False,
            max_calls=config["max_calls"],
            call_sink=sink,
            prompt_variant=config["variant"],
            max_seconds=config["total_time_cap_seconds"],
            halt_on=strict_live_halt if live else integrated.offline_halt,
        )
    except RunHalted as exc:
        _dump(
            root / "HALTED.json",
            {
                "reason": exc.reason,
                "at_call": exc.seq,
                "note": "INCOMPLETE. Stopped on a pre-declared condition; nothing was retried.",
            },
        )
        summary = {"outcome": "INCOMPLETE", "reason": f"halted: {exc.reason}", "model_identity": identity}
        _dump(root / "CHECK_SUMMARY.json", summary)
        return summary
    write_artifacts(result, root / "artifacts")
    nl = views.natural_language_view(result)
    _dump(root / "artifacts" / "VIEW_natural_language.json", nl)
    (root / "artifacts" / "VIEW_natural_language.md").write_text(views.render_natural_language(nl), encoding="utf-8")
    decision = result["decomposition_decision"] or {}
    writer_calls = sum(1 for c in result["calls"] if c["task"] == "children.write")
    child = result["pass1"]["children"][0] if len(result["pass1"]["children"]) == 1 else None
    route = (
        "no_split_pass_through"
        if decision.get("applied") and decision.get("outcome") == "no_decomposition_needed" and writer_calls == 0
        else "writer_path"
    )
    summary = {
        "outcome": "COMPLETE",
        "route": route,
        "decision": {k: decision.get(k) for k in ("outcome", "applied", "basis", "blocking")},
        "calls_total": len(result["calls"]),
        "writer_calls": writer_calls,
        "set_aside_prompt_echoes": result["parent_contract"]["post_processing"].get("set_aside_prompt_echoes", []),
        "child": None
        if child is None
        else {
            "kind": child["kind"],
            "wording": child["question"],
            "exactly_the_original_request": child["question"] == config["request"],
            "status": child["status"],
            "execution": child["execution"]["state"],
        },
        "same_as_recorded_v6_control": _same_as_recorded(result["calls"], recorded),
        "stop_reasons": [c.get("stop_reason") for c in result["calls"]],
        "model_identity": identity,
        "engine_code_sha256_prefixes": code_hashes(),
        "environment": integrated.environment(),
        "total_wall_seconds": round(time.time() - started, 2),
        "note": "the ROUTE is the finding, not a pass or fail; it covers this one request only",
    }
    _dump(root / "CHECK_SUMMARY.json", summary)
    return summary


def freeze_manifest(repo_root: Path, *, input_files: dict, tool_files: list[Path]) -> dict:
    """Everything that must not change between the authorization and the run, with its hash."""
    engine_dir = repo_root / "experiments" / "ask_cli_revised" / "decompose"
    settings = prompts.settings_for(CONFIG_B["variant"])
    manifest = {
        "artifact": "nosplit_check_freeze",
        "engine_version": ENGINE_VERSION,
        "config": CONFIG_B,
        "engine_code_sha256": {
            p.name: integrated.sha256_file(p) for p in sorted(engine_dir.glob("*.py")) if not p.name.startswith("test_")
        },
        "engine_tests_sha256": {p.name: integrated.sha256_file(p) for p in sorted(engine_dir.glob("test_*.py"))},
        "engine_support_sha256": {
            rel: integrated.sha256_file(repo_root / rel) for rel in integrated.FROZEN_ENGINE_SUPPORT
        },
        "tool_files_sha256": {p.name: integrated.sha256_file(p) for p in tool_files},
        "input_files_sha256": {name: integrated.sha256_file(p) for name, p in input_files.items()},
        "inventory": integrated.inventory_prompt_hashes(CONFIG_B["request"]),
        "writer": {
            "variant": settings["variant"],
            "schema_sha256": integrated.sha256_text(json.dumps(settings["schema"], sort_keys=True)),
            "limits": settings["limits"],
            "output_cap": settings["cap"],
        },
        "hard_caps": {k: CONFIG_B[k] for k in ("max_calls", "total_time_cap_seconds", "per_call_wall_timeout_seconds")},
        "reference_isolation": "the only input is the frozen v6 control record, read for comparison after the run; the held-out reference is not an input of any kind",
    }
    manifest["freeze_sha256"] = integrated.sha256_text(
        json.dumps({k: v for k, v in manifest.items() if k != "freeze_sha256"}, sort_keys=True)
    )
    return manifest
