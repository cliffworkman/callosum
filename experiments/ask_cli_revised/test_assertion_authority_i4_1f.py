"""PHASE 34 / I4-1f -- pure, unwired assertion_relation + aggregation + support_label battery gate.

Runs the six frozen batteries described in PHASE34_I4_1F_PROVENANCE_AGGREGATION_RESULTS.md and pins their hashes.
Mirrors the I4-1/1b/1c/1d convention: frozen JSON is authored and hashed BEFORE any classifier edit; the hashes
below are the freeze record. No model, network, or live search. Pure and unwired, exactly like its predecessors.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import assertion_authority as aa

HERE = Path(__file__).parent

_FROZEN_HASHES = {
    "assertion_relation_i4_1f_preregistered.json": "f67e81a2fa0100ad553a85df9073ac6cba719ddbe64bc5edee99b3fd7150a0a3",
    "prior_source_review_i4_1f_preregistered.json": "055181788ebfdc9afc3ceed5718839d0ab13fa656f6822684dd898a9fee23d1c",
    "aggregation_i4_1f_preregistered.json": "f7388c80f34684d1442a7b7acda98f298f9d022b67e97f632caa2a002482a7b5",
    "aggregation_i4_1f_holdout.json": "65c143e520604eb228657ee7a8e015a6ba01a181c36d0986460efcb1a99f1e30",
    "aggregation_i4_1f_twins.json": "a00dee4ccf9e2a9859758ff06f05bd2f0a0edc59a71e9c094fc18e337c589d8c",  # amended: T_CLIN_02 test-design correction, see results report
    "support_label_i4_1f_table.json": "eccbee4b7eed3557e131f513840c7dfe0067af24081fac275e2827c5185e2e41",
}


def _load(name):
    path = HERE / name
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == _FROZEN_HASHES[name], f"{name} drifted from its frozen hash: {digest}"
    return json.loads(data.decode("utf-8"))


def test_all_six_batteries_match_their_frozen_hash():
    for name in _FROZEN_HASHES:
        _load(name)


# ---- A. assertion_relation translation battery ----


@pytest.mark.parametrize("case", _load("assertion_relation_i4_1f_preregistered.json"), ids=lambda c: c["id"])
def test_assertion_relation_translation_battery(case):
    if case.get("expect_raises"):
        with pytest.raises(ValueError):
            aa.assertion_relation(case["assertion_source"])
    else:
        assert aa.assertion_relation(case["assertion_source"]) == case["expect"]


def test_assertion_relation_is_a_pure_1to1_rename_never_inventing_a_fourth_value():
    seen = {aa.assertion_relation(s) for s in aa.SOURCES}
    assert seen == set(aa.ASSERTION_RELATIONS)
    assert len(aa.SOURCES) == len(aa.ASSERTION_RELATIONS)


# ---- B. prior-source review-head ownership battery ----


def _resolve(case):
    text = case["text"]
    i = text.find(case["target_surface"])
    assert i != -1, f"{case['id']}: target_surface not found literally in text"
    return aa.classify_target_assertions(
        text,
        target_start=i,
        target_end=i + len(case["target_surface"]),
        is_caption=case.get("is_caption", False),
    )


@pytest.mark.parametrize("case", _load("prior_source_review_i4_1f_preregistered.json"), ids=lambda c: c["id"])
def test_prior_source_review_head_battery(case):
    res = _resolve(case)
    if case.get("expect_no_assertion"):
        assert res["target_scope"] == "no_governing_assertion"
        return
    assert len(res["assertions"]) == 1, f"{case['id']}: expected exactly one governing assertion"
    a = res["assertions"][0]
    assert a["assertion_source"] in aa.SOURCES
    assert aa.assertion_relation(a["assertion_source"]) == case["expect_relation"]
    if "expect_kind" in case:
        assert a["assertion_kind"] == case["expect_kind"]


# ---- C/D/E. aggregation preregistered + holdout + cross-domain twins ----


def _check_aggregation_case(case):
    res = _resolve(case)
    if case.get("expect_no_assertion"):
        assert res["target_scope"] == "no_governing_assertion"
        return
    assert len(res["assertions"]) == 1, f"{case['id']}: expected exactly one governing assertion"
    a = res["assertions"][0]
    assert a["aggregation"] == case["expect_aggregation"], case["id"]
    # the standalone public API must agree with the field embedded on the same assertion record
    i = case["text"].find(case["target_surface"])
    assert (
        aa.aggregation(
            case["text"],
            target_start=i,
            target_end=i + len(case["target_surface"]),
            is_caption=case.get("is_caption", False),
        )
        == case["expect_aggregation"]
    ), case["id"]
    if "expect_relation" in case:
        assert aa.assertion_relation(a["assertion_source"]) == case["expect_relation"], case["id"]
    if "expect_kind" in case:
        assert a["assertion_kind"] == case["expect_kind"], case["id"]
    if "expect_authority_veto" in case:
        assert a["authority_veto"] == case["expect_authority_veto"], case["id"]
    if "expect_finding_authority" in case:
        assert a["finding_authority"] == case["expect_finding_authority"], case["id"]


@pytest.mark.parametrize("case", _load("aggregation_i4_1f_preregistered.json"), ids=lambda c: c["id"])
def test_aggregation_preregistered_battery(case):
    _check_aggregation_case(case)


@pytest.mark.parametrize("case", _load("aggregation_i4_1f_holdout.json"), ids=lambda c: c["id"])
def test_aggregation_holdout_battery_first_and_only_run(case):
    _check_aggregation_case(case)


@pytest.mark.parametrize("case", _load("aggregation_i4_1f_twins.json"), ids=lambda c: c["id"])
def test_aggregation_cross_domain_twins(case):
    _check_aggregation_case(case)


def test_aggregation_output_is_always_one_of_the_two_closed_values():
    for case in _load("aggregation_i4_1f_preregistered.json") + _load("aggregation_i4_1f_holdout.json"):
        if case.get("expect_no_assertion"):
            continue
        res = _resolve(case)
        a = res["assertions"][0]
        assert a["aggregation"] in aa.AGGREGATIONS


def test_aggregation_public_function_fails_closed_like_classify_assertion_authority():
    text = "We review X."
    i = text.find("X")
    with pytest.raises(ValueError):
        aa.aggregation(text, target_start=i, target_end=i + 1)


# ---- F. support_label exhaustive table battery ----


@pytest.mark.parametrize("case", _load("support_label_i4_1f_table.json"), ids=lambda c: c["id"])
def test_support_label_table(case):
    assert aa.support_label(case["relation"], case["aggregation"], case["kind"]) == case["expect"]


def test_support_label_never_consumed_by_any_admissibility_function():
    """Static guard: ``support_label`` is display-only. No function in this pure, unwired module may call it and
    feed the result back into source/kind/authority classification."""
    source = (HERE / "assertion_authority.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    label_def = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "support_label")
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node is not label_def:
            calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            assert "support_label" not in calls, f"{node.name} must never consume support_label's own output"


# ---- Locality (section 5): a cue in one assertion must never leak to a neighbouring one ----


def test_aggregation_locality_within_one_sentence_two_clauses():
    text = "Across studies, X has been associated with Y. We found Z."
    i1 = text.find("associated with Y")
    res1 = aa.classify_target_assertions(text, target_start=i1, target_end=i1 + len("associated with Y"))
    a1 = res1["assertions"][0]
    assert a1["aggregation"] == aa.LITERATURE_SYNTHESIS

    i2 = text.find("Z")
    res2 = aa.classify_target_assertions(text, target_start=i2, target_end=i2 + 1)
    a2 = res2["assertions"][0]
    assert a2["aggregation"] == aa.NON_SYNTHETIC


def test_aggregation_locality_review_then_current_document_two_sentences():
    text = "A review found X. We found Y."
    i1 = text.find("X")
    res1 = aa.classify_target_assertions(text, target_start=i1, target_end=i1 + 1)
    a1 = res1["assertions"][0]
    assert a1["aggregation"] == aa.LITERATURE_SYNTHESIS

    i2 = text.rfind("Y")
    res2 = aa.classify_target_assertions(text, target_start=i2, target_end=i2 + 1)
    a2 = res2["assertions"][0]
    assert a2["aggregation"] == aa.NON_SYNTHETIC


# ---- Zero-runtime-change proofs ----


def test_classifier_is_still_unwired_static_guard():
    """Re-asserts I4-1's own static guard still holds after this increment's additions: no non-test module
    anywhere in the repository references assertion_authority by name."""
    root = HERE.parents[1]
    assert root.name == "callosum" or (root / "app").exists(), f"unexpected repo root resolved: {root}"
    offenders = []
    for sub in ("app", "integrations", "experiments", "tools", "tests", "mcp_server", "tui", "sync_server"):
        base = root / sub
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path.name.startswith("test_") or path.name == "assertion_authority.py":
                continue
            if "ask_cli_revised" in path.parts and path.name not in {
                "achieved_outcome_span.py",
            }:
                # scoped: only the two known-pure sibling modules in this package may be inspected for a reference;
                # everything else in this directory is this phase's own test/report material, not a production path.
                pass
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "assertion_authority" in text:
                offenders.append(str(path))
    assert offenders == [], f"assertion_authority is referenced outside its own tests: {offenders}"


def test_versions_are_unchanged_for_sufficiency_and_plan():
    from experiments.ask_cli_revised import sufficiency_engine as se
    from experiments.ask_cli_revised.answer_plan import plan as ap

    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V4
    assert ap.PLAN_VERSION == "answer-plan-step2-v4"
