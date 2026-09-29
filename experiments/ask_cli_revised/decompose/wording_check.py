"""One bounded, wording-only check of the ``prepared`` writer against the frozen integrated run (the v7 follow-up).

What is held FIXED (so the four written children are interpretable): the recorded obligation inventory (replayed, never regenerated), the
frozen hierarchy, contracts and clarification set, the model and its identity, decoding options, the matched schema, output cap and limits,
and every post-check. What changes is ONLY the deterministic preparation of each child and the prompt material that presents it.

Nothing here retrieves literature, generates an answer, opens the held-out reference or repairs a legacy check. It replays, verifies replay
identity BEFORE any call, writes only the listed children under hard call/time bounds, records every prompt and raw response, and freezes
what it produced. The live call needs a recorded authorization of the exact gate document (``integrated.check_authorization``).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from experiments.ask_cli_revised.decompose import ENGINE_VERSION, integrated, prompts, views
from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import clarifications as clar
from experiments.ask_cli_revised.decompose.calllog import CallLog, RunHalted, strict_live_halt
from experiments.ask_cli_revised.decompose.engine import (
    WriterBudgetExceeded,
    _apply_clarifications,
    code_hashes,
    rescore,
    run_engine,
)
from experiments.ask_cli_revised.decompose.model import BASE_OPTIONS, ReplayModel
from experiments.ask_cli_revised.decompose.parent import build_parent_contract

CONFIG = {
    "artifact": "wording_check_prepared_v7",
    "variant": "prepared",
    "baseline_variant": "corrected-full",
    "request": "primary_request",
    "children": ["c6", "c8", "c9", "c11"],
    "model": integrated.CONFIG["model"],
    "endpoint": integrated.CONFIG["endpoint"],
    "think": integrated.CONFIG["think"],
    "options": dict(BASE_OPTIONS),
    "repair": False,
    "automatic_retries": False,
    "max_writer_calls": 4,
    "max_calls": 4,
    "per_call_wall_timeout_seconds": 120,
    "total_time_cap_seconds": 300,
    "expected_model_digest": integrated.CONFIG["expected_model_digest"],
    "expected_model_family": integrated.CONFIG["expected_model_family"],
}


# Gate A of the closure pass: the two fragment children only. The model, options, schema, cap and post-checks are the v7 configuration.
CONFIG_A = {
    **CONFIG,
    "artifact": "wording_check_closure_a",
    "children": ["c9", "c11"],
    "max_writer_calls": 2,
    "max_calls": 2,
    "total_time_cap_seconds": 180,
}


class ModelCallRefused(RuntimeError):
    """Raised by ``RefusingModel``: an offline step tried to reach a model."""


class RefusingModel:
    label = "refusing"

    def call(self, prompt, *, schema, output_cap):
        raise ModelCallRefused("an offline step tried to call a model")

    def identity(self) -> dict:
        return {"kind": "refusing", "new_model_calls": 0}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _roundtrip(x):
    return json.loads(json.dumps(x, default=str))


def _without_model_label(x):
    """The recorded run labels its inventory model live; a replay labels it 'replay'. That label is the ONLY permitted difference."""
    if isinstance(x, dict):
        return {k: _without_model_label(v) for k, v in x.items() if k != "produced_by"}
    if isinstance(x, list):
        return [_without_model_label(v) for v in x]
    return x


def load_inputs(inputs_dir: Path, clarification_files: dict) -> dict:
    """Everything the check reads, from COPIES that were hashed at freeze time. The held-out reference is never among them."""
    d = Path(inputs_dir)
    approved, decided = clarification_files["approved"], clarification_files["decisions"]
    closure = clarification_files.get(
        "closure"
    )  # optional: later, prospective decisions (RC-10, D10 ...); never required
    calls = read_jsonl(d / "frozen_v6" / "model_calls.jsonl")
    return {
        "question": (d / "primary_request.txt").read_text(encoding="utf-8"),
        "inventory": [r for r in calls if r["task"].startswith("parent.")],
        "writer_calls": {r["unit_id"]: r for r in calls if r["task"] == "children.write"},
        "frozen_parent": json.loads((d / "frozen_v6" / "01_parent_contract.json").read_text(encoding="utf-8")),
        "frozen_children": json.loads((d / "frozen_v6" / "02_pass1_children.json").read_text(encoding="utf-8")),
        "rows": clar.load(approved) + (clar.load(closure) if closure else []),
        "annotations": clar.load_annotations(decided) + (clar.load_annotations(closure) if closure else []),
        "decisions": clar.load_decisions(decided) + (clar.load_decisions(closure) if closure else []),
    }


def rebuild_state(inp: dict) -> tuple[dict, list[dict], dict, ReplayModel]:
    """The parent contract and plans exactly as the engine builds them, from the RECORDED inventory (no model call)."""
    replay = ReplayModel(inp["inventory"], "frozen-v6")
    parent = build_parent_contract(CallLog(replay), inp["question"], whole_pass=True)
    _apply_clarifications(parent, inp["rows"], False)
    clar.annotate(parent, inp["annotations"])
    parent["researcher_decisions"] = inp["decisions"]
    plans = ch.plan_children(parent)
    return parent, plans, ch.by_id_map(parent), replay


def replay_identity(inp: dict) -> dict:
    """Does replaying the recorded inventory reproduce the frozen plans and contracts exactly? Checked BEFORE any call."""
    parent, plans, _, replay = rebuild_state(inp)
    frozen_plans = inp["frozen_children"]["plans"]
    diffs = []
    if _without_model_label(_roundtrip(parent)) != _without_model_label(inp["frozen_parent"]):
        diffs.append("parent contract differs from the frozen one")
    if _roundtrip(plans) != frozen_plans:
        diffs.append("plans differ from the frozen ones")
    if replay.misses:
        diffs.append(f"{len(replay.misses)} inventory prompt(s) had no recorded response")
    return {
        "identical": not diffs,
        "differences": diffs,
        "inventory_calls_replayed": len(inp["inventory"]),
        "new_model_calls": 0,
        "plans_compared": len(plans),
        "only_permitted_difference": "the inventory model label (recorded run: the live model; replay: 'replay[frozen-v6]')",
    }


def baseline_prompt_identity(inp: dict) -> dict:
    """Rebuild every corrected-full writer prompt from the replayed state and compare BYTES with the frozen record."""
    parent, plans, by_id, _ = rebuild_state(inp)
    render = prompts.settings_for(CONFIG["baseline_variant"])["render"]
    rows = []
    for plan in plans:
        rec = inp["writer_calls"].get(plan["child_id"])
        if rec is None:
            continue
        rebuilt = render(parent, plan, plans, by_id)
        rows.append(
            {
                "child": plan["child_id"],
                "identical": rebuilt == rec["prompt"],
                "sha256_rebuilt": hashlib.sha256(rebuilt.encode()).hexdigest(),
                "sha256_frozen": hashlib.sha256(rec["prompt"].encode()).hexdigest(),
            }
        )
    return {"all_identical": bool(rows) and all(r["identical"] for r in rows), "children": rows, "count": len(rows)}


def prepared_prompts(inp: dict, config: dict | None = None) -> dict:
    """{child: {prepared, baseline, frozen, preparation}}: the exact prompts, the historical corrected-full one, and the preparation record."""
    from experiments.ask_cli_revised.decompose import prompts_prepared

    parent, plans, by_id, _ = rebuild_state(inp)
    config = config or CONFIG
    base = prompts.settings_for(config["baseline_variant"])["render"]
    out = {}
    for plan in plans:
        if plan["child_id"] not in config["children"]:
            continue
        sub, prep = prompts_prepared.prepared_for(parent, plan, plans, by_id)
        out[plan["child_id"]] = {
            "prepared": prompts_prepared.render_prepared(parent, sub, prep),
            "baseline": base(parent, plan, plans, by_id),
            "frozen": (inp["writer_calls"].get(plan["child_id"]) or {}).get("prompt"),
            "preparation": prep,
        }
    return out


def unchanged_request_scores(inp: dict, prepared: dict) -> dict:
    """What the EXISTING checks say if the writer returned each prepared request exactly (offline; nothing is invented or repaired)."""
    scores = {}
    for cid, row in prepared.items():
        text = row["preparation"]["prepared_request"]
        res = rescore(
            inp["question"],
            ReplayModel(inp["inventory"], "frozen-v6"),
            {cid: {"question": text, "unresolved": []}},
            clarifications=inp["rows"],
            clarification_annotations=inp["annotations"],
            extract_mode="governing",
        )
        kid = next(c for c in res["pass1"]["children"] if c["child_id"] == cid)
        scores[cid] = {
            "wording": text,
            "status": kid["status"],
            "flags": [{k: v for k, v in f.items() if k in ("flag", "tokens", "words", "note")} for f in kid["flags"]],
        }
    return scores


# ---- preconditions of the live run ---------------------------------------------------------------------------------------------------
def preconditions(frozen: dict, rebuilt: dict, gate_path: Path, auth_path: Path | None, run_root: Path) -> dict:
    """Everything that must hold BEFORE a live call. Raises (and nothing is called) when the freeze changed, the gate does not cite the freeze,
    the researcher's authorization of THIS gate document is missing, or a previous run's outputs exist."""
    problems = integrated.verify_freeze(frozen, rebuilt)
    if problems:
        raise RuntimeError(f"REFUSED: the frozen code/data/settings changed since the freeze: {problems}")
    if not Path(gate_path).is_file():
        raise RuntimeError("REFUSED: there is no gate document to authorize")
    if frozen["freeze_sha256"] not in Path(gate_path).read_text(encoding="utf-8"):
        raise RuntimeError("REFUSED: the gate does not cite the freeze hash of the freeze manifest")
    auth = integrated.check_authorization(
        auth_path, gate_path
    )  # PermissionError without a recorded authorization of this exact gate
    if Path(run_root).exists():
        raise RuntimeError(f"REFUSED: {run_root} already exists; the check is run once and nothing is overwritten")
    return auth


# ---- the bounded live run --------------------------------------------------------------------------------------------------------------
def _dump(path: Path, payload) -> None:
    integrated._dump(path, payload)


def run_check(
    root: Path, model_factory, *, live: bool, inp: dict, identity_check=None, config: dict | None = None
) -> dict:
    """Replay identity first (offline), then the model identity, then ONLY the listed children. Never retries. Returns the summary."""
    from experiments.ask_cli_revised.decompose.__main__ import write_artifacts

    config = config or CONFIG
    root.mkdir(parents=True, exist_ok=True)
    started = time.time()
    ident = replay_identity(inp)
    _dump(root / "REPLAY_IDENTITY.json", ident)
    if not ident["identical"]:
        summary = {
            "outcome": "not_started",
            "reason": ident["differences"],
            "note": "replay identity failed before any generation call",
        }
        _dump(root / "CHECK_SUMMARY.json", summary)
        return summary
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
    prep = prepared_prompts(inp, config)
    _dump(
        root / "PREPARED_PROMPTS.json",
        {c: {"prepared": r["prepared"], "baseline": r["baseline"]} for c, r in prep.items()},
    )
    sink = root / "model_calls.jsonl"
    sink.write_text("", encoding="utf-8")
    record = {
        "caps": {k: config[k] for k in ("max_writer_calls", "max_calls", "total_time_cap_seconds")},
        "started_unix": started,
    }
    try:
        result = run_engine(
            inp["question"],
            model,
            repair=False,
            max_calls=config["max_calls"],
            call_sink=sink,
            inventory_model=ReplayModel(inp["inventory"], "frozen-v6"),
            clarifications=inp["rows"],
            clarification_annotations=inp["annotations"],
            researcher_decisions=inp["decisions"],
            prompt_variant=config["variant"],
            only=config["children"],
            use_proposed_briefs=False,
            max_seconds=config["total_time_cap_seconds"],
            halt_on=strict_live_halt if live else integrated.offline_halt,
            max_writer_calls=config["max_writer_calls"],
        )
    except RunHalted as exc:
        record.update(outcome="halted", reason=exc.reason, at_call=exc.seq)
        _dump(
            root / "HALTED.json",
            {**record, "note": "INCOMPLETE. Stopped on a pre-declared condition; nothing was retried."},
        )
        summary = {
            "outcome": "INCOMPLETE",
            "reason": f"halted: {exc.reason}",
            "run": record,
            "model_identity": identity,
        }
        _dump(root / "CHECK_SUMMARY.json", summary)
        return summary
    except WriterBudgetExceeded as exc:
        summary = {
            "outcome": "INCOMPLETE",
            "reason": f"writer budget: needed {exc.needed}, budget {exc.budget}",
            "model_identity": identity,
        }
        _dump(root / "CHECK_SUMMARY.json", summary)
        return summary
    write_artifacts(result, root / "artifacts")
    nl, ct = views.natural_language_view(result), views.contract_view(result)
    _dump(root / "artifacts" / "VIEW_natural_language.json", nl)
    _dump(root / "artifacts" / "VIEW_contract.json", ct)
    (root / "artifacts" / "VIEW_contract.md").write_text(views.render_contract(ct), encoding="utf-8")
    written = [c for c in result["pass1"]["children"] if c["kind"] != "not_selected"]
    summary = {
        "outcome": "COMPLETE"
        if len(written) == len(config["children"]) and all(c["kind"] == "generated" for c in written)
        else "INCOMPLETE",
        "written": [(c["child_id"], c["kind"], c["status"]) for c in written],
        "calls": result["manifest"]["call_summary"],
        "replay_identity_identical": ident["identical"],
        "model_identity": identity,
        "environment": integrated.environment(),
        "engine_code_sha256_prefixes": code_hashes(),
        "total_wall_seconds": round(time.time() - started, 2),
        "subset_by_design": "the other children are recorded not_selected; a subset run is INCOMPLETE as a decomposition and that is intended",
    }
    _dump(root / "CHECK_SUMMARY.json", summary)
    return summary


# ---- comparison ---------------------------------------------------------------------------------------------------------------------------
def _tokens(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9']+", text.lower())


def _bag_diff(after: str, before: str) -> tuple[list[str], list[str]]:
    """Words in ``after`` not in ``before`` and the reverse (a multiset difference, order kept; lexical only, never a judgment)."""

    def minus(left: list[str], right: list[str]) -> list[str]:
        pool, out = list(right), []
        for t in left:
            if t in pool:
                pool.remove(t)
            else:
                out.append(t)
        return out

    a, b = _tokens(after), _tokens(before)
    return minus(a, b), minus(b, a)


def comparison(frozen_children: dict, new_children: list[dict], prepared: dict) -> list[dict]:
    """One row per written child: the frozen wording/status/flags beside the new ones, and what the WRITER changed relative to the prepared
    request. A targeted functional check, NOT a controlled estimate: several changes travel together, one seed, four children."""
    frozen = {c["child_id"]: c for c in frozen_children["children"]}
    rows = []
    for c in new_children:
        if c["kind"] == "not_selected":
            continue
        cid = c["child_id"]
        f = frozen[cid]
        pr = c.get("preparation") or prepared[cid]["preparation"]
        added, removed = _bag_diff(c["question"], pr["prepared_request"])
        rows.append(
            {
                "child": cid,
                "frozen": {"wording": f["question"], "status": f["status"], "flags": [x["flag"] for x in f["flags"]]},
                "prepared_request_given_to_the_writer": pr["prepared_request"],
                "new": {"wording": c["question"], "status": c["status"], "flags": [x["flag"] for x in c["flags"]]},
                "writer_changes_vs_prepared_request": {
                    "words_added": added,
                    "words_removed": removed,
                    "identical_words": not added and not removed,
                },
                "declared_unresolved": c.get("declared_unresolved"),
            }
        )
    return rows


def freeze_manifest(
    repo_root: Path,
    check_dir: Path,
    *,
    input_files: dict,
    tool_files: list[Path],
    clarification_files: dict,
    config: dict | None = None,
) -> dict:
    """Everything that must not change between the authorization and the run, with its hash."""
    config = config or CONFIG
    engine_dir = repo_root / "experiments" / "ask_cli_revised" / "decompose"
    settings = prompts.settings_for(config["variant"])
    manifest = {
        "artifact": "wording_check_freeze",
        "engine_version": ENGINE_VERSION,
        "config": config,
        "engine_code_sha256": {
            p.name: integrated.sha256_file(p) for p in sorted(engine_dir.glob("*.py")) if not p.name.startswith("test_")
        },
        "engine_tests_sha256": {p.name: integrated.sha256_file(p) for p in sorted(engine_dir.glob("test_*.py"))},
        "engine_support_sha256": {
            rel: integrated.sha256_file(repo_root / rel) for rel in integrated.FROZEN_ENGINE_SUPPORT
        },
        "tool_files_sha256": {p.name: integrated.sha256_file(p) for p in tool_files},
        "input_files_sha256": {name: integrated.sha256_file(p) for name, p in input_files.items()},
        "clarification_files_sha256": {name: integrated.sha256_file(p) for name, p in clarification_files.items()},
        "writer": {
            "variant": settings["variant"],
            "schema_sha256": integrated.sha256_text(json.dumps(settings["schema"], sort_keys=True)),
            "limits": settings["limits"],
            "output_cap": settings["cap"],
            "extract_mode": settings["extract_mode"],
            "preflight": settings["preflight"],
        },
        "hard_caps": {
            k: config[k]
            for k in ("max_writer_calls", "max_calls", "total_time_cap_seconds", "per_call_wall_timeout_seconds")
        },
        "reference_isolation": "the runner reads only the hashed copies under inputs/; the held-out reference is not an input of any kind",
    }
    manifest["freeze_sha256"] = integrated.sha256_text(
        json.dumps({k: v for k, v in manifest.items() if k != "freeze_sha256"}, sort_keys=True)
    )
    return manifest
