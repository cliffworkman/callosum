"""Repeatable offline replay/integration of the c9+c11 vertical slice (2026-09-27).

**This is a replay of already-saved Gate 1 and Gate 2 stage artifacts, NOT a fresh live E2E run.** No model,
NLI, embedding, retrieval, localization, or eligibility call happens anywhere in this script.

Reads only:
  - the two frozen packet files `gate1_evidence_fixture.py` names,
  - the saved `runs/gate2-diagnostic-002/04_final_record.json` Gate 2 overview record.

Writes only, to a fresh, never-reused, attempt-specific output directory:
  - 00_integration_receipt.json  (input hashes, code version, stage-transition receipt)
  - 01_derived_manifest.json     (the c9+c11 manifest actually used, with provenance)
  - 02_partial_answer.md         (the rendered researcher-facing partial answer)
  - 03_detailed_audit_view.json  (the renderer's own classification manifest)

Modifies no existing file -- not the original pilot, the 8-call replay, the offline audit, either Gate 2
attempt, or the prior hand-built slice artifacts in `runs/gate2-diagnostic-002/`.

    python -m experiments.ask_cli_revised.contract_directed.tools.run_gate_integration [--run-id ID]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import freeze
from experiments.ask_cli_revised.contract_directed import gate1_evidence_fixture as fixture
from experiments.ask_cli_revised.contract_directed import gate_integration as integration

REPO = Path(r"C:\Users\cliff\callosum-worktrees\ask-contract-directed")
SAVED_RECORD_PATH = freeze.SLICE_ROOT / "runs" / "gate2-diagnostic-002" / "04_final_record.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="gate-integration-001")
    args = parser.parse_args(argv)

    run_dir = freeze.SLICE_ROOT / "runs" / args.run_id
    if run_dir.exists():
        raise SystemExit(f"{run_dir} exists; integration run ids are never reused")

    if not fixture.available():
        raise SystemExit("the frozen c9/c11 packet files are not present on this machine")
    if not SAVED_RECORD_PATH.is_file():
        raise SystemExit(f"{SAVED_RECORD_PATH} is not present; nothing to replay")

    manifest_rows = fixture.build_c9_c11_manifest()
    gate2_record = json.loads(SAVED_RECORD_PATH.read_text(encoding="utf-8"))["record"]

    input_files = {
        "c9_packet": fixture.M10_PACKET_PATH,
        "c11_packet": fixture.C11_PACKET_PATH,
        "gate2_saved_record": SAVED_RECORD_PATH,
    }
    receipt, markdown, detailed_audit_view = integration.build_integration_receipt(
        manifest_rows, gate2_record, repo=REPO, input_files=input_files
    )

    run_dir.mkdir(parents=True)
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
    print(json.dumps({"stage_transitions": receipt["stage_transitions"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
