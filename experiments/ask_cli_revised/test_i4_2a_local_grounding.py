"""I4-2a production seam: dependency states, local identity, version isolation, no policy gating."""

import ast
from pathlib import Path

import pytest

from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import direction_target as dt
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised import test_i4_1j_local_grounding as real
from experiments.ask_cli_revised import test_sufficiency_v4_category_satisfaction as category

V4, V5 = se.SUFFICIENCY_SEMANTICS_V4, se.SUFFICIENCY_SEMANTICS_V5
SPEC = se.new_role_spec("evidence", "reported result", "achieved_outcome_predicate")
FREE = se.new_role_completion(required_roles=["evidence"])
DEPENDENT = se.new_role_completion(required_roles=["target", "evidence"])


def unit(text, ids=("p",)):
    return {
        "unit_id": ids[0],
        "passage": text,
        "proposition_ids": list(ids),
        "proposition_passages": {pid: text for pid in ids},
        "flags": oe.passage_flags(text),
    }


def target(text="anger", pid="p"):
    return se.new_role_binding("target", state="filled", proposition_id=pid, exact_text=text)


def bind(units, completion=FREE, bindings=None, spec=SPEC, diagnostics=None):
    return sm._bind_achieved_outcome_v5(
        spec, units, role_completion=completion, sibling_bindings=bindings, diagnostics=diagnostics
    )


def test_three_p41_hits_join_and_dedupe_to_two_local_supports():
    diagnostics = {}
    result = bind([unit(real.P41)], diagnostics=diagnostics)[0]
    supports = result["candidate_supports"]
    assert [s["assertion_span"] for s in supports] == [[43, 200], [208, 372]]
    assert diagnostics["raw_result_predicate_hits"] == diagnostics["successful_assertion_joins"] == 3
    assert diagnostics["raw_hits_deduplicated"] == 1
    assert diagnostics["join_failures"] == 0
    assert result["exact_text"] == real.P41[43:200]
    assert supports[1]["assertion_relation"] == "unresolved"
    assert all(s["admissible"] is None and s["inadmissibility_reason"] is None for s in supports)


@pytest.mark.parametrize("text,span", real.C8_TRAIT_TARGETS.items())
def test_five_c8_traits(text, span):
    result = bind([unit(real.P41)], DEPENDENT, {"target": target(text)})[0]
    assert len(result["candidate_supports"]) == 1
    assert result["exact_text"] == real.P41[slice(*span)]


def test_c4_scope_precedes_lexical_matching_and_subject_is_retained():
    units = [unit(real.P11, ["p11"]), unit(real.P40, ["p40"])]
    result = bind(units, DEPENDENT, {"target": target("amygdala", "p40")})[0]
    assert result["proposition_id"] == "p40"
    assert result["candidate_supports"][0]["assertion_relation"] == "unresolved"
    result = bind(units, DEPENDENT, {"target": target(real.C4_P11_TARGET, "p11")})[0]
    assert real.C4_P11_TARGET in result["exact_text"]
    assert result["proposition_id"] == "p11"


@pytest.mark.parametrize(
    "pid,text,filled", [("p35", real.P35, False), ("p46", real.P46, False), ("p47", real.P47, True)]
)
def test_c2_local_evidence(pid, text, filled):
    assert bool(bind([unit(text, [pid])], DEPENDENT, {"target": target(real.C2_TARGETS[pid], pid)})) is filled


def test_c10_existing_hedged_guard_runs_first(monkeypatch):
    def forbidden(*args):
        raise AssertionError("guard-excluded passage must not reach localization")

    monkeypatch.setattr(sm.aos, "find_achieved_outcome_matches", forbidden)
    assert (
        bind(
            [unit(real.P29)], DEPENDENT, {"target": target("Hadza")}, spec={**SPEC, "disqualifying_guards": ["hedged"]}
        )
        == []
    )


@pytest.mark.parametrize(
    "binding",
    [
        None,
        {"state": "missing"},
        {"state": "ambiguous"},
        {"state": "filled", "exact_text": "", "proposition_id": "p"},
        {"state": "filled", "exact_text": "   ", "proposition_id": "p"},
        {"state": "filled", "exact_text": "anger", "proposition_id": None},
    ],
)
def test_unavailable_dependency_is_never_target_free(binding):
    bindings = {"target": binding} if binding else {}
    assert sm.resolve_target_dependency(DEPENDENT, "evidence", bindings)["status"] == "unavailable"
    assert bind([unit(real.P41)], DEPENDENT, bindings) == []


def test_missing_completion_context_is_unavailable():
    assert bind([unit(real.P41)], None) == []


