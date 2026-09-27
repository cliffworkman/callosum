"""Command line: `prepare` (offline, no model) and `live` (guarded: authorization + isolated-only endpoint + clean tree).

    python -m experiments.ask_cli_revised.contract_directed.run prepare --run-id pilot-prep-001 --children pilot
    python -m experiments.ask_cli_revised.contract_directed.run live --run-id pilot-001 --children pilot --authorization FILE

`prepare` runs every deterministic stage on the disposable copy under a REFUSE-ALL socket guard (so it provably makes no network
call), verifies the library copy and the baseline are unchanged, freezes the caps, budgets and pre-registered expectations, and
writes the authorization template Cliff must sign. `live` refuses without a matching confirmed authorization, verifies the
model digest and Ollama version, and confines the process to the isolated endpoint. Neither ever touches the shared Ollama.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from experiments.ask_cli_revised import library_copy  # noqa: E402
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.contract_directed import (  # noqa: E402
    budget,
    endpoint_guard,
    expectations,
    freeze,
    pipeline,
    report,
)
from experiments.ask_cli_revised.contract_directed import (
    model_stages as ms,
)
from experiments.ask_cli_revised.contract_directed.retriever import Retriever  # noqa: E402
from experiments.ask_cli_revised.contract_directed.store import Library  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
DB = freeze.SLICE_ROOT / "library.sqlite"
FINGERPRINT = freeze.SLICE_ROOT / "library.sqlite.fingerprint.json"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def code_identity() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=False).stdout.strip()

    return {
        "sha": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty_paths": [line for line in git("status", "--porcelain").splitlines() if line.strip()],
    }


def resolve_children(spec: str) -> tuple[list[str], budget.Caps, dict, str]:
    if spec == "pilot":
        return list(budget.PILOT_CHILDREN), budget.PILOT_CAPS, budget.PILOT_CEILINGS, "pilot"
    if spec == "full":
        return list(freeze.CHILD_IDS), budget.FULL_CAPS, budget.FULL_CEILINGS, "full"
    ids = [c.strip() for c in spec.split(",") if c.strip()]
    unknown = [c for c in ids if c not in freeze.CHILD_IDS]
    if unknown:
        raise SystemExit(f"unknown children: {unknown}")
    return ids, budget.FULL_CAPS, budget.FULL_CEILINGS, "custom"


def verify_integrity(substrate: freeze.FrozenSubstrate) -> dict:
    baseline_manifest = json.loads((freeze.SLICE_ROOT / "baseline_manifest.json").read_text(encoding="utf-8"))
    changed = freeze.verify_baseline_unchanged(baseline_manifest)
    try:
        library_copy.verify(DB, FINGERPRINT)
        library_ok = True
    except library_copy.LibraryCopyDrift:
        library_ok = False
    return {
        **{f"frozen.{k}": v for k, v in substrate.checks.items()},
        "library_copy_unchanged": library_ok,
        "baseline_artifacts_unchanged": not changed,
    }


def prepare(args) -> int:
    children, caps, ceilings, kind = resolve_children(args.children)
    run_dir = freeze.SLICE_ROOT / "runs" / args.run_id
    if run_dir.exists():
        raise SystemExit(f"{run_dir} exists; run ids are never reused")
    run_dir.mkdir(parents=True)
    substrate = freeze.load_frozen()
    integrity = verify_integrity(substrate)
    run_budget = budget.run_budget(children, caps, ceilings)
    with endpoint_guard.refuse_all():  # no network by construction during the deterministic dry-run
        library = Library(DB)
        try:
            retriever = Retriever(library)
            run = pipeline.Run(run_dir=run_dir, library=library, retriever=retriever, substrate=substrate, caps=caps)
            dry = pipeline.deterministic_dry_run(run, children)
            unsearchable = len(retriever.unsearchable)
            pool = len(retriever.index)
        finally:
            library.close()
    integrity_after = verify_integrity(substrate)
    manifest = {
        "created": now(),
        "kind": f"prepare ({kind})",
        "code": code_identity(),
        "frozen": {
            "question_sha256": freeze.QUESTION_SHA256,
            "hierarchy_integrity_sha256": freeze.HIERARCHY_INTEGRITY_SHA256,
            "model_facing_sha256": freeze.MODEL_FACING_SHA256,
            "library_sha256": freeze.LIBRARY_SHA256,
        },
        "model": {
            "name": freeze.MODEL,
            "digest": freeze.MODEL_DIGEST,
            "ollama_version": freeze.OLLAMA_VERSION,
            "endpoint": topo.ENDPOINTS["isolated"],
            "thinking": False,
            "options": dict(topo.SUPERVISOR_BASE_OPTIONS),
        },
        "children": children,
        "integrity_before": integrity,
        "integrity_after_dry_run": integrity_after,
        "network_during_prepare": "refused by endpoint_guard.refuse_all() for the whole deterministic dry-run",
        "retrieval": {
            "query_view": "child_only (the parent question is not used)",
            "pool_chunks": pool,
            "unsearchable_chunks_no_current_embedding": unsearchable,
        },
        "budget": run_budget,
        "recovery": {
            "passes": 1,
            "conditional_bridge": "built and tested offline; executes only if triggered AND separately authorized",
        },
        "stop_conditions": {
            "no_answer_rate_halt": 0.10,
            "min_calls_for_rate": 20,
            "retries": 0,
            "on_ceiling": "stop; remaining work recorded not_run_budget",
        },
    }
    (run_dir / "00_run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "budget.json").write_text(json.dumps(run_budget, indent=2), encoding="utf-8")
    (run_dir / "expectations.json").write_text(
        json.dumps(expectations.expectations_record(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    template = budget.authorization_template(f"{kind}-live", run_budget)
    (run_dir / "authorization_template.json").write_text(json.dumps(template, indent=2), encoding="utf-8")
    (run_dir / "prepare_summary.json").write_text(
        json.dumps({"deterministic_dry_run": dry, "integrity_ok": all(integrity_after.values())}, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "integrity_ok": all(integrity_after.values()),
                "worst_case_calls": run_budget["worst_case"]["worst_case_total_calls"],
                "dry_run": dry,
            },
            indent=2,
        )
    )
    return 0 if all(integrity_after.values()) else 1


def live(args) -> int:
    children, caps, ceilings, kind = resolve_children(args.children)
    substrate = freeze.load_frozen()
    run_budget = budget.run_budget(children, caps, ceilings)
    budget.check_authorization(
        args.authorization, run_budget, experiment_id=f"{kind}-live"
    )  # raises AuthorizationRefused
    code = code_identity()
    if code["dirty_paths"]:
        raise SystemExit(f"refusing a scored run from a dirty tree: {code['dirty_paths'][:5]}")
    integrity = verify_integrity(substrate)
    if not all(integrity.values()):
        raise SystemExit(f"integrity failed before the run: {[k for k, v in integrity.items() if not v]}")
    run_dir = freeze.SLICE_ROOT / "runs" / args.run_id
    run_dir.mkdir(parents=True)
    # Everything that must be on record BEFORE any inference: the frozen expectations (with their hash), the authorization
    # actually used, and the manifest (code identity, caps, budgets, ceilings, model, stop conditions).
    record = expectations.expectations_record()
    (run_dir / "expectations.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "authorization_used.json").write_text(
        Path(args.authorization).read_text(encoding="utf-8"), encoding="utf-8"
    )
    (run_dir / "00_run_manifest.json").write_text(
        json.dumps(
            {
                "created": now(),
                "kind": f"live ({kind})",
                "code": code,
                "children": children,
                "budget": run_budget,
                "integrity_before": integrity,
                "expectations": {"version": record["version"], "sha256": record["sha256"]},
                "model": {
                    "name": freeze.MODEL,
                    "digest": freeze.MODEL_DIGEST,
                    "ollama_version": freeze.OLLAMA_VERSION,
                    "endpoint": topo.ENDPOINTS["isolated"],
                    "thinking": False,
                    "options": dict(topo.SUPERVISOR_BASE_OPTIONS),
                },
                "stop_conditions": {
                    "no_answer_rate_halt": 0.10,
                    "min_calls_for_rate": 20,
                    "retries": 0,
                    "fallbacks": 0,
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with endpoint_guard.isolated_only():
        client = ms.FreeChatClient(topo.ENDPOINTS["isolated"])
        pre = {"at": now(), "ollama_version": client.version()}
        tags = {(e.get("name") or e.get("model")): e.get("digest") for e in client.tags()}
        pre["installed_digest"] = tags.get(freeze.MODEL)
        pre["resident_before"] = [e.get("name") or e.get("model") for e in client.ps()]
        (run_dir / "01_pre_call_ollama_state.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
        if pre["ollama_version"] != freeze.OLLAMA_VERSION or pre["installed_digest"] != freeze.MODEL_DIGEST:
            raise SystemExit(f"model digest / Ollama version differ from the recorded run: {pre}")
        library = Library(DB)
        try:
            retriever = Retriever(library)
            from experiments.ask_cli_revised.trace import TraceWriter

            trace = TraceWriter(run_dir)
            ledger = ms.Ledger(max_calls=ceilings["max_calls"], wall_seconds=ceilings["wall_seconds"])
            env = ms.Env(client=client, ledger=ledger, trace=trace)
            run = pipeline.Run(
                run_dir=run_dir,
                library=library,
                retriever=retriever,
                substrate=substrate,
                caps=caps,
                env=env,
                trace=trace,
            )
            status = pipeline.run_children(run, children)
        finally:
            library.close()
            if not pre["resident_before"]:
                client.unload(freeze.MODEL)
            client.close()
    integrity_after = verify_integrity(substrate)
    summary = report.write_all(run_dir, substrate, children, integrity=integrity_after)
    print(json.dumps({"status": status, "report": summary}, indent=2, default=str))
    return 0 if all(integrity_after.values()) and not status["halted"] else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "live"):
        p = sub.add_parser(name)
        p.add_argument("--run-id", required=True)
        p.add_argument("--children", default="pilot", help="pilot | full | comma-separated child ids")
        if name == "live":
            p.add_argument("--authorization", required=True)
    args = parser.parse_args(argv)
    return prepare(args) if args.command == "prepare" else live(args)


if __name__ == "__main__":
    sys.exit(main())
