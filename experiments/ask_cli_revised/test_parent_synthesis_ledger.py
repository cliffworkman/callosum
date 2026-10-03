"""Phase 26: the deterministic parent claim-ledger / gap-report builder. Pure, no model, no I/O.

Letters in test/method names cross-reference the Phase-26 brief's own required adversarial matrix
(Section 27) and the Phase-25 design audit's own test-matrix lettering where they coincide.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_test_support as pst
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt


def _claims_of_kind(claims, kind):
    return [c for c in claims if c["claim_kind"] == kind]


class SemanticClaimKeyTests(unittest.TestCase):
    def test_s_role_collision_is_distinguished(self):
        """Letter S: same category_description + proposition_id + exact_text, different role ->
        different keys. This is the Phase-26 correction to the Phase-25 audit's own dedup key."""
        a = psl.semantic_claim_key(
            claim_kind="role_value",
            role="region",
            category_description="a named region",
            proposition_id="p1",
            exact_text="the amygdala",
        )
        b = psl.semantic_claim_key(
            claim_kind="role_value",
            role="measure",
            category_description="a named region",
            proposition_id="p1",
            exact_text="the amygdala",
        )
        self.assertNotEqual(a, b)

    def test_identical_inputs_produce_the_identical_key(self):
        make = lambda: psl.semantic_claim_key(  # noqa: E731
            claim_kind="role_value",
            role="region",
            category_description="a named region",
            proposition_id="p1",
            exact_text="the amygdala",
        )
        self.assertEqual(make(), make())


class AtomicRoleValueTests(unittest.TestCase):
    """A single-own-evidence-role complete instance becomes one role_value claim."""

    def test_a_single_filled_role_becomes_a_role_value_claim(self):
        sealed = pst.sealed_with(("p1", 1, "the amygdala was implicated", ["x"]))
        specs = {"region": pst.spec("region", "a named brain region or network")}
        completion = se.new_role_completion(required_roles=["region"])
        inst = pst.instance({"region": pst.filled("region", "p1", "the amygdala")}, instance_key="i1")
        req = pst.requirement("x#req", specs, completion, "exists", [inst])
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        role_values = _claims_of_kind(claims, "role_value")
        self.assertEqual(len(role_values), 1)
        claim = role_values[0]
        self.assertEqual(claim["role"], "region")
        self.assertEqual(claim["category_description"], "a named brain region or network")
        self.assertEqual(claim["values"], [{"proposition_id": "p1", "exact_text": "the amygdala", "role": "region"}])
        self.assertEqual(claim["admissible_proposition_ids"], ["p1"])
        self.assertEqual(claim["child_ids"], ["x"])
        self.assertEqual(claim["requirement_ids"], ["x#req"])
        self.assertEqual(claim["instance_keys"], ["i1"])

    def test_missing_requirement_produces_no_claim(self):
        """Letter H."""
        sealed = pst.sealed_with()
        specs = {"region": pst.spec("region", "a named region")}
        completion = se.new_role_completion(required_roles=["region"])
        inst = pst.instance({"region": pst.missing("region")}, instance_key="i1")
        req = pst.requirement("x#req", specs, completion, "exists", [inst])
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        self.assertEqual(claims, [])

    def test_q_no_filled_findings_anywhere_is_an_empty_ledger(self):
        """Letter Q."""
        sealed = pst.sealed_with()
        specs = {"a": pst.spec("a", "category a")}
        completion = se.new_role_completion(required_roles=["a"])
        req1 = pst.requirement("x#req", specs, completion, "exists", [pst.instance({"a": pst.missing("a")})])
        req2 = pst.requirement("y#req", specs, completion, "exists", [pst.instance({"a": pst.missing("a")})])
        smf = {**pst.map_with("x", req1), **pst.map_with("y", req2)}
        self.assertEqual(psl.build_claim_ledger(smf, sealed), [])

    def test_i_ambiguous_instance_produces_no_claim_for_its_conflicting_role(self):
        """Letter I: an ambiguous binding state is never promoted into a claim."""
        sealed = pst.sealed_with(("p1", 1, "conflicting text", ["x"]))
        specs = {"a": pst.spec("a", "category a")}
        completion = se.new_role_completion(required_roles=["a"])
        binding = se.new_role_binding("a", state="ambiguous", reason="evidence_conflicting")
        inst = pst.instance({"a": binding}, instance_key="i1")
        req = pst.requirement("x#req", specs, completion, "exists", [inst])
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        self.assertEqual(claims, [])

    def test_g_partial_requirement_surfaces_only_its_filled_own_evidence_role(self):
        """Letter G: a partially_filled requirement's filled role becomes an atomic claim; the
        missing role never does, and no relationship between them is ever implied."""
        sealed = pst.sealed_with(("p1", 1, "region text", ["x"]))
        specs = {"a": pst.spec("a", "category a"), "b": pst.spec("b", "category b")}
        completion = se.new_role_completion(required_roles=["a", "b"])
        inst = pst.instance({"a": pst.filled("a", "p1", "region text"), "b": pst.missing("b")}, instance_key="i1")
        req = pst.requirement("x#req", specs, completion, "exists", [inst])
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["claim_kind"], "role_value")
        self.assertEqual(claims[0]["role"], "a")
        # never a relational claim: the requirement never completed
        self.assertEqual(_claims_of_kind(claims, "relational"), [])


