"""Phase 32 / I1b: direction target classification and the fail-closed attachment guard.

Generic alpha/beta fixtures only. Expected values are written by hand from the specification (relation direction versus
operand valence versus unknown), not read back from the classifier. The preserved-run check is the only place a
preserved identifier could appear, and it skips when the gitignored artifacts are absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised.answer_plan import direction_target as dt
from experiments.ask_cli_revised.test_answer_plan import (
    binding,
    build,
    instance,
    one_node,
    prop,
    requirement,
)

ALPHA_BETA = {"entity_x": "alpha", "measure_y": "beta"}


def _classify(sentence: str, sign: str | None = "negative", operands: dict | None = None) -> dict:
    return dt.classify_sentence(sentence, operands or ALPHA_BETA, sign)


# ---------------------------------------------------------------------------------------------------------------------
# the eight specified classifier cases
# ---------------------------------------------------------------------------------------------------------------------


def test_case1_alpha_was_negatively_associated_with_beta_is_a_relation_level_negative_direction():
    result = _classify("Alpha was negatively associated with beta.")
    assert result["target"] == "relation"


def test_case2_higher_alpha_predicted_lower_beta_is_a_relation_level_directional_association():
    # No literal valence word, so the sign is unconstrained (None). The comparatives pair across the relation.
    result = _classify("Higher alpha predicted lower beta.", sign=None)
    assert result["target"] == "relation"


def test_case3_negative_beta_evaluations_is_beta_valence_and_not_a_negative_relation():
    result = _classify("Alpha was associated with negative beta evaluations.")
    assert result["target"] == "operand"
    assert result["role"] == "measure_y"


def test_case4_beta_scores_were_negative_is_beta_valence_with_relation_direction_unknown():
    result = _classify("Alpha was associated with beta, and beta scores were negative.")
    assert result["target"] == "operand"
    assert result["role"] == "measure_y"
    assert result["target"] != "relation"


def test_case5_negative_alpha_was_associated_with_beta_is_alpha_valence_with_relation_direction_unknown():
    result = _classify("Negative alpha was associated with beta.")
    assert result["target"] == "operand"
    assert result["role"] == "entity_x"


def test_case6_a_direction_word_not_tied_to_the_relation_is_not_a_relation_direction():
    result = _classify(
        "Alpha was associated with beta in the first session, and negative results were reported in the methods."
    )
    assert result["target"] == "unknown"
    assert result["target"] != "relation"


def test_case8_ambiguous_opposite_signs_fail_closed():
    result = _classify("Alpha was positively associated with beta, and negatively with beta.")
    assert result["target"] == "unknown"
    assert result["reason"] == "conflicting_signs"


# ---------------------------------------------------------------------------------------------------------------------
# additional classifier behaviour
# ---------------------------------------------------------------------------------------------------------------------


def test_a_sentence_without_the_requested_direction_word_is_none():
    assert _classify("Alpha was associated with beta.", sign="negative")["target"] == "none"


def test_a_single_realised_operand_keeps_its_attribution_for_valence():
    # The preserved c6 pattern: one operand realised in the sentence, the sign is not tied to any relation.
    result = _classify(
        "Explicit negative attitudes were found with the beta questionnaire.",
        operands={"measure_y": "beta questionnaire"},
    )
    assert result["target"] == "operand"
    assert result["role"] == "measure_y"
    assert result["reason"] == "single_operand_sentence"


def test_a_relation_word_after_the_operands_without_adjacent_direction_is_unknown():
    # The direction word is not adjacent to the relational cue, and a cue alone never makes it a relation direction.
    result = _classify("Alpha and beta were associated, and negative findings followed.")
    assert result["target"] != "relation"


def test_classification_is_deterministic_and_has_no_score_field():
    sentence = "Alpha was negatively associated with beta."
    first, second = _classify(sentence), _classify(sentence)
    assert first == second
    assert set(first) == {"target", "role", "reason"}


def test_operand_surfaces_are_matched_case_insensitively_and_by_occurrence():
    result = _classify("ALPHA was negatively associated with BETA.", operands=ALPHA_BETA)
    assert result["target"] == "relation"


def test_a_valence_sentence_never_classifies_as_a_relation_direction():
    for sentence in (
        "Alpha was associated with negative beta evaluations.",
        "Alpha was associated with beta, and beta scores were negative.",
        "Negative alpha was associated with beta.",
    ):
        assert _classify(sentence)["target"] == "operand", sentence


# ---------------------------------------------------------------------------------------------------------------------
# answer-layer integration: attachment, valence and fail-closed suppression reach the claim records
# ---------------------------------------------------------------------------------------------------------------------

_SUMMARY = {
    "observed_values": ["negative"],
    "consensus_value": "negative",
    "has_within_instance_conflict": False,
    "has_across_instance_heterogeneity": False,
    "complete_instance_keys": ["k1"],
    "instance_keys_with_observations": ["k1"],
    "instance_keys_missing_observations": [],
    "conflicted_instance_keys": [],
}


def _direction_plan(props, *, inherited_pid="p0", own_pid="p1", direction_pid="p1"):
    spans = [{"paper_id": 1, "span_id": f"s{i}", "text": p["quote"], "chunk_id": i} for i, p in enumerate(props, 1)]
    req = requirement(
        "r::dir",
        ["ra", "rb"],
        [
            instance(
                "k1",
                {
                    "ra": binding(inherited_pid, "alpha", source="parent_context", supporting=[inherited_pid]),
                    "rb": binding(own_pid, "beta", supporting=[own_pid]),
                },
                direction=[
                    {"reported": True, "sign": "negative", "proposition_id": direction_pid, "exact_text": "negative"}
                ],
            )
        ],
        kind="relational",
        direction={"reported": True},
        direction_summary=_SUMMARY,
    )
    plan, _, _ = build(
        props, spans, {"c1": {"child_id": "c1", "requirements": [req]}}, one_node("c1"), ["r::dir"], ["ra", "rb"]
    )
    return plan


def _direction_claim(plan) -> dict:
    (claim,) = [r for r in plan["claim_roles"] if r.get("claim_kind") == "direction_or_effectiveness"]
    return claim


def test_integration_a_witnessed_relation_sentence_with_a_relation_target_attaches_the_direction():
    plan = _direction_plan([prop("p1", 1, "The alpha was negatively associated with beta.")])
    claim = _direction_claim(plan)
    assert claim["role"] == "attached_to_relation"
    assert claim["direction_target"] == "relation"


def test_integration_b_witnessed_relation_with_an_operand_valence_sentence_is_valence_not_relation():
    plan = _direction_plan([prop("p1", 1, "The alpha was associated with negative beta evaluations.")])
    claim = _direction_claim(plan)
    assert claim["role"] == "value_level"
    assert claim["direction_target"] == "operand"
    valence = [s for s in plan["nodes"][0]["statements"] if s["kind"] == "value_level_valence"]
    assert valence and valence[0]["subject"] == "beta"


def test_integration_c_unresolved_direction_target_is_suppressed_and_never_attached():
    plan = _direction_plan(
        [
            prop(
                "p1",
                1,
                "Alpha was associated with beta in the first session, and negative results were reported in the methods.",
            )
        ]
    )
    claim = _direction_claim(plan)
    assert claim["role"] == "suppressed"
    assert claim["direction_target"] == "unknown"
    assert claim["reasons"] == ["direction_target_unresolved"]
    assert not [s for s in plan["nodes"][0]["statements"] if s["kind"] == "value_level_valence"]


def test_integration_d_relation_sentence_on_an_unwitnessed_relation_is_not_attached():
    # alpha is inherited and is NOT realised in the child's own proposition p2, so the relation is not witnessed.
    plan = _direction_plan(
        [prop("p1", 1, "The alpha was negatively associated with beta."), prop("p2", 1, "Beta rose across sessions.")],
        direction_pid="p1",
        own_pid="p2",
    )
    claim = _direction_claim(plan)
    assert claim["role"] != "attached_to_relation"
    assert claim["direction_target"] == "relation"
    assert claim["reasons"] == ["direction_relation_not_attachable"]


# ---------------------------------------------------------------------------------------------------------------------
# preserved-run regression (skips when the gitignored artifacts are absent)
# ---------------------------------------------------------------------------------------------------------------------

_RUN = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "phase28-live-parent-synthesis-attempt2-20261004T014500Z"
    / "run"
)
_PRESERVED_MAP = _RUN / "17_sufficiency_map.json"
_PRESERVED_LEDGER = _RUN / "11_verified_ledger.json"


@pytest.mark.skipif(
    not (_PRESERVED_MAP.is_file() and _PRESERVED_LEDGER.is_file() and (_RUN.parent / "phase32").exists() is not None),
    reason="preserved Phase-28 Attempt-2 artifacts are not present in this checkout",
)
def test_preserved_direction_claim_stays_a_value_level_operand_valence(tmp_path):
    from experiments.ask_cli_revised.answer_plan import replay

    run_dir = Path(__file__).resolve().parents[2] / ".local" / "phase32" / "run_i1"
    if not run_dir.is_dir():
        pytest.skip("the I1 run directory (preserved map with I1 fields) is not present in this checkout")
    replay.main(["--run-dir", str(run_dir), "--out-dir", str(tmp_path)])
    plan = json.loads((tmp_path / "answer_plan.json").read_text(encoding="utf-8"))
    (claim,) = [r for r in plan["claim_roles"] if r.get("claim_kind") == "direction_or_effectiveness"]
    assert claim["role"] == "value_level"
    assert claim["direction_target"] == "operand"
    valence = [s for n in plan["nodes"] for s in n["statements"] if s["kind"] == "value_level_valence"]
    assert valence and valence[0]["subject"] == "Explicit Bias Questionnaire"
