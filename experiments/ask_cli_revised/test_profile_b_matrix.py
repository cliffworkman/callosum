"""Domain-neutral proof/value matrices through the detached v2 consumers.

Synthetic projections deliberately use the C test authority seam. They cannot acquire a D1
registry enrollment or enter the production profile-B output-authorization boundary.
"""

import copy
import json
from types import SimpleNamespace

import pytest

from experiments.ask_cli_revised import profile_b
from experiments.ask_cli_revised import test_i4_3c_witness as w
from experiments.ask_cli_revised import test_layerc_integrity as h
from experiments.ask_cli_revised import test_layerc_matrix as frozen_matrix
from experiments.ask_cli_revised import test_layerc_projection as f
from experiments.ask_cli_revised._layerc_common import ProjectionIntegrityError, canonical


def consume(args):
    smap, raw, authored = args
    smap = copy.deepcopy(smap)
    for child in smap.values():
        for req in child["requirements"]:
            req.setdefault("kind", "relational" if len(req["role_completion"]["required_roles"]) > 1 else "cardinality")
    authored = f.authored(smap)
    authored = copy.deepcopy(authored)
    authored["overlay"] = {
        "nodes": [{"label": "1", "literal_text": "What was found?", "owning_child_ids": list(smap)}],
        "requested_construct_terms": [],
        "facet_phrases": {},
    }
    projection = f.project((smap, raw, authored))
    before = canonical([smap, authored])
    fake = SimpleNamespace(
        authorization_ref="TEST-ONLY-NOT-ENROLLED",
        identities={
            "profile_ref": "TEST-ONLY",
            "sufficiency_identity": {"status": "supported_noncurrent", "version": w.V},
        },
    )
    result = profile_b._build_components(projection, authored, json.loads(raw), fake)
    assert canonical([smap, authored]) == before
    return result, projection


def relation_claims(x):
    return [c for c in x["claims"] if c["semantic_identity"]["family"] == "relational"]


@pytest.mark.parametrize(
    "case,mode,established,display_input,future", frozen_matrix.MATRIX, ids=[x[0] for x in frozen_matrix.MATRIX]
)
def test_all_frozen_A_R_inputs_through_consumers(monkeypatch, case, mode, established, display_input, future):
    original = f.project
    consumed = []

    def project_through(args, contexts=()):
        assert not contexts
        with monkeypatch.context() as restore:
            restore.setattr(f, "project", original)
            result, projection = consume(args)
        consumed.append(result)
        return projection

    monkeypatch.setattr(f, "project", project_through)
    frozen_matrix.test_value_coverage_matrix(case, mode, established, display_input, future)
    assert consumed or future == "reject_inconsistent"
    for result in consumed:
        for node in result["render"]["nodes"]:
            for statement in node["statements"]:
                for member in statement["members"]:
                    receipt = result["claim_evidence"][member["receipt_ref"]]
                    assert receipt["value_ref"] == member["value_ref"]
                    assert member["source_ref"] in receipt["citation"]


def test_P2_nonrepresentative_and_order_reversal():
    quote = "We found alpha was positively associated with beta."
    props = {pid: w.prop(pid, quote) for pid in ("P1", "P2")}
    candidates = [w.candidate(pid, quote) for pid in props]
    results = []
    for ordered in (candidates, list(reversed(candidates))):
        args = h.fixture({"evidence": w.binding("evidence", ordered), "name": w.legacy("name", "P2", "beta")}, props)
        original = copy.deepcopy(h.instance(args)["role_bindings"])
        result, projection = consume(args)
        relations = relation_claims(result)
        assert len(relations) == 1
        for unit in result["relation_units"].values():
            assert unit["semantic_establishedness"] == "established" and unit["witness_ids"] == ["P2"]
            for path in unit["paths"]:
                for vid in path["selected_support_refs"].values():
                    assert projection.records["support_views"][vid]["supporting_proposition_ids"] == ("P2",)
        assert h.instance(args)["role_bindings"] == original
        receipts = [r for r in result["claim_evidence"].values() if r["claim_ref"] == relations[0]["claim_id"]]
        for receipt in receipts:
            assert all(projection.records["sources"][ref]["proposition_id"] == "P2" for ref in receipt["citation"])
        results.append((relations, result["relation_units"]))
    assert results[0] == results[1]