class RelationalClaimTests(unittest.TestCase):
    def test_d_a_complete_jointly_grounded_instance_becomes_one_relational_claim(self):
        sealed = pst.sealed_with(("p1", 1, "the amygdala was linked to avoidance behavior", ["x"]))
        specs = {
            "region": pst.spec("region", "a named region"),
            "behavior": pst.spec("behavior", "a named behavior"),
        }
        completion = se.new_role_completion(required_roles=["region", "behavior"])
        inst = pst.instance(
            {
                "region": pst.filled("region", "p1", "the amygdala", source="model_mapping"),
                "behavior": pst.filled("behavior", "p1", "avoidance behavior"),
            },
            instance_key="i1",
        )
        req = pst.requirement("x#req", specs, completion, "exists", [inst], kind="relational")
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        relational = _claims_of_kind(claims, "relational")
        self.assertEqual(len(relational), 1)
        claim = relational[0]
        self.assertIsNone(claim["role"])
        self.assertCountEqual(
            claim["values"],
            [
                {"proposition_id": "p1", "exact_text": "the amygdala", "role": "region"},
                {"proposition_id": "p1", "exact_text": "avoidance behavior", "role": "behavior"},
            ],
        )
        self.assertEqual(claim["admissible_proposition_ids"], ["p1"])
        # the two roles are NEVER also surfaced as independent atomic claims -- exactly one
        # ParentClaim per finding (Section 12).
        self.assertEqual(_claims_of_kind(claims, "role_value"), [])

    def test_x_a_partial_relational_requirement_never_becomes_a_relational_claim(self):
        """Letter X: ingredients present, relation not jointly established -> no relational claim,
        but the one filled own-evidence role still surfaces atomically."""
        sealed = pst.sealed_with(("p1", 1, "the amygdala text", ["x"]))
        specs = {"region": pst.spec("region", "a named region"), "behavior": pst.spec("behavior", "a named behavior")}
        completion = se.new_role_completion(required_roles=["region", "behavior"])
        inst = pst.instance(
            {"region": pst.filled("region", "p1", "the amygdala"), "behavior": pst.missing("behavior")},
            instance_key="i1",
        )
        req = pst.requirement("x#req", specs, completion, "exists", [inst], kind="relational")
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        self.assertEqual(_claims_of_kind(claims, "relational"), [])
        role_values = _claims_of_kind(claims, "role_value")
        self.assertEqual(len(role_values), 1)
        self.assertEqual(role_values[0]["role"], "region")

    def test_k_parent_context_evidence_is_never_cited_as_the_childs_own(self):
        """Letter K: a parent-context-sourced role never contributes its own proposition_id to a
        relational claim's admissible evidence, and is excluded from role_value emission too."""
        sealed = pst.sealed_with(
            ("p1", 1, "the amygdala was named", ["parent"]),
            ("p2", 2, "attitudes shifted", ["child"]),
        )
        parent_specs = {"region": pst.spec("region", "a named region")}
        parent_completion = se.new_role_completion(required_roles=["region"])
        parent_inst = pst.instance(
            {"region": pst.filled("region", "p1", "the amygdala", source="model_mapping")}, instance_key="pi1"
        )
        parent_req = pst.requirement("parent#req", parent_specs, parent_completion, "exists", [parent_inst])

        child_specs = {
            "region": pst.spec("region", "a named region"),
            "attitude": pst.spec("attitude", "a named attitude"),
        }
        child_completion = se.new_role_completion(required_roles=["region", "attitude"])
        propagated_region = {
            **pst.filled("region", "p1", "the amygdala", source="model_mapping"),
            "provenance": {"candidate_source": "parent_context", "detail": "", "model": None},
        }
        child_inst = pst.instance(
            {"region": propagated_region, "attitude": pst.filled("attitude", "p2", "attitudes shifted")},
            instance_key="ci1",
        )
        child_req = pst.requirement(
            "child#req",
            child_specs,
            child_completion,
            "exists",
            [child_inst],
            kind="relational",
            parent_context_roles=["region"],
        )
        smf = {**pst.map_with("parent", parent_req), **pst.map_with("child", child_req)}
        claims = psl.build_claim_ledger(smf, sealed)
        # the child's own instance has only ONE own-evidence role (attitude) -- region is
        # parent-context -- so this is an atomic role_value claim, never relational, and the
        # parent's own p1 never appears as its citation.
        self.assertEqual(_claims_of_kind(claims, "relational"), [])
        child_claims = [c for c in claims if "child" in c["child_ids"]]
        self.assertEqual(len(child_claims), 1)
        self.assertEqual(child_claims[0]["role"], "attitude")
        self.assertEqual(child_claims[0]["admissible_proposition_ids"], ["p2"])
        self.assertNotIn("p1", child_claims[0]["admissible_proposition_ids"])


