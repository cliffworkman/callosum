"""One bounded, integrated decomposition-only test: the current engine, end to end, on the ORIGINAL request plus one simple control.

Nothing here retrieves literature, generates an answer, or touches any other request. It only sequences the engine, enforces the caps,
freezes what was produced, and keeps the held-out reference out of reach until the outputs and the blind evaluation are frozen.

Ordering rules the code enforces:

1. ``verify_freeze`` re-hashes the frozen code, clarification set, inputs and settings; a run refuses to start on any difference.
2. A run refuses to start without an authorization record naming the SHA-256 of the gate document that was authorized.
3. Every run has hard bounds: a total call cap (the inventory call count is KNOWN before any call: one per source unit, plus the
   whole-request call and the ambiguity call), a wall-clock budget, and a pre-declared stop condition checked after every call.
4. The number of writer calls is unknown until the fresh inventory exists, so it is checked AFTER the inventory and planning and BEFORE
   the first writer call. If the plan needs more than the budget the run stops as INCOMPLETE: no child is written, none is dropped, and
   a partial run can never be mistaken for a complete one.
5. Any halt, cap or budget stop ends the whole test; the summary says INCOMPLETE and why. Nothing is retried.
6. After a completed run the outputs are hashed and made read-only (``freeze_outputs``); the evaluator's blind evaluation is frozen next
   (``freeze_blind_evaluation``); only then does ``reference_diagnostic_allowed`` say yes.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import sys
import time
from pathlib import Path

from experiments.ask_cli_revised.decompose import ENGINE_VERSION, views
from experiments.ask_cli_revised.decompose.calllog import RunHalted, strict_live_halt
from experiments.ask_cli_revised.decompose.engine import WriterBudgetExceeded, code_hashes, run_engine
from experiments.ask_cli_revised.request_contract import build_request_contract

CONFIG = {
    "prompt_variant": "corrected-full",
    "model": "qwen3.5:9b",
    "endpoint": "http://127.0.0.1:11435",
    "think": False,
    "repair": False,
    "automatic_retries": False,
    "per_call_wall_timeout_seconds": 180,
    "total_time_cap_seconds": 1200,
    "requests": {
        "control_placebo": {"max_writer_calls": 1, "max_seconds": 300},
        "primary_request": {"max_writer_calls": 14, "max_seconds": 1200},
    },
    "order": ["control_placebo", "primary_request"],
    "expected_model_digest": "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7",
    "expected_model_family": {"family": "qwen35", "parameter_size": "9.7B", "quantization_level": "Q4_K_M"},
}
CONTROL_REQUEST = "What is a placebo effect?"
FROZEN_ENGINE_SUPPORT = (
    "experiments/ask_cli_revised/request_contract.py",
    "experiments/ask_cli_revised/calibration/run06/segment.py",
    "experiments/ask_cli_revised/calibration/structured_output.py",
    "experiments/ask_cli_revised/supervisor_eval/ollama_client.py",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def inventory_call_count(question: str, *, whole_pass: bool = True) -> int:
    """Known BEFORE any call: one per source unit, plus the whole-request call, plus the ambiguity call."""
    return len(build_request_contract(question)["source_units"]) + (1 if whole_pass else 0) + 1


def inventory_prompt_hashes(question: str) -> dict:
    """The inventory prompts depend only on the request, so they can be frozen before any call (the writer prompts cannot)."""
    from experiments.ask_cli_revised.decompose import parent as pm

    units = build_request_contract(question)["source_units"]
    return {
        "unit_prompts": {u["source_unit_id"]: sha256_text(pm.unit_prompt(question, u["text"])) for u in units},
        "whole_prompt": sha256_text(pm.whole_prompt(question)),
        "ambiguity_prompt": sha256_text(pm.ambiguity_prompt(question)),
        "obligation_schema": sha256_text(json.dumps(pm._OBLIGATION_SCHEMA, sort_keys=True)),
        "ambiguity_schema": sha256_text(json.dumps(pm._AMBIGUITY_SCHEMA, sort_keys=True)),
        "obligation_output_cap": pm.OBLIGATION_OUTPUT_CAP,
        "ambiguity_output_cap": pm.AMBIGUITY_OUTPUT_CAP,
    }


# ---- freeze --------------------------------------------------------------------------------------------------------------------------
def build_freeze(
    repo_root: Path, test_dir: Path, *, question_files: dict, clarification_files: dict, tool_files: list[Path]
) -> dict:
    """Everything that must not change between the authorization and the run, with its hash."""
    from experiments.ask_cli_revised.decompose import prompts

    engine_dir = repo_root / "experiments" / "ask_cli_revised" / "decompose"
    settings = prompts.settings_for(CONFIG["prompt_variant"])
    questions = {name: Path(p).read_text(encoding="utf-8") for name, p in question_files.items()}
    manifest = {
        "artifact": "integrated_test_freeze",
        "engine_version": ENGINE_VERSION,
        "config": CONFIG,
        "engine_code_sha256": {
            p.name: sha256_file(p) for p in sorted(engine_dir.glob("*.py")) if not p.name.startswith("test_")
        },
        "engine_tests_sha256": {p.name: sha256_file(p) for p in sorted(engine_dir.glob("test_*.py"))},
        "engine_support_sha256": {rel: sha256_file(repo_root / rel) for rel in FROZEN_ENGINE_SUPPORT},
        "tool_files_sha256": {p.name: sha256_file(p) for p in tool_files},
        "question_files_sha256": {name: sha256_file(p) for name, p in question_files.items()},
        "question_sha256_of_text": {name: sha256_text(text) for name, text in questions.items()},
        "clarification_files_sha256": {name: sha256_file(p) for name, p in clarification_files.items()},
        "writer": {
            "variant": settings["variant"],
            "schema_sha256": sha256_text(json.dumps(settings["schema"], sort_keys=True)),
            "limits": settings["limits"],
            "output_cap": settings["cap"],
            "extract_mode": settings["extract_mode"],
            "preflight": settings["preflight"],
            "proposed_briefs_used": False,
        },
        "inventory": {name: inventory_prompt_hashes(text) for name, text in questions.items()},
        "known_inventory_call_counts": {name: inventory_call_count(text) for name, text in questions.items()},
        "hard_caps": {
            name: {
                "inventory_calls": inventory_call_count(questions[name]),
                "max_writer_calls": CONFIG["requests"][name]["max_writer_calls"],
                "max_calls": inventory_call_count(questions[name]) + CONFIG["requests"][name]["max_writer_calls"],
                "max_seconds": CONFIG["requests"][name]["max_seconds"],
            }
            for name in CONFIG["order"]
        },
        "reference_isolation": "no frozen file reads the held-out reference; the runner reads only the copies under inputs/",
    }
    manifest["hard_caps"]["total_max_calls"] = sum(
        v["max_calls"] for k, v in manifest["hard_caps"].items() if isinstance(v, dict) and "max_calls" in v
    )
    manifest["freeze_sha256"] = sha256_text(
        json.dumps({k: v for k, v in manifest.items() if k != "freeze_sha256"}, sort_keys=True)
    )
    return manifest


def verify_freeze(frozen: dict, rebuilt: dict) -> list[str]:
    """Differences between the frozen manifest and one rebuilt now (empty means identical)."""
    return [
        f"{key} differs from the frozen manifest"
        for key in frozen
        if key != "freeze_sha256" and frozen[key] != rebuilt.get(key)
    ] + ([] if frozen.get("freeze_sha256") == rebuilt.get("freeze_sha256") else ["freeze_sha256 differs"])


def check_authorization(auth_path: Path | None, gate_path: Path) -> dict:
    """The run needs a record of the researcher's explicit authorization of THIS gate document (by hash)."""
    if auth_path is None or not Path(auth_path).exists():
        raise PermissionError(
            "no authorization record: the researcher must explicitly authorize the gate before any model call"
        )
    auth = json.loads(Path(auth_path).read_text(encoding="utf-8"))
    if auth.get("gate_sha256") != sha256_file(gate_path):
        raise PermissionError("the authorization names a different gate document than the one now frozen")
    if not str(auth.get("authorized_by") or "").strip() or not str(auth.get("authorization_quote") or "").strip():
        raise PermissionError("the authorization record must name who authorized it and quote the authorization")
    return auth


