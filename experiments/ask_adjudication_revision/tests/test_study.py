import copy

import pytest

from experiments.ask_adjudication_revision.capability import suite, synthetic_evidence
from experiments.ask_adjudication_revision.core import ROSTER, canonical, synthetic_cases
from experiments.ask_adjudication_revision.study import Review, SyntheticStudy, synthetic_design


def prepared(*, close=True, human=True):
    cases = synthetic_cases(18)
    packets = suite()
    records = [synthetic_evidence(sid, packets) for sid, _ in ROSTER[:3]]
    study = SyntheticStudy(cases)
    study.freeze_a(records, packets)
    for sid, _ in ROSTER[:3]:
        raw = canonical([{"candidate_id": c.candidate_id, "label": "NO_FLAG", "reason": ""} for c in cases])
        study.record_screen(sid, [c.candidate_id for c in cases], raw)
    if close:
        study.close_frontier()
    if human:
        study.amend_interstudy(
            findings="PRIVATE_PATTERN",
            changes="Challenge fixture relation",
            why="PRIVATE_RATIONALE",
            accessed_by=["FAKE_ORCHESTRATOR"],
        )
        study.freeze_b(synthetic_design(cases, rationale="PRIVATE_SELECTION"))
    return study, cases, records


def test_two_freezes_and_interstudy_access_are_ordered():
    study, cases, records = prepared(close=False, human=False)
    with pytest.raises(ValueError, match="NOT_YET_ALLOWED"):
        study.private_frontier()
    with pytest.raises(ValueError, match="NOT_YET_ALLOWED"):
        study.private_artifacts()
    with pytest.raises(ValueError):
        study.human_packet("fixture_a")
    with pytest.raises(ValueError):
        study.freeze_b(synthetic_design(cases))
    with pytest.raises(ValueError, match="FREEZE_A_IMMUTABLE"):
        study.freeze_a(records, suite())
    study.close_frontier()
    assert len(study.private_frontier()) == 3 * len(cases)
    with pytest.raises(ValueError, match="AMENDMENT_REQUIRED"):
        study.freeze_b(synthetic_design(cases))


def test_incomplete_study_cannot_close_and_missing_dispositions_are_preserved():
    cases = synthetic_cases(1)
    records = [synthetic_evidence(sid, suite()) for sid, _ in ROSTER[:3]]
    study = SyntheticStudy(cases)
    study.freeze_a(records, suite())
    with pytest.raises(ValueError, match="INCOMPLETE"):
        study.close_frontier()
    for sid, _ in ROSTER[:3]:
        study.record_screen(sid, [c.candidate_id for c in cases], b"refusal fixture")
    study.close_frontier()
    assert all(row["label"] is None for row in study.private_frontier())


def test_private_patterns_can_change_design_before_b_but_are_not_exported():
    study, cases, _ = prepared(human=False)
    assert study.private_frontier()[0]["label"] == "NO_FLAG"
    study.amend_interstudy(
        findings="PRIVATE_PATTERN", changes="Alter exact allocations", why="PRIVATE_RATIONALE", accessed_by=["FAKE"]
    )
    plan = synthetic_design(cases, seed="adapted-seed", rationale="PRIVATE_SELECTION")
    study.freeze_b(plan)
    before = study.private_artifacts()["freeze_b"]
    plan["allocations"].clear()
    assert study.private_artifacts()["freeze_b"] == before
    with pytest.raises(ValueError, match="FREEZE_B_IMMUTABLE"):
        study.freeze_b(synthetic_design(cases))
    exported = canonical(study.human_packet("fixture_a"))
    for secret in (
        b"PRIVATE_PATTERN",
        b"PRIVATE_RATIONALE",
        b"PRIVATE_SELECTION",
        b"NO_FLAG",
        b"fixture_a",
        b"unflagged",
    ):
        assert secret not in exported
    assert b"SYNTHETIC_SECRET" in exported  # The scientific object itself must be shown.


def test_seeded_selection_is_reproducible_and_without_duplicate_units():
    cases = synthetic_cases(20)
    assert synthetic_design(cases) == synthetic_design(cases)
    assert synthetic_design(cases, seed="other") != synthetic_design(cases)
    for allocation in synthetic_design(cases)["allocations"].values():
        ids = allocation["discovery"] + sum(allocation["challenges"].values(), []) + allocation["expansion"]
        assert len(ids) == len(set(ids)) == 16