class CategoryListTests(unittest.TestCase):
    def test_l_siblings_under_a_list_like_quantifier_fold_into_one_category_list_claim(self):
        """Letters L/M: several complete, single-own-evidence-role instances of the SAME role under
        a list-like quantifier become one category_list claim, preserving every contributing
        child/requirement/instance and every distinct exact_text."""
        sealed = pst.sealed_with(
            ("p1", 1, "bilateral fusiform", ["x"]),
            ("p1b", 1, "the amygdala", ["x"]),
            ("p1c", 1, "right hippocampus", ["x"]),
        )
        specs = {"region": pst.spec("region", "a named brain region or network")}
        completion = se.new_role_completion(required_roles=["region"])
        instances = [
            pst.instance(
                {"region": pst.filled("region", "p1", "bilateral fusiform", source="model_mapping")}, instance_key="i1"
            ),
            pst.instance(
                {"region": pst.filled("region", "p1b", "the amygdala", source="model_mapping")}, instance_key="i2"
            ),
            pst.instance(
                {"region": pst.filled("region", "p1c", "right hippocampus", source="model_mapping")}, instance_key="i3"
            ),
        ]
        req = pst.requirement(
            "x#req", specs, completion, "for_each_discovered_instance", instances, multi_instance=True
        )
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        lists = _claims_of_kind(claims, "category_list")
        self.assertEqual(len(lists), 1)
        self.assertEqual(len(lists[0]["values"]), 3)
        self.assertEqual(
            {v["exact_text"] for v in lists[0]["values"]}, {"bilateral fusiform", "the amygdala", "right hippocampus"}
        )
        self.assertEqual(lists[0]["instance_keys"], ["i1", "i2", "i3"])
        self.assertEqual(_claims_of_kind(claims, "role_value"), [])

    def test_w_a_non_list_like_quantifier_does_not_combine_siblings(self):
        """Letter W: at_least_n is NOT an audited list-like policy -- two complete instances stay
        two separate role_value claims."""
        sealed = pst.sealed_with(("p1", 1, "finding one", ["x"]), ("p2", 2, "finding two", ["x"]))
        specs = {"a": pst.spec("a", "category a")}
        completion = se.new_role_completion(required_roles=["a"])
        instances = [
            pst.instance({"a": pst.filled("a", "p1", "finding one")}, instance_key="i1"),
            pst.instance({"a": pst.filled("a", "p2", "finding two")}, instance_key="i2"),
        ]
        req = pst.requirement("x#req", specs, completion, "at_least_n", instances, quantifier_n=2)
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        self.assertEqual(_claims_of_kind(claims, "category_list"), [])
        self.assertEqual(len(_claims_of_kind(claims, "role_value")), 2)

    def test_exists_quantifier_with_multiple_distinct_complete_instances_is_audited_list_like(self):
        """``exists`` is included in the audited list-like set: sufficiency_recovery_targets.py's
        own rule #3 already documents that a single-role model_nomination_only role can fork an
        ``exists`` requirement into more than one final instance (the real c1 shape)."""
        sealed = pst.sealed_with(("p1", 1, "region a", ["x"]), ("p2", 2, "region b", ["x"]))
        specs = {"region": pst.spec("region", "a named region")}
        completion = se.new_role_completion(required_roles=["region"])
        instances = [
            pst.instance({"region": pst.filled("region", "p1", "region a", source="model_mapping")}, instance_key="i1"),
            pst.instance({"region": pst.filled("region", "p2", "region b", source="model_mapping")}, instance_key="i2"),
        ]
        req = pst.requirement("x#req", specs, completion, "exists", instances)
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        self.assertEqual(len(_claims_of_kind(claims, "category_list")), 1)


