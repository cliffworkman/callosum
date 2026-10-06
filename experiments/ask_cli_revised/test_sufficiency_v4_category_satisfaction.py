"""Phase 33 / I2-2: v4 category satisfaction, target-scoped terminality, and version parity.

Offline and deterministic: no model, no network, no E2E. Synthetic fixtures use generic terms only (alpha, beta,
gamma) and no domain vocabulary. Expectations follow the I2-1/I2-1b classifier contract and the I2-2 brief.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from experiments.ask_cli_revised import category_polarity as cp
from experiments.ask_cli_revised import direction_target as dtg
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt

HERE = Path(__file__).resolve().parent
V3 = se.SUFFICIENCY_SEMANTICS_V3
V4 = se.SUFFICIENCY_SEMANTICS_V4
POS, NUL, MEN, UNK = cp.POSITIVE, cp.NULL, cp.MENTIONED, cp.UNKNOWN
DEFAULT_TERMS = ("alpha", "beta")
REQUIREMENT_ID = "c#cat"
CHILD = "c3"


def _unit(unit_id, passage):
    return {
        "unit_id": unit_id,
        "paper_id": 1,
        "passage": passage,
        "proposition_ids": [f"{unit_id}-p"],
        "flags": oe.passage_flags(passage),
        "attached_children": [],
        "proposition_anchor": {},
    }


def _category_requirement(terms=DEFAULT_TERMS):
    spec = se.new_role_spec("cat", "category", "explicit_category_terms", requested_category_terms=list(terms))
    completion = se.new_role_completion(required_roles=["cat"])
    return se.new_requirement(
        REQUIREMENT_ID, "cardinality", {"cat": spec}, completion, "all_requested_categories", multi_instance=True
    )


def _map(units, terms=DEFAULT_TERMS, version=V4):
    return sm.map_cardinality_requirement(_category_requirement(terms), units, semantics_version=version)


def _instance(result, key):
    return next(i for i in result["instances"] if i["instance_key"] == key)


def _contract(units, terms=DEFAULT_TERMS):
    req = _map(units, terms)
    return {CHILD: se.new_contract(CHILD, [req])}, req


def _semantic(targets):
    return {tid: t for tid, t in targets.items() if t["reason"] == "semantic_goal_unsatisfied"}


def _completed(initial, log):
    outcomes = srt.structured_search_outcomes(srt.search_obligations(initial, initial, semantics_version=V4), log)
    return frozenset(
        tid for tid, state in outcomes[REQUIREMENT_ID]["target_states"].items() if state["state"] == "completed"
    )


def _log_row(target_id, reason_code):
    return {"gap": {"_recovery_target_id": target_id}, "reason_code": reason_code}


# ---------------------------------------------------------------------------------------------------------------------
# Synthetic satisfaction (A-J). Positive observation is the only satisfying polarity.
# ---------------------------------------------------------------------------------------------------------------------

POSITIVE_SENTENCE = "Alpha significantly predicted outcome."
NULL_SENTENCE = "Alpha was not significant."
MENTION_SENTENCE = "Alpha was measured in the sample."
UNKNOWN_SENTENCE = "The treatment did not increase alpha."


def test_a_positive_only_satisfies_the_category():
    result = _map([_unit("U1", POSITIVE_SENTENCE)])
    alpha = _instance(result, "alpha")
    assert alpha["complete"] is True
    assert alpha["state"] == "filled"
    assert alpha["category_observations"][0]["observation_polarity"] == POS


def test_b_null_only_does_not_satisfy_and_is_bound_not_filled_as_presence():
    result = _map([_unit("U1", NULL_SENTENCE)])
    alpha = _instance(result, "alpha")
    assert alpha["complete"] is False
    assert alpha["state"] == "partially_filled"
    assert alpha["category_observations"][0]["observation_polarity"] == NUL
    assert alpha["role_bindings"]["cat"]["state"] == "filled"  # observed, but presence not established


def test_c_null_then_positive_for_the_same_term_satisfies_regardless_of_unit_order():
    result = _map([_unit("U1", NULL_SENTENCE), _unit("U2", POSITIVE_SENTENCE)])
    alpha = _instance(result, "alpha")
    assert alpha["complete"] is True
    assert len(alpha["category_observations"]) == 2
    assert alpha["role_bindings"]["cat"]["provenance"]["observation_polarity"] == POS


def test_d_positive_then_null_for_the_same_term_satisfies_and_keeps_the_null():
    result = _map([_unit("U1", POSITIVE_SENTENCE), _unit("U2", NULL_SENTENCE)])
    alpha = _instance(result, "alpha")
    assert alpha["complete"] is True
    assert [o["observation_polarity"] for o in alpha["category_observations"]] == [POS, NUL]
    assert alpha["role_bindings"]["cat"]["provenance"]["observation_polarity"] == POS


def test_e_mentioned_only_does_not_satisfy():
    result = _map([_unit("U1", MENTION_SENTENCE)])
    alpha = _instance(result, "alpha")
    assert alpha["complete"] is False
    assert alpha["category_observations"][0]["observation_polarity"] == MEN


def test_f_unknown_only_does_not_satisfy():
    result = _map([_unit("U1", UNKNOWN_SENTENCE)])
    alpha = _instance(result, "alpha")
    assert alpha["complete"] is False
    assert alpha["category_observations"][0]["observation_polarity"] == UNK


def test_g_absent_term_is_missing_not_found_with_no_observations():
    result = _map([_unit("U1", "Gamma significantly predicted outcome.")])
    alpha = _instance(result, "alpha")
    assert alpha["category_observations"] == []
    assert alpha["state"] == "missing"
    assert alpha["reason"] == "not_found"


def test_h_one_positive_one_null_category_leaves_the_requirement_not_filled():
    result = _map([_unit("U1", POSITIVE_SENTENCE), _unit("U2", "Beta was not significant.")])
    assert _instance(result, "alpha")["complete"] is True
    assert _instance(result, "beta")["complete"] is False
    assert result["state"] != "filled"


def test_i_every_category_positive_fills_the_requirement():
    result = _map([_unit("U1", POSITIVE_SENTENCE), _unit("U2", "Beta significantly predicted outcome.")])
    assert result["state"] == "filled"
    assert result["reason"] is None


def test_j_a_v4_category_instance_without_observations_fails_closed():
    with pytest.raises(ValueError):
        se.category_goal_satisfied({"role_bindings": {}})


# ---------------------------------------------------------------------------------------------------------------------
# Target-scoped terminality (1-8). The completed set comes from the same structured-outcome path the engine uses.
# ---------------------------------------------------------------------------------------------------------------------


def test_1_null_only_target_with_no_log_row_is_not_attempted_and_emitted():
    contract, _ = _contract([_unit("U1", NULL_SENTENCE)])
    initial = srt.compute_recovery_targets(contract, {}, semantics_version=V4)
    semantic = _semantic(initial)
    assert len(semantic) == 1
    (tid,) = semantic
    outcomes = srt.structured_search_outcomes(srt.search_obligations(initial, initial, semantics_version=V4), [])
    assert outcomes[REQUIREMENT_ID]["target_states"][tid]["state"] == "not_attempted"
    after = srt.compute_recovery_targets(contract, {}, semantics_version=V4, completed_target_ids=frozenset())
    assert tid in after


def test_2_completed_no_new_evidence_suppresses_the_semantic_target():
    contract, _ = _contract([_unit("U1", NULL_SENTENCE)])
    initial = srt.compute_recovery_targets(contract, {}, semantics_version=V4)
    (tid,) = _semantic(initial)
    completed = _completed(initial, [_log_row(tid, "recovery_no_new_evidence")])
    after = srt.compute_recovery_targets(contract, {}, semantics_version=V4, completed_target_ids=completed)
    assert tid not in after


def test_3_completed_round_that_added_evidence_without_a_positive_is_still_terminal_for_this_run():
    # Documented behaviour, flagged for review: one completed round bounds the semantic obligation for this run,
    # even if the added evidence is still only a null. The binding stays unsatisfied (asserted), and no further
    # semantic target is generated for it.
    contract, req = _contract([_unit("U1", NULL_SENTENCE)])
    initial = srt.compute_recovery_targets(contract, {}, semantics_version=V4)
    (tid,) = _semantic(initial)
    completed = _completed(initial, [_log_row(tid, "recovery_added_evidence")])
    after = srt.compute_recovery_targets(contract, {}, semantics_version=V4, completed_target_ids=completed)
    assert tid not in after
    assert _instance(req, "alpha")["complete"] is False


def test_4_a_positive_added_removes_the_target_regardless_of_search_state():
    contract, req = _contract([_unit("U1", NULL_SENTENCE), _unit("U2", POSITIVE_SENTENCE)])
    after = srt.compute_recovery_targets(contract, {}, semantics_version=V4, completed_target_ids=frozenset())
    assert _semantic(after) == {}
    assert _instance(req, "alpha")["complete"] is True


def test_5_sibling_terms_are_independent_under_target_scoped_completion():
    contract, _ = _contract([_unit("U1", NULL_SENTENCE), _unit("U2", "Beta was not significant.")])
    initial = srt.compute_recovery_targets(contract, {}, semantics_version=V4)
    semantic = _semantic(initial)
    assert len(semantic) == 2
    alpha_tid = next(tid for tid, t in semantic.items() if "alpha" in json.dumps(t["scope"]))
    beta_tid = next(tid for tid in semantic if tid != alpha_tid)
    completed = _completed(initial, [_log_row(alpha_tid, "recovery_no_new_evidence")])
    after = srt.compute_recovery_targets(contract, {}, semantics_version=V4, completed_target_ids=completed)
    assert alpha_tid not in after
    assert beta_tid in after


def test_6_a_target_first_exposed_by_the_raw_final_map_is_recoverable_under_v4_only():
    initial_contract, _ = _contract([])
    initial = srt.compute_recovery_targets(initial_contract, {}, semantics_version=V4)
    assert _semantic(initial) == {}
    final_contract, _ = _contract([_unit("U1", NULL_SENTENCE)])
    raw_final = srt.compute_recovery_targets(final_contract, {}, semantics_version=V4)
    (tid,) = _semantic(raw_final)
    assert tid not in srt.search_obligations(initial, raw_final, semantics_version=V3)
    obligations = srt.search_obligations(initial, raw_final, semantics_version=V4)
    assert tid in obligations
    outcomes = srt.structured_search_outcomes(obligations, [])
    assert outcomes[REQUIREMENT_ID]["target_states"][tid]["state"] == "not_attempted"


def test_7_a_completed_mention_or_unknown_target_is_suppressed_like_a_null():
    for sentence in (MENTION_SENTENCE, UNKNOWN_SENTENCE):
        contract, _ = _contract([_unit("U1", sentence)])
        initial = srt.compute_recovery_targets(contract, {}, semantics_version=V4)
        (tid,) = _semantic(initial)
        completed = _completed(initial, [_log_row(tid, "recovery_no_new_evidence")])
        after = srt.compute_recovery_targets(contract, {}, semantics_version=V4, completed_target_ids=completed)
        assert tid not in after, sentence


def test_8_zero_evidence_is_unchanged_and_never_becomes_a_semantic_target():
    contract, req = _contract([])
    initial = srt.compute_recovery_targets(contract, {}, semantics_version=V4)
    assert _semantic(initial) == {}
    assert {t["reason"] for t in initial.values()} == {"missing"}
    still = srt.compute_recovery_targets(contract, {}, semantics_version=V4, completed_target_ids=frozenset(initial))
    assert set(still) == set(initial)  # completion never suppresses a non-semantic zero-evidence target
    assert srt.is_zero_evidence_terminal(req) is False  # permission is not granted for this requirement


def test_8b_a_bound_null_is_never_genuinely_empty_or_zero_evidence_terminal():
    _, req = _contract([_unit("U1", NULL_SENTENCE)])
    assert srt.is_genuinely_empty(req) is False
    assert srt.is_zero_evidence_terminal(req) is False


# ---------------------------------------------------------------------------------------------------------------------
# Version identity, v3 no-classifier-call, and v4 parity for non-category subsystems.
# ---------------------------------------------------------------------------------------------------------------------


def test_version_identity_is_v4_with_v3_historical_and_supported():
    assert se.SUFFICIENCY_SEMANTICS_VERSION == V4
    assert V3 in se.HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS
    assert V4 not in se.HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS
    assert V4 in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS
    assert V3 in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS


def test_v3_category_mapping_never_calls_the_classifier(monkeypatch):
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        raise AssertionError("the v3 path must not classify category observations")

    monkeypatch.setattr(cp, "classify_category_observation", spy)
    units = [_unit("U1", NULL_SENTENCE), _unit("U2", POSITIVE_SENTENCE)]
    result = sm.map_cardinality_requirement(_category_requirement(), units, semantics_version=V3)
    assert calls == []
    assert _instance(result, "alpha")["complete"] is True  # v3 first-match: the null binding alone counts


def test_v4_category_mapping_does_call_the_classifier(monkeypatch):
    calls = []
    real = cp.classify_category_observation

    def counting(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(cp, "classify_category_observation", counting)
    _map([_unit("U1", NULL_SENTENCE)])
    assert len(calls) >= 1


def test_v4_dispatch_for_non_category_paths_is_the_v3_rule():
    assert dtg._SINGLE_OPERAND_FALLBACK[V4] == dtg._SINGLE_OPERAND_FALLBACK[V3]
    assert rw._REFERENT_CONTAINMENT[V4] is rw._REFERENT_CONTAINMENT[V3]


def test_v4_leaves_a_non_category_requirement_identical_to_v3():
    relation = se.new_role_spec("relation", "relation", "achieved_outcome_predicate")
    requirement = se.new_requirement(
        "c1#atom", "atomic", {"relation": relation}, se.new_role_completion(required_roles=["relation"]), "exists"
    )
    assert se.is_category_requirement(requirement) is False
    requirement["instances"] = [se.new_instance("i1")]
    v3 = se.recompute_requirement(requirement, semantics_version=V3)
    v4 = se.recompute_requirement(requirement, semantics_version=V4)
    assert v3 == v4
    contract = {"c1": se.new_contract("c1", [requirement])}
    assert srt.compute_recovery_targets(contract, {}, semantics_version=V3) == srt.compute_recovery_targets(
        contract, {}, semantics_version=V4
    )


def test_the_classifier_vocabulary_carries_no_question_or_model_identifiers():
    source = (HERE / "category_polarity.py").read_text(encoding="utf-8")
    assert not re.search(r"\bq_[a-z]+\b|aib_hier|sufficiency_contract", source)
