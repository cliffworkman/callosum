"""PHASE 34 I4-1c gates: frozen batteries (run once, hashes pinned), the authority-veto invariants, source/kind parity.

The batteries are frozen BEFORE the I4-1c classifier change. Their sha256 values are pinned below, so an expectation
cannot be edited without this file failing. The generator that wrote them is i4_1c make_battery.py (not committed; see
PHASE34_I4_1C_NEGATED_AUTHORITY_RESULTS.md for its hash and the same rationale as I4-1b's generator).
"""

import hashlib
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.answer_plan import plan as pl

HERE = Path(__file__).resolve().parent
FROZEN = {
    "assertion_authority_i4_1c_preregistered.json": "7bf967d36916299f05fd671a3e2df63c3a5b4f13623c8ac7a9e1637b673fae21",
    "assertion_authority_i4_1c_holdout.json": "379f0bc26766f58ac9a0c1fec63ad04249668fb771cecbd79f468afe31cceded",
    "assertion_authority_i4_1c_twins.json": "edd487753e974d403828e40e5a04bcabde165fa7713578e5d2d9b3862aa8cef0",
}


def _load(name):
    return json.loads((HERE / name).read_bytes().decode("utf-8"))


_BATTERIES = {name: _load(name) for name in FROZEN}
_CASES = [(name, c) for name in FROZEN for c in _BATTERIES[name]["cases"]]


def _single(text, target, is_caption=False):
    if target.get("whole"):
        r = aa.classify_assertion_authority(text, target_start=0, target_end=len(text), is_caption=is_caption)
    else:
        o = aa.classify_surface(text, target["surface"], occurrence=target.get("occurrence"), is_caption=is_caption)
        if o["results"] is None:
            return {"ambiguity": o["ambiguity"], "fail_closed": o["ambiguity"]}
        r = o["results"]
    out = {
        "source": r["assertion_source"],
        "kind": r["assertion_kind"],
        "authority": r["finding_authority"],
        "source_resolution": r["source_resolution"],
        "authority_veto": r["authority_veto"],
    }
    if r.get("ambiguity"):
        out["ambiguity"] = r["ambiguity"]
        out["fail_closed"] = r["ambiguity"]
    return out


@pytest.mark.parametrize("name", list(FROZEN))
def test_frozen_battery_hash_is_pinned(name):
    assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == FROZEN[name]


@pytest.mark.parametrize("name,case", _CASES, ids=[f"{n.split('_')[-1].split('.')[0]}:{c['id']}" for n, c in _CASES])
def test_frozen_case(name, case):
    text, target = case["text"], case["target"]
    is_caption = case.get("is_caption", False)
    if "expect" in case:
        got = _single(text, target, is_caption)
        exp = case["expect"]
        if "fail_closed" in exp:
            assert got.get("fail_closed") == exp["fail_closed"], (case["id"], got)
        else:
            for k, v in exp.items():
                assert got.get(k) == v, (case["id"], k, got)
    if "expect_occurrences" in case:
        results = aa.classify_all_occurrences(text, target["surface"])
        exp = case["expect_occurrences"]
        assert len(results) == len(exp), case["id"]
        for rec, e in zip(results, exp, strict=True):
            got = {
                "source": rec["assertion_source"],
                "kind": rec["assertion_kind"],
                "authority": rec["finding_authority"],
                "authority_veto": rec["authority_veto"],
            }
            for k, v in e.items():
                assert got[k] == v, (case["id"], k, got)


def test_negated_result_predicate_keeps_source_and_kind_but_not_authority():
    text = "We did not find that scores increased."
    r = aa.classify_surface(text, "scores increased")["results"]
    assert r["assertion_source"] == "this_study"
    assert r["assertion_kind"] == "result"
    assert r["finding_authority"] == "candidate"
    assert r["authority_veto"] == "negated_result_predicate"


