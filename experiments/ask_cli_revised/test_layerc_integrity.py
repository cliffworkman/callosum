"""Generic substrate integrity, authority, wrapper and identity controls."""

import copy
import json

import pytest

from experiments.ask_cli_revised import layerc_projection as lp
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import test_i4_3c_witness as h
from experiments.ask_cli_revised import test_layerc_projection as f
from experiments.ask_cli_revised._layerc_common import (
    V8,
    ProjectionIntegrityError,
    canonical,
    digest,
    display_envelope,
    plain,
    semantic_claim_id,
)


def sealed(props):
    return canonical(
        {
            "verified_propositions": list(props.values()),
            "evidence_spans": [
                {
                    "paper_id": p["paper_id"],
                    "chunk_id": p["evidence_anchor_chunk_id"],
                    "span_id": p["evidence_span_id"],
                    "text": p["quote"],
                }
                for p in props.values()
            ],
        }
    ).encode()


def fixture(bindings=None, props=None, observe=False, context=None, verifiers=None):
    props = props or {"P2": h.prop("P2")}
    bindings = bindings or {
        "evidence": h.binding("evidence", [h.candidate("P2", props["P2"]["quote"])]),
        "name": h.legacy("name", text="beta"),
    }
    req, inst = h.run(bindings, props, observe=observe, context=context, verifiers=verifiers)
    req.update(
        role_specs={
            r: se.new_role_spec(
                r,
                "generic",
                "achieved_outcome_predicate" if "candidate_supports" in b else "model_nomination_only",
                disqualifying_guards=["hedged"] if "candidate_supports" in b else [],
            )
            for r, b in bindings.items()
        },
        instance_quantifier="exists",
        quantifier_n=None,
        instances=[inst],
        state=inst["state"],
    )
    smap = {"c": {"sufficiency_semantics_version": V8, "requirements": [req]}}
    return smap, sealed(props), f.authored(smap)


def category(sentences=("Alpha increased.",), terms=("Alpha",), requirement_id="r"):
    props = {f"P{i}": h.prop(f"P{i}", text) for i, text in enumerate(sentences)}
    units = [{"unit_id": pid, "proposition_ids": [pid], "passage": p["quote"], "flags": {}} for pid, p in props.items()]
    spec = se.new_role_spec("category", "category", "explicit_category_terms", requested_category_terms=terms)
    req = se.new_requirement(
        requirement_id,
        "cardinality",
        {"category": spec},
        se.new_role_completion(required_roles=["category"]),
        "all_requested_categories",
    )
    req = sm.map_cardinality_requirement(
        req,
        units,
        semantics_version=V8,
        witness_context={"child_id": "c", "requirement_id": requirement_id, "proposition_index": props},
    )
    smap = {"c": {"sufficiency_semantics_version": V8, "requirements": [req]}}
    return smap, sealed(props), f.authored(smap)


def instance(args):
    return args[0]["c"]["requirements"][0]["instances"][0]


def refresh_authored(args):
    return args[0], args[1], f.authored(args[0])


@pytest.mark.parametrize(
    "text,polarity,goal,positive,report",
    [
        ("Alpha increased.", "positive_finding", "established", True, True),
        ("Alpha was not significant.", "null_finding", "unestablished", False, True),
        ("Alpha was measured.", "mentioned_only", "unestablished", False, False),
        ("Alpha did not increase.", "unknown", "unestablished", False, False),
    ],
)
def test_category_scientific_reporting_separation(text, polarity, goal, positive, report):
    p = f.project(category([text])).records
    receipt = next(iter(p["value_coverage"].values()))
    assert receipt["scientific_goal_state"] == goal
    assert receipt["reported_finding"] == polarity
    assert bool(receipt["scientific_coverage_refs"]) == positive
    assert bool(receipt["typed_reporting_refs"]) == report
    assert receipt["presentation"]["finalization_required"]


