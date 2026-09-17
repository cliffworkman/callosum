import copy

import pytest

from experiments.ask_070.contracts import ContractError
from experiments.ask_070.scorer import context_choice, rate, score


def row(question="q1", model="m1", package="R_CONTROL", overall="LOSS_AND_ADDITION"):
    return {
        "question_id": question,
        "task_kind": "request_planning",
        "model_id": model,
        "package_id": package,
        "stratum_hash": "matched",
        "unit_id": "u1",
        "origin": "SYNTHETIC",
        "overall": overall,
        "flags": {"LOSS": True, "ADDITION": True, "MALFORMED": True},
        "mechanical_validity": True,
        "responsiveness": False,
        "completeness": False,
        "contamination": True,
        "dimensions": {"obligations": ["PRESERVED", "DRIFTED", "STARVED"], "null": ["STARVED"], "mixed": ["PRESERVED"]},
    }


def test_cooccurrence_and_axis_separation():
    report = score([row()], synthetic=True)["per_question"][0]
    assert report["overall_categories"] == {"LOSS_AND_ADDITION": 1}
    assert all(v["rate"] == 1 for v in report["independent_flags"].values())
    assert report["mechanical_validity"]["rate"] == 1 and report["responsiveness"]["rate"] == 0
    assert report["contamination_gate"] == "FAIL"
    assert report["dimensions"]["null"]["preserved"]["rate"] == 0
    assert report["dimensions"]["mixed"]["preserved"]["rate"] == 1


def test_divergent_questions_not_averaged():
    result = score([row(), row("q2", overall="FAITHFUL")], synthetic=True)
    assert len(result["per_question"]) == 2 and result["cross_question_average"] == "PROHIBITED"
    assert {r["fidelity"]["rate"] for r in result["per_question"]} == {0, 1}


def test_wilson_and_missing_denominators():
    assert rate(0, 0)["rate"] is None and rate(0, 10)["wilson_lower"] == 0
    assert rate(10, 10)["wilson_lower"] == pytest.approx(0.7224672, abs=1e-6)
    assert rate(5, 10)["wilson_lower"] == pytest.approx(0.236593, abs=1e-6)
    with pytest.raises(ContractError):
        rate(2, 1)


def test_factorial_contrasts_only_on_matched_strata():
    rows = [
        row(model=m, package=p, overall="FAITHFUL" if m == "m2" and p == "R_0_6" else "LOSS")
        for m in ("m1", "m2")
        for p in ("R_CONTROL", "R_0_6")
    ]
    result = score(rows, synthetic=True)["effects"][0]
    interaction = [c for c in result["contrasts"] if c["estimand"].endswith("INTERACTION")][0]
    assert interaction["difference_in_differences"] == 1
    assert score(rows[:1], synthetic=True)["effects"][0]["interaction_status"] == "NOT_ESTIMABLE"
    rows[3]["stratum_hash"] = "different-hardware"
    assert all(r["interaction_status"] == "NOT_ESTIMABLE" for r in score(rows, synthetic=True)["effects"])


def test_external_labels_required_and_duplicate_rejected():
    with pytest.raises(ContractError, match="HUMAN"):
        score([row()])
    r = row()
    r["origin"] = "HUMAN"
    with pytest.raises(ContractError, match="REVIEW"):
        score([r])
    with pytest.raises(ContractError, match="DUPLICATE"):
        score([row(), row()], synthetic=True)
    r = copy.deepcopy(row())
    del r["flags"]["MALFORMED"]
    with pytest.raises(ContractError):
        score([r], synthetic=True)


def test_context_asymmetry_and_unlabeled():
    assert context_choice("A", "C", ["C"])["under_distance"] == 2
    assert context_choice("D", "C", ["C"])["over_distance"] == 1
    assert context_choice("D", "C", ["C", "D"])["over_distance"] == 0
    assert context_choice(None, "C", ["C"])["status"] == "NO_CHOICE"
