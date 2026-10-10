"""Preregistered v8 compatible assignments and aligned observation qualification."""

import ast
import copy
import itertools
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import compatible_witness as cw
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import support_policy as sp
from experiments.ask_cli_revised import test_i4_2a_local_grounding as h

V = se.SUFFICIENCY_SEMANTICS_V8
FIXTURE = json.loads(Path(__file__).with_name("witness_i4_3c_preregistered.json").read_text(encoding="utf-8"))


def prop(pid, quote="alpha was positively associated with beta."):
    return {
        "proposition_id": pid,
        "quote": quote,
        "paper_id": 1,
        "evidence_anchor_chunk_id": pid,
        "evidence_span_id": pid,
        "verification": {"status": "verified"},
    }


def candidate(pid, quote, span=None, status="eligible", text=None):
    if span is None and text is None:
        span = [0, len(quote)]
    text = quote[slice(*span)] if span is not None else text
    c = se.new_candidate_support(
        supporting_proposition_ids=[pid],
        span_proposition_id=pid,
        exact_text=text,
        assertion_span=span,
        assertion_relation="current_document",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="interpretation" if status in ("policy", "both") else "result",
        attachment_ambiguous=status in ("ambiguous", "ambiguous_excluded"),
    )
    return se.new_evaluated_candidate_support(
        c,
        guard_exclusions=["hedged"] if status in ("guard", "both", "ambiguous_excluded") else [],
        support_policy_evaluation=sp.default_support_policy(
            **{k: c[k] for k in ("assertion_relation", "aggregation", "assertion_kind")}
        ),
    )


def binding(role, candidates, source="deterministic_mapping"):
    if candidates:
        result = sm._project_evaluated_supports(
            se.new_role_spec(role, "generic", "achieved_outcome_predicate"),
            candidates,
            [{"flags": {}} for _ in candidates],
        )[0]
    else:
        result = {**se.new_role_binding(role, state="missing"), "candidate_supports": []}
    result["provenance"]["candidate_source"] = source
    return result


def legacy(role, pid="P2", text="beta", source="deterministic_mapping"):
    return se.new_role_binding(
        role, state="filled", proposition_id=pid, exact_text=text, provenance={"candidate_source": source}
    )


def run(bindings, props, verifiers=None, context=None, observe=False, rc=None, key="i"):
    requirement = {
        "id": "r",
        "role_completion": rc or se.new_role_completion(required_roles=list(bindings)),
        "relationship_verifiers": verifiers if verifiers is not None else ["same_proposition"],
        "direction": {"required_sign": None} if observe else None,
        "effectiveness": {} if observe else None,
    }
    instance = {**se.new_instance(key), "role_bindings": bindings}
    before = copy.deepcopy(bindings)
    instance = se.recompute_instance(
        requirement["role_completion"],
        instance,
        requirement["relationship_verifiers"],
        context=context,
        semantics_version=V,
        witness_context={"child_id": "c", "requirement_id": "r", "proposition_index": props},
    )
    instance.update(rw.witness_instance(requirement, instance, props, semantics_version=V))
    if observe:
        units = [h.unit(p["quote"], [pid]) for pid, p in props.items()]
        sm.attach_aligned_observations(requirement, instance, units, props)
    assert bindings == before
    return requirement, instance


@pytest.mark.parametrize("case", FIXTURE["matrix"], ids=lambda c: c["id"])
def test_frozen_matrix_all_independent_permutations(case):
    props = {p: prop(p) for p in ("P1", "P2", "P3", "P4")}
    groups = []
    for group in case["groups"]:
        rows = []
        for item in group:
            pid, _, status = item.partition(":")
            rows.append(candidate(pid, props[pid]["quote"], [0, 5], status or "eligible"))
        groups.append(rows)
    baseline = None
    for ordered in itertools.product(*(itertools.permutations(g) for g in groups)):
        bs = {f"r{i}": binding(f"r{i}", list(cs)) for i, cs in enumerate(ordered)}
        if len(groups) == 1:
            bs["s"] = legacy("s")
        _, inst = run(bs, props)
        assert inst["relation_witnessed"] is case["I1"]
        result = (inst["complete"], inst["witness_ids"], inst["witness_bundle"])
        if baseline is None:
            baseline = result
        assert result == baseline


