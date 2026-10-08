"""PHASE 34 / I4-1g -- pure support_policy / candidate-support schema primitives.

Backward-compatibility gate first: every UNMODIFIED constructor call in this file must produce
byte-identical serialized output to the frozen "before" hashes captured prior to any code change
in this increment (see PHASE34_I4_1G_SUPPORT_SCHEMA_RESULTS.md section on the byte-parity gate).
Then the new, still-unwired schema primitives: new_support_policy, the optional RoleSpec
support_policy field, new_candidate_support/new_candidate_supports, and the two reference-only
aggregation/disambiguation helpers, each with a static guard proving no production module (engine
code included) consumes them yet.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import sufficiency_authoring as sa
from experiments.ask_cli_revised import sufficiency_engine as se

HERE = Path(__file__).parent


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ---- byte-parity gate (section 2/17): every one of these calls must be UNCHANGED by this increment ----

_BEFORE_HASHES = {
    "role_spec_minimal": "15dc036ef1b6c33ed142f82c53affb73ed5f405d165ce276d7e09d58135baa17",
    "role_spec_full": "edfc981578b751e0c8a62d3292f8bd137cdb2fae0070684bbedc273e9ffc9ce8",
    "role_spec_category": "30c9679d9099e9cfacf9b1fce41a2f3a5a85eabe3d4694ee3e9685aaf9cd1105",
    "role_binding_minimal": "2b2a97e743257b8f8de8af09c57b8241650589e70cea6b8bc3e874289d17c095",
    "role_binding_filled": "8fbcc6c20323f8453d0e90455b6b7d24d641c439cc62e7507781d54b4adb6afb",
    "role_binding_ambiguous": "47b186963d1277ebaaa4728811cefabe91e74bbc66551a4efd65981f95255fb3",
    "requirement_atomic_minimal": "0d6d16fef0841374ef9d3596fd9359f809646b750b83cb6b6366ab8314777127",
    "requirement_with_direction_effectiveness": "bbb61aff6f38af5ea46f7030d12638fecca50f7ae3bfa2af14a0b948dd1148c3",
    "requirement_cardinality": "d446c3056aa02eda790c14395d395c60e7401fd976f3abfc968db2b720b5c377",
    "qaib_stub_contracts": "73aea355a4ae28bc82a1387a7e52041ba23d1320a9650451345b0df631147936",
    "qaib_stub_frozen": "74b6f5be255368b4edb81212ecef1be1a27b6386a2e54733545ef2f8c2c84f5b",
}
_BEFORE_COMBINED_HASH = "2696958197f006df28f6b65ff6364f1b36930b18dfbcabe46e13534aa608d553"


def _rebuild_parity_cases():
    cases = {}
    cases["role_spec_minimal"] = se.new_role_spec("r1", "desc", "model_nomination_only")
    cases["role_spec_full"] = se.new_role_spec(
        "r2",
        "desc2",
        "achieved_outcome_predicate",
        disqualifying_guards=["hedged"],
        model_nomination_permitted=False,
        requested_category_terms=["X", "Y"],
        source_wording_span="the wording",
    )
    cases["role_spec_category"] = se.new_role_spec(
        "cat",
        "desc3",
        "explicit_category_terms",
        disqualifying_guards=[],
        requested_category_terms=["implicit", "explicit"],
        source_wording_span="w",
    )
    cases["role_binding_minimal"] = se.new_role_binding("r1")
    cases["role_binding_filled"] = se.new_role_binding(
        "r1",
        state="filled",
        reason=None,
        proposition_id="p1",
        exact_text="quote",
        provenance={"candidate_source": "deterministic_mapping", "detail": "x", "model": None},
        guard={"hedged": True},
    )
    cases["role_binding_ambiguous"] = se.new_role_binding("r1", state="ambiguous", reason="evidence_conflicting")
    rs = {"r1": se.new_role_spec("r1", "d", "model_nomination_only")}
    rc = se.new_role_completion(required_roles=["r1"])
    cases["requirement_atomic_minimal"] = se.new_requirement("req1", "atomic", rs, rc, "exists")
    cases["requirement_with_direction_effectiveness"] = se.new_requirement(
        "req2",
        "relational",
        rs,
        rc,
        "exists",
        direction=se.new_direction_assessment(),
        effectiveness=se.new_effectiveness_assessment(),
        multi_instance=True,
        source_wording_span="w2",
    )
    rs_cat = {
        "category_evidence": se.new_role_spec(
            "category_evidence",
            "d",
            "explicit_category_terms",
            disqualifying_guards=[],
            requested_category_terms=["a", "b"],
        )
    }
    rc_cat = se.new_role_completion(required_roles=["category_evidence"])
    cases["requirement_cardinality"] = se.new_requirement(
        "req3", "cardinality", rs_cat, rc_cat, "all_requested_categories", multi_instance=True
    )
    children = {
        cid: {"wording": f"stub wording for {cid}"}
        for cid in ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"]
    }
    contracts = sa.build_qaib_contract(children)
    cases["qaib_stub_contracts"] = contracts
    cases["qaib_stub_frozen"] = sa.freeze(contracts)
    return cases


def test_byte_parity_every_unmodified_constructor_call_is_unchanged():
    cases = _rebuild_parity_cases()
    for name, expected in _BEFORE_HASHES.items():
        got = _h(cases[name])
        assert got == expected, f"{name} drifted from its frozen pre-I4-1g hash: {got}"
    assert cases["qaib_stub_frozen"]["combined_hash"] == _BEFORE_COMBINED_HASH


def test_role_spec_without_support_policy_has_exactly_the_historical_seven_keys():
    """Section 9, load-bearing: an omitted optional field must be OMITTED, never materialized as
    a default/None/empty key on every historical object."""
    spec = se.new_role_spec("r", "d", "model_nomination_only")
    assert set(spec) == {
        "role",
        "category_description",
        "mapping_strategy",
        "disqualifying_guards",
        "model_nomination_permitted",
        "requested_category_terms",
        "source_wording_span",
    }
    assert "support_policy" not in spec


def test_role_binding_and_requirement_are_entirely_untouched():
    """new_role_binding/new_requirement/new_instance are not modified at all in I4-1g -- candidate_supports
    is introduced as an independent schema object, not yet a field on either (see the results report)."""
    binding = se.new_role_binding("r")
    assert set(binding) == {"role", "state", "reason", "proposition_id", "exact_text", "provenance", "guard"}
    rs = {"r": se.new_role_spec("r", "d", "model_nomination_only")}
    rc = se.new_role_completion(required_roles=["r"])
    req = se.new_requirement("req", "atomic", rs, rc, "exists")
    assert "candidate_supports" not in req
    assert "support_policy" not in req
    instance = se.new_instance()
    assert "candidate_supports" not in instance


# ---- new_support_policy (section 3/14) ----


def test_new_support_policy_canonicalizes_and_validates():
    policy = se.new_support_policy(
        allowed_assertion_relations=["unresolved", "current_document", "current_document"],
        aggregation_requirement="any",
        allowed_assertion_kinds=["result"],
    )
    assert policy == {
        "allowed_assertion_relations": ["current_document", "unresolved"],
        "aggregation_requirement": "any",
        "allowed_assertion_kinds": ["result"],
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"allowed_assertion_relations": ["not_a_relation"]},
        {"aggregation_requirement": "not_a_requirement"},
        {"allowed_assertion_kinds": ["not_a_kind"]},
        {"allowed_assertion_relations": []},
        {"allowed_assertion_kinds": []},
    ],
)
def test_new_support_policy_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        se.new_support_policy(**kwargs)


def test_new_support_policy_examples_from_the_directive_section_14():
    general_empirical = se.new_support_policy(
        allowed_assertion_relations=["current_document", "attributed_external", "unresolved"],
        aggregation_requirement="any",
        allowed_assertion_kinds=["result"],
    )
    current_document_only = se.new_support_policy(
        allowed_assertion_relations=["current_document"],
        aggregation_requirement="any",
        allowed_assertion_kinds=["result"],
    )
    definitional = se.new_support_policy(
        allowed_assertion_relations=["current_document", "attributed_external", "unresolved"],
        aggregation_requirement="any",
        allowed_assertion_kinds=["method_or_description", "interpretation"],
    )
    literature_synthesis = se.new_support_policy(
        allowed_assertion_relations=["current_document", "attributed_external", "unresolved"],
        aggregation_requirement="require_synthesis",
        allowed_assertion_kinds=["result"],
    )
    assert {
        general_empirical["allowed_assertion_relations"][0],
        current_document_only["allowed_assertion_relations"][0],
    } == {"attributed_external", "current_document"}
    assert current_document_only["allowed_assertion_relations"] == ["current_document"]
    assert definitional["allowed_assertion_kinds"] == ["interpretation", "method_or_description"]
    assert literature_synthesis["aggregation_requirement"] == "require_synthesis"
    for policy in (general_empirical, current_document_only, definitional, literature_synthesis):
        assert set(policy) == {"allowed_assertion_relations", "aggregation_requirement", "allowed_assertion_kinds"}


def test_new_support_policy_defaults_are_schema_examples_not_executable_defaults():
    """new_support_policy's own defaults are a usable schema example; this is NOT the same thing as I4-1e's
    future default admissibility predicate executing anywhere (section 5) -- confirmed separately by the
    production-consumption static guard below."""
    policy = se.new_support_policy()
    assert policy["aggregation_requirement"] == "any"


# ---- RoleSpec support_policy field (section 4) ----


def test_role_spec_accepts_an_explicit_validated_support_policy():
    policy = se.new_support_policy(allowed_assertion_kinds=["result"])
    spec = se.new_role_spec("r", "d", "model_nomination_only", support_policy=policy)
    assert spec["support_policy"] == policy
    assert set(spec) == {
        "role",
        "category_description",
        "mapping_strategy",
        "disqualifying_guards",
        "model_nomination_permitted",
        "requested_category_terms",
        "source_wording_span",
        "support_policy",
    }


def test_role_spec_canonicalizes_a_hand_authored_support_policy_dict():
    spec = se.new_role_spec(
        "r",
        "d",
        "model_nomination_only",
        support_policy={
            "allowed_assertion_relations": ["unresolved", "current_document"],
            "aggregation_requirement": "any",
            "allowed_assertion_kinds": ["result"],
        },
    )
    assert spec["support_policy"]["allowed_assertion_relations"] == ["current_document", "unresolved"]


def test_role_spec_rejects_a_malformed_support_policy():
    with pytest.raises(ValueError):
        se.new_role_spec("r", "d", "model_nomination_only", support_policy={"allowed_assertion_relations": ["x"]})
    with pytest.raises(ValueError):
        se.new_role_spec("r", "d", "model_nomination_only", support_policy={"wrong_key": 1})


def test_no_existing_q_aib_role_is_authored_with_a_support_policy():
    """Section 4, explicit instruction: do not author support_policy onto any existing q_aib role in this
    increment."""
    children = {
        cid: {"wording": f"stub wording for {cid}"}
        for cid in ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"]
    }
    contracts = sa.build_qaib_contract(children)
    for contract in contracts.values():
        for req in contract["requirements"]:
            for spec in req["role_specs"].values():
                assert "support_policy" not in spec


# ---- candidate-support record + collection (sections 6-9, 15) ----


def _direct_primary():
    return se.new_candidate_support(
        supporting_proposition_ids=["p1"],
        exact_text="We found X.",
        assertion_relation="current_document",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=True,
        support_label="direct_empirical",
    )


def test_candidate_support_examples_from_section_15():
    direct_primary = _direct_primary()
    direct_synthetic = se.new_candidate_support(
        supporting_proposition_ids=["p2"],
        exact_text="We found a meta-analytic effect of X on Y.",
        assertion_relation="current_document",
        aggregation="literature_synthesis",
        assertion_kind="result",
        admissible=True,
        support_label="direct_synthetic",
    )
    attributed_primary = se.new_candidate_support(
        supporting_proposition_ids=["p3"],
        exact_text="Previous studies found X.",
        assertion_relation="attributed_external",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=True,
        support_label="attributed_indirect",
    )
    attributed_synthetic = se.new_candidate_support(
        supporting_proposition_ids=["p4"],
        exact_text="A review found X.",
        assertion_relation="attributed_external",
        aggregation="literature_synthesis",
        assertion_kind="result",
        admissible=True,
        support_label="attributed_synthetic",
    )
    unresolved_synthetic = se.new_candidate_support(
        supporting_proposition_ids=["p5"],
        exact_text="Across studies, X has been implicated in Y.",
        assertion_relation="unresolved",
        aggregation="literature_synthesis",
        assertion_kind="result",
        admissible=True,
        support_label="unresolved_synthetic",
    )
    policy_excluded = se.new_candidate_support(
        supporting_proposition_ids=["p6"],
        exact_text="A review found X.",
        assertion_relation="attributed_external",
        aggregation="literature_synthesis",
        assertion_kind="result",
        admissible=False,
        inadmissibility_reason="support_policy_excluded",
    )
    attachment_ambiguous = se.new_candidate_support(
        supporting_proposition_ids=["p7"],
        exact_text="found X previous studies found Y",
        assertion_relation="unresolved",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=False,
        attachment_ambiguous=True,
        inadmissibility_reason="assertion_attachment_ambiguous",
    )
    for rec in (
        direct_primary,
        direct_synthetic,
        attributed_primary,
        attributed_synthetic,
        unresolved_synthetic,
        policy_excluded,
        attachment_ambiguous,
    ):
        assert set(rec) == {
            "supporting_proposition_ids",
            "span_proposition_id",
            "exact_text",
            "assertion_span",
            "predicate_span",
            "content_span",
            "assertion_relation",
            "aggregation",
            "assertion_kind",
            "support_label",
            "authority_veto",
            "is_caption",
            "attachment_ambiguous",
            "admissible",
            "inadmissibility_reason",
        }
    assert policy_excluded["admissible"] is False
    assert policy_excluded["inadmissibility_reason"] == "support_policy_excluded"
    assert attachment_ambiguous["attachment_ambiguous"] is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"assertion_relation": "synthesis"},
        {"aggregation": "synthetic"},
        {"assertion_kind": "candidate"},
        {"authority_veto": "unknown_veto"},
        {"inadmissibility_reason": "unknown_reason"},
        {"admissible": True, "inadmissibility_reason": "support_policy_excluded"},
        {"admissible": False, "inadmissibility_reason": None},
        {"supporting_proposition_ids": []},
        {"supporting_proposition_ids": ["p1", "p1"]},
        {"assertion_span": [0, 5]},
        {"assertion_span": [0, 5], "span_proposition_id": "p2"},
    ],
)
def test_candidate_support_rejects_invalid_or_inconsistent_input(kwargs):
    base = {
        "supporting_proposition_ids": ["p1"],
        "exact_text": "X",
        "assertion_relation": "current_document",
        "aggregation": "non_synthetic_or_unspecified",
        "assertion_kind": "result",
        "admissible": True,
    }
    base.update(kwargs)
    with pytest.raises(ValueError):
        se.new_candidate_support(**base)


def test_candidate_support_proposition_identity_is_plural_discovery_order_never_sorted():
    """I4-1j correction (section 3): the canonical identity is a required, non-empty, duplicate-free,
    discovery-ordered list -- never collapsed to a singular id, never sorted for canonical appearance."""
    rec = se.new_candidate_support(
        supporting_proposition_ids=["p9", "p2"],  # deliberately out of sort order
        exact_text="X",
        assertion_relation="current_document",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=True,
    )
    assert rec["supporting_proposition_ids"] == ["p9", "p2"]  # order preserved, not sorted to ["p2", "p9"]
    assert "proposition_id" not in rec


def test_candidate_support_span_proposition_id_required_with_a_span_and_must_be_a_member():
    rec = se.new_candidate_support(
        supporting_proposition_ids=["p1", "p2"],
        exact_text="greater proportionality was associated with attractiveness",
        assertion_relation="current_document",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=True,
        assertion_span=(43, 200),
        span_proposition_id="p1",
    )
    assert rec["span_proposition_id"] == "p1"
    # no span at all -- span_proposition_id may be omitted
    no_span = se.new_candidate_support(
        supporting_proposition_ids=["p1"],
        exact_text="X",
        assertion_relation="current_document",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=True,
    )
    assert no_span["span_proposition_id"] is None


def test_candidate_supports_collection_preserves_order_and_drops_nothing():
    a = _direct_primary()
    b = se.new_candidate_support(
        supporting_proposition_ids=["p8"],
        exact_text="A review found X.",
        assertion_relation="attributed_external",
        aggregation="literature_synthesis",
        assertion_kind="result",
        admissible=False,
        inadmissibility_reason="support_policy_excluded",
    )
    source_list = [b, a]
    collection = se.new_candidate_supports(source_list)
    assert collection == [b, a]  # source order preserved -- list position is never semantic
    assert collection is not source_list  # a defensive copy, not aliasing the caller's own list


def test_candidate_supports_collection_validates_shape():
    with pytest.raises(ValueError):
        se.new_candidate_supports([{"not": "a candidate support"}])


# ---- reference-only helpers (section 10, 12, frozen contract, not production behaviour) ----


def test_reference_future_role_state_filled_iff_any_admissible():
    a = _direct_primary()
    ambiguous_only = se.new_candidate_support(
        supporting_proposition_ids=["p9"],
        exact_text="found X previous studies found Y",
        assertion_relation="unresolved",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=False,
        attachment_ambiguous=True,
        inadmissibility_reason="assertion_attachment_ambiguous",
    )
    assert se.reference_future_role_state([ambiguous_only, a]) == ("filled", None)


def test_reference_future_role_state_ambiguous_only_when_no_admissible_and_one_attachment_ambiguous():
    ambiguous_only = se.new_candidate_support(
        supporting_proposition_ids=["p9"],
        exact_text="found X previous studies found Y",
        assertion_relation="unresolved",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
        admissible=False,
        attachment_ambiguous=True,
        inadmissibility_reason="assertion_attachment_ambiguous",
    )
    assert se.reference_future_role_state([ambiguous_only]) == ("ambiguous", "assertion_attachment_ambiguous")


def test_reference_future_role_state_policy_excluded_alone_is_missing_not_ambiguous():
    excluded_only = se.new_candidate_support(
        supporting_proposition_ids=["p10"],
        exact_text="A review found X.",
        assertion_relation="attributed_external",
        aggregation="literature_synthesis",
        assertion_kind="result",
        admissible=False,
        inadmissibility_reason="support_policy_excluded",
    )
    state, reason = se.reference_future_role_state([excluded_only])
    assert state == "missing"


def test_reference_future_role_state_empty_is_missing():
    assert se.reference_future_role_state([])[0] == "missing"


# ---- requested_category_terms generalized disambiguation contract (sections 11-13) ----


def test_requested_category_terms_field_name_is_retained_unchanged():
    """Section 13: retain the historical field name; generalize only its documented meaning."""
    spec = se.new_role_spec(
        "r", "d", "achieved_outcome_predicate", requested_category_terms=["Y"], source_wording_span="w"
    )
    assert spec["requested_category_terms"] == ["Y"]


@pytest.mark.parametrize(
    "candidates,terms,expected_text",
    [
        ([{"exact_text": "We found X."}, {"exact_text": "We found Y."}], [], None),
        ([{"exact_text": "We found X."}, {"exact_text": "We found Y."}], ["Y"], "We found Y."),
        ([{"exact_text": "We found X."}, {"exact_text": "We found Z."}], ["Y"], None),
        ([{"exact_text": "We found X and Y."}, {"exact_text": "We also found Y again."}], ["Y"], None),
    ],
)
def test_reference_future_requested_terms_disambiguation_contract(candidates, terms, expected_text):
    result = se.reference_future_requested_terms_disambiguation(candidates, terms)
    if expected_text is None:
        assert result is None
    else:
        assert result["exact_text"] == expected_text


def test_reference_disambiguation_never_first_match_fallback():
    candidates = [{"exact_text": "contains Y here"}, {"exact_text": "also contains Y there"}]
    assert se.reference_future_requested_terms_disambiguation(candidates, ["Y"]) is None


# ---- static, zero-production-consumption guards (sections 10, 16) ----

_NEW_NAMES = (
    "support_policy",
    "candidate_supports",
    "new_support_policy",
    "new_candidate_support",
    "new_candidate_supports",
    "reference_future_role_state",
    "reference_future_requested_terms_disambiguation",
    "span_proposition_id",
    # NOT "supporting_proposition_ids": I4-1j reused that exact field name for the candidate-support
    # schema's own corrected plural identity (section 3), but the literal string already, legitimately
    # predates I4-1j in `sufficiency_mapping.py` -- it is Phase 3's own, already-wired
    # `RoleBinding.provenance.supporting_proposition_ids` (the anchor-dedup provenance field; confirmed
    # present in real production data, e.g. `17_sufficiency_map.json`'s own c8 bindings:
    # `"supporting_proposition_ids": ["p20", "p9"]`). A bare substring scan cannot tell the two apart,
    # so including it here would fail on a genuine pre-existing feature, not a new consumption. The
    # genuinely new candidate-support API surface (`new_candidate_support`/`new_candidate_supports`,
    # already covered above) is what actually proves non-consumption for this schema.
)

_PRODUCTION_FILES_THAT_MUST_NOT_CONSUME_THE_NEW_SCHEMA = (
    "sufficiency_mapping.py",
    "sufficiency_recovery_targets.py",
    "sufficiency_diagnostic.py",
    "sufficiency_model_scope.py",
    "e2e.py",
)


@pytest.mark.parametrize("filename", _PRODUCTION_FILES_THAT_MUST_NOT_CONSUME_THE_NEW_SCHEMA)
def test_no_production_module_consumes_the_new_schema_names(filename):
    text = (HERE / filename).read_text(encoding="utf-8")
    allowed = (
        {"candidate_supports", "new_candidate_support", "span_proposition_id"}
        if filename == "sufficiency_mapping.py"
        else set()
    )
    offenders = [name for name in _NEW_NAMES if name not in allowed and name in text]
    assert offenders == [], f"{filename} already references {offenders} -- I4-1g must stay unconsumed"


def test_answer_plan_package_does_not_consume_the_new_schema_names():
    answer_plan_dir = HERE / "answer_plan"
    offenders = []
    for path in answer_plan_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}:{name}" for name in _NEW_NAMES if name in text]
    assert offenders == []


def test_recompute_instance_and_recompute_requirement_do_not_call_the_new_reference_helpers():
    """Same-file static guard: the engine's own production dispatch functions never call the new,
    reference-only helpers, and never read a support_policy/candidate_supports key."""
    source = (HERE / "sufficiency_engine.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guarded = {"recompute_instance", "recompute_requirement", "is_category_requirement", "category_goal_satisfied"}
    reference_only = {"reference_future_role_state", "reference_future_requested_terms_disambiguation"}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in guarded:
            calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            assert not (calls & reference_only), f"{node.name} must not call {calls & reference_only}"


def test_reference_helpers_are_never_called_by_any_other_function_in_this_module():
    source = (HERE / "sufficiency_engine.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    reference_only = {"reference_future_role_state", "reference_future_requested_terms_disambiguation"}
    defs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in reference_only}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in reference_only:
            calls = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            assert not (calls & reference_only), f"{node.name} must not call {calls & reference_only}"
    assert set(defs) == reference_only  # sanity: both helpers really exist, exactly once each


def test_versions_are_unchanged_for_sufficiency_and_plan():
    from experiments.ask_cli_revised.answer_plan import plan as ap

    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V5  # I4-2a integration
    assert ap.PLAN_VERSION == "answer-plan-step2-v4"