def test_multiple_dependencies_fail_closed_even_when_all_filled():
    completion = se.new_role_completion(required_roles=["target", "context", "evidence"])
    bindings = {"target": target(), "context": target()}
    assert sm.resolve_target_dependency(completion, "evidence", bindings)["status"] == "ambiguous"
    assert bind([unit(real.P41)], completion, bindings) == []


@pytest.mark.parametrize(
    "bindings,status",
    [
        ({}, "unavailable"),
        ({"a": target()}, "ready"),
        ({"b": target()}, "ready"),
        ({"a": target(), "b": target()}, "ambiguous"),
    ],
)
def test_generic_alternative_dependency(bindings, status):
    completion = se.new_role_completion(required_roles=["evidence"], alternative_role_groups=[["a", "b"]])
    assert sm.resolve_target_dependency(completion, "evidence", bindings)["status"] == status
    assert bool(bind([unit(real.P41)], completion, bindings)) is (status == "ready")


def test_optional_roles_and_evidence_own_alternative_group_create_no_dependency():
    completion = se.new_role_completion(alternative_role_groups=[["evidence", "other"]], optional_roles=["optional"])
    assert sm.resolve_target_dependency(completion, "evidence", {})["status"] == "target_free"
    assert bind([unit(real.P41)], completion)


def test_provenance_and_candidate_discovery_order_and_coordinate_anchor():
    units = [unit(real.P41, ["p9", "p2"]), unit(real.P41, ["p8"])]
    supports = bind(units)[0]["candidate_supports"]
    assert [s["span_proposition_id"] for s in supports] == ["p9", "p9", "p8", "p8"]
    assert supports[0]["supporting_proposition_ids"] == ["p9", "p2"]
    for support in supports:
        assert support["exact_text"] == real.P41[slice(*support["assertion_span"])]


@pytest.mark.parametrize("change", ["unequal", "absent", "duplicate"])
def test_invalid_plural_coordinate_identity_is_rejected(change):
    u = unit(real.P41, ["p9", "p2"])
    if change == "unequal":
        u["proposition_passages"]["p2"] += " "
    elif change == "absent":
        del u["proposition_passages"]
    else:
        u["proposition_ids"] = ["p9", "p9"]
    with pytest.raises(ValueError):
        bind([u])


def test_join_failure_is_missing(monkeypatch):
    monkeypatch.setattr(aa, "locate_containing_assertion", lambda *args: {"resolved": False})
    diagnostics = {}
    assert bind([unit(real.P41)], diagnostics=diagnostics) == []
    assert diagnostics["join_failures"] == 3


