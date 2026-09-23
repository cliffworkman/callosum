"""Bakeoff orchestration: freeze guard, one observation per case, resume, retry rules, receipts, CLI.

    python -m experiments.ask_cli_revised.supervisor_eval.run_eval preflight
    python -m experiments.ask_cli_revised.supervisor_eval.run_eval stage0  <key>
    python -m experiments.ask_cli_revised.supervisor_eval.run_eval battery <key> [--retry-technical CASE_ID ...]
    python -m experiments.ask_cli_revised.supervisor_eval.run_eval score   <key>
    python -m experiments.ask_cli_revised.supervisor_eval.run_eval report

Experimental discipline enforced here: the freeze is verified before any call; every frozen case is observed
once per model; a recorded case is never re-observed on resume; only a pre-observation technical failure
(connection dropped / server refused, no output produced) may be retried, and the retry is written into the
record. Committed receipts are text-free; raw prompts/outputs/reasoning stay under `.local/`.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from experiments.ask_070.hashing import digest
from experiments.ask_cli_revised.supervisor_eval import build_battery as bb
from experiments.ask_cli_revised.supervisor_eval import cases, freeze, juno_resources, models, scoring, stage0
from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient, gpu_fraction

WORK_DIR = bb.REPO_ROOT / ".local" / "ask-070-supervisor-bakeoff"
RECEIPT_DIR = bb.PACKAGE_DIR / "receipts"
_RETRYABLE_STATUSES = ("transport_error", "http_error")


class FreezeError(Exception):
    """The frozen battery is not intact; no model may be called."""


class IneligibleRetry(Exception):
    """Only a pre-observation technical failure may be retried."""


def load_frozen_battery(manifest_path, private_path, freeze_path):
    try:
        problems = freeze.verify(freeze_path, bb.freeze_spec(manifest_path, private_path))
    except FileNotFoundError as exc:
        raise FreezeError(f"freeze inputs missing: {exc.filename}") from exc
    if problems:
        raise FreezeError("; ".join(problems))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    private = {c["case_id"]: c for c in json.loads(Path(private_path).read_text(encoding="utf-8"))["cases"]}
    for case in manifest["cases"]:
        mine = private.get(case["case_id"])
        if mine is None:
            raise FreezeError(f"{case['case_id']}: not present in the private battery")
        if digest({"prompt": mine["prompt"], "schema": mine["schema"]}) != case["input_sha256"]:
            raise FreezeError(f"{case['case_id']}: input hash differs from the public manifest")
    return {"manifest": manifest, "cases": private}


def _read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _retry_eligible(call):
    return (
        call["status"] in _RETRYABLE_STATUSES
        and not call.get("content")
        and not (call.get("timings") or {}).get("eval_count")
    )


def _residency(client, tag):
    entry = next((m for m in client.ps() if m["name"] in (tag, f"{tag}:latest")), {})
    return {
        "size": entry.get("size"),
        "size_vram": entry.get("size_vram"),
        "gpu_fraction": gpu_fraction(entry) if entry else None,
    }


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


def _save_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def run_battery(client, candidate, *, battery, out_dir, think, sampler=None, log=print, retry_technical=()):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    calls_path = out_dir / "battery_calls.jsonl"
    latest = {row["case_id"]: row for row in _read_rows(calls_path)}
    retry = set(retry_technical)
    for case_id in sorted(retry):
        row = latest.get(case_id)
        if row is None or not _retry_eligible(row["call"]):
            raise IneligibleRetry(f"{case_id}: only a recorded, pre-observation technical failure may be retried")
    order = [c["case_id"] for c in battery["manifest"]["cases"]]
    pending = [cid for cid in order if cid not in latest or cid in retry]
    residency, resources = _load_json(out_dir / "residency.json"), _load_json(out_dir / "resources.json")
    if pending:
        tag = candidate["tag"]
        if sampler:
            sampler.start(candidate["key"])
        try:
            for cid in pending:
                case, previous = battery["cases"][cid], latest.get(cid)
                log(f"{candidate['key']}: {cid}")
                call = client.chat(
                    tag,
                    case["prompt"],
                    schema=case["schema"],
                    options=models.ENVELOPE,
                    think=think,
                    keep_alive=models.KEEP_ALIVE,
                    wall_timeout=models.BATTERY_CALL_WALL_TIMEOUT_S,
                )
                row = {
                    "case_id": cid,
                    "attempt": (previous["attempt"] + 1) if previous else 1,
                    "input_sha256": case["input_sha256"],
                    "call": call,
                }
                if previous:
                    row["retry_of"] = previous["attempt"]
                    row["retry_reason"] = (
                        f"prior attempt status {previous['call']['status']}: {previous['call'].get('error')}"
                    )
                with calls_path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    handle.flush()
                latest[cid] = row
                if not residency:
                    residency = _residency(client, tag)
                    _save_json(out_dir / "residency.json", residency)
        finally:
            if sampler:
                resources = sampler.stop()
                _save_json(out_dir / "resources.json", resources)
            client.unload(tag)
    return {"calls": [latest[cid] for cid in order], "residency": residency, "resources": resources}


def _stats(values):
    return {"median": statistics.median(values), "min": min(values), "max": max(values)} if values else None


def summarize_performance(calls):
    records = [c["call"] for c in calls]
    first, warm = records[0], records[1:]
    return {
        "first_call_load_seconds": (first["timings"].get("load_duration") or 0) / 1e9,
        "warm_calls": len(warm),
        "warm_latency_s": _stats([c["wall_seconds"] for c in warm]),
        "tokens_per_second": _stats(
            [c["generation_tokens_per_second"] for c in warm if c.get("generation_tokens_per_second")]
        ),
        "total_battery_wall_s": sum(c["wall_seconds"] for c in records),
        "generated_tokens_total": sum(c["timings"].get("eval_count") or 0 for c in records),
        "max_prompt_tokens": max((c["timings"].get("prompt_eval_count") or 0) for c in records),
        "call_statuses": dict(Counter(c["status"] for c in records)),
    }


def _trial_summary(t):
    c, tm = t["call"], t["call"].get("timings") or {}
    return {
        "name": t["name"],
        "status": c["status"],
        "valid_json": t["valid_json"],
        "wall_seconds": c["wall_seconds"],
        "load_seconds": (tm.get("load_duration") or 0) / 1e9,
        "prompt_tokens": tm.get("prompt_eval_count"),
        "generated_tokens": tm.get("eval_count"),
        "tokens_per_second": c.get("generation_tokens_per_second"),
    }


def _case_summary(result):
    keep = ("verdict", "reasons", "selected", "duplicates", "diagnostic_selected", "attached", "unmapped", "plan")
    return {cid: {k: v for k, v in r.items() if k in keep} for cid, r in result.items()}


def make_receipt(key, stage0_result, battery_result, scored):
    gates = {}
    for gate, verdict in scored["gates"].items():
        gates[gate] = (
            {"status": verdict["status"], "hits": len(verdict["detail"])}
            if gate == "G8"
            else {"status": verdict["status"], "detail": verdict["detail"]}
        )
    s0 = stage0_result or {}
    return {
        "candidate": key,
        "tag": s0.get("model"),
        "qualified": scored["qualified"],
        "gates": gates,
        "cases": _case_summary(scored["cases"]),
        "diagnostics": scored["diagnostics"],
        "stage0": {
            "verdict": s0.get("verdict"),
            "reason": s0.get("reason"),
            "identity": s0.get("identity"),
            "think_setting": s0.get("think_setting"),
            "envelope": s0.get("envelope"),
            "residency": s0.get("residency"),
            "enum_enforced": (s0.get("enum_probe") or {}).get("enforced"),
            "padded": s0.get("padded"),
            "trials": [_trial_summary(t) for t in s0.get("trials", [])],
            "host": {k: s0.get(k) for k in ("host_before", "host_resident", "host_after")},
        },
        "performance": {
            **summarize_performance(battery_result["calls"]),
            "residency": battery_result.get("residency"),
            "resources": battery_result.get("resources"),
        },
    }


def _flat_calls(rows):
    return [{**row["call"], "case_id": row["case_id"]} for row in rows]


def _paths():
    return bb.PACKAGE_DIR / bb.MANIFEST_NAME, bb.PRIVATE_DIR / bb.PRIVATE_NAME, bb.PACKAGE_DIR / bb.FREEZE_NAME


def _candidate(key):
    return models.by_key(key)


def _cmd_preflight(client):
    store_text = juno_resources.run_remote(juno_resources.STORE_COMMAND)
    out = {
        "ollama_version": client.version(),
        "models_present": sorted(m["name"] for m in client.tags()),
        "resident_now": client.ps(),
        "host": juno_resources.snapshot(),
        "store_probe": store_text,
    }
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    _save_json(WORK_DIR / "preflight.json", out)
    print(json.dumps({k: out[k] for k in ("ollama_version", "models_present", "resident_now", "host")}, indent=2))


def _cmd_stage0(client, key):
    cand = _candidate(key)
    store_check = juno_resources.assess_store(juno_resources.run_remote(juno_resources.STORE_COMMAND), cand["size_gb"])
    result = stage0.run(client, cand, host_snapshot=juno_resources.snapshot, store_check=store_check, log=print)
    (WORK_DIR / key).mkdir(parents=True, exist_ok=True)
    _save_json(WORK_DIR / key / "stage0.json", result)
    print(f"{key}: {result['verdict']} {result.get('reason') or ''}")


def _cmd_battery(client, key, retry):
    manifest_path, private_path, freeze_path = _paths()
    battery = load_frozen_battery(manifest_path, private_path, freeze_path)
    out_dir = WORK_DIR / key
    s0 = _load_json(out_dir / "stage0.json")
    if s0.get("verdict") != "ok":
        raise SystemExit(f"{key}: Stage 0 verdict is {s0.get('verdict')!r}; not running the battery")
    result = run_battery(
        client,
        _candidate(key),
        battery=battery,
        out_dir=out_dir,
        think=s0.get("think_setting"),
        sampler=juno_resources.JunoSampler(out_dir=out_dir),
        log=print,
        retry_technical=retry,
    )
    print(f"{key}: {len(result['calls'])} calls recorded")


def _score(key):
    out_dir = WORK_DIR / key
    result = run_battery_result_from_disk(out_dir)
    scored = scoring.score_model(cases.build_case_specs(), _flat_calls(result["calls"]))
    full = {"scored": scored, "g8_snippets": scored["gates"]["G8"]["detail"]}
    _save_json(out_dir / "score.json", full)
    return result, scored


def run_battery_result_from_disk(out_dir):
    rows = {}
    for row in _read_rows(Path(out_dir) / "battery_calls.jsonl"):
        rows[row["case_id"]] = row
    order = [c["case_id"] for c in cases.build_case_specs()]
    return {
        "calls": [rows[cid] for cid in order if cid in rows],
        "residency": _load_json(Path(out_dir) / "residency.json"),
        "resources": _load_json(Path(out_dir) / "resources.json"),
    }


def _cmd_score(key):
    _, scored = _score(key)
    print(json.dumps({"qualified": scored["qualified"], "gates": {g: v["status"] for g, v in scored["gates"].items()}}))


def _cmd_report():
    RECEIPT_DIR.mkdir(exist_ok=True)
    for cand in models.CANDIDATES:
        out_dir = WORK_DIR / cand["key"]
        s0 = _load_json(out_dir / "stage0.json")
        if not s0:
            continue
        if (out_dir / "battery_calls.jsonl").exists():
            result, scored = _score(cand["key"])
            receipt = make_receipt(cand["key"], s0, result, scored)
        else:
            receipt = {
                "candidate": cand["key"],
                "tag": cand["tag"],
                "qualified": None,
                "battery": "not run",
                "stage0": {k: s0.get(k) for k in ("verdict", "reason", "identity", "think_setting", "envelope")},
            }
        _save_json(RECEIPT_DIR / f"{cand['key']}.json", receipt)
        print(f"receipt: {cand['key']}")


def main(argv):
    command = argv[0] if argv else ""
    if command == "report":
        _cmd_report()
        return 0
    if command == "score" and len(argv) == 2:
        _cmd_score(argv[1])
        return 0
    if command in ("preflight", "stage0", "battery"):
        client = OllamaClient()
        try:
            if command == "preflight":
                _cmd_preflight(client)
            elif command == "stage0" and len(argv) == 2:
                _cmd_stage0(client, argv[1])
            elif command == "battery" and len(argv) >= 2:
                retry = argv[argv.index("--retry-technical") + 1 :] if "--retry-technical" in argv else []
                _cmd_battery(client, argv[1], set(retry))
            else:
                print(__doc__)
                return 2
        finally:
            client.close()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