@pytest.mark.parametrize("status", ["policy", "guard", "both", "ambiguous", "ambiguous_excluded"])
def test_excluded_or_ambiguous_candidate_never_positive(status):
    quote = "We found alpha increased."
    args = h.fixture({"x": w.binding("x", [w.candidate("P2", quote, status=status)])}, {"P2": w.prop("P2", quote)})
    result, projection = consume(args)
    assert not result["claims"] and not result["claim_evidence"]
    assert not projection.records["value_coverage"]


def test_zero_eligible_with_stale_representative_cannot_render():
    quote = "We found alpha increased."
    binding = w.binding("x", [w.candidate("P2", quote, status="policy")])
    binding.update(proposition_id="P2", exact_text=quote)
    result, _ = consume(h.fixture({"x": binding}, {"P2": w.prop("P2", quote)}))
    assert not result["claims"] and not result["render"]["nodes"][0]["statements"]


def test_multiple_paths_same_tuple_and_distinct_tuple_identity():
    quotes = {"P1": "We found alpha increased.", "P2": "We found alpha increased.", "P3": "We found beta increased."}
    props = {pid: w.prop(pid, quote) for pid, quote in quotes.items()}
    args = h.fixture(
        {
            "x": w.binding("x", [w.candidate(pid, quotes[pid]) for pid in ("P1", "P2")]),
            "y": w.binding("y", [w.candidate(pid, quotes[pid], [8, 13]) for pid in ("P1", "P2")]),
        },
        props,
    )
    result, _ = consume(args)
    assert len(relation_claims(result)) == 1
    assert len(relation_claims(result)[0]["relation_proof_refs"]) == 4
    assert {pid for u in result["relation_units"].values() for pid in u["witness_ids"]} == {"P1", "P2"}
    repeated = copy.deepcopy(args)
    for binding in h.instance(repeated)["role_bindings"].values():
        binding["candidate_supports"].append(copy.deepcopy(binding["candidate_supports"][0]))
    # A duplicate input path is deduplicated by the producer's frozen support identity.
    duplicated, _ = consume(repeated)
    for key in ("claims", "claim_evidence", "relation_units", "value_coverage", "render"):
        assert result[key] == duplicated[key]
    # Different operands create a different semantic claim, independent of evidence IDs.
    other, _ = consume(
        h.fixture({"x": w.binding("x", [w.candidate("P3", quotes["P3"])]), "y": w.legacy("y", "P3", "beta")}, props)
    )
    assert relation_claims(result)[0]["claim_id"] != relation_claims(other)[0]["claim_id"]


def test_inherited_operand_is_typed_and_never_own_witness_authority():
    quote = "We found alpha was positively associated with beta."
    args = h.fixture(
        {"x": w.binding("x", [w.candidate("P2", quote)]), "y": w.legacy("y", "P1", "beta", source="parent_context")},
        {"P1": w.prop("P1", "beta"), "P2": w.prop("P2", quote)},
    )
    result, _ = consume(args)
    assert relation_claims(result)
    for unit in result["relation_units"].values():
        assert unit["witness_ids"] == ["P2"]
        assert all(path["operand_sources"]["y"] == "inherited" for path in unit["paths"])


def test_link_only_completion_keeps_science_without_fake_I1_or_quote():
    args = h.fixture(
        {"a": w.legacy("a", "P1", "XYZ"), "b": w.legacy("b", "P2", "XYZ")},
        {"P1": w.prop("P1", "XYZ"), "P2": w.prop("P2", "XYZ")},
        context={"attachment_pieces": ["XYZ"]},
        verifiers=["contract_directed_links"],
    )
    result, _ = consume(args)
    assert relation_claims(result)
    for unit in result["relation_units"].values():
        assert unit["semantic_establishedness"] == "established"
        assert unit["relation_witnessed"] is False and not unit["witness_ids"]
        assert unit["renderability"] == "restricted"
    assert not result["render"]["nodes"][0]["statements"]