@pytest.mark.parametrize(
    "version", [se.SUFFICIENCY_SEMANTICS_V1, se.SUFFICIENCY_SEMANTICS_V2, se.SUFFICIENCY_SEMANTICS_V3, V4]
)
def test_historical_versions_keep_whole_passage_and_ignore_dependency(version, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("historical mapping reached v5")

    monkeypatch.setattr(sm, "_bind_achieved_outcome_v5", forbidden)
    result = sm._bind_role_candidates(
        SPEC, [unit(real.P41)], semantics_version=version, role_completion=DEPENDENT, sibling_bindings={}
    )[0]
    assert result["exact_text"] == real.P41
    assert "candidate_supports" not in result


def test_policy_is_never_consumed_and_verifier_remains_unregistered(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("I4-2a evaluated support policy")

    monkeypatch.setattr(se, "new_support_policy", forbidden)
    monkeypatch.setattr(se, "reference_future_role_state", forbidden)
    assert (
        len(
            bind([unit(real.P41)], spec={**SPEC, "support_policy": {"allowed_assertion_relations": []}})[0][
                "candidate_supports"
            ]
        )
        == 2
    )
    assert "same_local_assertion" not in se._VERIFIER_FUNCS
    tree = ast.parse(Path(sm.__file__).read_text(encoding="utf-8"))
    assert not any(isinstance(n, ast.Constant) and n.value == "support_policy" for n in ast.walk(tree))


@pytest.mark.parametrize("invalid", [0, 1, "true", [], {}])
def test_admissible_is_strictly_three_valued(invalid):
    with pytest.raises(ValueError):
        se.new_candidate_support(
            supporting_proposition_ids=["p"],
            exact_text="x",
            assertion_relation="unresolved",
            aggregation="non_synthetic_or_unspecified",
            assertion_kind="result",
            admissible=invalid,
        )


def test_unassessed_candidate_default_and_reason_constraint():
    args = dict(
        supporting_proposition_ids=["p"],
        exact_text="x",
        assertion_relation="unresolved",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
    )
    assert se.new_candidate_support(**args)["admissible"] is None
    with pytest.raises(ValueError):
        se.new_candidate_support(**args, inadmissibility_reason="support_policy_excluded")


def test_only_approved_classifier_apis_are_consumed_in_the_mapper():
    tree = ast.parse(Path(sm.__file__).read_text(encoding="utf-8"))
    allowed = {
        "aos": {"find_achieved_outcome_matches"},
        "aa": {"locate_containing_assertion", "assertion_relation", "support_label"},
        "tr": {"match_target_to_assertions"},
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in allowed:
            assert node.attr in allowed[node.value.id]


@pytest.mark.parametrize(
    "module_name,guard_name,reference",
    [
        ("test_assertion_authority_i4_1f", "test_classifier_is_still_unwired_static_guard", "assertion_authority"),
        ("test_assertion_authority", "test_classifier_is_unwired_static_guard", "assertion_authority"),
        ("test_achieved_outcome_span", "test_module_is_unwired_static_guard", "achieved_outcome_span"),
        ("test_i4_1j_local_grounding", "test_no_production_module_consumes_the_i4_1j_primitives", "target_relevance"),
    ],
)
def test_static_allow_lists_reject_a_second_production_consumer(
    tmp_path, monkeypatch, module_name, guard_name, reference
):
    import importlib

    module = importlib.import_module("experiments.ask_cli_revised." + module_name)
    here = tmp_path / "experiments/ask_cli_revised"
    here.mkdir(parents=True)
    monkeypatch.setattr(module, "HERE", here)
    (tmp_path / "app").mkdir()
    (here / "sufficiency_mapping.py").write_text(f"from experiments.ask_cli_revised import {reference}\n")
    getattr(module, guard_name)()  # exact authorized path passes
    other = tmp_path / "app/sufficiency_mapping.py"
    other.write_text(f"from experiments.ask_cli_revised import {reference}\n")
    with pytest.raises(AssertionError):
        getattr(module, guard_name)()


def test_v5_category_recovery_witness_and_direction_inherit_v4():
    units = [category._unit("U1", category.NULL_SENTENCE), category._unit("U2", category.POSITIVE_SENTENCE)]
    req = category._category_requirement()
    assert sm.map_cardinality_requirement(req, units, semantics_version=V5) == sm.map_cardinality_requirement(
        req, units, semantics_version=V4
    )
    assert rw._REFERENT_CONTAINMENT[V5] is rw._REFERENT_CONTAINMENT[V4]
    assert dt._SINGLE_OPERAND_FALLBACK[V5] == dt._SINGLE_OPERAND_FALLBACK[V4]
    mapped = sm.map_cardinality_requirement(req, units[:1], semantics_version=V4)
    contract = {"c": se.new_contract("c", [mapped])}
    assert srt.compute_recovery_targets(contract, {}, semantics_version=V5) == srt.compute_recovery_targets(
        contract, {}, semantics_version=V4
    )
    assert srt.search_obligations({"a": 1}, {"b": 2}, semantics_version=V5) == {"a": 1, "b": 2}


@pytest.mark.parametrize("version", [V4, V5])
@pytest.mark.parametrize("case", ["unequal_no_hits", "unequal_hits", "identical_hits", "single"])
def test_coordinate_validation_starts_only_at_raw_hits(version, case, monkeypatch):
    text = "QUOTE 11" if case == "unequal_no_hits" else real.P41
    ids = ["p3"] if case == "single" else ["p3", "p1", "p2"]
    u = unit(text, ids)
    if case == "unequal_no_hits":
        u["proposition_passages"] = {"p3": "QUOTE 13", "p1": "QUOTE 11", "p2": "QUOTE 12"}
    elif case == "unequal_hits":
        u["proposition_passages"]["p2"] += " "
    elif case == "single":
        del u["proposition_passages"]  # single-id units never need plural coordinate metadata

    def forbidden_join(*args, **kwargs):
        raise AssertionError("invalid/absent local spans must never reach assertion joining")

    if version == V4 or case in ("unequal_no_hits", "unequal_hits"):
        monkeypatch.setattr(aa, "locate_containing_assertion", forbidden_join)
    if version == V5 and case == "unequal_hits":
        with pytest.raises(ValueError, match="plural proposition spans require byte-identical sealed passages"):
            bind([u])
        return
    result = sm._bind_role_candidates(SPEC, [u], semantics_version=version, role_completion=FREE, sibling_bindings={})
    if case == "unequal_no_hits":
        assert result == []
    elif version == V4:
        assert result[0]["exact_text"] == text
        assert "candidate_supports" not in result[0]
    else:
        supports = result[0]["candidate_supports"]
        assert supports
        assert all(s["supporting_proposition_ids"] == ids for s in supports)
        assert all(s["span_proposition_id"] == ids[0] for s in supports)