# ---- one request ---------------------------------------------------------------------------------------------------------------------
def _dump(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def offline_halt(result) -> str | None:
    """The same stop conditions for a scripted or replayed run, which legitimately carries no provider stop reason."""
    if not result.provider_ok:
        return f"provider_failure: {result.failure_reason}"
    if result.truncated:
        return "truncated_at_output_cap"
    if not result.schema_ok:
        return f"unparseable_output: {result.failure_reason}"
    return None


def run_one(
    name: str,
    question: str,
    model,
    out_dir: Path,
    *,
    live: bool,
    clarifications: list[dict] | None = None,
    annotations: list[dict] | None = None,
    decisions: list[dict] | None = None,
    time_left: float | None = None,
) -> dict:
    """Run the engine on one request under its hard bounds. Returns an outcome record; never raises for a halt or a budget stop."""
    from experiments.ask_cli_revised.decompose.__main__ import write_artifacts

    caps = CONFIG["requests"][name]
    inv = inventory_call_count(question)
    max_calls = inv + caps["max_writer_calls"]
    max_seconds = min(caps["max_seconds"], time_left) if time_left is not None else caps["max_seconds"]
    out_dir.mkdir(parents=True, exist_ok=True)
    sink = out_dir / "model_calls.jsonl"
    sink.write_text("", encoding="utf-8")
    started = time.time()
    record = {
        "name": name,
        "request": question,
        "request_sha256": sha256_text(question),
        "caps": {
            "inventory_calls_known_in_advance": inv,
            "max_writer_calls": caps["max_writer_calls"],
            "max_calls": max_calls,
            "max_seconds": max_seconds,
        },
        "started_unix": started,
    }
    try:
        result = run_engine(
            question,
            model,
            repair=CONFIG["repair"],
            max_calls=max_calls,
            call_sink=sink,
            clarifications=clarifications,
            clarification_annotations=annotations,
            researcher_decisions=decisions,
            prompt_variant=CONFIG["prompt_variant"],
            use_proposed_briefs=False,
            max_seconds=max_seconds,
            halt_on=strict_live_halt if live else offline_halt,
            max_writer_calls=caps["max_writer_calls"],
        )
    except RunHalted as exc:
        record.update(outcome="halted", reason=exc.reason, at_call=exc.seq)
        _dump(
            out_dir / "HALTED.json",
            {
                **record,
                "note": "INCOMPLETE. The run stopped on a pre-declared condition; the calls made are in model_calls.jsonl; nothing was retried and no decomposition is claimed.",
            },
        )
        return record
    except WriterBudgetExceeded as exc:
        record.update(outcome="incomplete_writer_budget", needed_writer_calls=exc.needed, writer_budget=exc.budget)
        _dump(out_dir / "01_parent_contract.json", exc.parent)
        _dump(
            out_dir / "INCOMPLETE_writer_budget.json",
            {
                **record,
                "decision": exc.decision,
                "plans": exc.plans,
                "inventory_calls_made": len(exc.calls),
                "note": "INCOMPLETE. The fresh inventory plans more writer calls than the budget; the run stopped BEFORE writing any child (none written, none dropped).",
            },
        )
        return record
    write_artifacts(result, out_dir)
    nl, ct, cw = views.natural_language_view(result), views.contract_view(result), views.crosswalk(result)
    _dump(out_dir / "VIEW_natural_language.json", nl)
    _dump(out_dir / "VIEW_contract.json", ct)
    _dump(out_dir / "VIEW_crosswalk.json", cw)
    (out_dir / "VIEW_natural_language.md").write_text(views.render_natural_language(nl), encoding="utf-8")
    (out_dir / "VIEW_contract.md").write_text(views.render_contract(ct), encoding="utf-8")
    (out_dir / "VIEW_crosswalk.md").write_text(views.render_crosswalk(cw), encoding="utf-8")
    manifest = result["manifest"]
    complete = manifest["run_completeness"]["complete"]
    record.update(
        outcome="completed" if complete else "completed_incomplete",
        decision=(result["decomposition_decision"] or {}).get("outcome"),
        decision_applied=(result["decomposition_decision"] or {}).get("applied"),
        calls=manifest["call_summary"],
        calls_by_task={
            t: sum(1 for r in result["calls"] if r["task"] == t) for t in sorted({r["task"] for r in result["calls"]})
        },
        children=[(c["child_id"], c["kind"], c["status"]) for c in result["pass1"]["children"]],
        run_completeness=manifest["run_completeness"],
        elapsed_wall_seconds=round(time.time() - started, 2),
    )
    _dump(out_dir / "RUN_RECORD.json", record)
    return record


def capture_identity(model) -> dict:
    """The model's identity plus the runtime version and the model's own digest (metadata only, no generation). ``OllamaClient.tags()``
    returns the LIST of model records; a missing digest is recorded as a problem, never guessed."""
    identity = model.identity()
    client = getattr(model, "client", None)
    if client is None:
        return identity
    try:
        identity["ollama_version"] = client.version()
    except Exception as exc:  # noqa: BLE001 - recording metadata must never abort the precondition report
        identity["ollama_version"] = f"unavailable: {type(exc).__name__}"
    try:
        tags = client.tags()
        models = tags.get("models", []) if isinstance(tags, dict) else tags
        identity["digest"] = next((m.get("digest") for m in models if m.get("name") == identity.get("model")), None)
    except Exception as exc:  # noqa: BLE001
        identity["digest"] = None
        identity["digest_error"] = f"{type(exc).__name__}: {exc}"
    return identity


def check_identity(identity: dict) -> list[str]:
    """Preconditions on the model actually reached, checked BEFORE any generation call (``/api/show`` is metadata only)."""
    problems = []
    if identity.get("show_error"):
        problems.append(f"the model could not be inspected: {identity['show_error']}")
    shown = identity.get("show") or {}
    for key, want in CONFIG["expected_model_family"].items():
        if shown.get(key) != want:
            problems.append(f"model {key} is {shown.get(key)!r}, expected {want!r}")
    if CONFIG.get("expected_model_digest") and identity.get("digest") != CONFIG["expected_model_digest"]:
        problems.append(f"model digest is {identity.get('digest')!r}, expected {CONFIG['expected_model_digest']!r}")
    if identity.get("model") != CONFIG["model"]:
        problems.append(f"model is {identity.get('model')!r}, expected {CONFIG['model']!r}")
    if identity.get("endpoint") != CONFIG["endpoint"]:
        problems.append(f"endpoint is {identity.get('endpoint')!r}, expected {CONFIG['endpoint']!r}")
    if identity.get("think") is not CONFIG["think"]:
        problems.append(f"think is {identity.get('think')!r}, expected {CONFIG['think']!r}")
    return problems


def environment() -> dict:
    import httpx

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "httpx": httpx.__version__,
        "engine_version": ENGINE_VERSION,
    }