@pytest.mark.parametrize("second", ["negatively", "positively"])
def test_aligned_opposite_or_same_sign_without_first_path_wins(second):
    first = "We found alpha was positively associated with beta."
    rest = "We found alpha was " + second + " associated with beta."
    quote = first + " " + rest
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
    args = h.refresh_authored(args)
    result, projection = consume(args)
    assert len(projection.records["observations"]) >= 2
    claims = [c for c in result["claims"] if c["semantic_identity"]["family"] == "direction_or_effectiveness"]
    assert len(claims) == 1
    content = claims[0]["semantic_identity"]["content"]
    assert content["consensus"] == (None if second == "negatively" else "positive")
    assert content["conflict"]["has_within_instance_conflict"] == (second == "negatively")
    assert content["conflict"]["has_across_instance_heterogeneity"] is False


@pytest.mark.parametrize("complete", [False, True])
def test_effectiveness_conflict_preserves_completeness_without_new_I1_gate(complete):
    first = "We found alpha increased."
    quote = first + " We found no evidence that alpha increased."
    bindings = {
        "a": w.binding(
            "a", [w.candidate("P2", quote, [0, len(first)]), w.candidate("P2", quote, [len(first) + 1, len(quote)])]
        )
    }
    if not complete:
        bindings["b"] = w.se.new_role_binding("b", state="missing")
    args = h.fixture(bindings, {"P2": w.prop("P2", quote)}, observe=True)
    req = args[0]["c"]["requirements"][0]
    req["effectiveness_summary"] = w.se.summarize_observations(
        req["instances"], "effectiveness_observations", "conclusion"
    )
    result, projection = consume(h.refresh_authored(args))
    assert sorted(
        o["record"]["conclusion"] for o in projection.records["observations"].values() if o["kind"] == "effectiveness"
    ) == ["not_supported", "supported"]
    summaries = [c for c in result["claims"] if c["semantic_identity"]["family"] == "direction_or_effectiveness"]
    assert bool(summaries) == complete
    if complete:
        assert summaries[0]["semantic_identity"]["content"]["consensus"] is None
        assert summaries[0]["semantic_identity"]["content"]["conflict"]["has_within_instance_conflict"]


@pytest.mark.parametrize("mutation", ["proof", "excluded", "strategy", "foreign_category"])
def test_invalid_projection_never_enters_v2_consumers(mutation):
    args = h.category() if mutation == "foreign_category" else h.fixture()
    inst = h.instance(args)
    if mutation == "proof":
        next(iter(inst["witness_bundle"]["proofs"].values()))["assignment"] = {}
    elif mutation == "excluded":
        inst["role_bindings"]["evidence"]["candidate_supports"][0]["admissible"] = False
    elif mutation == "strategy":
        args[0]["c"]["requirements"][0]["role_specs"]["name"]["mapping_strategy"] = "unknown"
        args = h.refresh_authored(args)
    else:
        inst["category_observations"][0]["term"] = "foreign"
    with pytest.raises(ProjectionIntegrityError):
        consume(args)


@pytest.mark.parametrize(
    "wrapper",
    [
        "{x}.",
        "  {x}",
        "Nevertheless, {x}.",
        "However, {x}.",
        "Results: {x}.",
        "Prior work reports {x}.",
        "{x} while beta decreased.",
        "{x}6",
        "{x} (p < 0.05)",
        "{x}; beta decreased.",
        "{x}: beta decreased.",
        '"{x}"',
        "Figure 1: {x}.",
        "Jones found {x}.",
    ],
)
def test_accepted_wrapper_matrix_through_presentation(wrapper):
    text = "we found alpha increased"
    quote = wrapper.format(x=text)
    start = quote.index(text)
    args = h.fixture(
        {"x": w.binding("x", [w.candidate("P2", quote, [start, start + len(text)])])}, {"P2": w.prop("P2", quote)}
    )
    result, _ = consume(args)
    for row in result["value_coverage"].values():
        for item in row["accepted"]:
            assert item["raw_sentence"].strip() in (text, text + ".")