@pytest.mark.parametrize("second", ["negatively", "positively"])
def test_same_proposition_distinct_assertions_and_permutations(second):
    quote = (
        "We found alpha was positively associated with beta. We found alpha was " + second + " associated with beta."
    )
    target = legacy("target", text="alpha")
    bound = sm._bind_achieved_outcome_v7(
        h.SPEC, [h.unit(quote, ["P2"])], sibling_bindings={"target": target}, role_completion=h.DEPENDENT
    )[0]
    assert len(bound["candidate_supports"]) == 2
    baseline = None
    for cs in itertools.permutations(bound["candidate_supports"]):
        req, inst = run(
            {"evidence": binding("evidence", list(cs)), "target": target}, {"P2": prop("P2", quote)}, observe=True
        )
        ds = inst["direction_observations"]
        assert len(ds) == 2 and all(o["relation_eligible"] for o in ds)
        summary = se.summarize_observations(
            [inst], "direction_observations", "sign", observation_filter=se.counts_toward_relation_direction
        )
        if second == "negatively":
            for k in (
                "consensus_value",
                "observed_values",
                "has_within_instance_conflict",
                "has_across_instance_heterogeneity",
            ):
                assert summary[k] == FIXTURE["additional"]["opposite_same_P2"][k]
        else:
            assert summary["consensus_value"] == "positive"
        if baseline is None:
            baseline = ds
        assert ds == baseline
        for obs in ds:
            alignment = obs["evidence_alignment"]
            span = alignment["physical_scope"]["observation_span"]
            assert cw.text_hash(quote[slice(*span)]) == alignment["physical_scope"]["raw_text_sha256"]
            assert alignment["paths"][0]["witness_proof_refs"]


def test_local_effectiveness_without_i1_gate():
    quote = "We found alpha increased. We found no evidence that alpha increased."
    cut = quote.index("We found no")
    cs = [candidate("P2", quote, [0, cut - 1]), candidate("P2", quote, [cut, len(quote)])]
    for ordered in itertools.permutations(cs):
        _, inst = run(
            {"a": binding("a", list(ordered)), "b": se.new_role_binding("b", state="missing")},
            {"P2": prop("P2", quote)},
            observe=True,
        )
        assert inst["relation_witnessed"] is False
        assert sorted(o["conclusion"] for o in inst["effectiveness_observations"]) == ["not_supported", "supported"]


@pytest.mark.parametrize("second_contained", [False, True])
def test_inherited_alternatives_merge_paths_not_assertions(second_contained):
    quote = "alpha was positively associated with beta and gamma."
    parent_quote = "beta gamma absent"
    spans = [[0, 4], [5, 10] if second_contained else [11, 17]]
    cs = [candidate("Parent", parent_quote, s) for s in spans]
    original = None
    for ordered in itertools.permutations(cs):
        _, inst = run(
            {"a": binding("a", [candidate("P2", quote)]), "b": binding("b", list(ordered), "parent_context")},
            {"P2": prop("P2", quote), "Parent": prop("Parent", parent_quote)},
            observe=True,
        )
        assert inst["relation_witnessed"]
        assert len(inst["witness_proofs"]) == (2 if second_contained else 1)
        assert all(
            v["immediate_operand_source"] == "inherited"
            for v in inst["witness_bundle"]["support_views"].values()
            if v["placement"]["role"] == "b"
        )
        ds = inst["direction_observations"]
        assert len(ds) == 1
        assert len(ds[0]["evidence_alignment"]["paths"]) == (2 if second_contained else 1)
        if original is None:
            original = ds
        assert ds == original


def test_no_fallback_and_all_inherited():
    props = {"P2": prop("P2")}
    stale = {**legacy("a"), "candidate_supports": []}
    _, inst = run({"a": stale, "b": legacy("b")}, props)
    assert not inst["complete"] and inst["witness_provenance"]["failure_reason"] == "no_eligible_operand_support"
    _, inst = run({"a": legacy("a", source="parent_context"), "b": legacy("b", source="parent_context")}, props)
    assert inst["complete"] and not inst["relation_witnessed"]
    assert inst["witness_provenance"]["failure_reason"] == "no_own_operand"


