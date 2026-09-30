"""Layer A tests: the generic engine's own mechanics, plus five synthetic, domain-independent
fixtures (A-E, plus F/G added for frozen-contract/runtime-state independence and open-list
honest termination) proving the mechanism generalizes -- none of these mention q_aib vocabulary
or benchmark content. No model, no network, no E2E.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import sufficiency_engine as se


def _filled(role, prop_id, text, method="deterministic_mapping"):
    return se.new_role_binding(
        role,
        state="filled",
        proposition_id=prop_id,
        exact_text=text,
        provenance={"candidate_source": method, "detail": "", "model": None},
    )


def _missing(role, reason="not_found"):
    return se.new_role_binding(role, state="missing", reason=reason)


class RoleCompletionTests(unittest.TestCase):
    """Corrects the earlier `exists` conflation: a multi-role requirement must not fill from
    only one required role."""

    def _requirement(self):
        specs = {
            "a": se.new_role_spec("a", "entity A", "model_nomination_only"),
            "b": se.new_role_spec("b", "entity B", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        return se.new_requirement("t#req", "relational", specs, completion, "exists")

    def test_one_of_two_required_roles_does_not_fill(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "entity A text")
        inst["role_bindings"]["b"] = _missing("b")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "partially_filled")
        self.assertEqual(result["reason"], "incomplete_instance")
        self.assertFalse(result["instances"][0]["complete"])

    def test_both_required_roles_from_same_proposition_fills(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "entity A relates to entity B")
        inst["role_bindings"]["b"] = _filled("b", "p1", "entity A relates to entity B")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")
        self.assertTrue(result["instances"][0]["complete"])

    def test_both_roles_filled_from_unlinked_propositions_does_not_fill(self):
        """Never independent checkboxes: two roles filled from two DIFFERENT, unlinked
        propositions must not complete a jointly-required instance."""
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "entity A text")
        inst["role_bindings"]["b"] = _filled("b", "p2", "entity B text, unrelated paper")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "partially_filled")
        self.assertFalse(result["instances"][0]["complete"])

    def test_alternative_role_group_either_member_satisfies(self):
        specs = {
            "manifest": se.new_role_spec("manifest", "manifestation", "achieved_outcome_predicate"),
            "modality": se.new_role_spec("modality", "modality", "model_nomination_only"),
            "region": se.new_role_spec("region", "region", "model_nomination_only"),
        }
        completion = se.new_role_completion(
            required_roles=["manifest"], alternative_role_groups=[["modality", "region"]]
        )
        req = se.new_requirement("c#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["manifest"] = _filled("manifest", "p1", "an effect was found")
        inst["role_bindings"]["region"] = _filled("region", "p1", "an effect was found")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")

    def test_optional_role_never_gates_completeness(self):
        specs = {
            "req": se.new_role_spec("req", "required thing", "model_nomination_only"),
            "opt": se.new_role_spec("opt", "optional thing", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["req"], optional_roles=["opt"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["req"] = _filled("req", "p1", "text")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")

    def test_parent_context_role_is_exempt_from_joint_grounding_with_own_evidence(self):
        """A parent-context role structurally cannot share a proposition with anything this
        child retrieves -- pairing it with the child's OWN genuinely-filled role must still
        complete the instance, even though their proposition_ids necessarily differ."""
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["a"] = se.new_role_binding(
            "a",
            state="filled",
            proposition_id="parent-p1",
            exact_text="parent-established entity",
            provenance={"candidate_source": "parent_context", "detail": "from parent", "model": None},
        )
        inst["role_bindings"]["b"] = _filled("b", "child-p9", "this child's own genuinely-filled evidence")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")

    def test_two_own_evidence_roles_still_require_joint_grounding_even_with_parent_context_present(self):
        """The exemption is narrow: once TWO roles both come from this child's own evidence,
        they must still be shown to co-occur -- parent context never widens that."""
        specs = {
            "p": se.new_role_spec("p", "parent-sourced", "model_nomination_only"),
            "a": se.new_role_spec("a", "A", "model_nomination_only"),
            "b": se.new_role_spec("b", "B", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["p", "a", "b"])
        req = se.new_requirement("pg#req", "relational", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["p"] = se.new_role_binding(
            "p",
            state="filled",
            proposition_id="parent-p1",
            exact_text="context",
            provenance={"candidate_source": "parent_context", "detail": "", "model": None},
        )
        inst["role_bindings"]["a"] = _filled("a", "child-p1", "own evidence A")
        inst["role_bindings"]["b"] = _filled("b", "child-p2", "own evidence B, different proposition")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertNotEqual(result["state"], "filled")

    def test_requirement_construction_rejects_role_not_declared_in_specs(self):
        specs = {"a": se.new_role_spec("a", "A", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a", "b"])
        with self.assertRaises(ValueError):
            se.new_requirement("bad#req", "atomic", specs, completion, "exists")


def _filled_with_support(role, primary, supporting, text):
    """A model-mapping binding carrying the Phase 3 `supporting_proposition_ids` provenance
    field (the anchor-dedup's own record of every proposition a collapsed nomination actually
    rests on), distinct from `_filled`'s plain deterministic shape."""
    return se.new_role_binding(
        role,
        state="filled",
        proposition_id=primary,
        exact_text=text,
        provenance={
            "candidate_source": "model_mapping",
            "detail": "model_nomination_only",
            "model": "fake",
            "supporting_proposition_ids": list(supporting),
        },
    )


