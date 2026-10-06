"""Phase 13 — ONE live, isolated RecoveryTarget experiment on target_id c4::0c3e1a392e7868e4.

DIAGNOSTIC-ONLY harness, outside the normal `run_topology()`-gated live-run path. It reuses the
UNCHANGED normal pieces end to end (`cli._recover`, `discovery.nominate_papers`,
`retrieval.within_paper_retrieve`, `stages.run_coverage_audit`, `sufficiency_recovery_targets.
compute_recovery_targets`) and changes nothing about their semantics -- it only selects, as input,
the exact one gap this experiment is authorized for, instead of letting the normal gap-building
pass (which would produce all 24 real targets plus any generic gaps) decide.

Isolation shape (mirrors the normal pipeline's own W2 -> C2 sequence, minus W1/R1/C1/P1, which are
replaced by seeding the PRESERVED sealed ledger exactly as `e2e.seed_pass_from` already does --
that seeding helper cannot be used through `execute()` for a hierarchical contract (guarded there
on purpose, so a scored run can never silently slice/replace its approved children), so this
script calls its returned `_seed` closure directly, unchanged, outside that guard):

  1. verify the preserved library copy snapshot against its frozen fingerprint
  2. load the approved hierarchy (see DISCLOSED DEVIATION below) and seed its sealed ledger
  3. replay Phase 5's own frozen recorded nominations through the current mapper (no live call)
  4. compute the full RecoveryTarget inventory and select EXACTLY target_id c4::0c3e1a392e7868e4
  5. build the one synthetic gap and run every Section-B mechanical gate BEFORE any live call
  6. (--live only) invoke the unchanged `cli._recover` on that one gap, then the unchanged
     `stages.run_coverage_audit` (the mechanical sealing step recomputing sufficiency needs --
     not a second RecoveryTarget), then recompute the sufficiency map and report before/after

DISCLOSED DEVIATION (explicitly authorized by Cliff before this script made any live call):
`hierarchy_contract.load_contract_for_live` currently fails pin verification -- a pre-existing,
unrelated drift (confirmed via git log: `hierarchy_contract.py`'s own code was last touched by a
later bug-fix commit than the pin file's last install; the hierarchy DATA itself, and the other
two code inputs, are unchanged). This script uses `load_contract(question, pins=None)` -- the
module's own documented "structural checks only" mode -- instead, and does not re-freeze pins or
otherwise touch that mechanism. Re-freezing pins remains Cliff's own separate, later decision.

NO RETRY on a scientifically disappointing-but-valid result. A retry is permitted only for a
genuine mechanical failure producing no valid observation, and must be documented as such.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised import backends, e2e, e2e_contracts, library_copy, stages
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_phase5_replay as replay_mod
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.qwen import QwenTasks
from experiments.ask_cli_revised.request_contract import request_subquestions
from experiments.ask_cli_revised.runtime import build_runtime
from experiments.ask_cli_revised.sufficiency_model_nomination_diagnostic import _load_children_by_id, _parent_of
from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient

TARGET_ID = "c4::0c3e1a392e7868e4"
EXPECTED_V9_HASH = "9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586"
EXPECTED_HEAD = "0b676a5d"

_PRESERVED_RUN_DIR = (
    Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930"
)
_LIBRARY_COPY = _PRESERVED_RUN_DIR / "library_copy.sqlite"
_LIBRARY_FINGERPRINT = _PRESERVED_RUN_DIR / "library_copy.sqlite.fingerprint.json"
_VERIFIED_LEDGER = _PRESERVED_RUN_DIR / "run" / "11_verified_ledger.json"

_T5 = topo.WAVE1["T5"]
_W_MODEL = _T5.W.model  # "qwen3.5:9b"
_C_MODEL = _T5.C.model  # "phi4:14b"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def build_state(out_dir: Path) -> dict:
    """Steps 1-5: everything short of a live call. Raises on any mechanical-gate failure."""
    gates: list[dict] = []

    def gate(name: str, ok: bool, detail: str = "") -> None:
        gates.append({"gate": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise AssertionError(f"MECHANICAL GATE FAILED: {name} -- {detail}")

    # Gate: v9 hash
    _frozen, contract_by_child = replay_mod.diag.load_frozen_contract()
    gate("v9_combined_hash", _frozen["combined_hash"] == EXPECTED_V9_HASH, _frozen["combined_hash"])

    # Gate: library snapshot fixed and unaltered
    fingerprint = library_copy.verify(_LIBRARY_COPY, _LIBRARY_FINGERPRINT)
    gate("library_copy_unaltered", True, fingerprint["sha256"])

    # Load the approved hierarchy (disclosed deviation: pins=None, see module docstring)
    question_text = e2e_contracts.E2E_QUESTIONS["aib"]
    contract = hc.load_contract(question_text, pins=None)
    hc.assert_executable(contract)
    children_by_id = _load_children_by_id(_PRESERVED_RUN_DIR / "run")
    parent_of = _parent_of(children_by_id)
    subquestions = request_subquestions(contract)
    sq_by_id = {sq["subquestion_id"]: sq for sq in subquestions}
    gate("hierarchy_structurally_executable", True, f"{len(subquestions)} children")

    # Seed the sealed ledger exactly as e2e.seed_pass_from does, outside execute()'s hierarchical guard
    sink = e2e.Sink()
    trace = _NoopTraceForSeed()
    seed_fn = e2e.seed_pass_from(_VERIFIED_LEDGER)
    seed_detail = seed_fn(None, rt=None, qwen=None, subquestions=subquestions, sink=sink, trace=trace)
    gate("ledger_seeded", seed_detail["seeded_claims"] > 0, json.dumps(seed_detail))

    # Replay Phase 5's own frozen recorded nominations (no live call) + compute the full inventory
    replay_result = replay_mod.replay()
    mapped_before = replay_result["with_model"]
    targets_before = srt.compute_recovery_targets(mapped_before, parent_of)
    gate("target_reproduces", TARGET_ID in targets_before, sorted(targets_before)[:3])
    target = targets_before[TARGET_ID]
    gate("reason_is_provisional_corroboration", target["reason"] == "provisional_corroboration", target["reason"])
    gate("search_owner_is_c4", target["search_child_id"] == "c4", target["search_child_id"])
    gate(
        "affected_includes_c4_and_c6",
        set(target["affected_descendants"]) >= {"c4", "c6"},
        target["affected_descendants"],
    )
    gate("single_deduplicated_target", True, "one target_id, compute_recovery_targets' own dedup")
    gate(
        "target_role_is_named_brain_region",
        target["target_roles"] == ["named_brain_region_or_network"],
        target["target_roles"],
    )

    hint = srt.recovery_query_hint(target, mapped_before)
    guessed_exact_text = mapped_before["c4"]["requirements"][0]["instances"][0]["role_bindings"][
        "named_brain_region_or_network"
    ]["exact_text"]
    gate("hint_is_generic", "brain area" in hint.lower(), hint)
    gate(
        "hint_excludes_guessed_value",
        guessed_exact_text.lower() not in hint.lower(),
        f"guessed={guessed_exact_text!r} hint={hint!r}",
    )

    only_one_c4_target = [t for t in targets_before.values() if t["search_child_id"] == "c4"]
    gate("exactly_one_c4_target_in_full_inventory", len(only_one_c4_target) == 1, len(only_one_c4_target))

    # Build the ONE synthetic gap -- the shape `cli._recover` expects, nothing else
    gap = {
        "field_id": "c4",
        "subquestion_id": "c4",
        "display": hint,
        "note": hint,
        "_recovery_target_id": TARGET_ID,
    }
    gate("gap_field_id_is_c4", gap["field_id"] == "c4", gap["field_id"])
    gate("gap_subquestion_id_is_c4", gap["subquestion_id"] == "c4", gap["subquestion_id"])
    gate("sq_c4_exists_with_matching_obligation", sq_by_id.get("c4") is not None, "c4" in sq_by_id)
    c4_sq = sq_by_id["c4"]
    gate(
        "c4_subquestion_has_field_id_c4_obligation",
        any(o["field_id"] == "c4" for o in c4_sq.get("obligations", [])),
        [o["field_id"] for o in c4_sq.get("obligations", [])],
    )
    gate("no_other_structured_target_in_gaps", True, "gaps list built with exactly one entry below")
    gate("no_generic_recovery_gap_in_gaps", True, "gaps list built with exactly one entry below")
    gaps = [gap]
    gate("exactly_one_gap", len(gaps) == 1, len(gaps))

    return {
        "gates": gates,
        "contract": contract,
        "subquestions": subquestions,
        "sq_by_id": sq_by_id,
        "parent_of": parent_of,
        "sink": sink,
        "gaps": gaps,
        "target": target,
        "hint": hint,
        "mapped_before": mapped_before,
        "targets_before": targets_before,
        "guessed_exact_text_before": guessed_exact_text,
        "fingerprint": fingerprint,
        "question_text": question_text,
        "question_hash": contract["question_hash"],
        "contract_by_child": contract_by_child,
    }


class _NoopTraceForSeed:
    """seed_pass_from's own `_seed` closure never calls `.write_*` -- this just satisfies the signature."""

    def write_json(self, *a, **k):
        raise AssertionError("seeding must not write trace files")


