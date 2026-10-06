"""Phase 21 -- ONE bounded, production-shaped LIVE initial model-assisted sufficiency validation.

Restarted (Cliff Workman, 2026-10-02, pasted-content-id-d898) from a corrected, full-contract state
after the Phase-21 preflight's own dry run found a real Phase-19 request-multiplicity gap on real
c12 and Phase 19b (commit 23a7f164) repaired it. Authorized scope: exactly one live q_aib run of
the Phase-20b production U1 path, now running through Phase 19b's corrected composite
(scope, request_context) identity -- real reviewed hierarchy content, the real frozen+reviewed v9
sufficiency contract, real sealed evidence, the real `bound.qwen` client against the real
isolated/JUNO Ollama endpoint, the real Phase-19/19b `ALL_ELIGIBLE` nomination context, and the real
`compute_diagnostic_sufficiency_map`/`compute_direction_and_effectiveness` functions `execute()`
itself calls -- NOT a parallel reimplementation of the mapper. A held-fixed U2 pass is exercised
directly afterward (the same `exact_scope_set_policy(set())` policy Phase 20b built), proving it
makes zero additional physical calls, exactly mirroring what `execute()` would do if a recovery
round triggered a final remap.

**The fresh-call cap is mechanically re-derived for this restart, not reused from the original
Phase-21 attempt's stale count.** Phase 19's own exhaustive count of 15 *declared* semantic scopes
(`enumerate_model_nomination_scopes`) is an upper bound on scope-level authorization, not on
Phase-19b's own composite-key physical-call count -- `build_multi_instances` can split one declared
scope into several real `request_context`-keyed call slots (c12: 2 roles x 2 real units = 4 slots
from 2 declared scopes), while a declared scope with zero real candidate units in this evidence
costs zero slots. Running the real, unmodified `compute_diagnostic_sufficiency_map` once, offline,
against the real frozen v9 contract and the real preserved sealed evidence with a counting-only
fake client (never asserting a real nomination, just recording call shape/count) mechanically
derived **14** nonempty, `fresh`-status composite request keys for this exact evidence -- see
`PHASE21_LIVE_INITIAL_MODEL_ASSIST_VALIDATION_RESULTS.md` §5 for the full derivation and the
per-key breakdown (c9's and c11's declared scopes are never reached at all against this real
evidence; c8 reaches one real partitioned context). `MAX_FRESH_CALLS` below is this derived value,
not the stale scope-level count.

Two deliberate, disclosed departures from the full `run_topology()`/`main()` CLI path, both because
a hierarchical run structurally forbids seeding/slicing (`execute()` itself raises if asked):

1. **Hierarchy content is loaded via `hc.load_contract(question, pins=None)`, not
   `load_contract_for_live`.** `load_contract_for_live()` is confirmed, by actually calling it,
   to currently raise `HierarchyRejected(["pin drift: code input hierarchy_contract.py changed
   since the pins were generated"])` -- a pre-existing, disclosed drift (the hierarchy pins were
   last regenerated before Phase 20a's own `parent_of()` addition to that same file changed its
   tracked code-input hash; every prior live diagnostic in this lineage, per the Phase-20 audit,
   already used the `pins=None` structural-only loader for this same reason). Re-freezing the
   pins or reverting the code change are both explicitly out of scope for this phase. The
   STRUCTURAL content loaded is verified identical to the one genuinely-reviewed prior live run
   below (byte-identical `question_hash` and hierarchy `integrity_sha256`).
2. **Real sealed evidence is the PRESERVED ledger from a genuine prior live run
   (`.local/e2e-runs/q-aib-hierarchical-t5c-live-20260930/run/11_verified_ledger.json`), not a
   freshly-retrieved one.** Confirmed, before using it, to be byte-identical in `question_hash`
   and hierarchy `integrity_sha256` to the hierarchy loaded above -- the SAME real hierarchy, same
   question, same 11 children, 26 real verified propositions. A hierarchical `execute()` call
   cannot be seeded (`seed_pass`/`smoke_limits` are both refused for `hierarchy=True`), so this
   script reads the file directly and calls the exact same two production functions `execute()`
   itself would call on it. This also keeps the live footprint of this run EXCLUSIVELY to
   sufficiency nomination -- no fresh W1/R/C/P model calls, which are unrelated to what Phase 21
   validates and were already live-tested in the run this ledger is drawn from.

Every other component is the real, unmodified production object: `hierarchy_contract.parent_of`,
`sufficiency_freeze.load_verified`, `e2e.bind`, `e2e._sufficiency_u1_context`,
`sufficiency_model_scope.new_nomination_context`/`exact_scope_set_policy`,
`sufficiency_diagnostic.compute_diagnostic_sufficiency_map`/`compute_direction_and_effectiveness`,
`sufficiency_recovery_targets.compute_recovery_targets`, `backends.NativeWorker`, `qwen.QwenTasks`,
`supervisor_eval.ollama_client.OllamaClient`, `trace.TraceWriter`. Nothing here reimplements any of
them. The only new code is this orchestration script and `_CallCountGuard` (a pure pass-through
safety wrapper enforcing the authorized hard call cap -- it changes no behavior at or under the
cap).

Run once: `python -m experiments.ask_cli_revised.phase21_live_initial_model_assist_validation`
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from experiments.ask_cli_revised import e2e
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_freeze as sf
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient
from experiments.ask_cli_revised.trace import TraceWriter

ROOT = Path(__file__).resolve().parents[2]
PRESERVED_LEDGER = (
    ROOT / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run" / "11_verified_ledger.json"
)
EXPECTED_HEAD = "23a7f164c132e4aa060ee2d499c1e7dc28255297"  # Phase 19b HEAD (this restart's baseline)
PHASE_19B_COMMIT = "23a7f164c132e4aa060ee2d499c1e7dc28255297"
PHASE_20A_COMMIT = "b928d1406e928863b034d4ff4c62885a4f6dd124"
PHASE_20B_COMMIT = "304ad5ad99475f76d91e109164d7cff933b30ff4"
MAX_FRESH_CALLS = 14  # mechanically re-derived under Phase 19b's composite key -- see module docstring.
PROFILE_NAME = "T5"  # same W binding (qwen3.5:9b, isolated, think=False) as the preserved live run.


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_default(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    return str(obj)


class _CapDerivationClient:
    """Candidate-construction-only, never-live counting fake: used ONLY to mechanically derive the
    U1 fresh-call cap before any live call, per the Phase-21-restart brief's explicit requirement
    (section 5). Never asserts a real nomination -- always returns `[]` -- so it affects no
    scientific content, only lets the real, unmodified `compute_diagnostic_sufficiency_map` record
    exactly which composite (scope, request_context) keys would need a physical call."""

    model_name = "phase21-offline-cap-derivation-never-live"

    def __init__(self):
        self.calls: list[dict] = []

    def nominate_sufficiency_role(self, *, category_description, candidates):
        self.calls.append({"category_description": category_description, "n_candidates": len(candidates)})
        return []


def _derive_u1_call_cap(sealed, contract_by_child, parent_of) -> tuple[int, list, dict]:
    """Returns `(derived_cap, declared_scopes, receipts_by_status)`. `derived_cap` is the exact
    count of composite request keys that reached `status == "fresh"` (i.e. would make a real
    physical call) when the real `compute_diagnostic_sufficiency_map` is run, offline, against the
    real v9 contract and real preserved sealed evidence with `_CapDerivationClient`. This is the
    brief's own required "mechanically derive... using candidate construction only" step, run fresh
    in this same process immediately before authorization is written -- never a value merely copied
    from an earlier exploratory run."""
    declared_scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)
    client = _CapDerivationClient()
    ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
    sd.compute_diagnostic_sufficiency_map(
        sealed,
        contract_by_child,
        parent_of,
        model_client=client,
        nomination_context=ctx,
        semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION,
    )
    by_status: dict[str, list] = {}
    for key, receipt in ctx["in_pass_receipts"].items():
        by_status.setdefault(receipt["status"], []).append(key)
    derived_cap = len(client.calls)
    assert derived_cap == len(by_status.get("fresh", [])), "derivation accounting internally inconsistent"
    return derived_cap, declared_scopes, by_status


class _CallCountGuard:
    """Phase 21's own authorized hard cap (section 5): aborts BEFORE a call beyond `max_calls`.
    Pure pass-through below the cap -- delegates `model_name` and the one method Phase-19's own
    `make_fresh_call` lambda invokes, changing no behavior, adding only per-call timing capture
    for the latency report and a running log for the accounting report."""

    def __init__(self, inner, max_calls: int):
        self._inner = inner
        self._max_calls = max_calls
        self.call_log: list[dict] = []

    @property
    def model_name(self):
        return self._inner.model_name

    def nominate_sufficiency_role(self, *, category_description, candidates):
        attempt = len(self.call_log) + 1
        if attempt > self._max_calls:
            raise RuntimeError(
                f"Phase 21 hard cap exceeded: attempted fresh nomination call #{attempt} > "
                f"authorized maximum {self._max_calls} -- aborting, this is an invariant failure"
            )
        started = time.monotonic()
        result = self._inner.nominate_sufficiency_role(category_description=category_description, candidates=candidates)
        elapsed = round(time.monotonic() - started, 3)
        self.call_log.append(
            {
                "call_number": attempt,
                "category_description": category_description,
                "n_candidates_offered": len(candidates),
                "n_accepted": len(result),
                "elapsed_seconds": elapsed,
            }
        )
        return result


def _write_authorization(
    out_dir: Path,
    *,
    contract_hash: str,
    model_name: str,
    think,
    head: str,
    declared_scopes: list,
    derived_nonempty_keys: list,
) -> Path:
    record = {
        "phase": 21,
        "restart": True,
        "purpose": "bounded production-shaped live U1 sufficiency-nomination validation",
        "experiment_id": "q_aib_phase21_live_u1_model_assist_validation_20261002_restart",
        "authorized_by": "Cliff Workman",
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "brief_confirmed": True,
        "question": "aib",
        "question_sha256s": [_sha256_text(BENCHMARK_QUESTION)],
        "head": head,
        "phase_19b_commit": PHASE_19B_COMMIT,
        "phase_20a_commit": PHASE_20A_COMMIT,
        "phase_20b_commit": PHASE_20B_COMMIT,
        "v9_combined_hash": contract_hash,
        "profile": PROFILE_NAME,
        "model_name": model_name,
        "think": think,
        "feature_flag": "sufficiency_model_assist_enabled=True (direct production function call)",
        "sufficiency_recovery_gate": "OFF (not exercised in this phase)",
        "u1_policy": "all_eligible_policy()",
        "u2_policy": "exact_scope_set_policy(set()) with U1 receipts as prior_receipts (held fixed)",
        "declared_semantic_scopes_count": len(declared_scopes),
        "declared_semantic_scopes": [list(s) for s in declared_scopes],
        "derived_nonempty_request_keys_count": len(derived_nonempty_keys),
        "derived_nonempty_request_keys": [[list(k[0]), k[1]] for k in derived_nonempty_keys],
        "max_fresh_u1_calls": MAX_FRESH_CALLS,
        "max_fresh_u1_calls_derivation": (
            "mechanically derived offline (candidate construction only, no live call) by running "
            "the real compute_diagnostic_sufficiency_map against the real frozen v9 contract and "
            "the real preserved sealed evidence with a counting-only fake client; NOT the stale "
            "Phase-19 declared-scope count of 15, which Phase 19b's composite (scope, "
            "request_context) key makes an incorrect upper bound on physical calls"
        ),
        "max_fresh_u2_calls": 0,
        "no_retry": True,
        "scope_note": (
            "Hierarchy content loaded via pins=None (disclosed pin-drift bypass, not a review "
            "bypass of the sufficiency contract itself, which IS fully hash+review verified). Real "
            "sealed evidence reused from the preserved 2026-09-30 T5C live run's own verified "
            "ledger (confirmed byte-identical question_hash/hierarchy integrity to the hierarchy "
            "loaded for this run) rather than freshly retrieved, since a hierarchical execute() "
            "cannot be seeded and this keeps the live footprint exclusively to nomination."
        ),
        "preserved_ledger_path": str(PRESERVED_LEDGER.relative_to(ROOT)),
        "preserved_ledger_sha256": _sha256_file(PRESERVED_LEDGER),
    }
    path = out_dir / "phase21_authorization.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    import subprocess

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != EXPECTED_HEAD:
        print(f"[phase21] ABORT: HEAD is {head}, expected {EXPECTED_HEAD}")
        return 2
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    harness_path = str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/")
    unexpected_dirty = [line for line in dirty.splitlines() if line.strip() and not line.strip().endswith(harness_path)]
    if unexpected_dirty:
        print("[phase21] ABORT: working tree has unexpected changes beyond the harness itself")
        print("\n".join(unexpected_dirty))
        return 2

    contract_by_child = sf.load_verified()  # raises SufficiencyContractRejected if unverifiable
    if contract_by_child is None:
        print("[phase21] ABORT: no verified sufficiency contract found")
        return 2
    frozen = json.loads(sf.FROZEN_PATH.read_text(encoding="utf-8"))
    if frozen["combined_hash"] != "9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586":
        print(f"[phase21] ABORT: v9 combined_hash is {frozen['combined_hash']}, expected the frozen value")
        return 2

    contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)  # see module docstring §1
    parent_of = hc.parent_of(contract)

    if not PRESERVED_LEDGER.is_file():
        print(f"[phase21] ABORT: preserved ledger not found at {PRESERVED_LEDGER}")
        return 2
    sealed = json.loads(PRESERVED_LEDGER.read_text(encoding="utf-8"))
    if sealed["request_contract"]["question_hash"] != contract["question_hash"]:
        print("[phase21] ABORT: preserved ledger question_hash does not match the loaded hierarchy")
        return 2
    if sealed["request_contract"]["hierarchy"]["integrity_sha256"] != contract["hierarchy"]["integrity_sha256"]:
        print("[phase21] ABORT: preserved ledger hierarchy integrity does not match the loaded hierarchy")
        return 2

    # Section 5/0: mechanically derive the U1 fresh-call cap BEFORE any live call, using candidate
    # construction only (a counting-only fake client, never network, never a real nomination).
    derived_cap, declared_scopes, by_status = _derive_u1_call_cap(sealed, contract_by_child, parent_of)
    print(f"[phase21] declared semantic scopes: {len(declared_scopes)}")
    for status, keys in sorted(by_status.items()):
        print(f"[phase21] derivation status={status}: {len(keys)}")
    print(f"[phase21] mechanically derived U1 fresh-call cap: {derived_cap}")
    if derived_cap != MAX_FRESH_CALLS:
        print(
            f"[phase21] ABORT: freshly-derived cap ({derived_cap}) disagrees with this restart's "
            f"recorded expectation ({MAX_FRESH_CALLS}) -- something about the contract or preserved "
            "evidence has changed since that expectation was computed; investigate before proceeding"
        )
        return 2
    nonempty_keys = by_status.get("fresh", [])

    profile = topo.WAVE1[PROFILE_NAME]
    if profile.W.think is not False:
        print(f"[phase21] ABORT: profile {PROFILE_NAME} W.think is {profile.W.think!r}, not False")
        return 2
    if profile.W.model != "qwen3.5:9b":
        print(f"[phase21] ABORT: profile {PROFILE_NAME} W.model is {profile.W.model!r}, expected qwen3.5:9b")
        return 2

    run_id = f"phase21-live-initial-model-assist-validation-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    out_dir = ROOT / ".local" / "e2e-runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    trace = TraceWriter(out_dir / "run")

    client = OllamaClient(topo.ENDPOINTS[profile.W.endpoint])
    try:
        tags = {m.get("name") or m.get("model") for m in client.tags()}
        if profile.W.model not in tags and f"{profile.W.model}:latest" not in tags:
            print(f"[phase21] ABORT: {profile.W.model} not listed on {topo.ENDPOINTS[profile.W.endpoint]}")
            return 2

        auth_path = _write_authorization(
            out_dir,
            contract_hash=frozen["combined_hash"],
            model_name=profile.W.model,
            think=profile.W.think,
            head=head,
            declared_scopes=declared_scopes,
            derived_nonempty_keys=nonempty_keys,
        )
        print(f"[phase21] authorization written: {auth_path} sha256={_sha256_file(auth_path)}")

        bound = e2e.bind(
            profile, rt=None, clients={profile.W.endpoint: client}, trace=trace, managed_chat=lambda c: None
        )
        guarded = _CallCountGuard(bound.qwen, MAX_FRESH_CALLS)
        bound = e2e.Bound(qwen=guarded, supervisors=bound.supervisors)

        print("[phase21] >>> LIVE RUN BEGINS (no retry) <<<")
        started_u1 = time.monotonic()
        model_client, u1_context = e2e._sufficiency_u1_context(profile, bound)
        sufficiency_map_initial = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contract_by_child,
            parent_of,
            model_client=model_client,
            nomination_context=u1_context,
            semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION,
        )
        sd.compute_direction_and_effectiveness(
            sealed, sufficiency_map_initial, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
        u1_wall_seconds = round(time.monotonic() - started_u1, 3)
        u1_call_count_after = len(guarded.call_log)
        print(f"[phase21] U1 complete: {u1_call_count_after} physical calls, {u1_wall_seconds}s wall")

        u1_receipts_snapshot = dict(u1_context["in_pass_receipts"])
        u2_context = mscope.new_nomination_context(
            mscope.exact_scope_set_policy(set()), prior_receipts=u1_receipts_snapshot
        )
        started_u2 = time.monotonic()
        sufficiency_map_final = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contract_by_child,
            parent_of,
            model_client=model_client,
            nomination_context=u2_context,
            semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION,
        )
        sd.compute_direction_and_effectiveness(
            sealed, sufficiency_map_final, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
        u2_wall_seconds = round(time.monotonic() - started_u2, 3)
        u2_call_count_after = len(guarded.call_log)
        print(
            f"[phase21] U2 complete: {u2_call_count_after - u1_call_count_after} additional physical calls (must be 0)"
        )

        recovery_targets = srt.compute_recovery_targets(
            sufficiency_map_final, parent_of, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
    finally:
        client.close()
        trace.flush_qwen()
        trace.flush_events()

    u1_status_counts: dict[str, int] = {}
    for receipt in u1_context["in_pass_receipts"].values():
        u1_status_counts[receipt["status"]] = u1_status_counts.get(receipt["status"], 0) + 1
    u2_status_counts: dict[str, int] = {}
    for receipt in u2_context["in_pass_receipts"].values():
        u2_status_counts[receipt["status"]] = u2_status_counts.get(receipt["status"], 0) + 1

    result = {
        "run_id": run_id,
        "head": head,
        "v9_combined_hash": frozen["combined_hash"],
        "model_name": profile.W.model,
        "think": profile.W.think,
        "endpoint": topo.ENDPOINTS[profile.W.endpoint],
        "declared_semantic_scopes_count": len(declared_scopes),
        "derived_nonempty_request_keys_count": derived_cap,
        "u1": {
            "wall_seconds": u1_wall_seconds,
            "physical_calls": u1_call_count_after,
            "status_counts": u1_status_counts,
            "call_log": guarded.call_log[:u1_call_count_after],
            "receipts": {str(k): v for k, v in u1_context["in_pass_receipts"].items()},
        },
        "u2": {
            "wall_seconds": u2_wall_seconds,
            "physical_calls_delta": u2_call_count_after - u1_call_count_after,
            "status_counts": u2_status_counts,
            "receipts": {str(k): v for k, v in u2_context["in_pass_receipts"].items()},
        },
        "sufficiency_map_initial": sufficiency_map_initial,
        "sufficiency_map_final": sufficiency_map_final,
        "recovery_targets": recovery_targets,
    }
    result_path = out_dir / "phase21_result.json"
    result_path.write_text(json.dumps(result, indent=2, default=_json_default, sort_keys=True), encoding="utf-8")
    print(f"[phase21] result written: {result_path}")
    print(f"[phase21] out_dir: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