@pytest.mark.parametrize("mutation", ["duplicate", "burden", "challenge", "rule"])
def test_invalid_human_designs_fail_before_release(mutation):
    study, cases, _ = prepared(human=False)
    study.amend_interstudy(findings="x", changes="x", why="x", accessed_by=["FAKE"])
    plan = synthetic_design(cases)
    if mutation == "duplicate":
        plan["allocations"]["fixture_a"]["expansion"][0] = plan["allocations"]["fixture_a"]["discovery"][0]
    elif mutation == "burden":
        plan["max_unique_per_configuration"] = 25
    elif mutation == "challenge":
        plan["allocations"]["fixture_a"]["challenges"]["screen_independent"] = []
    else:
        plan["expansion_rule"] = "ignore shared misses"
    with pytest.raises(ValueError):
        study.freeze_b(plan)


def promote_release(study, config, session):
    pending = study.next_cases(config)
    for cid in pending:
        study.review(Review(cid, "PROMOTE", session))
    return pending


def test_promotion_requires_rereads_and_challenges():
    study, _, _ = prepared()
    first = promote_release(study, "fixture_a", "session1")
    assert len(first) == 3
    assert study.outcome("fixture_a") == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(ValueError, match="FRESH_SESSION"):
        study.review(Review(first[0], "PROMOTE", "session1"))
    assert set(promote_release(study, "fixture_a", "session2")) == set(first)
    challenges = promote_release(study, "fixture_a", "session3")
    assert len(challenges) == 9
    assert study.outcome("fixture_a") == "ELIGIBLE_FOR_INTEGRATION_REVIEW"
    assert not study.next_cases("fixture_a")


def test_one_confirmed_severe_halts_only_that_configuration_and_expands_survivor():
    study, _, _ = prepared()
    cid = study.next_cases("fixture_a")[0]
    study.review(Review(cid, "REJECT", "s1", "Synthetic source inversion", severe=True))
    assert study.outcome("fixture_a") == "INSUFFICIENT_EVIDENCE"
    study.review(Review(cid, "REJECT", "s2", "Synthetic inversion confirmed", severe=True))
    assert study.outcome("fixture_a") == "HALT_CONFIGURATION"
    assert study.next_cases("fixture_a") == ()
    promote_release(study, "fixture_b", "s1")
    promote_release(study, "fixture_b", "s2")
    assert len(promote_release(study, "fixture_b", "s3")) == 13  # Nine challenges + four random expansion fixtures.
    assert study.outcome("fixture_b") == "ELIGIBLE_FOR_INTEGRATION_REVIEW"


def test_disagreement_minor_reject_and_uncertainty_do_not_become_severe():
    for label in ("REJECT", "UNCERTAIN"):
        study, _, _ = prepared()
        cid = study.next_cases("fixture_a")[0]
        study.review(Review(cid, label, "s1", "Fixture concern", severe=False))
        study.review(Review(cid, "PROMOTE", "s2"))
        assert study.outcome("fixture_a") == "INSUFFICIENT_EVIDENCE"
        assert not study.next_cases("fixture_a")


def test_exposure_blocks_release_and_real_labels_are_rejected():
    study, cases, _ = prepared()
    with pytest.raises(ValueError, match="GENUINE_HUMAN_LABELS_DISABLED"):
        Review(cases[0].candidate_id, "PROMOTE", "s", origin="HUMAN")
    with pytest.raises(ValueError, match="REAL_STUDY_DISABLED"):
        SyntheticStudy(cases, origin="REAL")
    study.expose()
    with pytest.raises(ValueError, match="BLOCKED"):
        study.human_packet("fixture_a")
    with pytest.raises(ValueError, match="BLINDING"):
        study.outcome("fixture_a")


def test_freeze_a_copies_caller_data():
    study, _, records = prepared(human=False)
    before = copy.deepcopy(study.private_artifacts()["freeze_a"])
    records[0]["displayed_model"] = "modified"
    assert study.private_artifacts()["freeze_a"] == before


def test_diagnostics_open_only_after_a_detected_problem_and_are_optional():
    study, _, _ = prepared()
    cid = study.next_cases("fixture_a")[0]
    with pytest.raises(ValueError, match="POST_FAILURE_ONLY"):
        study.diagnostic_form(cid)
    study.review(Review(cid, "UNCERTAIN", "s1", "Synthetic endpoint concern"))
    assert "relation_endpoints" in study.diagnostic_form(cid)["optional_dimensions"]
    study.record_diagnostics(cid, {"relation_endpoints": "One optional synthetic source-anchored diagnostic"})
    assert len(study.private_artifacts()["diagnostics"][cid]) == 1
    with pytest.raises(ValueError, match="IMMUTABLE"):
        study.record_diagnostics(cid, {"subject": "replacement"})
    assert study.outcome("fixture_a") == "INSUFFICIENT_EVIDENCE"