def test_unlocated_established_value_retained_without_display():
    quote = "We found alpha increased."
    result, _ = consume(
        h.fixture(
            {"x": w.binding("x", [w.candidate("P2", quote, text="alpha", span=None)])}, {"P2": w.prop("P2", quote)}
        )
    )
    assert result["claims"]
    assert all(
        p["scientific_goal_state"] == "established" and p["display_state"] == "unavailable"
        for p in result["value_coverage"].values()
    )
    assert result["plan"]["nodes"][0]["state"] == "partial"


@pytest.mark.parametrize(
    "policy,second_located,expected",
    [
        ("exists", False, "answered"),
        ("for_each_discovered_instance", False, "partial"),
        ("for_each_discovered_instance", True, "answered"),
        ("at_least_n", False, "partial"),
        ("at_least_n", True, "answered"),
        ("open_list", True, "partial"),
    ],
)
def test_reporting_quantifier_never_unions_across_instances(policy, second_located, expected):
    quote = "We found alpha increased."
    props = {"P2": w.prop("P2", quote)}
    args = h.fixture({"x": w.binding("x", [w.candidate("P2", quote)])}, props)
    second = w.candidate("P2", quote) if second_located else w.candidate("P2", quote, text="alpha", span=None)
    _, inst = w.run({"x": w.binding("x", [second])}, props, key="second")
    req = args[0]["c"]["requirements"][0]
    req["instances"].append(inst)
    req["instance_quantifier"] = policy
    req["quantifier_n"] = 2 if policy == "at_least_n" else None
    if policy == "open_list":
        req["state"] = "partially_filled"
    result, _ = consume(h.refresh_authored(args))
    assert result["plan"]["nodes"][0]["state"] == expected


def test_generic_summary_keys_use_the_existing_presentation_canonicalization(monkeypatch):
    from experiments.ask_cli_revised import layerc_presentation as presentation

    quote = "We found Alpha increased."
    observed = []
    original = presentation.cl.evaluate_sentence

    def inspected(sentence, pid, ctx, requirements, **kwargs):
        observed.append(ctx.generic_requirements(ctx.props[pid]["quote"]))
        return original(sentence, pid, ctx, requirements, **kwargs)

    monkeypatch.setattr(presentation.cl, "evaluate_sentence", inspected)
    consume(h.fixture({"x": w.binding("x", [w.candidate("P2", quote)])}, {"P2": w.prop("P2", quote)}))
    assert observed and all(ids == ["r"] for ids in observed)


@pytest.mark.parametrize("mode", ["alternative", "two_values_one_source", "null", "scope", "duplicate", "physical"])
def test_category_coverage_pairs_through_consumers(mode):
    sentences = ["Alpha increased.", "Alpha increased in another sample."]
    terms = ("Alpha",)
    if mode == "two_values_one_source":
        sentences, terms = ["Alpha increased while Beta decreased."], ("Alpha", "Beta")
    if mode == "null":
        sentences = ["Alpha was not significant."]
    if mode in ("duplicate", "physical"):
        sentences = ["Alpha increased.", "Alpha increased."]
    args = h.category(sentences, terms=terms)
    if mode == "duplicate":
        obs = h.instance(args)["category_observations"]
        obs.append(copy.deepcopy(obs[0]))
        obs.reverse()
    result, projection = consume(args)
    assert result["claims"]
    for receipt in result["claim_evidence"].values():
        for ref in receipt["scientific_coverage"]:
            if ref["kind"] == "category_observation":
                obs = projection.records["category_observations"][ref["ref"]]
                value = projection.records["semantic_values"][receipt["value_ref"]]
                assert obs["observation"]["term"] == value["literal"]
    if mode == "null":
        assert all(
            r["scientific_goal_state"] == "unestablished" and r["reported_finding"] == "null_finding"
            for r in result["claim_evidence"].values()
        )
    if mode == "scope":
        other, _ = consume(h.category(sentences, requirement_id="other"))
        assert {c["claim_id"] for c in result["claims"]}.isdisjoint(c["claim_id"] for c in other["claims"])
