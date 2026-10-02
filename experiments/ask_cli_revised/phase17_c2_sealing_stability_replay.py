"""Phase 17 §I: deterministic/offline counterfactual replay using recorded artifacts only.

No live model call. No retrieval. No recovery execution.

This is a standalone script (the Phase 13/15 precedent: `phase13_c4_recovery_experiment.py`,
`phase15_c4_semantic_consumption_experiment.py`), not a pytest-collected test -- it depends on
`.local/e2e-runs/` artifacts that are real but gitignored, so it is run manually, not in CI.

Inputs, both already-recorded (never recomputed live):
  - the q-aib-hierarchical-t5c-live-20260930 preserved run's own `11_verified_ledger.json` (26
    real source-verified records) and `12_coverage_audit.initial.json` (phi4:14b's real C1
    coverage-audit result over them) -- the exact file `phase15_c4_semantic_consumption_
    experiment.py` itself already treats as "the original ledger from already-recorded
    artifacts" (`_ORIGINAL_LEDGER`), reused here rather than a second copy.
  - Phase 13's own real recovered proposition text (`PHASE13_C4_LIVE_RECOVERY_EXPERIMENT_
    RESULTS.md` / `phase15_c4_semantic_consumption_experiment.py`'s own docstring): "a cortical
    region in the right temporo-parietal junction (RTPJ)", attached to c4 only in every account.

Scoping note (disclosed, not silently omitted): this replay proves the MECHANISM -- that
append-only sealing preserves whatever a real recorded C1 call said for p3/p16, byte-for-byte,
while still correctly attaching the new p27 to c4 -- using `12_coverage_audit.initial.json` as a
real, recorded C1 result. It does not attempt to reproduce PHASE15_C4_SEMANTIC_CONSUMPTION_
RESULTS.md's own narrated numbers bit-for-bit: that report's own "original" comparison point was
not fully pinned down from available artifacts in the time budgeted for this phase (its own
script layers a second, separate live re-seal on top of this same baseline before narrating
"gained"/"moved"). `AppendOnlySealTests` in `test_stages.py` is the primary, CI-running proof of
the mechanism itself; this script is the best-effort tie to the real preserved corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.ask_cli_revised import stages

_RUN_DIR = Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run"
_LEDGER_PATH = _RUN_DIR / "11_verified_ledger.json"
_COVERAGE_INITIAL_PATH = _RUN_DIR / "12_coverage_audit.initial.json"

_P27_CLAIM = "a cortical region in the right temporo-parietal junction (RTPJ)"
_P27_PAPER_ID = 74
_P27_CHUNK_ID = 35979
_P27_SPAN_ID = "e8"


def _load_prior_sealed() -> tuple[dict, list[dict]]:
    """Reconstruct, purely/locally, the real C1 sealed ledger from the two recorded artifacts."""
    ledger_dump = json.loads(_LEDGER_PATH.read_text(encoding="utf-8"))
    coverage_initial = json.loads(_COVERAGE_INITIAL_PATH.read_text(encoding="utf-8"))
    records = [
        {
            "subquestion_id": row.get("subquestion_id", row["proposition_id"]),
            "proposition_text": row["proposition_text"],
            "quote": row.get("quote", ""),
            "paper_id": row["paper_id"],
            "evidence_anchor_chunk_id": row["evidence_anchor_chunk_id"],
            "evidence_span_id": row.get("evidence_span_id", "e1"),
            "mapping_state": "mapped",
            "obligation_ids": [],
            "verification": {"status": "verified"},
            "provenance": {"origin": "initial"},
        }
        for row in ledger_dump["verified_propositions"]
    ]
    contract = ledger_dump["request_contract"]
    subquestions = ledger_dump["subquestions"]
    prior_sealed = stages.seal(contract, subquestions, records, [], coverage_initial)
    return prior_sealed, records


def run() -> dict:
    prior_sealed, records = _load_prior_sealed()
    recorded = {
        row["proposition_id"]: row["responsive_obligation_ids"] for row in prior_sealed["verified_propositions"]
    }
    before = {"p3": recorded.get("p3"), "p16": recorded.get("p16")}

    grown = records + [
        {
            "subquestion_id": "c4",
            "proposition_text": _P27_CLAIM,
            "quote": _P27_CLAIM,
            "paper_id": _P27_PAPER_ID,
            "evidence_anchor_chunk_id": _P27_CHUNK_ID,
            "evidence_span_id": _P27_SPAN_ID,
            "mapping_state": "mapped",
            "obligation_ids": [],
            "verification": {"status": "verified"},
            "provenance": {"origin": "recovery"},
        }
    ]
    new_pids = stages.verify_stable_prefix_and_new_pids(prior_sealed, grown)
    assert new_pids == {"p27"}, f"expected exactly p27 as the new suffix, got {new_pids}"

    subquestions = prior_sealed["subquestions"]
    obligations = [sq["obligations"][0] for sq in subquestions]
    c4_only = {
        "authority": {"kind": "offline_replay", "role": "C"},
        "assessed": True,
        "obligations": [
            {
                "field_id": ob["field_id"],
                "subquestion_id": sq["subquestion_id"],
                "source_unit_id": ob.get("source_unit_id"),
                "note": ob["note"],
                "display": ob["note"],
                "state": "judged_responsive" if ob["field_id"] == "c4" else "no_responsive_claim",
                "proposition_ids": ["p27"] if ob["field_id"] == "c4" else [],
                "mechanical_gaps": 0,
            }
            for sq, ob in zip(subquestions, obligations, strict=True)
        ],
        "outcome": None,
    }
    final = stages.seal(prior_sealed["request_contract"], subquestions, grown, [], c4_only, prior_sealed=prior_sealed)
    after = {row["proposition_id"]: row["responsive_obligation_ids"] for row in final["verified_propositions"]}

    result = {
        "p3_before": before["p3"],
        "p3_after": after.get("p3"),
        "p3_preserved": before["p3"] == after.get("p3"),
        "p16_before": before["p16"],
        "p16_after": after.get("p16"),
        "p16_preserved": before["p16"] == after.get("p16"),
        "p27_after": after.get("p27"),
        "p27_attached_to_c4_only": after.get("p27") == ["c4"],
        "every_old_pid_byte_identical": all(after[pid] == recorded[pid] for pid in recorded),
    }
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