def test_absence_of_evidence_keeps_source_and_kind_but_not_authority():
    text = "We found no evidence that scores increased."
    r = aa.classify_surface(text, "scores increased")["results"]
    assert r["assertion_source"] == "this_study"
    assert r["assertion_kind"] == "result"
    assert r["finding_authority"] == "candidate"
    assert r["authority_veto"] == "absence_of_evidence"


def test_authority_veto_never_leaks_to_an_unvetoed_sibling_assertion():
    text = "We did not find that scores increased, but we found that revenue decreased."
    vetoed = aa.classify_surface(text, "scores increased")["results"]
    sibling = aa.classify_surface(text, "revenue decreased")["results"]
    assert vetoed["authority_veto"] == "negated_result_predicate"
    assert vetoed["finding_authority"] == "candidate"
    assert sibling["authority_veto"] is None
    assert sibling["finding_authority"] == "authoritative"


def test_results_label_resolver_does_not_override_the_veto():
    text = "Results: We did not find that scores increased."
    r = aa.classify_surface(text, "scores increased")["results"]
    assert r["source_resolution"] == "parsed"
    assert r["finding_authority"] == "candidate"
    assert r["authority_veto"] == "negated_result_predicate"


def test_prior_work_authority_is_unaffected_but_veto_is_still_recorded():
    text = "Previous studies did not find that scores increased."
    r = aa.classify_surface(text, "scores increased")["results"]
    assert r["assertion_source"] == "prior_work"
    assert r["finding_authority"] == "candidate"
    assert r["authority_veto"] == "negated_result_predicate"


def test_emphasis_did_find_is_not_negation():
    text = "We did find that scores increased."
    r = aa.classify_surface(text, "scores increased")["results"]
    assert r["finding_authority"] == "authoritative"
    assert r["authority_veto"] is None


def test_not_only_does_not_veto_solely_from_the_token_not():
    text = "We found not only that scores increased, but also that revenue decreased."
    r = aa.classify_surface(text, "scores increased")["results"]
    assert r["finding_authority"] == "authoritative"
    assert r["authority_veto"] is None


def test_interpretation_method_and_caption_kinds_are_never_vetoed():
    # The veto gate only ever evaluates when kind == result; it must never touch an already-candidate kind.
    r_interp = aa.classify_surface("We did not suggest that scores increased.", "scores increased")["results"]
    assert r_interp["assertion_kind"] == "interpretation"
    assert r_interp["authority_veto"] is None
    r_caption = aa.classify_surface("We found that scores increased.", "scores increased", is_caption=True)["results"]
    assert r_caption["authority_veto"] is None
    assert r_caption["finding_authority"] == "candidate"


def test_finding_authority_validates_authority_veto():
    with pytest.raises(ValueError):
        aa.finding_authority("this_study", "result", False, "not_a_real_veto")
    assert aa.finding_authority("this_study", "result", False, "negated_result_predicate") == "candidate"
    assert aa.finding_authority("this_study", "result", False, None) == "authoritative"


def test_versions_are_unchanged_for_sufficiency_and_plan():
    # sufficiency/PLAN_VERSION are the frozen invariants this gate exists to protect. RULESET_VERSION is the
    # classifier's own ruleset identity, explicitly allowed to move per increment (I4-1b's own test file already
    # relaxed this exact check for the same reason); I4-1f moves it again, to "i4-1f.0".
    assert se.SUFFICIENCY_SEMANTICS_VERSION == "sufficiency-semantics-v5"  # I4-2a integration
    assert pl.PLAN_VERSION == "answer-plan-step2-v4"
    assert aa.RULESET_VERSION.startswith("i4-1")


def test_outputs_are_json_safe_and_deterministic():
    text = "We did not find that scores increased, but we found no evidence that revenue increased."
    first = aa.classify_target_assertions(text, target_start=0, target_end=len(text))
    second = aa.classify_target_assertions(text, target_start=0, target_end=len(text))
    assert first == second
    json.dumps(first, allow_nan=False)