class SupportSetSamePropositionTests(unittest.TestCase):
    """Phase 4 adversarial proof: `same_proposition` joint-grounding uses a binding's FULL
    proposition-support set (primary + `supporting_proposition_ids`), never the primary alone --
    fixing the exact issue the Phase 3 structural replay found (c1 spuriously flipping
    `filled` -> `partially_filled` purely from which of two anchor-duplicate propositions the
    anchor-dedup happened to pick as primary). Still strictly proposition-IDENTITY, never
    evidence-anchor identity: the engine layer these tests exercise never even receives an
    anchor, so anchor co-occurrence structurally cannot leak into this check."""

    def _two_role_requirement(self):
        specs = {
            "a": se.new_role_spec("a", "entity A", "model_nomination_only"),
            "b": se.new_role_spec("b", "entity B", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        return se.new_requirement("sup#req", "relational", specs, completion, "exists")

    def test_primary_selection_order_cannot_change_truth_when_support_sets_are_identical(self):
        """The exact Phase 3 scenario: two bindings collapsed from the SAME anchor-duplicate
        pair {p2, p11}, but choosing p11 as primary for one and p2 (via a third, deterministic
        role elsewhere) as the other's own identity must not matter -- both orderings of WHICH
        proposition became primary must agree, since the underlying support sets are identical."""
        req = self._two_role_requirement()

        inst1 = se.new_instance()
        inst1["role_bindings"]["a"] = _filled_with_support("a", "p11", ["p11", "p2"], "text")
        inst1["role_bindings"]["b"] = _filled_with_support("b", "p11", ["p11", "p2"], "text")
        req1 = {**req, "instances": [inst1]}
        result1 = se.recompute_requirement(req1)

        inst2 = se.new_instance()
        inst2["role_bindings"]["a"] = _filled_with_support("a", "p2", ["p11", "p2"], "text")
        inst2["role_bindings"]["b"] = _filled_with_support("b", "p11", ["p11", "p2"], "text")
        req2 = {**req, "instances": [inst2]}
        result2 = se.recompute_requirement(req2)

        self.assertEqual(result1["state"], "filled")
        self.assertEqual(result1["state"], result2["state"])

    def test_bindings_with_one_shared_supporting_proposition_pass(self):
        req = self._two_role_requirement()
        inst = se.new_instance()
        # "a" is a plain deterministic binding on p2; "b" collapsed from {p9, p2} but chose p9 as
        # primary -- p2 is still in "b"'s recorded support, so they must jointly ground.
        inst["role_bindings"]["a"] = _filled("a", "p2", "own evidence")
        inst["role_bindings"]["b"] = _filled_with_support("b", "p9", ["p9", "p2"], "own evidence")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")

    def test_disjoint_support_sets_fail_even_when_conceptually_from_one_anchor(self):
        """Never anchor-loosened: even a binding shape meant to represent 'these two nominations
        happened to share a physical anchor' must still fail this check when their RECORDED
        proposition support genuinely does not overlap -- this engine layer never receives an
        anchor at all, so it structurally cannot let anchor co-occurrence substitute for real
        proposition-identity overlap."""
        req = self._two_role_requirement()
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled_with_support("a", "p1", ["p1", "p3"], "text")
        inst["role_bindings"]["b"] = _filled_with_support("b", "p7", ["p7", "p9"], "text")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertNotEqual(result["state"], "filled")
        self.assertFalse(result["instances"][0]["complete"])

    def test_legacy_bindings_without_supporting_proposition_ids_retain_original_behavior(self):
        """Every deterministic binding, and every pre-Phase-3 model binding: no
        `supporting_proposition_ids` field at all -- must behave EXACTLY as the original
        single-proposition-id check did."""
        req = self._two_role_requirement()

        same_prop = se.new_instance()
        same_prop["role_bindings"]["a"] = _filled("a", "p1", "text")
        same_prop["role_bindings"]["b"] = _filled("b", "p1", "text")
        same_result = se.recompute_requirement({**req, "instances": [same_prop]})
        self.assertEqual(same_result["state"], "filled")

        diff_prop = se.new_instance()
        diff_prop["role_bindings"]["a"] = _filled("a", "p1", "text")
        diff_prop["role_bindings"]["b"] = _filled("b", "p2", "different proposition")
        diff_result = se.recompute_requirement({**req, "instances": [diff_prop]})
        self.assertNotEqual(diff_result["state"], "filled")

    def test_relational_requirement_does_not_fill_from_anchor_co_occurrence_alone(self):
        """A relational pairing whose two roles were independently bound to DIFFERENT
        propositions (no recorded supporting-id overlap at all) must never complete merely
        because a human might know, out of band, that those propositions share a physical
        anchor -- this function has no anchor input and must not fill regardless."""
        req = self._two_role_requirement()
        inst = se.new_instance()
        # p4 and p5 are stipulated (in the scenario this test documents) to share one physical
        # evidence anchor -- but NEITHER binding's own supporting_proposition_ids records that,
        # so the check must see them as unrelated.
        inst["role_bindings"]["a"] = _filled("a", "p4", "text from one proposition")
        inst["role_bindings"]["b"] = _filled("b", "p5", "text from a same-anchor sibling proposition")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertNotEqual(result["state"], "filled")


class InstanceQuantifierTests(unittest.TestCase):
    def _pair_requirement(self, quantifier, **kwargs):
        specs = {
            "x": se.new_role_spec("x", "X", "model_nomination_only"),
            "y": se.new_role_spec("y", "Y", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["x", "y"])
        return se.new_requirement("m#req", "relational", specs, completion, quantifier, **kwargs)

    def test_all_requested_categories_partial_when_one_category_missing(self):
        req = self._pair_requirement("all_requested_categories")
        complete = se.new_instance("adults")
        complete["role_bindings"] = {
            "x": _filled("x", "p1", "adults text"),
            "y": _filled("y", "p1", "adults text"),
        }
        missing = se.new_instance("children")
        missing["role_bindings"] = {"x": _missing("x"), "y": _missing("y")}
        req["instances"] = [complete, missing]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "partially_filled")
        self.assertEqual(result["reason"], "category_missing")

    def test_for_each_discovered_instance_one_paired_of_three_is_not_filled(self):
        """Direct fix for the earlier wrong default: pairing one of several discovered
        instances must not satisfy the whole requirement."""
        req = self._pair_requirement("for_each_discovered_instance")
        paired = se.new_instance("country_a")
        paired["role_bindings"] = {"x": _filled("x", "p1", "a"), "y": _filled("y", "p1", "a")}
        unpaired1 = se.new_instance("country_b")
        unpaired1["role_bindings"] = {"x": _filled("x", "p2", "b"), "y": _missing("y")}
        unpaired2 = se.new_instance("country_c")
        unpaired2["role_bindings"] = {"x": _filled("x", "p3", "c"), "y": _missing("y")}
        req["instances"] = [paired, unpaired1, unpaired2]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "partially_filled")
        self.assertNotEqual(result["state"], "filled")

    def test_for_each_discovered_instance_filled_only_when_every_instance_complete(self):
        req = self._pair_requirement("for_each_discovered_instance")
        one = se.new_instance("k1")
        one["role_bindings"] = {"x": _filled("x", "p1", "a"), "y": _filled("y", "p1", "a")}
        two = se.new_instance("k2")
        two["role_bindings"] = {"x": _filled("x", "p2", "b"), "y": _filled("y", "p2", "b")}
        req["instances"] = [one, two]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")

    def test_at_least_n(self):
        req = self._pair_requirement("at_least_n", quantifier_n=2)
        one = se.new_instance("k1")
        one["role_bindings"] = {"x": _filled("x", "p1", "a"), "y": _filled("y", "p1", "a")}
        req["instances"] = [one]
        self.assertEqual(se.recompute_requirement(req)["state"], "partially_filled")
        two = se.new_instance("k2")
        two["role_bindings"] = {"x": _filled("x", "p2", "b"), "y": _filled("y", "p2", "b")}
        req["instances"] = [one, two]
        self.assertEqual(se.recompute_requirement(req)["state"], "filled")

    def test_open_list_never_reaches_filled(self):
        req = self._pair_requirement("open_list")
        complete = se.new_instance("k1")
        complete["role_bindings"] = {"x": _filled("x", "p1", "a"), "y": _filled("y", "p1", "a")}
        req["instances"] = [complete]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "partially_filled")
        self.assertNotEqual(result["state"], "filled")