@pytest.mark.parametrize(
    "mutation",
    [
        "term",
        "instance",
        "role",
        "requirement",
        "polarity",
        "classifier",
        "source",
        "guard",
        "audit",
        "missing",
    ],
)
def test_category_integrity(mutation):
    args = category()
    inst = instance(args)
    obs = inst["category_observations"][0]
    if mutation == "term":
        obs["term"] = "Beta"
    elif mutation == "instance":
        inst["instance_key"] = "Beta"
    elif mutation == "role":
        inst["witness_bundle"]["placement"]["role"] = "foreign"
    elif mutation == "requirement":
        inst["witness_bundle"]["placement"]["requirement_id"] = "foreign"
    elif mutation == "polarity":
        obs["observation_polarity"] = "contrary_finding"
    elif mutation == "classifier":
        obs["classifier"] = "future"
    elif mutation == "source":
        obs["source_passage"] = "Beta increased."
    elif mutation == "guard":
        args[0]["c"]["requirements"][0]["role_specs"]["category"]["disqualifying_guards"] = ["hedged"]
        obs["guard"]["hedged"] = True
        args = refresh_authored(args)
    elif mutation == "audit":
        obs["classifier_audit"] = {}
    else:
        inst["role_bindings"]["category"]["state"] = "missing"
    with pytest.raises(ProjectionIntegrityError):
        f.project(args)


def test_ambiguous_category_does_not_gain_coverage():
    args = category()
    instance(args)["category_observations"][0]["ambiguity"] = "uncertain_attachment"
    p = f.project(args).records
    receipt = next(iter(p["value_coverage"].values()))
    assert not receipt["scientific_coverage_refs"] and not receipt["authorized_display_source_refs"]


def test_category_duplicate_reorder_and_distinct_sources():
    args = category(["Alpha increased.", "Alpha increased."])
    a = f.project(args).records
    inst = instance(args)
    inst["category_observations"].reverse()
    inst["category_observations"].append(copy.deepcopy(inst["category_observations"][0]))
    b = f.project(args).records
    assert a["semantic_values"] == b["semantic_values"]
    assert a["category_observations"] == b["category_observations"]
    assert a["value_coverage"] == b["value_coverage"]
    assert len(b["category_observations"]) == 2


def test_no_cross_value_or_cross_scope_text_borrowing():
    args = category(["Alpha increased, but Beta was measured."], terms=("Alpha", "Beta"))
    p = f.project(args).records
    for receipt in p["value_coverage"].values():
        for edge in receipt["scientific_coverage_refs"]:
            assert (
                p["category_observations"][edge["ref"]]["observation"]["term"] == receipt["placement"]["instance_key"]
            )
    other = f.project(category(["Alpha increased."], requirement_id="another")).records
    assert not set(p["semantic_values"]).intersection(other["semantic_values"])


@pytest.mark.parametrize(
    "wrapper,allowed",
    [
        ("{x}.", True),
        ("  {x}", True),
        ("Nevertheless, {x}.", True),
        ("However, {x}.", True),
        ("Results: {x}.", True),
        ("Prior work reports {x}.", True),
        ("{x} while beta decreased.", False),
        ("{x}6", False),
        ("{x} (p < 0.05)", False),
        ("{x}; beta decreased.", False),
        ("{x}: beta decreased.", False),
        ('"{x}"', False),
        ("Figure 1: {x}.", True),
        ("Jones found {x}.", True),
    ],
)
def test_envelope_matrix(wrapper, allowed):
    text = "we found alpha increased"
    quote = wrapper.format(x=text)
    at = quote.index(text)
    _, e = display_envelope("source", quote, [at, at + len(text)])
    rendered = quote[slice(*e["display_span"])]
    assert rendered.strip() in (text, text + ".")
    assert rendered.strip().endswith(".") == (allowed and quote[at + len(text) :].startswith("."))
    assert e["semantic_support_added"] is False
    assert all(a["text"].strip() in ("", ".") for a in e["added_intervals"])


