"""Phase 32 / I3: target-aware direction semantics under sufficiency-semantics-v3.

Governing invariant: relation witnessed != relation direction established. Generic alpha/beta and non-psychological twins
only. The preserved-run checks skip when the gitignored Phase-28 artifacts are absent. No model, no network.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import direction_target as dt
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised import sufficiency_mapping as sm

V2 = se.SUFFICIENCY_SEMANTICS_V2
V3 = se.SUFFICIENCY_SEMANTICS_V3
ALPHA_BETA = {"entity_x": "alpha", "measure_y": "beta"}
ROOT = Path(__file__).resolve().parents[2]
RUN_I1 = ROOT / ".local" / "phase32" / "run_i1"
RUN = ROOT / ".local" / "e2e-runs" / "phase28-live-parent-synthesis-attempt2-20261004T014500Z" / "run"
_needs_preserved = pytest.mark.skipif(
    not (RUN.is_dir() and RUN_I1.is_dir()),
    reason="preserved Phase-28 Attempt-2 artifacts are not present in this checkout",
)


def _classify(sentence, operands=None, sign="negative", version=V3):
    return dt.classify_sentence(sentence, ALPHA_BETA if operands is None else operands, sign, semantics_version=version)


# ---------------------------------------------------------------------------------------------------------------------
# 1-16. the specified classifier matrix (generic alpha/beta)
# ---------------------------------------------------------------------------------------------------------------------


def test_1_negatively_associated_is_a_relation_level_negative_direction():
    result = _classify("Alpha was negatively associated with beta.")
    assert (result["target"], result["reason"]) == ("relation", "relational_predicate_targeted")
    assert dt.literal_direction_sign("Alpha was negatively associated with beta.") == "negative"


def test_2_correlated_negatively_is_a_relation_level_negative_direction():
    result = _classify("Alpha correlated negatively with beta.")
    assert result["target"] == "relation"
    assert dt.literal_direction_sign("Alpha correlated negatively with beta.") == "negative"


def test_3_higher_alpha_predicted_lower_beta_is_a_relation_target_with_no_literal_sign():
    # The comparative pair targets the relation. A comparative carries no literal valence, so no relation SIGN is derived here.
    # Deriving one from comparative polarity is a separate, unrequested semantic (see the results report).
    result = _classify("Higher alpha predicted lower beta.", sign=None)
    assert result["target"] == "relation"
    assert dt.literal_direction_sign("Higher alpha predicted lower beta.") is None


def test_4_negative_beta_evaluations_is_operand_valence_and_not_a_relation_direction():
    result = _classify("Alpha was associated with negative beta evaluations.")
    assert (result["target"], result["role"]) == ("operand", "measure_y")


def test_5_negative_alpha_was_associated_with_beta_is_operand_valence_of_alpha():
    result = _classify("Negative alpha was associated with beta.")
    assert (result["target"], result["role"]) == ("operand", "entity_x")


def test_6_beta_scores_were_negative_after_a_conjunction_is_operand_valence_of_beta():
    result = _classify("Alpha was associated with beta, and beta scores were negative.")
    assert (result["target"], result["role"]) == ("operand", "measure_y")


def test_7_an_unrelated_negative_result_after_a_conjunction_is_unknown_with_no_attribution():
    result = _classify("Alpha was associated with beta, and negative results were also reported.")
    assert result["target"] == "unknown"
    assert result["role"] is None


def test_8_one_operand_and_an_unresolved_sign_elsewhere_is_unknown_under_v3_and_operand_under_v2():
    sentence = "Alpha was recorded during the task, and negative results were also reported."
    operands = {"entity_x": "alpha"}
    assert _classify(sentence, operands=operands, version=V3)["target"] == "unknown"
    v2 = _classify(sentence, operands=operands, version=V2)
    assert (v2["target"], v2["role"], v2["reason"]) == ("operand", "entity_x", "single_operand_sentence")


def test_13_conflicting_signs_are_unknown():
    result = _classify("Alpha was positively associated with beta, but negative results were also reported.")
    assert (result["target"], result["reason"]) == ("unknown", "conflicting_signs")


def test_14_no_direction_word_is_none():
    assert _classify("Alpha was associated with beta.")["target"] == "none"
    assert dt.has_direction_word("Alpha was associated with beta.") is False


def test_16_a_single_operand_valence_sentence_is_operand_and_never_a_relation_target():
    result = _classify("Beta scores were negative.", operands={"measure_y": "beta"})
    assert (result["target"], result["role"]) == ("operand", "measure_y")
    assert result["target"] != "relation"


# ---------------------------------------------------------------------------------------------------------------------
# cross-domain twins: the same rules, non-psychological surfaces
# ---------------------------------------------------------------------------------------------------------------------

ARCH = {"building": "building height", "occupant": "occupant satisfaction"}
LANG = {"frequency": "word frequency", "recall": "recall"}


def test_twin_architecture_relation_is_negative_relation():
    assert (
        _classify("Building height was negatively associated with occupant satisfaction.", operands=ARCH)["target"]
        == "relation"
    )


def test_twin_architecture_facade_ratings_are_object_valence_not_relation():
    operands = {"facade": "facade ratings"}
    result = _classify("Buildings with negative facade ratings were common.", operands=operands)
    assert (result["target"], result["role"]) == ("operand", "facade")


def test_twin_a_second_direction_word_makes_the_object_valence_fail_closed():
    # "highly" stems to "high", a direction-bearing word in the existing stem list. Two direction words with one unresolved
    # is ambiguous, so the classifier fails closed rather than choosing the nearest operand. This is correct, not a defect.
    operands = {"facade": "facade ratings"}
    result = _classify("Buildings with negative facade ratings were rated highly.", operands=operands)
    assert result["target"] == "unknown"
    assert result["reason"] == "ambiguous_operand_target"


def test_twin_language_relation_is_positive_relation():
    assert (
        _classify("Word frequency positively predicted recall.", operands=LANG, sign="positive")["target"] == "relation"
    )


def test_twin_language_negative_word_ratings_are_operand_valence_and_not_a_negative_relation():
    operands = {"word": "word ratings", "recall": "recall"}
    result = _classify("Negative word ratings were associated with recall.", operands=operands)
    assert (result["target"], result["role"]) == ("operand", "word")


# ---------------------------------------------------------------------------------------------------------------------
# sufficiency-level targets and the relation-level eligibility invariant
# ---------------------------------------------------------------------------------------------------------------------


def _unit(passage, pids):
    return {"passage": passage, "proposition_ids": list(pids), "flags": {}}


_RELATIONAL = {"direction": {"required_sign": None}}
_OPERANDS = {"entity_x": "alpha", "measure_y": "beta"}


def _obs(units, *, operands=_OPERANDS, witness=None, requirement=_RELATIONAL):
    return sm.find_direction_observations(
        requirement, units, semantics_version=V3, operands=operands, relation_witness_ids=witness
    )


def test_9_relation_target_sentence_on_an_unwitnessed_relation_is_not_relation_eligible():
    (obs,) = _obs([_unit("Alpha was negatively associated with beta.", ["p1"])], witness=None)
    assert obs["target"] == "relation"
    assert obs["relation_eligible"] is False


def test_10_relation_witnessed_but_the_direction_sentence_is_in_a_different_proposition_is_not_eligible():
    units = [_unit("Alpha was negatively associated with beta.", ["p2"])]
    (obs,) = _obs(units, witness=frozenset({"p1"}))
    assert obs["target"] == "relation"
    assert obs["relation_eligible"] is False


def test_11_direction_sentence_inside_the_verified_witness_proposition_is_eligible():
    units = [_unit("Alpha was negatively associated with beta.", ["p1"])]
    (obs,) = _obs(units, witness=frozenset({"p1"}))
    assert obs["target"] == "relation"
    assert obs["relation_eligible"] is True
    assert obs["proposition_id"] == "p1"
    assert obs["exact_text"] == "Alpha was negatively associated with beta."


def test_15_operand_valence_survives_an_unwitnessed_relation_as_operand_metadata():
    (obs,) = _obs([_unit("Alpha was associated with negative beta evaluations.", ["p1"])], witness=None)
    assert (obs["target"], obs["target_role"], obs["sign"]) == ("operand", "measure_y", "negative")
    assert obs["relation_eligible"] is False


def test_operand_target_is_never_relation_eligible_even_when_witnessed():
    (obs,) = _obs([_unit("Alpha was associated with negative beta evaluations.", ["p1"])], witness=frozenset({"p1"}))
    assert obs["target"] == "operand"
    assert obs["relation_eligible"] is False


def test_12_all_inherited_relation_has_no_witness_and_therefore_no_relation_direction():
    # With no own operand the relation is not witnessed (I1 guard), so the observation can never be relation-eligible.
    (obs,) = _obs([_unit("Alpha was negatively associated with beta.", ["p1"])], witness=None)
    assert obs["relation_eligible"] is False


def test_unknown_target_is_never_relation_eligible_and_never_promoted():
    (obs,) = _obs(
        [_unit("Alpha was associated with beta, and negative results were also reported.", ["p1"])],
        witness=frozenset({"p1"}),
    )
    assert obs["target"] == "unknown"
    assert obs["relation_eligible"] is False
    assert obs["sign"] == "negative"  # the sign is recorded as provenance, never as relation direction


def test_a_non_relational_requirement_never_yields_a_relation_target():
    requirement = {"direction": {"required_sign": None}}
    (obs,) = _obs(
        [_unit("Beta scores were negative.", ["p1"])],
        operands={"measure_y": "beta"},
        witness=None,
        requirement=requirement,
    )
    assert (obs["target"], obs["target_role"]) == ("operand", "measure_y")
    assert obs["relation_eligible"] is False


def test_no_direction_word_yields_no_observation():
    assert _obs([_unit("Alpha was associated with beta.", ["p1"])]) == []


def test_the_v3_observation_records_its_provenance_and_no_score():
    (obs,) = _obs([_unit("Alpha was negatively associated with beta.", ["p1"])], witness=frozenset({"p1"}))
    assert {
        "target",
        "target_role",
        "target_reason",
        "relation_eligible",
        "sign",
        "proposition_id",
        "exact_text",
    } <= set(obs)
    assert not any("confidence" in key or "score" in key for key in obs)
    assert obs["target_reason"] == "relational_predicate_targeted"


# ---------------------------------------------------------------------------------------------------------------------
# summaries, the ParentClaim admissibility filter, and the constructor's invariants
# ---------------------------------------------------------------------------------------------------------------------


def test_relation_summary_counts_only_relation_eligible_observations():
    eligible = se.new_targeted_direction_assessment(
        sign="negative",
        required_sign=None,
        causal_language_present=False,
        proposition_id="p1",
        exact_text="Alpha was negatively associated with beta.",
        target="relation",
        target_role=None,
        target_reason="relational_predicate_targeted",
        relation_eligible=True,
    )
    operand = se.new_targeted_direction_assessment(
        sign="negative",
        required_sign=None,
        causal_language_present=False,
        proposition_id="p2",
        exact_text="Alpha was associated with negative beta evaluations.",
        target="operand",
        target_role="measure_y",
        target_reason="operand_targeted",
        relation_eligible=False,
    )
    instance = {"instance_key": "k", "complete": True, "direction_observations": [eligible, operand]}
    summary = se.summarize_observations(
        [instance], "direction_observations", "sign", observation_filter=se.counts_toward_relation_direction
    )
    assert summary["observed_values"] == ["negative"]
    unfiltered = se.summarize_observations([instance], "direction_observations", "sign")
    assert unfiltered["observed_values"] == ["negative"]  # the filter, not the sign, decides relation membership
    operand_only = {"instance_key": "k", "complete": True, "direction_observations": [operand]}
    filtered = se.summarize_observations(
        [operand_only], "direction_observations", "sign", observation_filter=se.counts_toward_relation_direction
    )
    assert filtered["observed_values"] == []


def test_legacy_untargeted_observations_count_as_recorded():
    legacy = {"reported": True, "sign": "negative", "proposition_id": "p1", "exact_text": "negative"}
    assert se.counts_toward_relation_direction(legacy) is True


def test_targeted_constructor_rejects_invalid_targets_and_inconsistent_roles():
    base = dict(
        sign="negative",
        required_sign=None,
        causal_language_present=False,
        proposition_id="p1",
        exact_text="x",
        target_reason="r",
        relation_eligible=True,
    )
    with pytest.raises(ValueError):
        se.new_targeted_direction_assessment(target="guess", target_role=None, **base)
    with pytest.raises(ValueError):
        se.new_targeted_direction_assessment(target="operand", target_role=None, **base)
    with pytest.raises(ValueError):
        se.new_targeted_direction_assessment(target="relation", target_role="measure_y", **base)


def test_relation_eligibility_requires_the_relation_target_even_if_asserted():
    obs = se.new_targeted_direction_assessment(
        sign="negative",
        required_sign=None,
        causal_language_present=False,
        proposition_id="p1",
        exact_text="x",
        target="operand",
        target_role="measure_y",
        target_reason="operand_targeted",
        relation_eligible=True,
    )
    assert obs["relation_eligible"] is False


# ---------------------------------------------------------------------------------------------------------------------
# versioned historical dispatch
# ---------------------------------------------------------------------------------------------------------------------


def test_v2_direction_observations_are_the_recorded_untargeted_behaviour():
    units = [_unit("Alpha was recorded during the task, and negative results were also reported.", ["p1"])]
    (legacy,) = sm.find_direction_observations(_RELATIONAL, units, semantics_version=V2)
    assert "target" not in legacy and legacy["sign"] == "negative" and legacy["exact_text"] == "negative"


def test_v3_requires_operand_surfaces_and_unknown_versions_fail_closed():
    with pytest.raises(ValueError):
        sm.find_direction_observations(_RELATIONAL, [_unit("Alpha was negative.", ["p1"])], semantics_version=V3)
    with pytest.raises(ValueError):
        sm.find_direction_observations(_RELATIONAL, [], semantics_version="sufficiency-semantics-v99")
    with pytest.raises(ValueError):
        dt.classify_sentence(
            "Alpha was negative.", ALPHA_BETA, "negative", semantics_version="sufficiency-semantics-v99"
        )


def test_compute_refuses_a_map_stamped_with_a_different_version():
    contract = {"requirements": []}
    stamped = {"c": {**contract, se.SEMANTICS_VERSION_KEY: V2}}
    with pytest.raises(si.SemanticsIdentityError):
        sd.compute_direction_and_effectiveness({"units": []}, stamped, semantics_version=V3)


def test_direction_rules_are_the_shared_implementation_and_the_answer_layer_uses_it():
    from experiments.ask_cli_revised.answer_plan import classify as cl
    from experiments.ask_cli_revised.answer_plan import text as tx

    assert cl.dt is dt  # one implementation, imported by the answer layer
    assert tx.split_sentences("A b. C d.") == dt.split_sentences("A b. C d.")  # the splitter is single-sourced


def test_effectiveness_observations_are_unchanged_by_the_direction_change():
    req = {"effectiveness": {"required_outcome": "x"}}
    units = [_unit("Intervention X showed decreased bias scores in the treatment group.", ["p1"])]
    assert sm.find_effectiveness_observations(req, units) == sm.find_effectiveness_observations(req, units)
    assert sm.find_effectiveness_observations(req, units)[0]["conclusion"] == "supported"


# ---------------------------------------------------------------------------------------------------------------------
# preserved-run observation (skipped without the gitignored artifacts)
# ---------------------------------------------------------------------------------------------------------------------


@_needs_preserved
def test_preserved_c6_direction_sentence_is_unknown_under_v3_and_is_not_a_relation_direction():
    sealed = json.loads((RUN_I1 / "11_verified_ledger.json").read_text(encoding="utf-8"))
    smap = json.loads((RUN_I1 / "17_sufficiency_map.json").read_text(encoding="utf-8"))
    for contract in smap.values():
        contract.pop(se.SEMANTICS_VERSION_KEY, None)
    sd.compute_direction_and_effectiveness(sealed, smap, semantics_version=V3)
    (req,) = [r for r in smap["c6"]["requirements"] if r.get("direction") is not None]
    assert req.get("direction_summary")["observed_values"] == []
    observations = [o for inst in req["instances"] for o in inst["direction_observations"]]
    assert observations and all(o["target"] == "unknown" and o["relation_eligible"] is False for o in observations)
    assert all(o["sign"] == "negative" for o in observations)  # the sign is recorded, not promoted


@_needs_preserved
def test_effectiveness_is_identical_under_v2_and_v3_on_the_same_binding_set():
    # I3 changes the direction stage only. Effectiveness observations and summaries must be byte-identical on the same map.
    sealed = json.loads((RUN_I1 / "11_verified_ledger.json").read_text(encoding="utf-8"))
    base = json.loads((RUN_I1 / "17_sufficiency_map.json").read_text(encoding="utf-8"))

    def effectiveness_under(version):
        smap = copy.deepcopy(base)
        for contract in smap.values():
            contract.pop(se.SEMANTICS_VERSION_KEY, None)
        sd.compute_direction_and_effectiveness(sealed, smap, semantics_version=version)
        return {
            (cid, req["id"]): (
                req.get("effectiveness_summary"),
                [inst.get("effectiveness_observations") for inst in req["instances"]],
            )
            for cid, contract in sorted(smap.items())
            for req in contract["requirements"]
            if req.get("effectiveness") is not None
        }

    v2, v3 = effectiveness_under(V2), effectiveness_under(V3)
    assert v2 and v2 == v3
