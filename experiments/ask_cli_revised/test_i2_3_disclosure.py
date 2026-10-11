"""I2-3 presentation matrix over unchanged real v8 producers and Layer C consumers.

Detached cases exercise the pure disclosure seam, not fresh invocation authorization.
Public cases separately exercise the selected current answer and its bound context.
"""

import copy

import pytest

from experiments.ask_cli_revised import test_i4_3c_witness as w
from experiments.ask_cli_revised import test_layerc_integrity as h
from experiments.ask_cli_revised import test_profile_b_matrix as matrix
from experiments.ask_cli_revised import test_reviewed_fresh as public
from experiments.ask_cli_revised._layerc_common import plain
from experiments.ask_cli_revised.answer_plan import disclosure_v5 as disclosure
from experiments.ask_cli_revised.answer_plan import render_v5


def disclose(args, *, recovery=None, search=None):
    before = copy.deepcopy(args)
    baseline, projection = matrix.consume(args)
    result = copy.deepcopy(baseline)
    plan = result["plan"]
    recovery, search = recovery or {}, search or {}
    reqs = {q["id"]: q for c in args[0].values() for q in c["requirements"]}
    for node in plan["nodes"]:
        for facet in node["facets"]:
            facet["disclosures"] = disclosure.facet_disclosures(
                facet,
                reqs[facet["facet_id"]],
                projection.records,
                result["value_coverage"],
                recovery,
                search,
                result["relation_units"],
            )
    plan["source_qualifications"] = disclosure.source_qualifications(projection.records)
    plan["disclosure_context"] = {"recovery": recovery, "search": search}
    result["render"] = render_v5.render(plan, result["claims"], result["claim_evidence"], result["parent_synthesis"])
    assert args == before
    for field in ("claims", "claim_evidence", "relation_units", "value_coverage", "parent_synthesis"):
        assert result[field] == baseline[field]
    for old, new in zip(baseline["plan"]["nodes"], plan["nodes"], strict=True):
        assert old["state"] == new["state"]
        for a, b in zip(old["facets"], new["facets"], strict=True):
            assert a == {k: v for k, v in b.items() if k != "disclosures"}
    assert result["render"]["citations"] == baseline["render"]["citations"]
    for node in result["render"]["nodes"]:
        for statement in node["statements"]:
            for member in statement["members"]:
                receipt = result["claim_evidence"][member["receipt_ref"]]
                assert member["value_ref"] == receipt["value_ref"]
                assert member["source_ref"] in receipt["citation"]
    return result, baseline, projection


def atomic(status="eligible", *, located=True, relation="current_document", synthesis=False):
    quote = "We found alpha increased."
    candidate = w.candidate("P2", quote, status=status, text=None if located else "alpha")
    candidate["assertion_relation"] = relation
    if synthesis:
        candidate["aggregation"] = "literature_synthesis"
    candidate["support_policy_evaluation"] = w.sp.default_support_policy(
        **{k: candidate[k] for k in ("assertion_relation", "aggregation", "assertion_kind")}
    )
    return h.fixture({"outcome": w.binding("outcome", [candidate])}, {"P2": w.prop("P2", quote)})


def empty():
    return h.fixture({"outcome": w.binding("outcome", [])})


def facet(result):
    return result["plan"]["nodes"][0]["facets"][0]


def text(result):
    return result["render"]["layer1"]


def test_atomic_positive_and_plain_no_boilerplate():
    result, old, _ = disclose(atomic())
    assert text(result) == text(old) == "1. What was found?\nWe found alpha increased. [1]\n"
    assert facet(result)["state"] == "answered" and not facet(result)["disclosures"]


def test_relation_and_nonrepresentative_P2_citations():
    quote = "We found alpha was positively associated with beta."
    props = {"P1": w.prop("P1", "We found alpha increased."), "P2": w.prop("P2", quote)}
    args = h.fixture(
        {
            "evidence": w.binding("evidence", [w.candidate(pid, p["quote"]) for pid, p in props.items()]),
            "name": w.legacy("name", "P2", "beta"),
        },
        props,
    )
    result, old, _ = disclose(args)
    assert text(result) == text(old)
    assert facet(result)["relation_established"]
    related = [s for s in result["render"]["nodes"][0]["statements"] if "associated" in s["text"]]
    assert related and {m["proposition_id"] for s in related for m in s["members"]} == {"P2"}


def test_null_answers_reporting_but_not_positive_goal_or_recovery():
    pending = {"t": {"search_child_id": "c", "requirement_id": "r"}}
    result, old, _ = disclose(h.category(["Alpha was not significant."]), recovery=pending)
    assert facet(result)["state"] == "answered"
    assert facet(result)["scientific_goal_state"] == "incomplete"
    assert not facet(result)["recovery_closed_by_reporting"]
    assert "Alpha was not significant. [1]" in text(result)
    assert "does not establish the positive finding" in text(result)
    assert "completed scoped search is not recorded" in text(result)
    assert "positive finding" not in text(old)
    assert result["plan"]["disclosure_context"]["recovery"] == pending