def test_envelope_overrun_and_semantic_crossing():
    with pytest.raises(ProjectionIntegrityError):
        display_envelope("s", "alpha", [0, 99])
    _, e = display_envelope("s", "alpha then beta.", [0, 5])
    assert e["display_span"] == [0, 6]
    assert e["added_intervals"][0]["text"] == " "


@pytest.mark.parametrize(
    "mutation",
    [
        "record",
        "quote_hash",
        "locator",
        "proof_placement",
        "proof_tuple",
        "own",
        "observation",
        "unknown_strategy",
        "payload_conflict",
    ],
)
def test_stored_reference_integrity(mutation):
    args = fixture(observe=True)
    i = instance(args)
    b = i["witness_bundle"]
    if mutation == "record":
        next(iter(b["support_records"].values()))["exact_text"] = "substitute"
    elif mutation == "quote_hash":
        b["sealed_input_sha256"] = "0" * 64
    elif mutation == "locator":
        raw = json.loads(args[1])
        raw["evidence_spans"][0]["chunk_id"] = "foreign"
        args = args[0], canonical(raw).encode(), args[2]
    elif mutation == "proof_placement":
        next(iter(b["proofs"].values()))["placement"]["child_id"] = "foreign"
    elif mutation == "proof_tuple":
        next(iter(b["proofs"].values()))["assignment"]["name"]["support_view_id"] = "missing"
    elif mutation == "own":
        next(iter(b["support_views"].values()))["immediate_operand_source"] = "inherited"
    elif mutation == "observation":
        i["direction_observations"][0]["evidence_alignment"]["paths"][0]["basis_ref"] = "orphan"
    elif mutation == "unknown_strategy":
        args[0]["c"]["requirements"][0]["role_specs"]["name"]["mapping_strategy"] = "guess_entity"
        args = refresh_authored(args)
    else:
        c = copy.deepcopy(i["role_bindings"]["evidence"]["candidate_supports"][0])
        c["authority_veto"] = "absence_of_evidence"
        i["role_bindings"]["evidence"]["candidate_supports"].append(c)
    with pytest.raises(ProjectionIntegrityError):
        f.project(args)


def test_null_legacy_and_unlocated_candidate_are_diagnostics():
    args = fixture({"name": h.legacy("name", text=None)})
    p = f.project(args).records
    assert not p["semantic_values"] and p["diagnostics"][0]["reason"] == "value_unresolvable"
    quote = "alpha increased."
    c = h.candidate("P2", quote, text="alpha increased", span=None)
    p = f.project(fixture({"evidence": h.binding("evidence", [c])}, {"P2": h.prop("P2", quote)})).records
    r = next(iter(p["value_coverage"].values()))
    assert r["scientific_goal_state"] == "established" and "source_unlocated" in r["limitations"]
    assert not r["authorized_display_source_refs"]


@pytest.mark.parametrize("status", ["guard", "policy", "both", "ambiguous", "ambiguous_excluded"])
def test_excluded_and_ambiguous_never_positive(status):
    props = {"P2": h.prop("P2")}
    args = fixture({"evidence": h.binding("evidence", [h.candidate("P2", props["P2"]["quote"], status=status)])}, props)
    p = f.project(args).records
    assert not p["support_views"] and not p["semantic_values"]
    assert all(m["diagnostic_only"] for m in p["candidate_metadata"].values())


def test_claim_identity_is_closed_and_path_independent():
    scope = {"owner_ids": ["c"], "requirement_ids": ["r"]}
    a = semantic_claim_id(
        "category_list",
        scope,
        {
            "role": "name",
            "member_value_ids": ["b", "a"],
            "grouping": {"instance_quantifier": "exists", "quantifier_n": None, "requested_category_terms": []},
        },
    )
    b = semantic_claim_id(
        "category_list",
        scope,
        {
            "role": "name",
            "member_value_ids": ["a", "b", "a"],
            "grouping": {"instance_quantifier": "exists", "quantifier_n": None, "requested_category_terms": []},
        },
    )
    assert a == b and len(a.split(":sha256:")[1]) == 64
    with pytest.raises(ProjectionIntegrityError):
        semantic_claim_id("role_value", scope, {"role": "r", "value_id": "v", "proposition_id": "P2"})