class DeduplicationTests(unittest.TestCase):
    def test_d_identical_fact_from_sibling_requirements_folds_with_joint_provenance(self):
        """Letter D (dedup): the same (role, category_description, proposition_id, exact_text)
        surfaced by two sibling requirements folds into ONE claim with both as provenance."""
        sealed = pst.sealed_with(("p1", 1, "bilateral fusiform", ["x", "y"]))
        specs = {"region": pst.spec("region", "a named brain region or network")}
        completion = se.new_role_completion(required_roles=["region"])
        req_x = pst.requirement(
            "x#req",
            specs,
            completion,
            "exists",
            [pst.instance({"region": pst.filled("region", "p1", "bilateral fusiform", source="model_mapping")})],
        )
        req_y = pst.requirement(
            "y#req",
            specs,
            completion,
            "exists",
            [pst.instance({"region": pst.filled("region", "p1", "bilateral fusiform", source="model_mapping")})],
        )
        smf = {**pst.map_with("x", req_x), **pst.map_with("y", req_y)}
        claims = psl.build_claim_ledger(smf, sealed)
        role_values = _claims_of_kind(claims, "role_value")
        self.assertEqual(len(role_values), 1)
        self.assertEqual(role_values[0]["child_ids"], ["x", "y"])
        self.assertEqual(role_values[0]["requirement_ids"], ["x#req", "y#req"])

    def test_e_same_value_different_role_or_category_never_folds(self):
        """Letter E: 'independent corroboration'/different-slot facts are never collapsed."""
        sealed = pst.sealed_with(("p1", 1, "the shared text", ["x", "y"]))
        specs_x = {"culture": pst.spec("culture", "a named culture existing")}
        specs_y = {"culture": pst.spec("culture", "a named culture paired with a measure")}
        completion = se.new_role_completion(required_roles=["culture"])
        req_x = pst.requirement(
            "x#req",
            specs_x,
            completion,
            "exists",
            [pst.instance({"culture": pst.filled("culture", "p1", "the shared text", source="model_mapping")})],
        )
        req_y = pst.requirement(
            "y#req",
            specs_y,
            completion,
            "exists",
            [pst.instance({"culture": pst.filled("culture", "p1", "the shared text", source="model_mapping")})],
        )
        smf = {**pst.map_with("x", req_x), **pst.map_with("y", req_y)}
        claims = psl.build_claim_ledger(smf, sealed)
        role_values = _claims_of_kind(claims, "role_value")
        self.assertEqual(len(role_values), 2)  # different category_description -> never folded