def run_test(
    root: Path,
    model_factory,
    *,
    live: bool,
    questions: dict,
    clarifications: list[dict],
    annotations: list[dict],
    decisions: list[dict],
    identity_check=None,
) -> dict:
    """The whole test: control first, then the original request. The first non-completed run ends the test as INCOMPLETE."""
    root.mkdir(parents=True, exist_ok=True)
    model = model_factory()
    identity = capture_identity(model)
    if identity_check is not None:
        problems = identity_check(identity)
        if problems:
            summary = {
                "outcome": "not_started",
                "reason": problems,
                "note": "a precondition failed before any generation call",
            }
            _dump(root / "TEST_SUMMARY.json", summary)
            return summary
    started = time.time()
    runs: dict[str, dict] = {}
    for name in CONFIG["order"]:
        left = CONFIG["total_time_cap_seconds"] - (time.time() - started)
        if left <= 0:
            runs[name] = {"outcome": "not_run", "reason": "total time cap exhausted"}
            break
        with_clar = name == "primary_request"
        runs[name] = run_one(
            name,
            questions[name],
            model,
            root / name,
            live=live,
            clarifications=clarifications if with_clar else None,
            annotations=annotations if with_clar else None,
            decisions=decisions if with_clar else None,
            time_left=left,
        )
        if runs[name]["outcome"] != "completed":
            break
    complete = all(runs.get(n, {}).get("outcome") == "completed" for n in CONFIG["order"])
    summary = {
        "outcome": "COMPLETE" if complete else "INCOMPLETE",
        "runs": {n: {k: v for k, v in r.items() if k not in ("request",)} for n, r in runs.items()},
        "not_run": [n for n in CONFIG["order"] if n not in runs],
        "model_identity": identity,
        "environment": environment(),
        "total_wall_seconds": round(time.time() - started, 2),
        "engine_code_sha256_prefixes": code_hashes(),
        "note": "COMPLETE means both runs finished with every planned child written or passed through. Anything else is INCOMPLETE and is reported as such; nothing was retried.",
    }
    _dump(root / "TEST_SUMMARY.json", summary)
    return summary