@pytest.mark.parametrize(
    "verifiers,context,expected",
    [
        (["contract_directed_links"], None, []),
        (["same_proposition", "contract_directed_links"], {"attachment_pieces": ["XYZ"]}, ["contract_directed_links"]),
        (["contract_directed_links", "same_proposition"], None, ["same_proposition"]),
        (
            ["contract_directed_links", "same_proposition"],
            {"attachment_pieces": ["XYZ"]},
            ["contract_directed_links", "same_proposition"],
        ),
        (["same_proposition", "same_proposition"], None, ["same_proposition"]),
    ],
)
def test_verifier_or(verifiers, context, expected):
    different = expected == ["contract_directed_links"]
    props = {"P1": prop("P1", "XYZ"), "P2": prop("P2", "XYZ")}
    _, inst = run(
        {"a": legacy("a", "P1", "XYZ"), "b": legacy("b", "P2" if different else "P1", "XYZ")}, props, verifiers, context
    )
    proofs = [p for p in inst["witness_bundle"]["proofs"].values() if p["purpose"] == "completion_joint"]
    assert sorted(p["verifier_id"] for p in proofs) == sorted(expected)
    for p in proofs:
        if p["verifier_id"] == "contract_directed_links":
            assert "proposition_id" not in p["join"]


def test_reference_identity_duplicates_stability_conflicts():
    props = {"P2": prop("P2")}
    a = candidate("P2", props["P2"]["quote"], [0, 5])
    b = candidate("P2", props["P2"]["quote"], [6, 9])

    def refs(cs, key="i"):
        return run({"a": binding("a", cs), "b": legacy("b")}, props, key=key)[1]["witness_bundle"]

    single = refs([a])
    assert refs([a, a]) == single
    inserted = refs([a, b])
    assert set(single["support_records"]) <= set(inserted["support_records"])
    assert inserted == refs([b, a])
    assert not set(single["support_records"]) & set(refs([a], "other")["support_records"])
    excluded = candidate("P2", props["P2"]["quote"], [0, 5], "guard")
    with pytest.raises(cw.WitnessIntegrityError, match="conflicting"):
        refs([a, excluded])


@pytest.mark.parametrize("kind", ["wrong_text", "range", "alias", "attribution"])
def test_malformed_locators(kind):
    props = {"P2": prop("P2"), "P3": prop("P3", "different quote")}
    c = candidate("P2", props["P2"]["quote"], [0, 5])
    if kind == "wrong_text":
        c["exact_text"] = "wrong"
    elif kind == "range":
        c["assertion_span"] = [0, 999]
    elif kind == "alias":
        c["supporting_proposition_ids"].append("P3")
    else:
        c["attribution"] = {"target": {"quote_sha256": "wrong"}}
    with pytest.raises(cw.WitnessIntegrityError):
        run({"a": {**legacy("a"), "candidate_supports": [c]}, "b": legacy("b")}, props)


def test_unlocated_and_legacy_empty_null():
    props = {"P2": prop("P2")}
    _, inst = run(
        {"a": binding("a", [candidate("P2", props["P2"]["quote"], text="alpha")]), "b": legacy("b")},
        props,
        observe=True,
    )
    assert inst["relation_witnessed"] and not inst["direction_observations"]
    assert any(d["reason"] == "candidate_assertion_locator_unavailable" for d in inst["witness_bundle"]["diagnostics"])
    _, inst = run({"a": legacy("a", None, None), "b": legacy("b")}, props)
    assert len(inst["witness_bundle"]["support_views"]) == 2 and not inst["relation_witnessed"]
    _, inst = run({"a": legacy("a", text=None), "b": legacy("b")}, props)
    assert inst["relation_witnessed"]


@pytest.mark.parametrize("verbatim", [True, False])
def test_continuation(verbatim):
    p = prop("P2")
    p["anchors"] = [{"verbatim": True}, {"verbatim": verbatim}]
    _, inst = run({"a": legacy("a"), "b": legacy("b")}, {"P2": p})
    assert inst["relation_witnessed"] is verbatim


