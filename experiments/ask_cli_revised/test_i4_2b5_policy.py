"""Frozen I4-2b4 policy, orthogonal gates, schema and representative contracts."""

import copy
import itertools
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import support_policy as sp
from experiments.ask_cli_revised import test_i4_2a_local_grounding as old

FROZEN = json.loads(Path(__file__).with_name("support_policy_i4_2b5_preregistered.json").read_text())
NAMES = ["absent_default", *FROZEN["policies"]]


def evaluate(name, triple):
    if name == "absent_default":
        return sp.default_support_policy(**triple)
    return sp.evaluate_authored_support_policy(FROZEN["policies"][name], **triple)


@pytest.mark.parametrize("row", FROZEN["triples"])
@pytest.mark.parametrize("name", NAMES)
def test_frozen_all_triples(row, name):
    triple = {k: row[k] for k in ("assertion_relation", "aggregation", "assertion_kind")}
    value = evaluate(name, triple)
    failures = row["outcomes"][name]
    assert value["passed"] == (not failures)
    assert value["failed_dimensions"] == [f[0] for f in failures]
    assert value["reasons"] == [f[1] for f in failures]
    assert value["policy_identity"] == (
        "empirical-default-v1" if name == "absent_default" else FROZEN["policy_ids"][name]
    )
    se.validate_support_policy_evaluation(value)


def candidate(*, ambiguous=False, guard=True, policy=True, relation="current_document", synthesis=False, **metadata):
    base = se.new_candidate_support(
        supporting_proposition_ids=["p1"],
        exact_text="unchanged",
        assertion_relation=relation,
        aggregation="literature_synthesis" if synthesis else "non_synthetic_or_unspecified",
        assertion_kind="result" if policy else "interpretation",
        attachment_ambiguous=ambiguous,
        **metadata,
    )
    triple = {k: base[k] for k in ("assertion_relation", "aggregation", "assertion_kind")}
    return se.new_evaluated_candidate_support(
        base,
        guard_exclusions=[] if guard else ["hedged"],
        support_policy_evaluation=sp.default_support_policy(**triple),
    )


@pytest.mark.parametrize("case", FROZEN["multiple_candidates"], ids=lambda c: c["id"])
@pytest.mark.parametrize("reverse", [False, True])
def test_frozen_candidate_sets(case, reverse):
    cs = [
        candidate(
            **spec,
            relation="attributed_external" if i and "attributed" in case["id"] else "current_document",
            synthesis="syntheses" in case["id"],
        )
        for i, spec in enumerate(case["candidates"])
    ]
    if reverse:
        cs.reverse()
    assert se.aggregate_support_role(cs)[0] == case["expected"]
    assert se.reference_future_role_state(cs) == se.aggregate_support_role(cs)


@pytest.mark.parametrize("ambiguous,guard,policy", list(itertools.product((False, True), repeat=3)))
def test_orthogonal_table(ambiguous, guard, policy):
    c = candidate(ambiguous=ambiguous, guard=guard, policy=policy)
    assert c["admissible"] == (guard and policy)
    state = "missing" if not (guard and policy) else "ambiguous" if ambiguous else "filled"
    assert se.aggregate_support_role([c])[0] == state


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("row", FROZEN["triples"])
def test_metadata_never_changes_policy_or_aggregation(name, row):
    triple = {k: row[k] for k in ("assertion_relation", "aggregation", "assertion_kind")}
    expected = evaluate(name, triple)
    states = set()
    for veto, caption, label in itertools.product(
        se.SUPPORT_AUTHORITY_VETOES, (False, True), ("direct", "synthetic", "arbitrary")
    ):
        base = se.new_candidate_support(
            supporting_proposition_ids=["p1"],
            exact_text="no semantic text inspection",
            **triple,
            authority_veto=veto,
            is_caption=caption,
            support_label=label,
        )
        evaluated = se.new_evaluated_candidate_support(
            base, guard_exclusions=[], support_policy_evaluation=evaluate(name, triple)
        )
        assert evaluated["support_policy_evaluation"] == expected
        states.add(se.aggregate_support_role([evaluated])[0])
    assert states == {"filled" if expected["passed"] else "missing"}


