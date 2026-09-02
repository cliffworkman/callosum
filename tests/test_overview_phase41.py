from __future__ import annotations

import json

import pytest

from tools.qualification import overview_battery, overview_phase41

RECEIPTS = overview_battery.PROFILE_DIR / "phase4-1-receipt-index.json"


def test_phase41_cohort_keeps_the_base_battery_frozen() -> None:
    # Re-frozen 2026-09-01 (inc 557) alongside test_overview_cloud_calibration.py's identical witness -- see
    # that file's comment for why this re-freeze is behaviorally neutral for what the study tested.
    assert overview_battery.verify_freeze()["aggregate_sha256"] == (
        "944213c0b1aaf6c6f43717d0ba7a243d336875f5156af26d9930575c8f68ed9b"
    )
    freeze = overview_phase41.verify_search_freeze()
    assert freeze["base_battery_aggregate_sha256"] == overview_battery.verify_freeze()["aggregate_sha256"]


def test_phase41_candidates_are_exact_unique_execution_identities() -> None:
    candidates = [overview_phase41.cohort_candidate(f"P{number:02d}") for number in range(1, 8)]
    assert len({candidate["artifact_sha256"] for candidate in candidates}) == 7
    assert len({candidate["artifact_id"] for candidate in candidates}) == 7
    assert all(len(candidate["chat_template_sha256"]) == 64 for candidate in candidates)
    assert all(candidate["requested_gpu_layers"] > 0 for candidate in candidates)
    assert all(candidate["artifact_bytes"] > 0 for candidate in candidates)


def test_phase41_unknown_candidate_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="unknown Phase 4.1 candidate"):
        overview_phase41.cohort_candidate("P99")


def test_phase41_receipts_cover_the_frozen_cohort_without_advancing() -> None:
    cohort = json.loads(overview_phase41.COHORT_PATH.read_text(encoding="utf-8"))
    receipts = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    assert {row["candidate_code"] for row in receipts["results"]} == {
        row["candidate_code"] for row in cohort["candidates"]
    }
    assert all(row["failed_stage"] == "stage1_reliability" for row in receipts["results"])
    assert all(row["result"] == "not_qualified" for row in receipts["results"])
    assert receipts["adjudication"]["status"] == "not_started_no_stage1_survivor"
    assert receipts["challenge_holdout"]["opened"] is False
    assert receipts["result"] == "no_mechanical_survivor"