@pytest.mark.parametrize("tamper", ["input", "quote", "view", "proof", "basis"])
def test_stale_or_malformed_bundle(tamper):
    props = {"P2": prop("P2")}
    req, inst = run({"a": legacy("a"), "b": legacy("b")}, props)
    bundle = inst["witness_bundle"]
    if tamper == "input":
        inst["role_bindings"]["a"]["exact_text"] = "other"
    elif tamper == "quote":
        props["P2"]["quote"] += " changed"
    elif tamper == "view":
        next(iter(bundle["support_views"].values()))["supporting_proposition_ids"] = ["wrong"]
    elif tamper == "proof":
        next(iter(bundle["proofs"].values()))["assignment"]["a"]["support_view_id"] = "wrong"
    else:
        next(iter(bundle["observation_bases"].values()))["selected_views"]["a"] = "wrong"
    with pytest.raises(cw.WitnessIntegrityError):
        rw.witness_instance(req, inst, props, semantics_version=V)


@pytest.mark.parametrize(
    "text",
    [
        "plain.",
        "  alpha\twas\npositive.  ",
        "First. Second.",
        "Same. Same.",
        "Results: alpha, while beta.",
        "Alpha; beta.",
        'Alpha. "Beta."',
        "e.g. alpha (beta).",
    ],
)
def test_sentence_offset_roundtrip(text):
    for sentence, span in sm._aligned_sentence_spans(text):
        assert " ".join(text[slice(*span)].split()) == sentence


def test_local_scope_excludes_neighbor():
    quote = "alpha was positively associated with beta, while gamma was negatively associated with delta."
    span = [0, quote.index(",")]
    cs = [candidate("P2", quote, span), candidate("P2", quote, [quote.index("gamma"), len(quote)], "both")]
    for ordered in itertools.permutations(cs):
        _, inst = run(
            {"a": binding("a", list(ordered)), "b": legacy("b", text="beta")}, {"P2": prop("P2", quote)}, observe=True
        )
        assert [(o["sign"], o["relation_eligible"]) for o in inst["direction_observations"]] == [("positive", True)]


def test_support_order_normalization_and_physical_alias_dedup():
    quote = "alpha was positively associated with beta."
    props = {p: {**prop(p, quote), "evidence_anchor_chunk_id": 1, "evidence_span_id": 1} for p in ("P1", "P2")}
    c = candidate("P1", quote)
    c["supporting_proposition_ids"] = ["P1", "P2"]
    other = copy.deepcopy(c)
    other["supporting_proposition_ids"].reverse()
    b = legacy("b", "P1")
    b["provenance"]["supporting_proposition_ids"] = ["P2"]
    _, one = run({"a": binding("a", [c]), "b": b}, props, observe=True)
    _, two = run({"a": binding("a", [other, c]), "b": b}, props, observe=True)
    assert one["witness_bundle"] == two["witness_bundle"]
    assert one["direction_observations"] == two["direction_observations"]
    assert len(one["direction_observations"]) == 1
    assert len(one["direction_observations"][0]["evidence_alignment"]["paths"]) == 2


def test_layer_c_mismatch_is_visible():
    props = {p: prop(p) for p in ("P1", "P2")}
    req, inst = run(
        {
            "a": binding("a", [candidate("P1", props["P1"]["quote"]), candidate("P2", props["P2"]["quote"])]),
            "b": legacy("b"),
        },
        props,
    )
    assert inst["complete"] and inst["relation_witnessed"]
    assert (
        se.relationship_witness_support_ids(
            req["role_completion"], inst["role_bindings"], req["relationship_verifiers"]
        )
        == set()
    )
    # The same guarded legacy construction used by the answer ledger remains unchanged.
    assert "joint-witness support set is empty" in Path(psl.__file__).read_text(encoding="utf-8")


