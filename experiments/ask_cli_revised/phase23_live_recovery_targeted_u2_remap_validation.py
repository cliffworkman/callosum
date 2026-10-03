"""Phase 23 -- ONE BOUNDED LIVE RECOVERY + EXACT-REQUEST U2 REMAP VALIDATION.

Authorized by Cliff Workman, 2026-10-02, after "Phase 22 accepted and CLOSED" (commit 2e8bb879).
This is an EMPIRICAL VALIDATION phase, not an implementation phase: exactly ONE live q_aib run
through the real, unmodified production `execute()` -- real W1/R1/C1 retrieval, a real recovery
round (W2/R2/C2), the real Phase-22 target-scoped U2 remap -- with NO retry and NO production code
change. Expected tracked production-code diff from starting HEAD (`2e8bb8795e3703fabf6b7cbf8dcb5721
f7562f6a`): ZERO.

**Profile choice, Cliff's own verbatim framing (must be preserved exactly, recorded again in the
authorization record and the results doc):**

    "Use T0 for Phase 23. The purpose of this one-shot experiment is to guarantee exercise of the
    recovery/remap mechanism, not to validate P. Treat legacy P as an explicit experimental
    qualification. Do not interpret the run as evidence about production model-driven planning. A
    later broader E2E gate should use T5/production P once recovery itself has been proven live."

T0's own W/R roles bind `kind="managed_local"`, which requires an installed local Qwen runtime this
machine does not have (`CALLOSUM_APP_DATA_DIR` unset; no `managed-local-ai/target.json` under either
real desktop app-data directory -- confirmed by direct inspection). Cliff's second, explicit
resolution (AskUserQuestion, "T0-shaped variant on JUNO (recommended)"): swap ONLY W/R to the same
`ollama`/`qwen3.5:9b`/`think=False` binding Phase 21's own T5 profile used against the authorized
isolated JUNO Ollama (`:11435`), keeping P="legacy" (so a SEARCH action is guaranteed to fire -- the
whole point of this run), C="det", S="off" unchanged from T0 itself:

    replace(topo.WAVE1["T0"], W=_ollama(_QWEN35, think=False), R=_ollama(_QWEN35, think=False))

Four disclosed, auditable departures from a literal `run_topology()`/CLI invocation (every other
component is the real, unmodified production object -- nothing here reimplements any mapper,
policy, or retrieval logic):

1. **Hierarchy content loaded via `hc.load_contract(question, pins=None)`, not
   `load_contract_for_live`** -- the same pre-existing, disclosed pin-drift bypass Phase 21 already
   used (`load_contract_for_live` currently raises on a code-input hash mismatch unrelated to the
   hierarchy's own reviewed content; re-freezing the pins is out of scope here).
2. **A custom profile variant** (above) is constructed directly as a `topo.Profile` dataclass and
   passed straight to `bind()`/`execute()` -- never routed through `topo.resolve_profile`'s own
   name-registry lookup, since this variant is not (and should not be) registered as a standing
   named profile for a one-shot experimental qualification.
3. **`execute()` is called directly, not through `run_topology()`.** `run_topology()`'s own
   `execute(...)` call site (`e2e.py` line ~1133) never threads `sufficiency_recovery_gate_enabled`
   at all -- confirmed by direct read, no CLI flag exists for it either -- so reaching Phase 22's
   production gate requires calling `execute()` directly. This script replicates `run_topology()`'s
   own pre-`execute()` setup sequence verbatim (`endpoints_used`, `require_models`, `build_runtime`,
   `bind`, `backends.ResidencyGuard`) rather than reimplementing any of it differently.
4. **`run_topology()`'s own `scored=True` path is not used, for a structural reason, not a
   convenience one:** `provenance.assert_clean()` refuses on ANY dirty path including an untracked
   file via `--untracked-files=all` -- and this harness script itself must exist, uncommitted, at
   the moment it runs (it cannot commit itself before it has been proven to work, and the brief
   forbids any retry once live). This script therefore runs its OWN explicit git-state check
   (`git status --porcelain`), mirroring Phase 21's own precedent exactly: ABORT unless the only
   dirty path in the tree is this harness file itself. This preserves the real safety property
   `assert_clean` protects (no uncommitted PRODUCTION code drift) without that property being
   vacuously unsatisfiable merely because a new one-shot script must be written to drive it.

`execute()`'s own return dict already carries everything this validation's audit needs
(`sealed`, `sufficiency_map_initial`, `sufficiency_map_final`, `sufficiency_recovery_targets`
[the POST-remap recomputation], `sufficiency_model_assist`, `stage_log`, `records_total`, ...) --
`recovery_targets_initial` (the BEFORE-recovery inventory) is the one value `execute()` computes
internally but does not return; it is recomputed post-hoc, read-only, from the written
`17_sufficiency_map.initial.json` trace artifact via the same pure
`sufficiency_recovery_targets.compute_recovery_targets` function `execute()` itself calls -- not a
reimplementation, a second call to the identical pure function on the identical inputs.

No `_CallLoggingOllamaClient`/call-classification wrapper is built: `execute()`'s own `stage_log`
(real `wall_seconds` per U1/W1/W2/U2 stage) and the "18_sufficiency_model_assist.json" trace
artifact (every real nomination receipt: scope, request_context, status, candidates_offered,
accepted) already give complete, PRODUCTION-GENERATED call accounting -- a parallel observability
wrapper would duplicate this and risk drifting from what the real run actually did.

Run once: `python -m experiments.ask_cli_revised.phase23_live_recovery_targeted_u2_remap_validation`
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from experiments.ask_cli_revised import backends, e2e, e2e_checks, library_copy
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_freeze as sf
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.runtime import build_runtime
from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient
from experiments.ask_cli_revised.trace import TraceWriter

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HEAD = "2e8bb8795e3703fabf6b7cbf8dcb5721f7562f6a"  # Phase 22 HEAD (this run's authorized baseline).
EXPECTED_V9_HASH = "9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586"
PRESERVED_T5C_DIR = ROOT / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930"
LIBRARY_COPY_PATH = PRESERVED_T5C_DIR / "library_copy.sqlite"
LIBRARY_FINGERPRINT_PATH = PRESERVED_T5C_DIR / "library_copy.sqlite.fingerprint.json"
HARNESS_RELATIVE_PATH = str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_default(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=lambda item: str(item))
    return str(obj)


def _t0_juno_profile() -> topo.Profile:
    """Cliff's exact approved variant (module docstring): T0 with W/R swapped to the isolated-JUNO
    ollama/qwen3.5:9b/think=False binding; P stays "legacy", C stays "det", S stays "off"."""
    base = topo.WAVE1["T0"]
    variant = replace(
        base,
        name="T0*J-phase23",
        W=topo._ollama(topo._QWEN35, think=False),
        R=topo._ollama(topo._QWEN35, think=False),
    )
    topo.validate(variant)
    return variant


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _git_dirty_paths() -> list[str]:
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True)
    return [line[3:] for line in status.splitlines() if line.strip()]


def _write_authorization(
    out_dir: Path, *, profile: topo.Profile, declared_scopes: list, head: str, v9_hash: str
) -> Path:
    record = {
        "phase": 23,
        "purpose": "ONE bounded live recovery + exact-request U2 remap validation",
        "experiment_id": "q_aib_phase23_live_recovery_targeted_u2_remap_validation_20261002",
        "authorized_by": "Cliff Workman",
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "brief_confirmed": True,
        "question": "aib",
        "question_sha256s": [_sha256_text(BENCHMARK_QUESTION)],
        "authorized_head": head,
        "v9_combined_hash": v9_hash,
        "profile_name": profile.name,
        "profile_source": "T0 with W/R swapped to isolated-JUNO ollama/qwen3.5:9b/think=False; P=legacy, C=det, S=off",
        "model_name": profile.W.model,
        "think": profile.W.think,
        "endpoint": topo.ENDPOINTS[profile.W.endpoint],
        "profile_choice_framing_verbatim": (
            "Use T0 for Phase 23. The purpose of this one-shot experiment is to guarantee exercise "
            "of the recovery/remap mechanism, not to validate P. Treat legacy P as an explicit "
            "experimental qualification. Do not interpret the run as evidence about production "
            "model-driven planning. A later broader E2E gate should use T5/production P once "
            "recovery itself has been proven live."
        ),
        "sufficiency_model_assist_enabled": True,
        "sufficiency_recovery_gate_enabled": True,
        "one_run_no_retry": True,
        "one_recovery_round": True,
        "declared_semantic_scopes_count": len(declared_scopes),
        "declared_semantic_scopes": [list(s) for s in declared_scopes],
        "declared_scope_ceiling_note": (
            "This is the mechanically-knowable UPPER BOUND on authorization-scope level requests "
            "before any live call (mscope.enumerate_model_nomination_scopes against the frozen v9 "
            "contract). Unlike Phase 21, the REACHED/nonempty/physical U1 and U2 call counts cannot "
            "be pre-derived this time: U1 runs over a sealed ledger that does not exist until this "
            "SAME live run's own W1/R1/C1 round has completed, and U2's own fresh-request set F is "
            "a function of the recovery round's real search results, which also do not exist until "
            "this same live run's W2/R2/C2 round has completed. Both counts are therefore honestly "
            "reported post-hoc in the results document, never pre-declared as a ceiling here."
        ),
        "recovery_gate_note": (
            "sufficiency_recovery_gate_enabled=True is the ONE production flag run_topology() "
            "cannot express (confirmed by direct read of its own execute() call site) -- this is "
            "why execute() is called directly rather than through run_topology(); every other "
            "component reused is the real, unmodified production object."
        ),
        "departures_from_literal_cli_path": [
            "hierarchy loaded via hc.load_contract(question, pins=None), not load_contract_for_live (pre-existing pin-drift bypass)",
            "a custom Profile variant constructed directly, not resolved via topo.resolve_profile's name registry",
            "execute() called directly (replicating run_topology()'s own pre-execute setup verbatim), not through run_topology()",
            "run_topology()'s scored=True path is not used; this script runs its own equivalent dirty-tree check excluding only this harness file",
        ],
        "library_copy_path": str(LIBRARY_COPY_PATH.relative_to(ROOT)),
        "library_fingerprint_path": str(LIBRARY_FINGERPRINT_PATH.relative_to(ROOT)),
    }
    path = out_dir / "phase23_authorization.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    head = _git_head()
    if head != EXPECTED_HEAD:
        print(f"[phase23] ABORT: HEAD is {head}, expected {EXPECTED_HEAD}")
        return 2
    dirty = _git_dirty_paths()
    unexpected_dirty = [p for p in dirty if p.strip() != HARNESS_RELATIVE_PATH]
    if unexpected_dirty:
        print("[phase23] ABORT: working tree has unexpected changes beyond the harness itself")
        print("\n".join(unexpected_dirty))
        return 2

    contract_by_child = sf.load_verified()  # raises SufficiencyContractRejected if unverifiable
    if contract_by_child is None:
        print("[phase23] ABORT: no verified sufficiency contract found")
        return 2
    frozen = json.loads(sf.FROZEN_PATH.read_text(encoding="utf-8"))
    if frozen["combined_hash"] != EXPECTED_V9_HASH:
        print(f"[phase23] ABORT: v9 combined_hash is {frozen['combined_hash']}, expected {EXPECTED_V9_HASH}")
        return 2

    if not LIBRARY_COPY_PATH.is_file():
        print(f"[phase23] ABORT: library copy not found at {LIBRARY_COPY_PATH}")
        return 2
    if not LIBRARY_FINGERPRINT_PATH.is_file():
        print(f"[phase23] ABORT: library fingerprint not found at {LIBRARY_FINGERPRINT_PATH}")
        return 2
    try:
        library_before = library_copy.verify(LIBRARY_COPY_PATH, LIBRARY_FINGERPRINT_PATH)
    except library_copy.LibraryCopyDrift as exc:
        print(f"[phase23] ABORT: library copy has drifted from its frozen fingerprint: {exc}")
        return 2

    profile = _t0_juno_profile()
    if profile.W.think is not False:
        print(f"[phase23] ABORT: profile W.think is {profile.W.think!r}, not False")
        return 2
    if profile.W.model != topo._QWEN35:
        print(f"[phase23] ABORT: profile W.model is {profile.W.model!r}, expected {topo._QWEN35!r}")
        return 2
    if profile.P.kind != "legacy":
        print(f"[phase23] ABORT: profile P.kind is {profile.P.kind!r}, expected 'legacy'")
        return 2

    declared_scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)
    print(f"[phase23] declared semantic scopes (upper bound, pre-live): {len(declared_scopes)}")

    run_id = f"phase23-live-recovery-targeted-u2-remap-validation-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    out_dir = ROOT / ".local" / "e2e-runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=False)

    auth_path = _write_authorization(
        out_dir, profile=profile, declared_scopes=declared_scopes, head=head, v9_hash=frozen["combined_hash"]
    )
    print(f"[phase23] authorization written: {auth_path} sha256={_sha256_file(auth_path)}")

    # Reuse the real, standing experiment gate (EXPERIMENT_GATE.md) exactly as run_topology() would.
    hc.check_authorization(str(auth_path), BENCHMARK_QUESTION)

    hier_contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)  # module docstring, departure #1
    sufficiency_parent_of = hc.parent_of(hier_contract)
    hc.assert_executable(hier_contract)

    trace_dir = out_dir / "run"
    trace = TraceWriter(trace_dir)

    endpoints = e2e.endpoints_used(profile)
    print(f"[phase23] endpoints used: {endpoints}")
    clients = {endpoint: OllamaClient(topo.ENDPOINTS[endpoint]) for endpoint in endpoints}

    def close_clients() -> None:
        for client in clients.values():
            try:
                client.close()
            except Exception:  # noqa: BLE001 - teardown must never mask the real result
                pass

    try:
        digests = e2e.require_models(clients, profile)
    except Exception as exc:
        close_clients()
        print(f"[phase23] ABORT: required model(s) not available: {exc}")
        return 2
    print(f"[phase23] required-model digests confirmed: {digests}")

    needs_qwen = any(getattr(profile, role).kind == "managed_local" for role in e2e._roles(profile))
    rt = build_runtime(LIBRARY_COPY_PATH, want_verifier=True, want_qwen=needs_qwen)
    guard = backends.ResidencyGuard(clients)

    result = None
    started = time.monotonic()
    try:
        bound = e2e.bind(profile, rt=rt, clients=clients, trace=trace, managed_chat=lambda c: None)
        print("[phase23] >>> LIVE RUN BEGINS (no retry) <<<")
        result = e2e.execute(
            rt=rt,
            profile=profile,
            contract=hier_contract,
            trace=trace,
            guard=guard,
            bound=bound,
            entail=None,  # S is "off" for this profile; execute() only requires entail when S is bound
            sufficiency_contract=contract_by_child,
            sufficiency_parent_of=sufficiency_parent_of,
            sufficiency_model_assist_enabled=True,
            sufficiency_recovery_gate_enabled=True,
        )
        print("[phase23] LIVE RUN COMPLETE")
    finally:
        try:
            guard.release_all()
        except Exception:  # noqa: BLE001 - teardown must never mask the real result
            pass
        close_clients()
        rt.close()
    elapsed = round(time.monotonic() - started, 1)

    try:
        library_after = library_copy.verify(LIBRARY_COPY_PATH, LIBRARY_FINGERPRINT_PATH)
    except library_copy.LibraryCopyDrift as exc:
        library_after = None
        print(f"[phase23] WARNING: library copy drifted during the run: {exc}")

    report = e2e_checks.mechanical_report(trace.dir, profile=profile, question_key=hc.HIER_QUESTION_KEY)
    trace.write_json("16_mechanical_checks.json", report)

    # Post-hoc, read-only recomputation of the BEFORE-recovery inventory: execute() computes this
    # internally but does not return it. Same pure function, same inputs (sufficiency_map_initial),
    # not a reimplementation.
    recovery_targets_initial = (
        srt.compute_recovery_targets(result["sufficiency_map_initial"], sufficiency_parent_of)
        if result["sufficiency_map_initial"] is not None
        else {}
    )

    # Independent audit cross-check of F (Phase 22's own fresh-request projection), recomputed
    # read-only from the trace artifacts this run already wrote -- never re-authorizing anything,
    # never a second live call.
    sealed = result["sealed"]
    initial_u1_receipts = {}  # read back from the trace artifact, not a live object reference
    assist_path = trace.dir / "18_sufficiency_model_assist.json"
    projected_f: list = []
    if assist_path.is_file() and result["sufficiency_map_initial"] is not None and recovery_targets_initial:
        assist = json.loads(assist_path.read_text(encoding="utf-8"))
        initial_u1_receipts = {(tuple(r["scope"]), r["request_context"]): r for r in assist["initial"]}
        post_recovery_keys = e2e._sufficiency_post_recovery_request_inventory(
            sealed, contract_by_child, sufficiency_parent_of
        )
        initial_keys = frozenset(initial_u1_receipts.keys())
        projected_f = sorted(
            srt.project_fresh_request_keys(
                recovery_targets_initial,
                contract_by_child,
                result["sufficiency_map_initial"],
                initial_keys,
                post_recovery_keys,
            ),
            key=lambda k: str(k),
        )

    summary = {
        "run_id": run_id,
        "head": head,
        "v9_combined_hash": frozen["combined_hash"],
        "model_name": profile.W.model,
        "think": profile.W.think,
        "endpoint": topo.ENDPOINTS[profile.W.endpoint],
        "profile": {
            "name": profile.name,
            "W": profile.W.kind,
            "R": profile.R.kind,
            "C": profile.C.kind,
            "P": profile.P.kind,
            "S": profile.S.kind,
        },
        "elapsed_seconds": elapsed,
        "declared_semantic_scopes_count": len(declared_scopes),
        "library_unchanged_after_run": library_after == library_before,
        "stage_log": result["stage_log"],
        "skipped": result["skipped"],
        "recovery_plan": result["recovery_plan"],
        "recovery_log": result["recovery_log"],
        "records_total": result["records_total"],
        "verified_claims": len(sealed["verified_propositions"]),
        "sealed_hash": result["sealed_hash"],
        "recovery_targets_initial_count": len(recovery_targets_initial),
        "recovery_targets_initial": recovery_targets_initial,
        "recovery_targets_final_count": len(result["sufficiency_recovery_targets"]),
        "recovery_targets_final": result["sufficiency_recovery_targets"],
        "sufficiency_map_initial": result["sufficiency_map_initial"],
        "sufficiency_map_final": result["sufficiency_map_final"],
        "sufficiency_model_assist": result["sufficiency_model_assist"],
        "projected_fresh_request_keys_f": [[list(k[0]), k[1]] for k in projected_f],
        "projected_fresh_request_keys_f_count": len(projected_f),
        "mechanical_checks": {name: check["ok"] for name, check in report["checks"].items()},
        "gate_no_answer": report["no_answer"]["gate"],
        "technical_validity_issues": report["technical_validity"]["issues"],
    }
    result_path = out_dir / "phase23_result.json"
    result_path.write_text(json.dumps(summary, indent=2, default=_json_default, sort_keys=True), encoding="utf-8")
    print(f"[phase23] result written: {result_path}")
    print(f"[phase23] out_dir: {out_dir}")
    print(f"[phase23] stage_log: {[s['stage'] for s in result['stage_log']]}")
    print(f"[phase23] skipped: {[s['stage'] for s in result['skipped']]}")
    print(
        f"[phase23] recovery_targets_initial: {len(recovery_targets_initial)}; recovery_targets_final: {len(result['sufficiency_recovery_targets'])}"
    )
    if result["sufficiency_model_assist"]:
        print(f"[phase23] U1 by_status: {result['sufficiency_model_assist']['initial']['by_status']}")
        print(f"[phase23] U2 by_status: {result['sufficiency_model_assist']['final']['by_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