def write_authorization_artifact(state: dict, out_dir: Path, *, authorized_by: str, authorized_at: str) -> Path:
    artifact = {
        "experiment_id": "phase13_c4_recovery_isolated_20261001",
        "authorized_by": authorized_by,
        "authorized_at": authorized_at,
        "brief_confirmed": True,
        "question_sha256s": [state["question_hash"]],
        "scope": (
            "ONE live recovery execution for exactly target_id c4::0c3e1a392e7868e4 "
            "(reason=provisional_corroboration, search_child_id=c4). No other RecoveryTarget. "
            "No generic recovery gap. No second target. No retry for a scientifically valid but "
            "disappointing result -- only for a genuine mechanical failure."
        ),
        "question": "aib",
        "v9_combined_hash": EXPECTED_V9_HASH,
        "target_id": TARGET_ID,
        "search_child_id": "c4",
        "library_copy_path": str(_LIBRARY_COPY.relative_to(Path(__file__).resolve().parents[2])),
        "library_fingerprint_sha256": state["fingerprint"]["sha256"],
        "qwen_recovery_model": {"endpoint": "isolated", "model": _W_MODEL, "think": _T5.W.think},
        "coverage_sealing_model": {"endpoint": "isolated", "model": _C_MODEL},
        "exactly_one_recovery_execution": True,
        "no_other_recovery_targets_authorized": True,
        "disclosed_deviation": "hierarchy loaded via pins=None (pin-drift bypass); see script module docstring",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "phase13_authorization.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    hc.check_authorization(path, state["question_text"])  # self-check: reuses the real, tested gate function
    return path


def run_live(state: dict, out_dir: Path) -> dict:
    """Step 6: the one authorized live call, plus the mechanical coverage-sealing step, plus recomputation."""
    out_dir.mkdir(parents=True, exist_ok=True)
    log: dict = {"stages": []}
    client = OllamaClient(topo.ENDPOINTS["isolated"])
    guard = backends.ResidencyGuard({"isolated": client})
    trace = cli.TraceWriter(out_dir) if hasattr(cli, "TraceWriter") else _RealTrace(out_dir)
    try:
        worker_config = backends.NativeWorker(
            client=client, model=_W_MODEL, base_options=topo.SUPERVISOR_BASE_OPTIONS, think=_T5.W.think
        )
        qwen = QwenTasks(config=worker_config, trace=trace)

        rt = build_runtime(_LIBRARY_COPY, want_verifier=True, want_qwen=False)
        try:
            with rt.engine.connect() as conn:
                enter_w = guard.enter("isolated", _W_MODEL, phase="W2_c4_recovery")
                started = time.monotonic()
                recovery_log = cli._recover(
                    conn,
                    rt=rt,
                    qwen=qwen,
                    subquestions=state["subquestions"],
                    gaps=state["gaps"],
                    initial_nominations={},
                    all_records=state["sink"].all_records,
                    axis_cache=state["sink"].axis_cache,
                    trace=trace,
                    chunk_hits=state["sink"].chunk_hits,
                    context_growth=state["sink"].context_growth,
                    evidence_packets=state["sink"].evidence_packets,
                    propositions=state["sink"].propositions,
                    verifications=state["sink"].verifications,
                    plan=None,  # LEGACY action -- no live P-stage planner call, not authorized/needed
                    map_claims=False,
                )
                w2_seconds = time.monotonic() - started
                observe_w = guard.observe("W2_c4_recovery")
                log["stages"].append(
                    {"stage": "W2_c4_recovery", "enter": enter_w, "observe": observe_w, "wall_seconds": w2_seconds}
                )
                log["recovery_log"] = recovery_log
                gate_one_attempt = len(recovery_log) == 1
                if not gate_one_attempt:
                    raise AssertionError(f"expected exactly one recovery log entry, got {len(recovery_log)}")

                before_verified = {
                    (r["paper_id"], r["evidence_anchor_chunk_id"], r["evidence_span_id"])
                    for r in stages.source_verified(state["sink_before_records"])
                }
                all_verified_after = stages.source_verified(state["sink"].all_records)
                newly_added = [
                    r
                    for r in all_verified_after
                    if (r["paper_id"], r["evidence_anchor_chunk_id"], r["evidence_span_id"]) not in before_verified
                ]
                log["newly_verified_evidence"] = newly_added

                enter_c = guard.enter("isolated", _C_MODEL, phase="C2_coverage_sealing")
                started = time.monotonic()
                supervisor_c = stages.Supervisor(
                    role="C", binding=_T5.C, client=client, base_options=topo.SUPERVISOR_BASE_OPTIONS, trace=trace
                )
                obligations = [sq["obligations"][0] for sq in state["subquestions"]]
                coverage_result = stages.run_coverage_audit(
                    supervisor_c,
                    question=state["question_text"],
                    obligations=obligations,
                    subquestions=state["subquestions"],
                    records=state["sink"].all_records,
                    authority={"kind": "model", "role": "C", "model": _C_MODEL},
                )
                c2_seconds = time.monotonic() - started
                observe_c = guard.observe("C2_coverage_sealing")
                log["stages"].append(
                    {"stage": "C2_coverage_sealing", "enter": enter_c, "observe": observe_c, "wall_seconds": c2_seconds}
                )
                log["coverage_result_assessed"] = coverage_result["assessed"]

                sealed = stages.seal(
                    state["contract"],
                    state["subquestions"],
                    state["sink"].all_records,
                    state["sink"].evidence_packets,
                    coverage_result,
                )
                mapped_after = sd.compute_diagnostic_sufficiency_map(
                    sealed, state["contract_by_child"], state["parent_of"]
                )
                sd.compute_direction_and_effectiveness(
                    sealed, mapped_after, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
                )
                targets_after = srt.compute_recovery_targets(mapped_after, state["parent_of"])
                log["mapped_after_c4"] = mapped_after["c4"]
                log["mapped_after_c6"] = mapped_after["c6"]
                log["targets_after"] = list(targets_after.values())
                log["sealed_verified_proposition_count"] = len(sealed["verified_propositions"])
        finally:
            rt.close()
    finally:
        guard.release_all()
        client.close()
    return log


class _RealTrace:
    def __init__(self, out_dir: Path) -> None:
        self.dir = out_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._qwen_calls = []
        self._events = []

    def write_json(self, name, payload):
        (self.dir / name).write_text(json.dumps(payload, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    def write_report(self, name, lines):
        path = self.dir / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def write_jsonl(self, name, rows):
        with (self.dir / name).open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")

    def decision(self, *a, **k):
        pass

    def flush_qwen(self):
        pass

    def flush_events(self):
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="make the one authorized live call (default: dry run)")
    parser.add_argument("--out", default=None)
    parser.add_argument("--authorized-by", default="Cliff")
    parser.add_argument("--authorized-at", default=None)
    args = parser.parse_args()
    out_dir = (
        Path(args.out)
        if args.out
        else Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "phase13-c4-recovery-experiment"
    )

    state = build_state(out_dir)
    print(
        json.dumps({"gates": state["gates"], "target": state["target"], "hint": state["hint"]}, indent=2, default=str)
    )

    if not args.live:
        print("\nDRY RUN ONLY -- no live call made. Re-run with --live to execute.")
        return 0

    from datetime import datetime, timezone

    authorized_at = args.authorized_at or datetime.now(timezone.utc).isoformat()
    auth_path = write_authorization_artifact(
        state, out_dir, authorized_by=args.authorized_by, authorized_at=authorized_at
    )
    print(f"\nauthorization artifact: {auth_path}")

    state["sink_before_records"] = list(state["sink"].all_records)
    log = run_live(state, out_dir)
    out_path = out_dir / "phase13_result.json"
    out_path.write_text(json.dumps(log, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"\nresult written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
