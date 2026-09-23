"""Qwen3.5 reasoning-budget sensitivity arm: `num_predict` 4,096 -> 8,192 on the calls the first tranche could not observe.

`qwen3.5:9b` (native reasoning) hit the 4,096-token ceiling while still reasoning on some frozen calls, which left those calls
"unusable" rather than right or wrong. This arm changes exactly ONE execution variable for exactly those calls and observes each
once. It is evidence for a later token-budget decision, not a production policy: nothing here is imported by production code, and
8192 is not added to the frozen registry or envelope.

Deliberately small. Per-case verdicts go through the frozen case judges only (never a battery-wide gate, never a Qualified flag):
the arm reruns a handful of cases, so any battery-level result would be synthetic.
"""

import json
import os
from pathlib import Path

from experiments.ask_cli_revised.supervisor_eval import extension, models, scoring

ORIGINAL_KEY = "qwen3.5-9b"
ARM_KEY = "qwen3.5-9b-8k-sensitivity"
NUM_PREDICT = 8192


def select_censored_cases(rows, order):
    """Cases whose recorded call completed transport-wise but stopped on the token cap, in battery order."""
    censored = {
        r["case_id"] for r in rows if r["call"].get("status") == "ok" and r["call"].get("done_reason") == "length"
    }
    return [cid for cid in order if cid in censored]


def assert_only_num_predict_changed(env):
    changed = {k for k in set(env) | set(models.ENVELOPE) if env.get(k) != models.ENVELOPE.get(k)}
    if changed != {"num_predict"}:
        raise ValueError(f"the arm may change only num_predict; differences: {sorted(changed) or 'none'}")
    return env


def envelope_8k():
    return assert_only_num_predict_changed({**models.ENVELOPE, "num_predict": NUM_PREDICT})


def context_headroom(prompt_tokens, generated, num_ctx):
    total = prompt_tokens + generated
    return {
        "prompt_tokens": prompt_tokens,
        "generated": generated,
        "total": total,
        "headroom": num_ctx - total,
        "ok": total <= num_ctx,
    }


def assert_separate_dirs(original, arm):
    if Path(original).resolve() == Path(arm).resolve():
        raise ValueError("the sensitivity arm must not write into the first tranche's result directory")


def approx_split(call):
    """Reasoning vs final tokens by character proportion. An estimate: Ollama reports only the total (`eval_count`)."""
    thinking, content = len(call.get("thinking") or ""), len(call.get("content") or "")
    total = (call.get("timings") or {}).get("eval_count") or 0
    if not (thinking + content) or not total:
        return None
    reasoning = round(total * thinking / (thinking + content))
    return {"reasoning": reasoning, "final": total - reasoning, "approximate": True}


def prefix_agreement(original, new):
    """Determinism diagnostic only: how much of the 4K run's reasoning text the 8K run reproduces verbatim from the start."""
    common = len(os.path.commonprefix([original, new]))
    return {
        "common_chars": common,
        "original_chars": len(original),
        "fraction_of_original": (common / len(original)) if original else None,
    }


def _result(spec, obs, judged):
    if obs["obj"] is None:
        return None
    family = spec["family"]
    if family == "A":
        return {"selected": judged["selected"]}
    if family == "B":
        coverage = {
            ob: {"status": e["status"], "supports": list(e["supporting_proposition_ids"])}
            for ob, e in obs["obj"]["coverage"].items()
        }
        return {"coverage": coverage, "attached": judged["attached"], "unmapped": judged["unmapped"]}
    return {"plan": judged["plan"]}


def judge_case(spec, call):
    """One call -> the frozen per-case judgment plus the ids it returned. Never a gate, never a Qualified flag."""
    obs = scoring._observe(spec, call)
    judged = scoring._judge(spec, obs)
    return {
        "verdict": judged["verdict"],
        "reasons": judged.get("reasons", []),
        "structured_valid": obs["obj"] is not None,
        "invented_ids": obs["invented"],
        "absence_hits": len(scoring.corpus_absence_hits(obs["rationale"])),
        "result": _result(spec, obs, judged),
    }


def case_record(spec, original_row, arm_row, num_ctx):
    o, a = original_row["call"], arm_row["call"]
    timings = a.get("timings") or {}
    judged = judge_case(spec, a)
    return {
        "case_id": spec["case_id"],
        "cap_4096": {
            "status": o["status"],
            "done_reason": o["done_reason"],
            "eval_count": (o.get("timings") or {}).get("eval_count"),
            "verdict": judge_case(spec, o)["verdict"],
        },
        "cap_8192": {
            "status": a["status"],
            "done_reason": a.get("done_reason"),
            "completed": a["status"] == "ok" and a.get("done_reason") == "stop",
            "hit_cap": a.get("done_reason") == "length",
            "eval_count": timings.get("eval_count"),
            "approx_split": approx_split(a),
            "wall_seconds": a.get("wall_seconds"),
            "tokens_per_second": a.get("generation_tokens_per_second"),
            "context": context_headroom(timings.get("prompt_eval_count") or 0, timings.get("eval_count") or 0, num_ctx),
            **judged,
        },
        "prefix": prefix_agreement(o.get("thinking") or "", a.get("thinking") or ""),
    }


def arm_block(freeze_path, meta):
    frozen = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
    return {
        "kind": "execution-envelope sensitivity arm on the first tranche's length-censored calls; post-hoc, predeclared; "
        "not part of the frozen first tranche",
        "arm_of": "first-tranche",
        "candidate": ORIGINAL_KEY,
        "changed_variable": {"num_predict": [models.ENVELOPE["num_predict"], NUM_PREDICT]},
        "unchanged": "num_ctx, prompts, schemas, orderings, temperature, seed, think, num_thread, num_batch, keep-alive, watchdogs",
        "first_tranche_freeze_commit": extension.FIRST_TRANCHE_FREEZE_COMMIT,
        "first_tranche_results_commit": extension.FIRST_TRANCHE_RESULTS_COMMIT,
        "freeze_sha256": frozen["freeze_sha256"],
        "battery_manifest_sha256": frozen["json"]["battery_manifest"],
        "private_battery_sha256": frozen["private_files"]["battery.private.json"],
        "envelope": envelope_8k(),
        "artifact": meta.get("artifact"),
        "runtime": meta.get("runtime"),
    }
