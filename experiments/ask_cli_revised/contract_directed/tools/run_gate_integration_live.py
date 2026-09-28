"""EXACTLY ONE bounded live c9+c11 partial-pipeline integration run (2026-09-28 authorization).

Cliff authorized exactly one fresh Qwen S-role overview call against the frozen c9+c11 Gate 1
evidence/coverage manifest, followed by the existing local-NLI screening and deterministic
partial-answer rendering. This is NOT a fresh eleven-child E2E run and NOT new Gate 1 evidence
discovery -- it projects `gate1_evidence_fixture.build_c9_c11_manifest()` (unchanged since
`b523fb9a`) through the existing `overview_bridge` / `overview.build_overview` / `gate_integration`
seam via `gate_integration.build_live_integration_receipt` -- never a second renderer, never a
duplicated overview implementation, and it never touches `e2e.py`.

**The new run never reads `runs/gate2-diagnostic-002/04_final_record.json`.** That prior saved
record is a comparison artifact only, named below but never opened; this script's rendering input
is always the fresh record this run's own live call produces, held in memory and then written to
THIS run's own `00_integration_receipt.json` / `04_final_record.json` -- different, run-scoped paths.

Preflight, entirely offline, in this order (Section 3 of the authorization):
  1. worktree/commit identity, frozen input hashes, the exact 4 manifest rows (c9/M10, c9/W21,
     c11/M12, c11/M13), the W21 coverage-constraint text, and that the real frozen parent question
     (and every coverage constraint) appears verbatim in the actual rendered prompt -- using the
     SAME `overview.select_for_prompt` / `render_prompt` that `build_overview` itself calls.
  2. `on_prompt_ready` / `on_raw_response` wiring at the committed call boundaries: a disposable
     rehearsal directory proves THIS run's own real prompt+manifest round-trips through
     `DiagnosticTrace` byte-for-byte before the real run directory (or any model call) exists.
  3. the integrated driver's own offline test coverage
     (`test_gate_integration.py::RunLiveOverviewCallTests`, which exercises the actual
     `run_live_overview_call` / `build_live_integration_receipt` functions with a scripted client,
     not just `overview.build_overview` in isolation) must be green, checked here by re-running
     that module and refusing to proceed otherwise.
  4. the worktree must be clean (no uncommitted changes) -- refuses a scored run from a dirty tree,
     exactly like `run.py`'s own `live` command.

If ANY offline check fails, this script exits non-zero before touching the network. If every check
passes, it makes AT MOST ONE call: the isolated Ollama endpoint (127.0.0.1:11435) is version/digest
pre-checked (must match `freeze.OLLAMA_VERSION` / `freeze.MODEL_DIGEST` exactly, refusing otherwise),
then `gate_integration.build_live_integration_receipt` is invoked exactly once, through a real
`stages.Supervisor` bound to `topology.OVERVIEW_PROFILES["T5O"].S` with `topology.OVERVIEW_S_OPTIONS`
(thinking ON) and the real local NLI support scorer from `runtime.build_runtime`. There is no retry,
no fallback, no parameter change, and no second call under any circumstance -- a timeout, a
mechanical failure, or a downstream exception all end the run, with whatever was written before the
failure left in place and this script exiting non-zero rather than claiming success.

    python -m experiments.ask_cli_revised.contract_directed.tools.run_gate_integration_live [--run-id ID]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import psutil

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from experiments.ask_cli_revised import overview as ov  # noqa: E402
from experiments.ask_cli_revised import overview_evidence as oe  # noqa: E402
from experiments.ask_cli_revised import runtime as ask_runtime  # noqa: E402
from experiments.ask_cli_revised import stages  # noqa: E402
from experiments.ask_cli_revised import topology as topo  # noqa: E402
from experiments.ask_cli_revised.contract_directed import (
    endpoint_guard,  # noqa: E402
    freeze,  # noqa: E402
    gate2_trace,  # noqa: E402
)
from experiments.ask_cli_revised.contract_directed import gate1_evidence_fixture as fixture  # noqa: E402
from experiments.ask_cli_revised.contract_directed import gate_integration as integration  # noqa: E402
from experiments.ask_cli_revised.contract_directed import model_stages as ms  # noqa: E402
from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge  # noqa: E402

REPO = Path(r"C:\Users\cliff\callosum-worktrees\ask-contract-directed")
DB = freeze.SLICE_ROOT / "library.sqlite"
RUNS_ROOT = freeze.SLICE_ROOT / "runs"
# Named for provenance/comparison only. This path is NEVER opened anywhere in this script.
COMPARISON_ONLY_PRIOR_RECORD = str(RUNS_ROOT / "gate2-diagnostic-002" / "04_final_record.json")
# The local process loads the embedding + NLI models (runtime.build_runtime); the isolated Ollama server
# (same machine, a separate process) needs its own headroom to load Qwen3.5:9b if not already resident. A
# prior background run on this machine was killed by the harness for system-wide memory pressure -- this
# floor exists so a live call is never attempted into that same condition. It does not know the isolated
# Ollama process's own footprint or residency state; that is checked separately, only after this passes,
# via a real /api/ps call inside main().
MIN_AVAILABLE_MEMORY_BYTES = 4 * 1024**3  # 4 GiB
# An explicit, off-by-default escape hatch for a human who has already seen a real preflight failure and
# instructs this exact run to proceed anyway (2026-09-28: Cliff, having freed what memory was available and
# still short of the floor, said "it's not going to get better than this, please continue"). This does NOT
# lower MIN_AVAILABLE_MEMORY_BYTES -- every future run keeps the real 4 GiB floor as its default -- it only
# lets ONE explicitly-flagged invocation proceed, with the actual reading and the override itself recorded
# in this run's own preflight output and integration receipt rather than silently bypassed.
MEMORY_FLOOR_OVERRIDE_ENV = "CALLOSUM_ASK_LIVE_MEMORY_FLOOR_OVERRIDE"


def _check_available_memory() -> dict:
    vm = psutil.virtual_memory()
    info = {
        "total_gib": round(vm.total / 1024**3, 2),
        "available_gib": round(vm.available / 1024**3, 2),
        "percent_used": vm.percent,
        "min_required_gib": round(MIN_AVAILABLE_MEMORY_BYTES / 1024**3, 2),
        "floor_overridden_by_explicit_instruction": False,
    }
    if vm.available < MIN_AVAILABLE_MEMORY_BYTES:
        if os.environ.get(MEMORY_FLOOR_OVERRIDE_ENV) == "1":
            info["floor_overridden_by_explicit_instruction"] = True
            print(
                f"MEMORY FLOOR OVERRIDDEN by explicit instruction ({MEMORY_FLOOR_OVERRIDE_ENV}=1): only "
                f"{info['available_gib']} GiB available, below the {info['min_required_gib']} GiB floor. "
                "Proceeding anyway; this fact is recorded in the run's own output."
            )
            return info
        raise SystemExit(
            f"preflight failed: only {info['available_gib']} GiB available (of {info['total_gib']} GiB total, "
            f"{info['percent_used']:.1f}% used) -- below the {info['min_required_gib']} GiB floor. Free up "
            "memory (close other applications) before attempting the live call."
        )
    return info


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=False).stdout.strip()


def _rehearse_persistence(prompt: str, manifest: dict) -> None:
    """Preflight item 2: prove `DiagnosticTrace` write+read-back round-trips THIS run's real prompt and
    manifest exactly, in a disposable directory, before the real run directory (or any model call) exists."""
    tmp = Path(tempfile.mkdtemp(prefix="gate_integration_live_preflight_"))
    try:
        rehearsal = gate2_trace.DiagnosticTrace(tmp / "rehearsal")
        rehearsal.prompt_ready(prompt, manifest)
        written = json.loads((tmp / "rehearsal" / "02_prompt_and_manifest.json").read_text(encoding="utf-8"))
        if written["prompt"] != prompt:
            raise SystemExit("preflight failed: rehearsal prompt readback did not match exactly")
        if written["manifest"] != manifest:
            raise SystemExit("preflight failed: rehearsal manifest readback did not match exactly")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _offline_driver_tests_pass() -> bool:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "experiments/ask_cli_revised/contract_directed/test_gate_integration.py",
            "-q",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
    return result.returncode == 0


def offline_preflight() -> dict:
    """Every offline check in Section 3 item 1-2 of the authorization. Raises `SystemExit` with a plain
    explanation on the first failure -- never proceeds past a failed check."""
    dirty = [line for line in _git("status", "--porcelain").splitlines() if line.strip()]
    commit_sha = _git("rev-parse", "HEAD")

    if not fixture.available():
        raise SystemExit("preflight failed: the frozen c9/c11 packet fixtures are not present on this machine")

    manifest_rows = fixture.build_c9_c11_manifest()
    if len(manifest_rows) != 4:
        raise SystemExit(f"preflight failed: expected exactly 4 manifest rows, got {len(manifest_rows)}")
    by_id = {(r["child_id"], r["unit_id"]): r for r in manifest_rows}
    for key in (("c9", "M10"), ("c9", "W21"), ("c11", "M12"), ("c11", "M13")):
        if key not in by_id:
            raise SystemExit(f"preflight failed: expected manifest row {key} is missing")
    w21 = by_id[("c9", "W21")]
    if not (w21.get("constraint_text") or "").strip():
        raise SystemExit("preflight failed: c9/W21's coverage-constraint text is missing or empty")

    sealed = integration.build_sealed_ledger(manifest_rows)  # raises ValueError on a question-hash drift
    question = sealed["request_contract"]["original_question"]
    if sealed["request_contract"]["question_hash"] != freeze.QUESTION_SHA256:
        raise SystemExit("preflight failed: question hash does not match the frozen substrate")
    if not question.strip() or len(question.strip()) < 20:
        raise SystemExit(
            f"preflight failed: the rendered question looks like a placeholder, not the real one: {question!r}"
        )

    constraints = bridge.coverage_constraints(manifest_rows)
    if not constraints:
        raise SystemExit("preflight failed: no coverage constraints were projected (expected the W21 constraint)")

    states = sealed["obligation_states"]
    units, claims = oe.build_units(sealed)
    sent_unit_ids, prompt = ov.select_for_prompt(units, claims, question, states, coverage_constraints=constraints)
    if question.strip() not in prompt:
        raise SystemExit(
            "preflight failed: the real frozen parent question does not appear verbatim in the rendered prompt"
        )
    for constraint_text in constraints:
        if constraint_text not in prompt:
            raise SystemExit(
                f"preflight failed: coverage constraint text missing from the rendered prompt: {constraint_text!r}"
            )

    manifest_for_rehearsal = {
        "sealed_ledger_hash": integration.sealed_ledger_hash(sealed),
        "question_hash": sealed["request_contract"]["question_hash"],
        "sent_unit_ids": sent_unit_ids,
        "eligible_unit_ids": [u["unit_id"] for u in units if u["eligibility"]["eligible"]],
        "part_ids": [s["field_id"] for s in states],
        "coverage_constraints": list(constraints),
    }
    _rehearse_persistence(prompt, manifest_for_rehearsal)

    if not _offline_driver_tests_pass():
        raise SystemExit(
            "preflight failed: experiments/ask_cli_revised/contract_directed/test_gate_integration.py is not green"
        )

    if dirty:
        raise SystemExit(f"preflight failed: refusing a live call from a dirty tree: {dirty[:5]}")

    memory = _check_available_memory()

    return {
        "manifest_rows": manifest_rows,
        "commit_sha": commit_sha,
        "question": question,
        "constraints": list(constraints),
        "sent_unit_ids": sent_unit_ids,
        "prompt_char_len": len(prompt),
        "comparison_reference_never_read": COMPARISON_ONLY_PRIOR_RECORD,
        "memory": memory,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", default="gate-integration-live-001")
    args = parser.parse_args(argv)

    run_dir = RUNS_ROOT / args.run_id
    if run_dir.exists():
        raise SystemExit(f"{run_dir} exists; live run ids are never reused")

    print("running offline preflight...")
    preflight = offline_preflight()
    print(json.dumps({k: v for k, v in preflight.items() if k != "manifest_rows"}, indent=2, default=str))
    print("offline preflight passed.")

    manifest_rows = preflight["manifest_rows"]
    rt = ask_runtime.build_runtime(DB, want_gemini=False, want_verifier=True, want_qwen=False)
    try:
        entail = rt.verifier.support_scorer.support_and_contradiction_many
        # DiagnosticTrace.__init__ creates run_dir itself (mkdir(parents=True, exist_ok=False)) -- a second,
        # redundant mkdir here raced against it and raised FileExistsError before any network call was ever
        # attempted (2026-09-28, first live-driver invocation: caught before any retry).
        trace = gate2_trace.DiagnosticTrace(run_dir)
        trace.manifest_ready(manifest_rows)
        (run_dir / "preflight_report.json").write_text(
            json.dumps({k: v for k, v in preflight.items() if k != "manifest_rows"}, indent=2, default=str),
            encoding="utf-8",
        )

        with endpoint_guard.isolated_only():
            client = ms.FreeChatClient(topo.ENDPOINTS["isolated"])
            pre: dict = {}
            try:
                pre = {"at": integration.now(), "ollama_version": client.version()}
                tags = {(e.get("name") or e.get("model")): e.get("digest") for e in client.tags()}
                pre["installed_digest"] = tags.get(freeze.MODEL)
                pre["resident_before"] = [e.get("name") or e.get("model") for e in client.ps()]
                (run_dir / "pre_call_ollama_state.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
                if pre["ollama_version"] != freeze.OLLAMA_VERSION or pre["installed_digest"] != freeze.MODEL_DIGEST:
                    raise SystemExit(f"model digest / Ollama version differ from the frozen recorded run: {pre}")

                supervisor = stages.Supervisor(
                    role="S",
                    binding=topo.OVERVIEW_PROFILES["T5O"].S,
                    client=client,
                    base_options=topo.OVERVIEW_S_OPTIONS,
                )
                input_files = {"c9_packet": fixture.M10_PACKET_PATH, "c11_packet": fixture.C11_PACKET_PATH}
                try:
                    result = integration.build_live_integration_receipt(
                        manifest_rows,
                        supervisor=supervisor,
                        entail=entail,
                        trace=trace,
                        repo=REPO,
                        input_files=input_files,
                    )
                except Exception as exc:  # noqa: BLE001 -- the authorized catch-anything boundary for this one call
                    trace.exception(exc)
                    print(f"LIVE CALL FAILED after being attempted: {type(exc).__name__}: {exc}")
                    print(f"partial artifacts preserved in {run_dir}")
                    return 2
            finally:
                client.close()

        receipt, markdown, detailed_audit_view, record, reasoning = result
        receipt["comparison_reference_never_read"] = COMPARISON_ONLY_PRIOR_RECORD
        (run_dir / "00_integration_receipt.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        (run_dir / "01_derived_manifest.json").write_text(
            json.dumps(manifest_rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        (run_dir / "02_partial_answer.md").write_text(markdown, encoding="utf-8")
        (run_dir / "03_detailed_audit_view.json").write_text(
            json.dumps(detailed_audit_view, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        print(f"wrote {run_dir}")
        print(
            json.dumps(
                {"state": record["state"], "stage_transitions": receipt["stage_transitions"]}, indent=2, default=str
            )
        )
        return 0
    finally:
        rt.close()


if __name__ == "__main__":
    raise SystemExit(main())