def test_profile_identity_and_byte_digest():
    args = fixture()
    for field, value in (
        ("name", "latest"),
        ("sealed_artifact_sha256", "0" * 64),
        ("sufficiency_identity", {"status": "current", "version": V8}),
    ):
        p = f.profile(*args)
        p[field] = value
        p["authorization_sha256"] = digest({k: v for k, v in p.items() if k != "authorization_sha256"})
        with pytest.raises(ProjectionIntegrityError):
            lp.validate_layerc_inputs(*args, profile=p)


def test_selected_path_order_and_input_immutability():
    props = {"P1": h.prop("P1"), "P2": h.prop("P2")}
    cs = [h.candidate(pid, p["quote"]) for pid, p in props.items()]
    args = fixture({"evidence": h.binding("evidence", cs), "name": h.legacy("name")}, props)
    before = copy.deepcopy(args)
    a = f.project(args)
    assert args == before
    instance(args)["role_bindings"]["evidence"]["candidate_supports"].reverse()
    b = f.project(args)
    assert a.records["semantic_values"] == b.records["semantic_values"]
    assert a.records["value_coverage"] == b.records["value_coverage"]
    assert "candidate_supports" not in canonical(plain(a.records))


@pytest.mark.parametrize("mode", ["missing", "matching", "duplicate", "mismatch", "bad_designator"])
def test_link_context(mode):
    pieces = [{"chunk_id": "P1", "start": 0, "end": 3, "text": "XYZ", "section": None, "page_start": 1}]
    props = {"P1": h.prop("P1", "XYZ"), "P2": h.prop("P2", "XYZ")}
    args = fixture(
        {"a": h.legacy("a", "P1", "XYZ"), "b": h.legacy("b", "P2", "XYZ")},
        props,
        context={"attachment_pieces": pieces},
        verifiers=["contract_directed_links"],
    )
    proof_id = next(iter(instance(args)["witness_bundle"]["proofs"]))
    contexts = []
    if mode in ("matching", "duplicate", "mismatch"):
        contexts = [
            {
                "proof_id": proof_id,
                "attachment_pieces": copy.deepcopy(pieces),
                "source_locators": [{"proposition_id": "P1", "quote_sha256": f.text_hash("XYZ")}],
            }
        ]
        if mode == "duplicate":
            contexts *= 2
        if mode == "mismatch":
            contexts[0]["attachment_pieces"][0]["text"] = "OTHER"
    if mode == "bad_designator":
        instance(args)["witness_bundle"]["proofs"][proof_id]["join"]["designators"] = ["other"]
    if mode in ("mismatch", "bad_designator"):
        with pytest.raises(ProjectionIntegrityError):
            f.project(args, contexts)
    else:
        p = f.project(args, contexts).records
        status = p["link_context_status"][proof_id]
        assert status["status"] == ("missing" if mode == "missing" else "present")
        assert bool(status["citation_refs"]) == (mode != "missing")
        assert not instance(args)["witness_ids"]


def test_positive_category_with_unrelated_exclusion():
    args = category()
    extra = fixture(
        {"evidence": h.binding("evidence", [h.candidate("P2", "alpha increased.", status="policy")])},
        {"P2": h.prop("P2", "alpha increased.")},
    )
    # Separate maps prove exclusion diagnostics cannot authorize a category. No shared flat pool.
    a, b = f.project(args).records, f.project(extra).records
    assert next(iter(a["value_coverage"].values()))["scientific_coverage_refs"]
    assert not b["value_coverage"]
    assert len(b["candidate_metadata"]) == 1


def test_declared_strategy_not_role_label_controls_value():
    args = fixture(
        {"a_named_brain_person": h.binding("a_named_brain_person", [h.candidate("P2", "alpha increased.")])},
        {"P2": h.prop("P2", "alpha increased.")},
    )
    p = f.project(args).records
    assert next(iter(p["semantic_values"].values()))["kind"] == "literal_assertion"