def test_purity_and_closed_verifier_vocabulary():
    assert set(se._VERIFIER_FUNCS) == {"same_proposition", "contract_directed_links"}
    source = Path(cw.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {
        "__future__",
        "copy",
        "hashlib",
        "itertools",
        "json",
        "experiments.ask_cli_revised",
        "experiments.ask_cli_revised.contract_directed.links",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed
        if isinstance(node, ast.Import):
            assert all(n.name in allowed for n in node.names)
    assert "support_policy import" not in source and "assertion_authority" not in source


def test_actual_layer_c_exception_stale_metadata_and_operands():
    from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
    from experiments.ask_cli_revised.answer_plan import relations as ar

    props = {p: prop(p) for p in ("P1", "P2")}
    bs = {
        "a": binding("a", [candidate("P1", props["P1"]["quote"]), candidate("P2", props["P2"]["quote"])]),
        "b": legacy("b"),
    }
    req, inst = run(bs, props)
    authored = se.new_requirement(
        "r",
        "relational",
        {r: se.new_role_spec(r, "generic", "model_nomination_only") for r in bs},
        req["role_completion"],
        "exists",
        relationship_verifiers=["same_proposition"],
    )
    authored.update(instances=[inst], state="filled")
    mapped = {"c": {"requirements": [authored]}}
    sealed = {"verified_propositions": list(props.values())}
    with pytest.raises(ValueError, match="joint-witness support set is empty"):
        psl.build_claim_ledger(mapped, sealed)
    old = rw.witness_instance(req, inst, props, semantics_version=se.SUFFICIENCY_SEMANTICS_V7)
    assert ar._stored_metadata_check(inst, old) == "disagrees"
    unit = ar.relation_units(mapped, sealed, semantics_version=V)[0]
    assert unit["status"] == "witnessed" and unit["witness_ids"] == ["P2"]
    assert [x["proposition_id"] for x in unit["operands"]] == ["P1", "P2"]
    prior = se.recompute_instance(
        req["role_completion"],
        {**inst, "complete": False},
        req["relationship_verifiers"],
        semantics_version=se.SUFFICIENCY_SEMANTICS_V7,
    )
    assert not prior["complete"]
    assert srt._relationship_unverified_roles(req["role_completion"], prior) == ["a", "b"]
    assert srt._relationship_unverified_roles(req["role_completion"], inst) is None
    assert not se.eligible_parent_instances({**authored, "instances": [prior]}, "a")
    assert se.eligible_parent_instances(authored, "a") == [inst]


def test_participation_alternatives_optional_prerequisite():
    props = {p: prop(p) for p in ("P1", "P2")}
    rc = se.new_role_completion(required_roles=["a"], alternative_role_groups=[["b", "c"]], optional_roles=["d"])
    _, inst = run({"a": legacy("a"), "b": legacy("b"), "c": legacy("c", "P1"), "d": legacy("d", "P1")}, props, rc=rc)
    assert not inst["complete"]  # both filled alternatives participate, not a convenient one.
    _, inst = run(
        {"a": legacy("a"), "b": legacy("b"), "c": se.new_role_binding("c", state="missing"), "d": legacy("d", "P1")},
        props,
        rc=rc,
    )
    assert inst["complete"] and inst["joint_grounding"]["participating_roles"] == ["a", "b"]
    _, inst = run({"a": se.new_role_binding("a", state="missing"), "b": legacy("b"), "c": legacy("c")}, props, rc=rc)
    assert inst["joint_grounding"]["status"] == "blocked_prerequisite"
    assert not any(p["purpose"] == "completion_joint" for p in inst["witness_bundle"]["proofs"].values())


def test_distinct_sources_equal_text_do_not_merge():
    quote = "alpha was positively associated with beta."
    props = {p: prop(p, quote) for p in ("P1", "P2")}
    cs = [candidate(p, quote) for p in props]
    for c in cs:
        c["supporting_proposition_ids"] = ["P1", "P2"]
    b = legacy("b", "P1")
    b["provenance"]["supporting_proposition_ids"] = ["P2"]
    for ordered in itertools.permutations(cs):
        _, inst = run({"a": binding("a", list(ordered)), "b": b}, props, observe=True)
        observations = inst["direction_observations"]
        assert len(observations) == 2
        assert all(len(o["evidence_alignment"]["paths"]) == 2 for o in observations)


def test_parent_copy_references_are_child_scoped_and_inherited():
    props = {"P2": prop("P2")}
    req, parent = run({"a": binding("a", [candidate("P2", props["P2"]["quote"])]), "b": legacy("b")}, props)
    carried = copy.deepcopy(parent["role_bindings"]["a"])
    carried["provenance"] = {"candidate_source": "parent_context", "source_lineage": ["origin"]}
    _, child = run({"a": carried, "b": legacy("b")}, props, key="child")
    parent_ref = next(
        v["support_ref"] for v in parent["witness_bundle"]["support_views"].values() if v["placement"]["role"] == "a"
    )
    child_view = next(v for v in child["witness_bundle"]["support_views"].values() if v["placement"]["role"] == "a")
    assert child_view["support_ref"] != parent_ref
    assert child_view["immediate_operand_source"] == "inherited"
    assert carried["candidate_supports"] == parent["role_bindings"]["a"]["candidate_supports"]
    assert "witness_bundle" not in carried
    late = copy.deepcopy(parent)
    late["role_bindings"]["a"]["provenance"]["model_dependency_origins"] = [{"incidental": "annotation"}]
    assert rw.witness_instance(req, late, props, semantics_version=V)["witness_bundle"] == parent["witness_bundle"]


def test_proof_id_is_exact_complete_body_hash():
    _, inst = run({"a": legacy("a"), "b": legacy("b")}, {"P2": prop("P2")})
    for proof in inst["witness_bundle"]["proofs"].values():
        body = {k: v for k, v in proof.items() if k != "proof_id"}
        assert proof["proof_id"] == "witness-proof-v1:sha256:" + cw.digest(body)


@pytest.mark.parametrize("tamper", ["joint", "i1_refs", "placement", "path", "checks"])
def test_forged_receipts_and_rehashed_paths_fail(tamper):
    props = {"P2": prop("P2")}
    req, inst = run({"a": legacy("a"), "b": legacy("b")}, props)
    if tamper == "joint":
        inst["joint_grounding"]["status"] = "bypassed_lt_two_own"
    elif tamper == "i1_refs":
        inst["witness_proofs"] = []
    elif tamper == "placement":
        inst["instance_key"] = "other"
    elif tamper == "path":
        bundle = inst["witness_bundle"]
        old, basis = next(iter(bundle["observation_bases"].items()))
        basis["direction_paths"][0]["operand_text_refs"]["a"]["sha256"] = "wrong"
        del bundle["observation_bases"][old]
        key = cw.reference("observation-basis-v1", {k: v for k, v in basis.items() if k != "basis_id"})
        basis["basis_id"] = key
        bundle["observation_bases"][key] = basis
    else:
        bundle = inst["witness_bundle"]
        old = inst["witness_proofs"][0]
        proof = bundle["proofs"].pop(old)
        proof["checks"]["containment_rule"] = "forged"
        key = "witness-proof-v1:sha256:" + cw.digest({k: v for k, v in proof.items() if k != "proof_id"})
        proof["proof_id"] = key
        bundle["proofs"][key] = proof
        inst["witness_proofs"] = [key]
    with pytest.raises(cw.WitnessIntegrityError):
        rw.witness_instance(req, inst, props, semantics_version=V)


def test_duplicate_registry_proof_conflict():
    registry = {}
    cw._put(registry, "proof", {"value": 1})
    cw._put(registry, "proof", {"value": 1})
    assert len(registry) == 1
    with pytest.raises(cw.WitnessIntegrityError, match="conflicting"):
        cw._put(registry, "proof", {"value": 2})


@pytest.mark.parametrize(
    "version",
    [
        se.SUFFICIENCY_SEMANTICS_V4,
        se.SUFFICIENCY_SEMANTICS_V5,
        se.SUFFICIENCY_SEMANTICS_V6,
        se.SUFFICIENCY_SEMANTICS_V7,
    ],
)
def test_historical_recompute_ignores_malformed_witness_context(version):
    rc = se.new_role_completion(required_roles=["a", "b"])
    instance = {**se.new_instance("i"), "role_bindings": {"a": legacy("a"), "b": legacy("b")}}
    actual = se.recompute_instance(
        rc, instance, ["same_proposition"], semantics_version=version, witness_context=object()
    )
    assert actual["complete"] and "witness_bundle" not in actual