class RecoveryRoutingTests(unittest.TestCase):
    """recovery_needed is a run-level, separate decision from semantic `state` (never derivable
    from `state` alone)."""

    def _open_list_req(self, n_complete: int):
        specs = {"a": se.new_role_spec("a", "A", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("o#req", "atomic", specs, completion, "open_list", multi_instance=True)
        instances = []
        for i in range(n_complete):
            inst = se.new_instance(f"k{i}")
            inst["role_bindings"] = {"a": _filled("a", f"p{i}", "text")}
            instances.append(inst)
        req["instances"] = instances
        return se.recompute_requirement(req)

    def test_open_list_zero_complete_instances_needs_recovery(self):
        req = self._open_list_req(0)
        status = se.new_search_status(req["id"])
        self.assertTrue(se.compute_recovery_needed(req, status))

    def test_open_list_one_complete_instance_allows_one_bounded_breadth_pass(self):
        """Final researcher decision: do NOT set recovery_needed=False immediately after the
        first complete instance -- allow exactly one bounded breadth-seeking attempt first."""
        req = self._open_list_req(1)
        status = se.new_search_status(req["id"], breadth_pass_used=False)
        self.assertTrue(se.compute_recovery_needed(req, status))

    def test_open_list_after_breadth_pass_used_terminates_honestly(self):
        req = self._open_list_req(1)
        status = se.new_search_status(req["id"], breadth_pass_used=True)
        self.assertFalse(se.compute_recovery_needed(req, status))
        # state stays honestly non-exhaustive even though recovery has stopped
        self.assertEqual(req["state"], "partially_filled")

    def test_open_list_after_budget_exhausted_terminates_even_without_breadth_pass_flag(self):
        req = self._open_list_req(1)
        status = se.new_search_status(req["id"], recovery_budget_exhausted=True)
        self.assertFalse(se.compute_recovery_needed(req, status))

    def test_recovery_budget_exhausted_stops_non_openlist_recovery_without_changing_state(self):
        specs = {"a": se.new_role_spec("a", "A", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("plain#req", "atomic", specs, completion, "exists")
        req["instances"] = [se.new_instance()]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "missing")
        exhausted = se.new_search_status(req["id"], recovery_budget_exhausted=True)
        self.assertFalse(se.compute_recovery_needed(req, exhausted))
        fresh = se.new_search_status(req["id"])
        self.assertTrue(se.compute_recovery_needed(req, fresh))
        # state itself is untouched by search-process facts
        self.assertEqual(req["state"], "missing")


class FrozenContractHashTests(unittest.TestCase):
    """The same frozen sufficiency-contract hash must survive running the question with
    different authorized recovery budgets -- runtime search state is never hashed."""

    def _contract(self):
        specs = {"a": se.new_role_spec("a", "A", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("h#req", "atomic", specs, completion, "exists")
        return se.new_contract("h", [req])

    def test_hash_stable_before_and_after_mapping_runs(self):
        contract = self._contract()
        before = se.contract_hash(contract)
        req = contract["requirements"][0]
        req["instances"] = [se.new_instance()]
        req["instances"][0]["role_bindings"]["a"] = _filled("a", "p1", "text")
        contract["requirements"][0] = se.recompute_requirement(req)
        after = se.contract_hash(contract)
        self.assertEqual(before, after)

    def test_hash_unaffected_by_search_status_recovery_budget(self):
        contract = self._contract()
        h1 = se.contract_hash(contract)
        # SearchStatus is a wholly separate object; varying it cannot touch the contract at all.
        se.new_search_status(contract["requirements"][0]["id"], configured_recovery_budget=1)
        se.new_search_status(contract["requirements"][0]["id"], configured_recovery_budget=100)
        h2 = se.contract_hash(contract)
        self.assertEqual(h1, h2)

    def test_frozen_view_excludes_runtime_fields(self):
        contract = self._contract()
        contract["requirements"][0]["instances"] = [se.new_instance()]
        frozen = se.frozen_view(contract)
        self.assertNotIn("instances", frozen["requirements"][0])
        self.assertNotIn("state", frozen["requirements"][0])
        self.assertNotIn("reason", frozen["requirements"][0])


class ModelMappingProvenanceTests(unittest.TestCase):
    """Model signal is a nomination the engine independently grounds -- never an unsupported
    verdict, but the classification itself, once accepted, must not be described as
    independently re-derived."""

    def test_model_sourced_binding_can_still_reach_filled(self):
        binding = _filled("a", "p1", "specific instance text", method="model_mapping")
        self.assertEqual(binding["provenance"]["candidate_source"], "model_mapping")
        specs = {"a": se.new_role_spec("a", "A", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("mm#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = binding
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")
        self.assertEqual(
            result["instances"][0]["role_bindings"]["a"]["provenance"]["candidate_source"], "model_mapping"
        )


# ---------------------------------------------------------------------------------------------
# Synthetic, domain-independent generalization fixtures (A-G). Zero q_aib vocabulary, zero
# benchmark content -- each proves the mechanism on a different, unrelated question shape.
# ---------------------------------------------------------------------------------------------


class FixtureA_AtomicExists(unittest.TestCase):
    """A: "Which assay measured compound X?" -- identification vs. observed-result distinction."""

    def _requirement(self):
        specs = {
            "assay": se.new_role_spec("assay", "named assay or measurement method", "named_instrument_lexicon"),
            "result": se.new_role_spec("result", "an observed measurement result", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["assay", "result"])
        return se.new_requirement("A#req", "atomic", specs, completion, "exists")

    def test_identification_alone_does_not_fill(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["assay"] = _filled("assay", "p1", "An HPLC assay was used to prepare the sample.")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertNotEqual(result["state"], "filled")
        self.assertEqual(result["state"], "partially_filled")

    def test_identification_plus_result_fills(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["assay"] = _filled("assay", "p1", "An HPLC assay detected compound X at 3 minutes.")
        inst["role_bindings"]["result"] = _filled("result", "p1", "An HPLC assay detected compound X at 3 minutes.")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")


class FixtureB_Relational(unittest.TestCase):
    """B: "How does temperature relate to reaction rate?" -- multi-role exists + optional direction."""

    def _requirement(self, with_direction=False):
        specs = {
            "temperature": se.new_role_spec("temperature", "temperature", "model_nomination_only"),
            "reaction_rate": se.new_role_spec("reaction_rate", "reaction rate", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["temperature", "reaction_rate"])
        direction = se.new_direction_assessment() if with_direction else None
        return se.new_requirement("B#req", "relational", specs, completion, "exists", direction=direction)

    def test_multirole_exists_does_not_fill_from_one_role(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["temperature"] = _filled("temperature", "p1", "temperature was raised")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertNotEqual(result["state"], "filled")

    def test_two_roles_from_unlinked_propositions_never_fill(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["temperature"] = _filled("temperature", "p1", "temperature was raised in paper 1")
        inst["role_bindings"]["reaction_rate"] = _filled("reaction_rate", "p2", "reaction rate increased in paper 2")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertNotEqual(result["state"], "filled")

    def test_direction_is_genuinely_optional_and_contract_declared(self):
        without = self._requirement(with_direction=False)
        withd = self._requirement(with_direction=True)
        self.assertIsNone(without["direction"])
        self.assertIsNotNone(withd["direction"])


class FixtureC_Cardinality(unittest.TestCase):
    """C: "Does the effect occur in adults and children?" -- all_requested_categories."""

    def test_one_category_present_other_missing_is_partial(self):
        specs = {"evidence": se.new_role_spec("evidence", "supporting evidence", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["evidence"])
        req = se.new_requirement("C#req", "cardinality", specs, completion, "all_requested_categories")
        adults = se.new_instance("adults")
        adults["role_bindings"]["evidence"] = _filled("evidence", "p1", "the effect was observed in adults")
        children = se.new_instance("children")
        children["role_bindings"]["evidence"] = _missing("evidence", reason="category_missing")
        req["instances"] = [adults, children]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "partially_filled")
        self.assertEqual(result["reason"], "category_missing")


class FixtureD_MultiInstance(unittest.TestCase):
    """D: "Which countries use the policy and how is it implemented in each?" -- proves the
    c11 fix generalizes to a wholly unrelated domain, and that a bare entity name alone is
    insufficient (no manifestation/implementation evidence)."""

    def _requirement(self):
        specs = {
            "country": se.new_role_spec("country", "named country", "model_nomination_only"),
            "implementation": se.new_role_spec(
                "implementation", "how the policy is implemented there", "achieved_outcome_predicate"
            ),
        }
        completion = se.new_role_completion(required_roles=["country", "implementation"])
        return se.new_requirement(
            "D#req", "relational", specs, completion, "for_each_discovered_instance", multi_instance=True
        )

    def test_country_name_alone_is_incomplete_instance(self):
        req = self._requirement()
        inst = se.new_instance("Country A")
        inst["role_bindings"]["country"] = _filled("country", "p1", "Country A adopted the policy in 2020.")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["instances"][0]["state"], "partially_filled")
        self.assertEqual(result["instances"][0]["reason"], "incomplete_instance")

    def test_pairing_one_of_three_discovered_countries_does_not_fill(self):
        req = self._requirement()
        a = se.new_instance("Country A")
        a["role_bindings"] = {
            "country": _filled("country", "p1", "Country A implemented the policy via local grants."),
            "implementation": _filled("implementation", "p1", "Country A implemented the policy via local grants."),
        }
        b = se.new_instance("Country B")
        b["role_bindings"] = {
            "country": _filled("country", "p2", "Country B also uses the policy."),
            "implementation": _missing("implementation"),
        }
        c = se.new_instance("Country C")
        c["role_bindings"] = {
            "country": _filled("country", "p3", "Country C has adopted the policy too."),
            "implementation": _missing("implementation"),
        }
        req["instances"] = [a, b, c]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "partially_filled")
        self.assertNotEqual(result["state"], "filled")


class FixtureE_SimpleDefinition(unittest.TestCase):
    """E: "What is construct X?" -- one atomic requirement, no relational/cardinality/
    multi-instance machinery. Confirms the engine doesn't force richer structure."""

    def test_single_role_exists_requirement_needs_no_extra_structure(self):
        specs = {"definition": se.new_role_spec("definition", "a definition of the construct", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["definition"])
        req = se.new_requirement("E#req", "atomic", specs, completion, "exists")
        self.assertFalse(req["multi_instance"])
        self.assertIsNone(req["direction"])
        self.assertIsNone(req["effectiveness"])
        inst = se.new_instance()
        inst["role_bindings"]["definition"] = _filled("definition", "p1", "Construct X is defined as ...")
        req["instances"] = [inst]
        result = se.recompute_requirement(req)
        self.assertEqual(result["state"], "filled")


class FixtureF_HashIndependentOfBudget(unittest.TestCase):
    """F: freezing the same contract twice with different SearchStatus.configured_recovery_budget
    values produces an identical contract hash."""

    def test_hash_identical_across_two_different_budgets(self):
        specs = {"a": se.new_role_spec("a", "A", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req1 = se.new_requirement("F#req", "atomic", specs, completion, "exists")
        contract1 = se.new_contract("f", [req1])
        h1 = se.contract_hash(contract1)
        se.new_search_status(req1["id"], configured_recovery_budget=1)

        req2 = se.new_requirement("F#req", "atomic", specs, completion, "exists")
        contract2 = se.new_contract("f", [req2])
        h2 = se.contract_hash(contract2)
        se.new_search_status(req2["id"], configured_recovery_budget=50)

        self.assertEqual(h1, h2)


class FixtureG_OpenListHonestTermination(unittest.TestCase):
    """G: an open_list requirement can terminate with supported instances while remaining
    semantically non-exhaustive -- state stays partially_filled, recovery_needed goes False
    only after the bounded breadth pass, never a claim the search was exhaustive."""

    def test_terminates_non_exhaustive_after_breadth_pass(self):
        specs = {"kind": se.new_role_spec("kind", "a kind/category found", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["kind"])
        req = se.new_requirement("G#req", "atomic", specs, completion, "open_list", multi_instance=True)
        inst = se.new_instance("kind_1")
        inst["role_bindings"]["kind"] = _filled("kind", "p1", "one supported kind was found")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "partially_filled")
        status = se.new_search_status(req["id"], breadth_pass_used=True)
        self.assertFalse(se.compute_recovery_needed(req, status))
        # never silently promoted to "filled" just because recovery stopped
        self.assertEqual(req["state"], "partially_filled")


if __name__ == "__main__":
    unittest.main()