# ---- freezing outputs, and the reference gate ---------------------------------------------------------------------------------------------
def _files(root: Path, skip: tuple[str, ...]) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.name not in skip)


def freeze_outputs(root: Path) -> dict:
    """Hash every output file and make it read-only. The views and the raw model outputs are frozen together, BEFORE any reference."""
    files = _files(root, ("OUTPUTS_FROZEN.json", "EVALUATION_FROZEN.json"))
    hashes = {str(p.relative_to(root)).replace("\\", "/"): sha256_file(p) for p in files}
    for p in files:
        os.chmod(p, stat.S_IREAD)
    record = {
        "artifact": "outputs_frozen",
        "frozen_unix": time.time(),
        "files": hashes,
        "note": "raw model outputs and both views, frozen before the held-out reference is consulted",
    }
    _dump(root / "OUTPUTS_FROZEN.json", record)
    return record


def outputs_unchanged(root: Path) -> list[str]:
    frozen = json.loads((root / "OUTPUTS_FROZEN.json").read_text(encoding="utf-8"))["files"]
    return [k for k, v in frozen.items() if not (root / k).exists() or sha256_file(root / k) != v]


def freeze_blind_evaluation(root: Path, evaluation_path: Path) -> dict:
    """Record the hash of the evaluator's blind evaluation (written from the frozen outputs alone) before the reference is consulted."""
    if not (root / "OUTPUTS_FROZEN.json").exists():
        raise PermissionError("the outputs are not frozen yet")
    if outputs_unchanged(root):
        raise PermissionError(f"frozen outputs changed: {outputs_unchanged(root)}")
    record = {
        "artifact": "evaluation_frozen",
        "evaluation_file": str(evaluation_path.name),
        "evaluation_sha256": sha256_file(evaluation_path),
        "frozen_unix": time.time(),
    }
    _dump(root / "EVALUATION_FROZEN.json", record)
    return record


def reference_diagnostic_allowed(root: Path, evaluation_path: Path) -> tuple[bool, str]:
    """The held-out reference may be consulted only after the outputs AND the blind evaluation are frozen and still unchanged."""
    if not (root / "OUTPUTS_FROZEN.json").exists():
        return False, "the outputs are not frozen"
    if outputs_unchanged(root):
        return False, f"frozen outputs changed: {outputs_unchanged(root)}"
    if not (root / "EVALUATION_FROZEN.json").exists():
        return False, "the blind evaluation is not frozen"
    ev = json.loads((root / "EVALUATION_FROZEN.json").read_text(encoding="utf-8"))
    if not evaluation_path.exists() or sha256_file(evaluation_path) != ev["evaluation_sha256"]:
        return False, "the frozen blind evaluation changed"
    return True, "outputs and blind evaluation are frozen and unchanged"
