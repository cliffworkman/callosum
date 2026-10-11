"""Accepted domain-neutral A-J semantic controls, retained with the fresh entry."""

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import test_profile_b_matrix as m
from experiments.ask_cli_revised import test_profile_b_static as routing


def consume(args):
    result, projection = m.consume(args)
    for node in result["render"]["nodes"]:
        for statement in node["statements"]:
            for item in statement["members"]:
                receipt = result["claim_evidence"][item["receipt_ref"]]
                assert receipt["value_ref"] == item["value_ref"]
                assert item["source_ref"] in receipt["citation"]
    assert result["plan"]["plan_version"] == "answer-plan-step2-v5"
    return result, projection


def test_A_atomic_named_value():
    args = m.h.fixture({"item": m.w.legacy("item", "P2", "alpha")}, {"P2": m.w.prop("P2", "We found alpha increased.")})
    result, _ = consume(args)
    assert len(result["claims"]) == 1
    assert result["claims"][0]["semantic_identity"]["family"] == "role_value"
    assert result["plan"]["nodes"][0]["state"] == "answered"


def test_B_same_proposition():
    quote = "We found alpha was positively associated with beta."
    result, projection = consume(
        m.h.fixture(
            {"outcome": m.w.binding("outcome", [m.w.candidate("P2", quote)]), "item": m.w.legacy("item", "P2", "beta")},
            {"P2": m.w.prop("P2", quote)},
        )
    )
    assert m.relation_claims(result)
    assert result["plan"]["nodes"][0]["state"] == "answered"
    assert all(u["relation_witnessed"] and u["witness_ids"] == ["P2"] for u in result["relation_units"].values())


def test_C_incompatible():
    quote = "We found alpha was positively associated with beta."
    result, _ = consume(
        m.h.fixture(
            {"outcome": m.w.binding("outcome", [m.w.candidate("P1", quote)]), "item": m.w.legacy("item", "P2", "beta")},
            {p: m.w.prop(p, quote) for p in ("P1", "P2")},
        )
    )
    assert result["claims"] and not m.relation_claims(result)
    assert not any(u["relation_witnessed"] for u in result["relation_units"].values())
    assert result["plan"]["nodes"][0]["state"] == "partial"


def test_D_category_positive():
    result, _ = consume(m.h.category(["Amber increased."], terms=("Amber",)))
    facet = result["plan"]["nodes"][0]["facets"][0]
    assert facet["state"] == "answered"
    assert facet["category_axes"]["Amber"]["reported_finding"] == "positive_finding"


def test_E_category_null():
    result, _ = consume(m.h.category(["Amber was not significant."], terms=("Amber",)))
    facet = result["plan"]["nodes"][0]["facets"][0]
    assert facet["state"] == "answered"
    assert facet["category_axes"]["Amber"]["scientific_goal_state"] == "unestablished"
    assert facet["category_axes"]["Amber"]["reported_finding"] == "null_finding"
    assert not facet["recovery_closed_by_reporting"]


def test_F_independent_members():
    result, projection = consume(m.h.category(["Amber increased.", "Cobalt increased."], terms=("Amber", "Cobalt")))
    values = {p["value_ref"] for p in result["value_coverage"].values()}
    assert len(values) == 2
    for receipt in result["claim_evidence"].values():
        literal = projection.records["semantic_values"][receipt["value_ref"]]["literal"]
        expected = "P0" if literal == "Amber" else "P1"
        assert {projection.records["sources"][s]["proposition_id"] for s in receipt["citation"]} == {expected}


def test_G_inherited():
    m.test_inherited_operand_is_typed_and_never_own_witness_authority()


def test_H_nonrepresentative():
    m.test_P2_nonrepresentative_and_order_reversal()


def test_I_opposite_direction():
    m.test_aligned_opposite_or_same_sign_without_first_path_wins("negatively")


def test_J_legacy_default(tmp_path):
    routing.test_default_and_legacy_route_never_activate_B(tmp_path)
    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V7