class CombinabilityBoundaryTests(unittest.TestCase):
    def test_y_same_child_does_not_imply_combinability(self):
        """Letter Y: two unrelated role_value facts from the SAME child stay two separate claims."""
        sealed = pst.sealed_with(("p1", 1, "region text", ["x"]), ("p2", 1, "behavior text", ["x"]))
        specs = {"region": pst.spec("region", "a named region"), "behavior": pst.spec("behavior", "a named behavior")}
        completion_a = se.new_role_completion(required_roles=["region"])
        completion_b = se.new_role_completion(required_roles=["behavior"])
        req_a = pst.requirement(
            "x#reqA",
            specs,
            completion_a,
            "exists",
            [pst.instance({"region": pst.filled("region", "p1", "region text")})],
        )
        req_b = pst.requirement(
            "x#reqB",
            specs,
            completion_b,
            "exists",
            [pst.instance({"behavior": pst.filled("behavior", "p2", "behavior text")})],
        )
        smf = {"x": se.new_contract("x", [req_a, req_b])}
        claims = psl.build_claim_ledger(smf, sealed)
        self.assertEqual(len(claims), 2)
        self.assertEqual(_claims_of_kind(claims, "relational"), [])

    def test_z_same_hierarchy_parent_does_not_imply_combinability(self):
        """Letter Z: two children sharing a declared ``parent_of`` parent still never combine
        unrelated role_value claims into a relation."""
        sealed = pst.sealed_with(("p1", 1, "region text", ["c5"]), ("p2", 2, "attitude text", ["c6"]))
        specs = {"region": pst.spec("region", "a named region")}
        completion = se.new_role_completion(required_roles=["region"])
        req5 = pst.requirement(
            "c5#req", specs, completion, "exists", [pst.instance({"region": pst.filled("region", "p1", "region text")})]
        )
        specs6 = {"attitude": pst.spec("attitude", "a named attitude")}
        completion6 = se.new_role_completion(required_roles=["attitude"])
        req6 = pst.requirement(
            "c6#req",
            specs6,
            completion6,
            "exists",
            [pst.instance({"attitude": pst.filled("attitude", "p2", "attitude text")})],
        )
        smf = {**pst.map_with("c5", req5), **pst.map_with("c6", req6)}
        claims = psl.build_claim_ledger(smf, sealed, parent_of={"c5": "c4", "c6": "c4"})
        self.assertEqual(len(claims), 2)
        self.assertEqual(_claims_of_kind(claims, "relational"), [])


class CitationIdentityTests(unittest.TestCase):
    def test_v_proposition_id_is_the_only_citation_identity_child_local_ids_never_collide(self):
        """Letter V: two different children each independently call something 'U1' in their own
        local Overview numbering (irrelevant here -- see NoOverviewProseInputTests); the ledger's
        own citation identity is proposition_id, which these fixtures assign as distinct real ids
        -- no collision is possible because the ledger never consumes a child-local alias."""
        sealed = pst.sealed_with(("pA", 1, "child A's own finding", ["a"]), ("pB", 2, "child B's own finding", ["b"]))
        specs = {"x": pst.spec("x", "category x")}
        completion = se.new_role_completion(required_roles=["x"])
        req_a = pst.requirement(
            "a#req", specs, completion, "exists", [pst.instance({"x": pst.filled("x", "pA", "child A's own finding")})]
        )
        req_b = pst.requirement(
            "b#req", specs, completion, "exists", [pst.instance({"x": pst.filled("x", "pB", "child B's own finding")})]
        )
        smf = {**pst.map_with("a", req_a), **pst.map_with("b", req_b)}
        claims = psl.build_claim_ledger(smf, sealed)
        cited = {claim["admissible_proposition_ids"][0] for claim in claims}
        self.assertEqual(cited, {"pA", "pB"})


class SealedPropositionValidationTests(unittest.TestCase):
    def test_unresolvable_proposition_id_fails_loud(self):
        """Section 21: a filled role binding naming a proposition_id absent from the sealed ledger
        must raise, never silently build a claim with missing provenance."""
        sealed = pst.sealed_with()  # empty -- "p404" resolves nowhere
        specs = {"a": pst.spec("a", "category a")}
        completion = se.new_role_completion(required_roles=["a"])
        req = pst.requirement(
            "x#req", specs, completion, "exists", [pst.instance({"a": pst.filled("a", "p404", "ghost text")})]
        )
        with self.assertRaises(ValueError):
            psl.build_claim_ledger(pst.map_with("x", req), sealed)


class NoOverviewProseInputTests(unittest.TestCase):
    def test_build_claim_ledger_signature_takes_no_overview_record(self):
        """Section 24: the pure function signature makes it structurally obvious that per-child
        Overview sentences/proposals play no role."""
        import inspect

        params = list(inspect.signature(psl.build_claim_ledger).parameters)
        self.assertEqual(params, ["sufficiency_map_final", "sealed", "parent_of"])
        for forbidden in ("overview", "overview_record", "proposals", "items", "unit_id"):
            self.assertNotIn(forbidden, params)