def test_established_value_unavailable_for_display_is_not_absence():
    result, _, _ = disclose(atomic(located=False))
    assert facet(result)["scientific_goal_state"] == "established"
    assert "presentation limitation, not scientific absence" in text(result)
    assert "does not establish an answer" not in text(result)
    assert "search" not in text(result) and not result["render"]["citations"]


def test_one_authorized_path_avoids_redundant_display_warning():
    quote = "We found alpha increased."
    args = h.fixture(
        {"x": w.binding("x", [w.candidate("P2", quote), w.candidate("P2", quote, text=quote)])},
        {"P2": w.prop("P2", quote)},
    )
    result, _, _ = disclose(args)
    assert facet(result)["state"] == "answered" and not facet(result)["disclosures"]


@pytest.mark.parametrize("state", ["not_attempted", "not_completed", "completed"])
def test_scoped_search_disclosure_uses_stored_certification(state):
    status = {
        "r": {
            "completed": state == "completed",
            "terminal": state == "completed",
            "target_states": {"t": {"state": state, "reason_code": None}},
        }
    }
    result, _, _ = disclose(empty(), search=status)
    assert facet(result)["state"] == "not_established"
    assert not result["render"]["citations"]
    if state == "completed":
        assert "completed scoped search found no satisfying evidence" in text(result)
        assert "does not establish absence beyond that search" in text(result)
    elif state == "not_completed":
        assert "Recovery was attempted, but the scoped search is incomplete" in text(result)
    else:
        assert "Recovery has not completed" in text(result)
    assert result["plan"]["disclosure_context"]["search"] == status


def test_no_status_is_not_a_completed_empty_search():
    result, _, _ = disclose(empty())
    assert "completed scoped search is not recorded" in text(result)
    assert "found no satisfying evidence" not in text(result)


@pytest.mark.parametrize(
    "relation,synthesis,prefix",
    [
        ("attributed_external", False, "The source reports prior evidence:"),
        ("attributed_external", True, "The source reports a synthesis of prior evidence:"),
        ("current_document", True, "The source reports a synthesis:"),
        ("unresolved", True, "Synthesis evidence:"),
    ],
)
def test_ownership_comes_from_selected_path_metadata(relation, synthesis, prefix):
    result, old, projection = disclose(atomic(relation=relation, synthesis=synthesis))
    assert facet(result)["state"] == "answered"
    assert prefix in text(result) and prefix not in text(old)
    for q in result["plan"]["source_qualifications"].values():
        payload = projection.records["candidate_metadata"][q["candidate_metadata_ref"]]["payload"]
        assert q["assertion_relation"] == payload["assertion_relation"] == relation
    assert "[1]" in text(result)


def test_independently_supported_operands_do_not_establish_relation():
    props = {"P1": w.prop("P1", "We found alpha increased."), "P2": w.prop("P2", "We found beta increased.")}
    args = h.fixture({"a": w.legacy("a", "P1", "alpha"), "b": w.legacy("b", "P2", "beta")}, props)
    result, _, _ = disclose(args)
    assert facet(result)["relation_established"] is False
    assert "separately supported findings do not suffice" in text(result)
    assert all(not u["relation_witnessed"] for u in result["relation_units"].values())


@pytest.mark.parametrize("status", ["policy", "guard", "both", "ambiguous", "ambiguous_excluded"])
def test_exclusions_and_attachment_are_orthogonal_and_never_citations(status):
    result, _, _ = disclose(atomic(status))
    kinds = {d["kind"] for d in facet(result)["disclosures"]}
    assert ("attachment_uncertainty" in kinds) == (status in ("ambiguous", "ambiguous_excluded"))
    assert ("excluded_evidence" in kinds) == (status != "ambiguous")
    assert not result["claims"] and not result["render"]["citations"]
    assert "We found alpha increased" not in text(result)


def test_direction_conflict_is_aligned_and_disclosed():
    first = "We found alpha was positively associated with beta."
    quote = first + " We found alpha was negatively associated with beta."
    args = h.fixture(
        {
            "evidence": w.binding(
                "evidence",
                [w.candidate("P2", quote, [0, len(first)]), w.candidate("P2", quote, [len(first) + 1, len(quote)])],
            ),
            "name": w.legacy("name", "P2", "alpha"),
        },
        {"P2": w.prop("P2", quote)},
        observe=True,
    )
    req = args[0]["c"]["requirements"][0]
    req["direction_summary"] = w.se.summarize_observations(
        req["instances"], "direction_observations", "sign", observation_filter=w.se.counts_toward_relation_direction
    )
    result, _, projection = disclose(h.refresh_authored(args))
    assert "Direction observations conflict for the same finding" in text(result)
    assert "positively associated" in text(result) and "negatively associated" in text(result)
    for d in facet(result)["disclosures"]:
        if d["kind"] == "observation_conflict":
            assert all(ref in projection.records["summaries"] for ref in d["evidence_refs"])


