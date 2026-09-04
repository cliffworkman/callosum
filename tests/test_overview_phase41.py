from __future__ import annotations

import json

import pytest

from tools.qualification import overview_battery, overview_phase41

RECEIPTS = overview_battery.PROFILE_DIR / "phase4-1-receipt-index.json"


def test_phase41_cohort_keeps_the_base_battery_frozen() -> None:
    # Re-frozen 2026-09-01 (inc 557) alongside test_overview_cloud_calibration.py's identical witness -- see
    # that file's comment for why this re-freeze is behaviorally neutral for what the study tested.
    # inc 575: providers.py moved again, fixing a truncated model answer that surfaced to a real user as a
    # raw JSONDecodeError. Confirmed behaviourally neutral for what THIS study tested: the additions read the
    # finish_reason/stop_reason the provider already returned (no request field changes), and the one real
    # generation-setting change (_MAX_TOKENS 2048 -> 4096) governs only the Anthropic `messages` wire, which
    # none of this battery's local GGUF candidates use -- their Overview cap is the unchanged 256. The
    # recorded null result stays reproducible. See INCREMENT-575-NOTES.md and the profile README.
    assert overview_battery.verify_freeze()["aggregate_sha256"] == (
        "3591ed8dcd424fa0dbbc2b8b71f9858adb6da9c81ae90a6996aef1588d6a6bc3"
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