class OrderInvarianceTests(unittest.TestCase):
    def _two_child_map(self):
        specs = {"a": pst.spec("a", "category a")}
        completion = se.new_role_completion(required_roles=["a"])
        req_x = pst.requirement(
            "x#req", specs, completion, "exists", [pst.instance({"a": pst.filled("a", "p1", "finding x")})]
        )
        req_y = pst.requirement(
            "y#req", specs, completion, "exists", [pst.instance({"a": pst.filled("a", "p2", "finding y")})]
        )
        return req_x, req_y

    def test_t_dict_insertion_order_of_sufficiency_map_final_does_not_change_the_claim_set(self):
        sealed = pst.sealed_with(("p1", 1, "finding x", ["x"]), ("p2", 2, "finding y", ["y"]))
        req_x, req_y = self._two_child_map()
        forward = psl.build_claim_ledger({**pst.map_with("x", req_x), **pst.map_with("y", req_y)}, sealed)
        backward = psl.build_claim_ledger({**pst.map_with("y", req_y), **pst.map_with("x", req_x)}, sealed)
        self.assertEqual({c["claim_id"] for c in forward}, {c["claim_id"] for c in backward})

    def test_u_claim_id_is_order_invariant_in_its_own_inputs(self):
        sealed = pst.sealed_with(("p1", 1, "region a", ["x"]), ("p2", 2, "region b", ["x"]))
        specs = {"region": pst.spec("region", "a named region")}
        completion = se.new_role_completion(required_roles=["region"])
        forward = [
            pst.instance({"region": pst.filled("region", "p1", "region a", source="model_mapping")}, instance_key="i1"),
            pst.instance({"region": pst.filled("region", "p2", "region b", source="model_mapping")}, instance_key="i2"),
        ]
        req_forward = pst.requirement("x#req", specs, completion, "exists", forward)
        req_backward = pst.requirement("x#req", specs, completion, "exists", list(reversed(forward)))
        claims_forward = psl.build_claim_ledger(pst.map_with("x", req_forward), sealed)
        claims_backward = psl.build_claim_ledger(pst.map_with("x", req_backward), sealed)
        self.assertEqual({c["claim_id"] for c in claims_forward}, {c["claim_id"] for c in claims_backward})


class ModelDependencyTests(unittest.TestCase):
    def test_j_a_model_dependent_fill_renders_identically_but_is_flagged_internally(self):
        """Letter J: model-dependence never changes the claim's own values; it is a separate,
        inspectable provenance fact."""
        sealed = pst.sealed_with(("p1", 1, "the amygdala", ["x"]))
        specs = {"region": pst.spec("region", "a named region")}
        completion = se.new_role_completion(required_roles=["region"])
        inst = pst.instance({"region": pst.filled("region", "p1", "the amygdala", source="model_mapping")})
        req = pst.requirement("x#req", specs, completion, "exists", [inst])
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        self.assertEqual(len(claims), 1)
        self.assertTrue(claims[0]["model_dependency"]["any"])
        self.assertEqual(claims[0]["values"][0]["exact_text"], "the amygdala")


class DirectionEffectivenessClaimTests(unittest.TestCase):
    def test_e_conflicting_directions_preserve_heterogeneity_never_collapse_to_consensus(self):
        """Letter E (direction/effectiveness flavor): reuses Phase 18's own summarize_observations
        verbatim -- never recomputed."""
        sealed = pst.sealed_with(
            ("p1", 1, "Intervention X showed decreased bias scores in the treatment group.", ["x"]),
            ("p2", 2, "No significant effect of Intervention X on bias scores was observed.", ["x"]),
        )
        specs = {"a": pst.spec("a", "category a")}
        completion = se.new_role_completion(required_roles=["a"])
        inst1 = pst.instance({"a": pst.filled("a", "p1", "decreased bias scores")}, instance_key="i1")
        inst2 = pst.instance({"a": pst.filled("a", "p2", "no significant effect")}, instance_key="i2")
        req = pst.requirement(
            "x#req",
            specs,
            completion,
            "for_each_discovered_instance",
            [inst1, inst2],
            multi_instance=True,
            effectiveness=se.new_effectiveness_assessment(),
        )
        from experiments.ask_cli_revised import sufficiency_diagnostic as sd

        smf = pst.map_with("x", req)
        sd.compute_direction_and_effectiveness(sealed, smf)
        claims = psl.build_claim_ledger(smf, sealed)
        de = _claims_of_kind(claims, "direction_or_effectiveness")
        self.assertEqual(len(de), 1)
        summary = de[0]["direction_or_effectiveness"]
        self.assertTrue(summary["has_across_instance_heterogeneity"])
        self.assertIsNone(summary["consensus_value"])

    def test_consensus_effectiveness_claim_carries_the_full_orthogonal_view(self):
        sealed, smf = pst.real_c12_fixture()
        claims = psl.build_claim_ledger(smf, sealed)
        de = _claims_of_kind(claims, "direction_or_effectiveness")
        self.assertEqual(len(de), 1)
        summary = de[0]["direction_or_effectiveness"]
        self.assertEqual(summary["consensus_value"], "supported")
        self.assertFalse(summary["has_within_instance_conflict"])
        self.assertFalse(summary["has_across_instance_heterogeneity"])