def test_mixed_reporting_and_science_keep_category_distinctions():
    args = h.category(
        ["Alpha increased.", "Beta was not significant.", "Gamma was measured."], terms=["Alpha", "Beta", "Gamma"]
    )
    result, _, _ = disclose(args)
    assert facet(result)["state"] == "partial"
    assert facet(result)["category_axes"]["Alpha"]["scientific_goal_state"] == "established"
    assert facet(result)["category_axes"]["Beta"]["reported_finding"] == "null_finding"
    assert "Alpha increased." in text(result) and "Beta was not significant." in text(result)
    assert "answers only part" in text(result) and "positive finding sought" in text(result)


@pytest.mark.parametrize("relational", [False, True])
def test_public_current_selected_answer_no_extra_boilerplate(monkeypatch, relational):
    result = public.run_public(monkeypatch, relational=relational, recovery=True)
    output = result["layerc_v2"]
    assert output["plan"]["sufficiency_identity"] == {"status": "current", "version": w.V}
    assert output["plan"]["plan_version"] == "answer-plan-step2-v5"
    assert result["selected_answer"] == text(output)
    assert len(result["selected_answer"].splitlines()) == 2
    assert not facet(output)["disclosures"]
    assert plain(output["plan"]["disclosure_context"]) == {"recovery": {}, "search": {}}


def reviewed_values(*, category=False, empty_allowed=False):
    values = list(public.inputs())
    cid = next(iter(values[1]))
    if category:
        spec = w.se.new_role_spec("category", "category", "explicit_category_terms", requested_category_terms=["alpha"])
        req = w.se.new_requirement(
            "result-obligation",
            "cardinality",
            {"category": spec},
            w.se.new_role_completion(required_roles=["category"]),
            "all_requested_categories",
        )
        values[1] = {cid: w.se.frozen_view(w.se.new_contract(cid, [req]))}
    values[1][cid]["requirements"][0]["empty_result_semantically_allowed"] = empty_allowed
    values[2] = public.rc.single_question(values[0], values[1], requested_construct_terms=["alpha"])
    values[4]["inputs"] = public.reviewed_ask_inputs.input_refs(*values[:4])
    return values


def test_public_null_disclosure_is_in_selected_answer(monkeypatch):
    result = public.run_public(monkeypatch, values=reviewed_values(category=True), quote="alpha was not significant.")
    output = result["layerc_v2"]
    assert facet(output)["report_state"] == "answered"
    assert facet(output)["scientific_goal_state"] == "incomplete"
    assert "alpha was not significant." in result["selected_answer"]
    assert "does not establish the positive finding" in result["selected_answer"]
    assert "scoped search" in result["selected_answer"]
    assert output["plan"]["disclosure_context"]["recovery"]


@pytest.mark.parametrize("completed", [False, True])
def test_public_scoped_recovery_disclosure_is_in_selected_answer(monkeypatch, completed):
    result = public.run_public(
        monkeypatch,
        values=reviewed_values(empty_allowed=True),
        no_evidence=True,
        sufficiency_recovery=True,
        recovery_reason="recovery_no_new_evidence" if completed else "no_search",
    )
    output = result["layerc_v2"]
    status = output["plan"]["disclosure_context"]["search"]["result-obligation"]
    assert status["completed"] is completed and status["terminal"] is completed
    assert facet(output)["state"] == "not_established"
    expected = "completed scoped search found no satisfying evidence" if completed else "scoped search is incomplete"
    assert expected in result["selected_answer"]
    assert not output["render"]["citations"]


def test_preserved_p8_p36_null_reporting_disclosure_without_history_mutation():
    from experiments.ask_cli_revised import layerc_consumer, producer_replay, profile_b
    from experiments.ask_cli_revised.claim_v2 import requirements

    rep = producer_replay.reproduce_accepted_v8()
    bound = layerc_consumer.verify_and_project(
        rep.smap,
        rep.input_bundle.files["preserved-run/11_verified_ledger.json"],
        rep.authored_contract,
        rep.receipt,
        input_bundle=rep.input_bundle,
    )
    result = profile_b._build_components(bound.projection, bound.authored, bound.sealed, bound.producer_authorization)
    original = copy.deepcopy(result)
    # A detached presentation probe, NOT a modified or reauthorized historical replay.
    target = next(n for n in result["plan"]["nodes"] if n["label"] == "3")
    category = next(f for f in target["facets"] if f["category_axes"])
    category["disclosures"] = disclosure.facet_disclosures(
        category,
        requirements(bound.authored)[(category["child_id"], category["facet_id"])],
        bound.projection.records,
        result["value_coverage"],
        plain(rep.input_bundle.recovery_targets),
        {},
        result["relation_units"],
    )
    rendered = render_v5.render(result["plan"], result["claims"], result["claim_evidence"], result["parent_synthesis"])
    assert "does not establish the positive finding" in rendered["layer1"]
    assert category["state"] == "answered" and category["scientific_goal_state"] == "incomplete"
    assert category["category_axes"]["implicit"]["reported_finding"] == "null_finding"
    assert rendered["citations"] == original["render"]["citations"]
    assert result["claims"] == original["claims"] and result["value_coverage"] == original["value_coverage"]