VALID = FROZEN["policies"]["A_current_document"]
BAD_POLICIES = [
    None,
    {},
    [],
    "policy",
    {"allowed_assertion_relations": ["current_document"]},
    {**VALID, "extra": True},
    {**VALID, "allowed_assertion_relations": []},
    {**VALID, "allowed_assertion_kinds": []},
    {**VALID, "allowed_assertion_relations": None},
    {**VALID, "allowed_assertion_relations": "current_document"},
    {**VALID, "allowed_assertion_relations": [[]]},
    {**VALID, "allowed_assertion_relations": ["unknown"]},
    {**VALID, "allowed_assertion_kinds": ["bad"]},
    {**VALID, "aggregation_requirement": None},
    {**VALID, "aggregation_requirement": "all"},
]


@pytest.mark.parametrize("policy", BAD_POLICIES)
@pytest.mark.parametrize("units", [[], [old.unit("This may persist.")]])
def test_bad_stored_policies_fail_at_role_entry(policy, units):
    with pytest.raises(ValueError):
        sm._bind_achieved_outcome_v7(
            {**old.SPEC, "support_policy": policy}, units, sibling_bindings={}, role_completion=old.FREE
        )


def test_default_is_not_builder_and_authored_replaces(monkeypatch):
    triple = dict(assertion_relation="unresolved", aggregation="non_synthetic_or_unspecified", assertion_kind="result")
    authored = se.new_support_policy()
    assert sp.evaluate_authored_support_policy(authored, **triple)["passed"]
    monkeypatch.setattr(se, "new_support_policy", lambda **kw: pytest.fail("default called builder"))
    assert not sp.default_support_policy(**triple)["passed"]


@pytest.mark.parametrize("name", FROZEN["policies"])
def test_canonical_identity(name):
    p = copy.deepcopy(FROZEN["policies"][name])
    for k in ("allowed_assertion_relations", "allowed_assertion_kinds"):
        p[k] = list(reversed(p[k])) + p[k]
    assert se.support_policy_identity("authored", se.canonical_support_policy(p)) == FROZEN["policy_ids"][name]


def test_all_three_authored_failures():
    p = {**VALID, "aggregation_requirement": "require_synthesis"}
    result = sp.evaluate_authored_support_policy(
        p, assertion_relation="unresolved", aggregation="non_synthetic_or_unspecified", assertion_kind="interpretation"
    )
    assert result["failed_dimensions"] == ["relation", "aggregation", "kind"]
    assert result["reasons"] == [
        "assertion_relation_not_allowed",
        "aggregation_requires_synthesis",
        "assertion_kind_not_allowed",
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("admissible", None),
        ("admissible", 1),
        ("admissible", False),
        ("inadmissibility_reason", "support_policy_excluded"),
        ("attachment_ambiguous", 1),
        ("guard_exclusions", ["hedged"]),
        ("guard_exclusions", None),
        ("guard_exclusions", ["a", "a"]),
        ("support_policy_evaluation", {}),
    ],
)
def test_inconsistent_candidate_rejected(field, value):
    c = candidate()
    c[field] = value
    with pytest.raises(ValueError):
        se.aggregate_support_role([c])
    with pytest.raises(ValueError):
        se.new_candidate_supports([c])


@pytest.mark.parametrize(
    "field,value",
    [
        ("passed", False),
        ("passed", 1),
        ("schema_version", "future"),
        ("policy_source", "unknown"),
        ("policy_identity", "forged"),
        ("policy_snapshot", {}),
        ("failed_dimensions", ["kind"]),
        ("reasons", ["non_result_kind"]),
        ("failed_dimensions", ["unknown"]),
        ("reasons", "arbitrary"),
    ],
)
def test_inconsistent_policy_record_rejected(field, value):
    c = candidate()
    c["support_policy_evaluation"][field] = value
    with pytest.raises(ValueError):
        se.aggregate_support_role([c])