class UpstreamErrorBoundaryTests(unittest.TestCase):
    def test_r_the_real_c12_wrong_value_is_reproduced_verbatim_never_corrected(self):
        """Letter R: the confirmed-wrong target_manifestation nomination (Phase 23a #21) must
        survive into the parent ledger exactly as the sufficiency engine recorded it."""
        sealed, smf = pst.real_c12_fixture()
        claims = psl.build_claim_ledger(smf, sealed)
        relational = _claims_of_kind(claims, "relational")
        self.assertEqual(len(relational), 1)
        values_by_role = {v["role"]: v["exact_text"] for v in relational[0]["values"]}
        self.assertEqual(values_by_role["intervention"], pst.C12_INTERVENTION_TEXT)
        # the confirmed-WRONG value, reproduced unchanged -- not "fixed", not suppressed.
        self.assertEqual(values_by_role["target_manifestation"], pst.C12_WRONG_TARGET_MANIFESTATION_TEXT)
        self.assertEqual(values_by_role["observed_effect_or_outcome"], pst.C12_OUTCOME_TEXT)
        # the off-topic U30 intervention candidate is NOT jointly grounded (incomplete instance)
        # and surfaces only as its own atomic claim, plainly, with no "fix" either.
        role_values = _claims_of_kind(claims, "role_value")
        offtopic = [c for c in role_values if c["values"][0]["exact_text"] == pst.C12_OFFTOPIC_INTERVENTION_TEXT]
        self.assertEqual(len(offtopic), 1)
        other_outcome = [c for c in role_values if "U19" in c["instance_keys"]]
        self.assertEqual(len(other_outcome), 1)


class GapReportTests(unittest.TestCase):
    def _target(self, **overrides):
        payload = dict(
            search_child_id="x",
            trigger_child_id="x",
            requirement_id="x#req",
            target_roles=["a"],
            reason="missing",
            goal_mode="single_role",
            scope={"kind": "none"},
            category_descriptions=["category a"],
        )
        payload.update(overrides)
        return srt.new_recovery_target(**payload)

    def test_gap_report_projects_the_minimal_schema_in_deterministic_order(self):
        t1 = self._target(target_roles=["b"])
        t2 = self._target(target_roles=["a"])
        targets = {t1["target_id"]: t1, t2["target_id"]: t2}
        gaps = psl.build_gap_report(targets)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(
            list(gaps[0].keys()),
            [
                "target_id",
                "search_child_id",
                "requirement_id",
                "target_roles",
                "reason",
                "goal_mode",
                "category_descriptions",
            ],
        )
        self.assertEqual([g["target_id"] for g in gaps], sorted(t["target_id"] for t in (t1, t2)))

    def test_reason_and_goal_mode_distinctions_are_preserved(self):
        t = self._target(reason="relationship_unverified", goal_mode="relationship")
        gaps = psl.build_gap_report({t["target_id"]: t})
        self.assertEqual(gaps[0]["reason"], "relationship_unverified")
        self.assertEqual(gaps[0]["goal_mode"], "relationship")

    def test_empty_inventory_is_an_empty_report(self):
        self.assertEqual(psl.build_gap_report({}), [])

    def test_sufficiency_map_final_is_optional_and_defaults_to_no_cross_validation(self):
        t = self._target()
        gaps = psl.build_gap_report({t["target_id"]: t})  # no second argument
        self.assertEqual(len(gaps), 1)

    def test_a_dangling_requirement_id_fails_loud_when_a_map_is_supplied(self):
        t = self._target(requirement_id="ghost#req")
        with self.assertRaises(ValueError):
            psl.build_gap_report(
                {t["target_id"]: t}, sufficiency_map_final={"x": {"child_id": "x", "requirements": []}}
            )


if __name__ == "__main__":
    unittest.main()