def test_three_claim_identity_families():
    scope = {"owner_ids": ["c"], "requirement_ids": ["r"]}
    contents = [
        ("role_value", {"role": "x", "value_id": "v"}),
        (
            "relational",
            {
                "relation_kind": "joint_own_completion",
                "operands": {"x": "v", "y": "w"},
                "relation_contract": {
                    "required_roles": ["y", "x"],
                    "alternative_role_groups": [],
                    "relationship_verifiers": ["same_proposition"],
                },
            },
        ),
        (
            "direction_or_effectiveness",
            {
                "summary_kind": "direction",
                "operands": {"x": "v"},
                "target_contract": {"required_sign": None},
                "consensus": "positive",
                "conflict": {"within_instance": False, "across_instances": False},
            },
        ),
    ]
    for family, content in contents:
        before = copy.deepcopy(content)
        assert semantic_claim_id(family, scope, content) == semantic_claim_id(family, scope, content)
        assert content == before


def _replace_ref(value, old, new):
    if isinstance(value, dict):
        return {_replace_ref(k, old, new): _replace_ref(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_ref(v, old, new) for v in value]
    return new if value == old else value


@pytest.mark.parametrize("mutation", ["foreign", "wrong_join", "wrong_checks", "wrong_roles", "wrong_source"])
def test_rehashed_proof_tampering_is_not_authorization(mutation):
    args = fixture()
    b = instance(args)["witness_bundle"]
    old = next(k for k, p in b["proofs"].items() if p["purpose"] == "i1_relation_witness")
    p = b["proofs"][old]
    if mutation == "foreign":
        p["placement"] = {**p["placement"], "child_id": "elsewhere"}
    elif mutation == "wrong_join":
        p["join"]["proposition_id"] = "missing"
    elif mutation == "wrong_checks":
        p["checks"]["continuation_anchors"] = [{"verbatim": True}]
    elif mutation == "wrong_roles":
        p["participating_roles"] = ["evidence"]
    else:
        p["assignment"]["name"]["immediate_operand_source"] = "inherited"
    new = "witness-proof-v1:sha256:" + digest({k: v for k, v in p.items() if k != "proof_id"})
    args = _replace_ref(args[0], old, new), args[1], args[2]
    with pytest.raises(ProjectionIntegrityError):
        f.project(args)


def test_same_reference_conflicting_body_and_identical_duplicate():
    from experiments.ask_cli_revised._layerc_common import put

    registry = {}
    put(registry, "ref", {"x": 1})
    put(registry, "ref", {"x": 1})
    with pytest.raises(ProjectionIntegrityError):
        put(registry, "ref", {"x": 2})


def test_selected_inherited_containment_receipt():
    quote = "alpha was positively associated with beta."
    props = {"P2": h.prop("P2", quote), "P1": h.prop("P1", "Beta")}
    args = fixture(
        {"a": h.legacy("a", "P2", "alpha"), "b": h.legacy("b", "P1", "Beta", source="parent_context")}, props
    )
    projection = f.project(args).records
    assert any(
        r["establishment_refs"][0]["immediate_operand_source"] == "inherited"
        for r in projection["value_coverage"].values()
    )
    p = next(p for p in instance(args)["witness_bundle"]["proofs"].values() if p["purpose"] == "i1_relation_witness")
    assert p["checks"]["inherited"]["b"]["present"] is True


@pytest.mark.parametrize("field", ["policy_identity", "policy_snapshot", "policy_source"])
def test_policy_receipt_bound_to_authored_contract(field):
    args = fixture()
    receipt = instance(args)["role_bindings"]["evidence"]["candidate_supports"][0]["support_policy_evaluation"]
    receipt[field] = {} if field == "policy_snapshot" else "forged"
    with pytest.raises(ProjectionIntegrityError):
        f.project(args)