def test_partial_evaluated_and_unevaluated_rejected():
    for key in ("guard_exclusions", "support_policy_evaluation"):
        c = candidate()
        del c[key]
        with pytest.raises(ValueError):
            se.aggregate_support_role([c])
    c = candidate()
    del c["guard_exclusions"]
    del c["support_policy_evaluation"]
    c["admissible"] = None
    with pytest.raises(ValueError):
        se.aggregate_support_role([c])


def bind(units, spec=None, diagnostics=None):
    return sm._bind_achieved_outcome_v7(
        spec or old.SPEC, units, sibling_bindings={}, role_completion=old.FREE, diagnostics=diagnostics
    )


def test_passage_guard_independent_from_local_assertion():
    u = old.unit("We found that X increased. It may persist.")
    original = copy.deepcopy(u)
    spec = {**old.SPEC, "disqualifying_guards": ["hedged", "hedged", "absent_guard"]}
    c = bind([u], spec)[0]["candidate_supports"][0]
    assert c["exact_text"] == "We found that X increased"
    assert c["guard_exclusions"] == ["hedged"]
    assert c["support_policy_evaluation"]["passed"] is True
    assert c["inadmissibility_reason"] == "disqualifying_guard_excluded"
    assert u == original and spec["disqualifying_guards"] == ["hedged", "hedged", "absent_guard"]


def test_multiple_guards_authored_order_and_no_candidate_rescue():
    spec = {**old.SPEC, "disqualifying_guards": ["absence_statement", "hedged", "absence_statement"]}
    c = bind([old.unit("We found that X increased. No evidence was available. It may persist.")], spec)[0][
        "candidate_supports"
    ][0]
    assert c["guard_exclusions"] == ["absence_statement", "hedged"]
    assert bind([old.unit("It may persist.")], spec) == []


def test_guarded_bad_coordinates_remain_loud():
    u = old.unit("We found that X increased. It may persist.", ["p1", "p2"])
    u["proposition_passages"]["p2"] += " mismatch"
    with pytest.raises(ValueError, match="byte-identical"):
        bind([u], {**old.SPEC, "disqualifying_guards": ["hedged"]})


def test_eligible_only_projection_and_no_instance_fork():
    units = [
        old.unit("We found that X increased. It may persist.", ["p1"]),
        old.unit("Previous studies found that X increased.", ["p2"]),
    ]
    bs = bind(units, {**old.SPEC, "disqualifying_guards": ["hedged"]})
    assert len(bs) == 1
    b = bs[0]
    assert len(b["candidate_supports"]) == 2 and b["state"] == "filled"
    assert b["proposition_id"] == "p2"
    assert b["provenance"]["supporting_proposition_ids"] == ["p2"]


@pytest.mark.parametrize("ambiguous,guard,policy", [(True, True, True), (False, False, True), (False, True, False)])
def test_no_unsafe_legacy_surface(ambiguous, guard, policy):
    c = candidate(ambiguous=ambiguous, guard=guard, policy=policy)
    b = sm._project_evaluated_supports(old.SPEC, [c], [{"flags": {}}])[0]
    assert b["proposition_id"] is b["exact_text"] is None
    assert b["candidate_supports"] == [c] and b["guard"] == se.new_role_binding("r")["guard"]


def test_schema_defensive_copy():
    c = candidate()
    copy_c = se.new_candidate_supports([c])[0]
    copy_c["support_policy_evaluation"]["policy_snapshot"]["kind"] = "changed"
    assert c["support_policy_evaluation"]["policy_snapshot"]["kind"] == "empirical_default"
