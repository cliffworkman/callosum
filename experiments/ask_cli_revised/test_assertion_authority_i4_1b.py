"""PHASE 34 I4-1b gates: frozen batteries (run once, hashes pinned), multi-assertion invariants, label rules, versions.

The batteries are frozen BEFORE the I4-1b classifier change. Their sha256 values are pinned below, so an expectation cannot
be edited without this file failing. The generator that wrote them is i4_1b_make_battery.py.
"""

import hashlib
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.answer_plan import plan as pl

HERE = Path(__file__).resolve().parent
# Hashes pinned on the exact committed bytes. The pre-commit end-of-file-fixer hook added one trailing newline to each
# file at commit time (no content change otherwise -- see PHASE34_I4_1B_STRUCTURAL_CONTEXT_RESULTS.md); the hashes
# below are post-fixer, matching what actually lives in the repository.
FROZEN = {
    "assertion_authority_i4_1b_preregistered.json": "5b3519463050768c41ce0a1db378c40c4c86126afe794fc271cb3342b94ae216",
    "assertion_authority_i4_1b_holdout.json": "23d02abf8000ea734ff6e97b77e286920fceec47ce3d67ab5965a2949664a032",
    "assertion_authority_i4_1b_twins.json": "50dec8186d7165aff478a53f352d52f69aa0e99ac3a76946e6f0b7616832d834",
}


def _load(name):
    raw = (HERE / name).read_bytes()
    return json.loads(raw.decode("utf-8"))


_BATTERIES = {name: _load(name) for name in FROZEN}
_CASES = [(name, c) for name in FROZEN for c in _BATTERIES[name]["cases"]]


def _target_bounds(text, target):
    if target.get("whole"):
        return 0, len(text)
    s = text.find(target["surface"])
    assert s >= 0, target["surface"]
    occ = target.get("occurrence")
    if occ is not None:
        pos = -1
        for _ in range(occ):
            pos = text.find(target["surface"], pos + 1)
        s = pos
    return s, s + len(target["surface"])


def _single(text, target):
    if target.get("whole"):
        r = aa.classify_assertion_authority(text, target_start=0, target_end=len(text))
    else:
        o = aa.classify_surface(text, target["surface"], occurrence=target.get("occurrence"))
        if o["results"] is None:
            return {"ambiguity": o["ambiguity"], "fail_closed": o["ambiguity"]}
        r = o["results"]
    if r.get("ambiguity"):
        return {"ambiguity": r["ambiguity"], "fail_closed": r["ambiguity"]}
    return {
        "source": r["assertion_source"],
        "kind": r["assertion_kind"],
        "authority": r["finding_authority"],
        "source_resolution": r["source_resolution"],
    }


@pytest.mark.parametrize("name", list(FROZEN))
def test_frozen_battery_hash_is_pinned(name):
    assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == FROZEN[name]


@pytest.mark.parametrize("name,case", _CASES, ids=[f"{n.split('_')[-1].split('.')[0]}:{c['id']}" for n, c in _CASES])
def test_frozen_case(name, case):
    text, target = case["text"], case["target"]
    if "expect" in case:
        got = _single(text, target)
        exp = case["expect"]
        if "fail_closed" in exp:
            assert got.get("fail_closed") == exp["fail_closed"], got
        else:
            for k, v in exp.items():
                assert got.get(k) == v, (case["id"], k, got)
    if "expect_multi" in case:
        ts, te = _target_bounds(text, target)
        r = aa.classify_target_assertions(text, target_start=ts, target_end=te)
        exp = case["expect_multi"]
        assert r["target_scope"] == exp["scope"], (case["id"], r["target_scope"])
        assert r["aggregate_authority"] is None
        assert len(r["assertions"]) == len(exp["assertions"]), (case["id"], len(r["assertions"]))
        for rec, e in zip(r["assertions"], exp["assertions"], strict=True):
            got = {
                "source": rec["assertion_source"],
                "kind": rec["assertion_kind"],
                "authority": rec["finding_authority"],
                "source_resolution": rec["source_resolution"],
                "covers_target": rec["covers_target"],
            }
            for k, v in e.items():
                assert got[k] == v, (case["id"], k, got)
    if "expect_occurrences" in case:
        results = aa.classify_all_occurrences(text, target["surface"])
        exp = case["expect_occurrences"]
        assert len(results) == len(exp), case["id"]
        for rec, e in zip(results, exp, strict=True):
            for k, v in e.items():
                key = {
                    "source": "assertion_source",
                    "kind": "assertion_kind",
                    "authority": "finding_authority",
                    "source_resolution": "source_resolution",
                }[k]
                assert rec[key] == v, (case["id"], k, rec[key])
    if "expect_ambiguity" in case:
        assert aa.classify_surface(text, target["surface"])["ambiguity"] == case["expect_ambiguity"]


def test_multi_api_never_collapses_to_one_authority():
    text = "Previous studies found X. We found Y."
    r = aa.classify_target_assertions(text, target_start=0, target_end=len(text))
    assert r["target_scope"] == "multi_assertion"
    assert r["aggregate_authority"] is None
    assert {a["finding_authority"] for a in r["assertions"]} == {"candidate", "authoritative"}


def test_singular_call_still_fails_closed_on_multi_assertion_target():
    text = "Previous studies found X. We found Y."
    r = aa.classify_assertion_authority(text, target_start=0, target_end=len(text))
    assert r["ambiguity"] == "target_crosses_assertion_boundary"
    assert r["finding_authority"] == "candidate"


def test_label_alone_grants_no_ownership():
    for text in ("Results: Scores increased.", "Specificity: Scores increased.", "Discussion: Scores increased."):
        r = aa.classify_assertion_authority(text, target_start=text.index("Scores"), target_end=len(text) - 1)
        assert r["assertion_source"] != "this_study" or r["source_resolution"] == "structural_results_label"


def test_structural_resolver_only_for_results_label():
    for label in ("Discussion", "Findings", "Outcomes", "Specificity", "Results and discussion", "Results section"):
        text = f"{label}: Scores increased."
        r = aa.classify_assertion_authority(text, target_start=text.index("Scores"), target_end=len(text) - 1)
        assert r["assertion_source"] == "unknown", label
        assert r["source_resolution"] == "unresolved", label


def test_run_in_label_fields_are_retained_for_audit():
    text = "Results: Scores increased."
    r = aa.classify_assertion_authority(text, target_start=text.index("Scores"), target_end=len(text) - 1)
    assert r["input"]["run_in_label_surface"] == "Results"
    assert r["input"]["run_in_label_normalized"] == "results"
    assert r["input"]["run_in_label_span"] == [0, 7]


def test_versions_are_unchanged_for_sufficiency_and_plan():
    # sufficiency/PLAN_VERSION are the frozen invariants this gate exists to protect. RULESET_VERSION is the
    # classifier's own local version and is explicitly allowed to move with each increment that changes its outputs
    # (I4-1c bumped it to "i4-1c.0"); it is checked here only for a non-empty i4-1 family value, not pinned to one string.
    assert se.SUFFICIENCY_SEMANTICS_VERSION == "sufficiency-semantics-v5"  # I4-2a integration
    assert pl.PLAN_VERSION == "answer-plan-step2-v4"
    assert aa.RULESET_VERSION.startswith("i4-1")


def test_outputs_are_json_safe_and_deterministic():
    text = "Results: Previous studies found that scores increased. We found that scores decreased."
    first = aa.classify_target_assertions(text, target_start=0, target_end=len(text))
    second = aa.classify_target_assertions(text, target_start=0, target_end=len(text))
    assert first == second
    json.dumps(first, allow_nan=False)
