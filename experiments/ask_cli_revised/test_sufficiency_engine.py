"""Layer A tests: the generic engine's own mechanics, plus five synthetic, domain-independent
fixtures (A-E, plus F/G added for frozen-contract/runtime-state independence and open-list
honest termination) proving the mechanism generalizes -- none of these mention q_aib vocabulary
or benchmark content. No model, no network, no E2E.
"""

from __future__ import annotations

import copy
import unittest

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm


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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertEqual(result["state"], "partially_filled")
        self.assertEqual(result["reason"], "incomplete_instance")
        self.assertFalse(result["instances"][0]["complete"])

    def test_both_required_roles_from_same_proposition_fills(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "entity A relates to entity B")
        inst["role_bindings"]["b"] = _filled("b", "p1", "entity A relates to entity B")
        req["instances"] = [inst]
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result1 = se.recompute_requirement(req1, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

        inst2 = se.new_instance()
        inst2["role_bindings"]["a"] = _filled_with_support("a", "p2", ["p11", "p2"], "text")
        inst2["role_bindings"]["b"] = _filled_with_support("b", "p11", ["p11", "p2"], "text")
        req2 = {**req, "instances": [inst2]}
        result2 = se.recompute_requirement(req2, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        same_result = se.recompute_requirement(
            {**req, "instances": [same_prop]}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        self.assertEqual(same_result["state"], "filled")

        diff_prop = se.new_instance()
        diff_prop["role_bindings"]["a"] = _filled("a", "p1", "text")
        diff_prop["role_bindings"]["b"] = _filled("b", "p2", "different proposition")
        diff_result = se.recompute_requirement(
            {**req, "instances": [diff_prop]}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertEqual(result["state"], "partially_filled")
        self.assertNotEqual(result["state"], "filled")

    def test_for_each_discovered_instance_filled_only_when_every_instance_complete(self):
        req = self._pair_requirement("for_each_discovered_instance")
        one = se.new_instance("k1")
        one["role_bindings"] = {"x": _filled("x", "p1", "a"), "y": _filled("y", "p1", "a")}
        two = se.new_instance("k2")
        two["role_bindings"] = {"x": _filled("x", "p2", "b"), "y": _filled("y", "p2", "b")}
        req["instances"] = [one, two]
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertEqual(result["state"], "filled")

    def test_at_least_n(self):
        req = self._pair_requirement("at_least_n", quantifier_n=2)
        one = se.new_instance("k1")
        one["role_bindings"] = {"x": _filled("x", "p1", "a"), "y": _filled("y", "p1", "a")}
        req["instances"] = [one]
        self.assertEqual(
            se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)["state"], "partially_filled"
        )
        two = se.new_instance("k2")
        two["role_bindings"] = {"x": _filled("x", "p2", "b"), "y": _filled("y", "p2", "b")}
        req["instances"] = [one, two]
        self.assertEqual(
            se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)["state"], "filled"
        )

    def test_open_list_never_reaches_filled(self):
        req = self._pair_requirement("open_list")
        complete = se.new_instance("k1")
        complete["role_bindings"] = {"x": _filled("x", "p1", "a"), "y": _filled("y", "p1", "a")}
        req["instances"] = [complete]
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        return se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

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
        req = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        contract["requirements"][0] = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertEqual(result["state"], "filled")
        self.assertEqual(
            result["instances"][0]["role_bindings"]["a"]["provenance"]["candidate_source"], "model_mapping"
        )


class StopSearchCertificationTests(unittest.TestCase):
    """Phase 9 (Phase 8 Option F): semantic answer-sufficiency (`state`) and stop-search
    authority (`compute_stop_search_certified`/`compute_recovery_needed`) are separate axes. Zero
    q_aib vocabulary -- every fixture here is a generic single/dual-role requirement."""

    def _req(self, req_id, role_bindings, *, required=("a",), optional=()):
        specs = {r: se.new_role_spec(r, r, "model_nomination_only") for r in set(role_bindings)}
        completion = se.new_role_completion(required_roles=list(required), optional_roles=list(optional))
        req = se.new_requirement(req_id, "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"] = role_bindings
        req["instances"] = [inst]
        return se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

    def test_deterministic_filled_is_stop_search_certified(self):
        req = self._req("det#req", {"a": _filled("a", "p1", "text", method="deterministic_mapping")})
        self.assertEqual(req["state"], "filled")
        self.assertTrue(se.compute_stop_search_certified(req))
        self.assertFalse(se.compute_recovery_needed(req, se.new_search_status(req["id"])))

    def test_model_only_filled_is_provisional_for_stop_search(self):
        req = self._req("mm#req", {"a": _filled("a", "p1", "text", method="model_mapping")})
        self.assertEqual(req["state"], "filled")  # semantic state unaffected
        self.assertFalse(se.compute_stop_search_certified(req))
        # bounded-breadth shape, mirroring open_list's own first-pass allowance exactly
        fresh = se.new_search_status(req["id"], breadth_pass_used=False)
        self.assertTrue(se.compute_recovery_needed(req, fresh))
        spent = se.new_search_status(req["id"], breadth_pass_used=True)
        self.assertFalse(se.compute_recovery_needed(req, spent))
        exhausted = se.new_search_status(req["id"], recovery_budget_exhausted=True)
        self.assertFalse(se.compute_recovery_needed(req, exhausted))

    def test_mixed_completion_is_provisional_when_the_model_binding_is_required(self):
        """Both roles required; both jointly grounded on the SAME proposition so the instance
        completes -- one role is deterministic, the other is model_mapping. Since the
        model-sourced role is itself completion-critical (required), the fill is provisional."""
        req = self._req(
            "mixed#req",
            {
                "a": _filled("a", "p1", "deterministic text", method="deterministic_mapping"),
                "b": _filled("b", "p1", "model text", method="model_mapping"),
            },
            required=("a", "b"),
        )
        self.assertEqual(req["state"], "filled")
        self.assertFalse(se.compute_stop_search_certified(req))

    def test_optional_model_binding_does_not_taint_an_otherwise_deterministic_completion(self):
        """`b` is declared OPTIONAL -- it never gates completion (`completion_roles` excludes it),
        so a model-sourced `b` alongside a deterministic, independently-sufficient required `a`
        must not make the fill provisional."""
        req = self._req(
            "optional#req",
            {
                "a": _filled("a", "p1", "deterministic text", method="deterministic_mapping"),
                "b": _filled("b", "p9", "unrelated model text", method="model_mapping"),
            },
            required=("a",),
            optional=("b",),
        )
        self.assertEqual(req["state"], "filled")
        self.assertTrue(se.compute_stop_search_certified(req))
        self.assertFalse(se.compute_recovery_needed(req, se.new_search_status(req["id"])))

    def test_missing_and_partially_filled_behavior_is_unchanged(self):
        """`compute_stop_search_certified` is a no-op (returns True, meaningless) outside the
        `filled` branch -- `compute_recovery_needed`'s own missing/partial logic must be
        byte-identical to its pre-Phase-9 behavior (already covered by RecoveryRoutingTests;
        restated here directly alongside the new predicate for a single-file proof)."""
        missing_req = self._req("missing#req", {"a": _missing("a")})
        self.assertEqual(missing_req["state"], "missing")
        self.assertTrue(se.compute_stop_search_certified(missing_req))  # trivially true, not meaningful
        self.assertTrue(se.compute_recovery_needed(missing_req, se.new_search_status(missing_req["id"])))

        partial_req = self._req(
            "partial#req",
            {"a": _filled("a", "p1", "text", method="model_mapping"), "b": _missing("b")},
            required=("a", "b"),
        )
        self.assertEqual(partial_req["state"], "partially_filled")
        self.assertTrue(se.compute_recovery_needed(partial_req, se.new_search_status(partial_req["id"])))

    def test_search_policy_never_mutates_the_frozen_contract_or_its_hash(self):
        contract = se.new_contract("c", [self._req("mm#req", {"a": _filled("a", "p1", "t", method="model_mapping")})])
        before = se.contract_hash(contract)
        req = contract["requirements"][0]
        se.compute_stop_search_certified(req)
        se.compute_recovery_needed(req, se.new_search_status(req["id"], breadth_pass_used=True))
        se.compute_recovery_needed(req, se.new_search_status(req["id"], recovery_budget_exhausted=True))
        after = se.contract_hash(contract)
        self.assertEqual(before, after)

    def test_answer_rendering_can_still_consume_provisional_filled_content(self):
        """A provisional fill is fully usable for answer construction -- its `state`/`exact_text`/
        `role_bindings` are completely untouched by stop-search querying; nothing is hidden or
        downgraded (the direct analogue of invariant #4)."""
        req = self._req("render#req", {"a": _filled("a", "p1", "the specific finding text", method="model_mapping")})
        se.compute_stop_search_certified(req)  # querying it must not mutate anything renderable
        self.assertEqual(req["state"], "filled")
        self.assertEqual(req["instances"][0]["role_bindings"]["a"]["exact_text"], "the specific finding text")
        self.assertEqual(req["instances"][0]["role_bindings"]["a"]["state"], "filled")

    def test_compute_functions_are_pure_and_never_mutate_their_input(self):
        req = self._req("pure#req", {"a": _filled("a", "p1", "t", method="model_mapping")})
        before = copy.deepcopy(req)
        se.compute_stop_search_certified(req)
        se.compute_recovery_needed(req, se.new_search_status(req["id"]))
        self.assertEqual(req, before)


class TransitiveProvenanceTests(unittest.TestCase):
    """Phase 11 (Phase 10's confirmed gap): a `parent_context`-sourced binding must remain
    machine-readably model-dependent for stop-search purposes, across ARBITRARY propagation
    depth, without `candidate_source` itself ever being overloaded and without parsing
    `provenance["detail"]`'s free text anywhere. Zero q_aib vocabulary."""

    def _req(self, req_id, role_bindings, *, required=("a", "b")):
        specs = {r: se.new_role_spec(r, r, "model_nomination_only") for r in set(role_bindings)}
        completion = se.new_role_completion(required_roles=list(required))
        req = se.new_requirement(req_id, "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"] = role_bindings
        req["instances"] = [inst]
        return se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

    def _propagated(self, source_candidate_source, *, upstream_model_dependent=None, source_lineage=None, model=None):
        """Builds a binding's own provenance as `_propagated_provenance` would have left it after
        ONE hop from a source carrying `source_candidate_source` (plus optional pre-existing
        structured ancestry, for multi-hop fixtures) -- exercises the real function, never
        hand-authors the resulting shape."""
        source_provenance = {"candidate_source": source_candidate_source, "model": model}
        if upstream_model_dependent is not None:
            source_provenance["upstream_model_dependent"] = upstream_model_dependent
        if source_lineage is not None:
            source_provenance["source_lineage"] = source_lineage
        provenance = sm._propagated_provenance("parent#req", {"provenance": source_provenance})
        return se.new_role_binding("a", state="filled", proposition_id="p1", exact_text="t", provenance=provenance)

    # 1. direct model_mapping required role -> provisional (restated here for a single-file proof
    # of every item in the Phase 11 Part C list, alongside the Phase 9 StopSearchCertificationTests
    # that already cover this).
    def test_direct_model_mapping_required_role_is_provisional(self):
        req = self._req("direct#req", {"a": _filled("a", "p1", "t", method="model_mapping")}, required=("a",))
        self.assertFalse(se.compute_stop_search_certified(req))

    # 2. model_mapping parent -> parent_context child -> provisional
    def test_one_hop_propagation_remains_provisional(self):
        a = self._propagated("model_mapping")
        self.assertEqual(a["provenance"]["candidate_source"], "parent_context")  # immediate identity preserved
        self.assertTrue(a["provenance"]["upstream_model_dependent"])
        req = self._req("onehop#req", {"a": a, "b": _filled("b", "p2", "t2", method="deterministic_mapping")})
        self.assertEqual(req["state"], "filled")
        self.assertFalse(se.compute_stop_search_certified(req))

    # 3. model_mapping parent -> parent_context -> parent_context grandchild -> STILL provisional
    def test_two_hop_propagation_remains_provisional(self):
        hop1 = self._propagated("model_mapping")
        hop2_provenance = sm._propagated_provenance("grandchild#req", hop1)
        self.assertTrue(hop2_provenance["upstream_model_dependent"])
        self.assertEqual(hop2_provenance["source_lineage"], ["model_mapping", "parent_context", "parent_context"])
        a = se.new_role_binding("a", state="filled", proposition_id="p1", exact_text="t", provenance=hop2_provenance)
        req = self._req("twohop#req", {"a": a, "b": _filled("b", "p2", "t2", method="deterministic_mapping")})
        self.assertFalse(se.compute_stop_search_certified(req))

    # 4. fully deterministic parent_context ancestry -> can certify normally
    def test_fully_deterministic_ancestry_can_certify(self):
        a = self._propagated("deterministic_mapping")
        self.assertFalse(a["provenance"]["upstream_model_dependent"])
        req = self._req("cleanancestry#req", {"a": a, "b": _filled("b", "p2", "t2", method="deterministic_mapping")})
        self.assertEqual(req["state"], "filled")
        self.assertTrue(se.compute_stop_search_certified(req))

    # 5. mixed deterministic/model ancestry remains provisional whenever the model-dependent
    # inherited binding is completion-critical (required)
    def test_mixed_ancestry_stays_provisional_when_the_model_dependent_role_is_required(self):
        a = self._propagated("model_mapping")  # required role, model-dependent via propagation
        b = _filled("b", "p2", "t2", method="deterministic_mapping")  # required, clean
        req = self._req("mixedreq#req", {"a": a, "b": b}, required=("a", "b"))
        self.assertFalse(se.compute_stop_search_certified(req))

    # 6. optional inherited model-dependent binding does not taint deterministic completion
    def test_optional_propagated_model_dependent_binding_does_not_taint(self):
        a = _filled("a", "p1", "t", method="deterministic_mapping")  # the ONLY required role
        b = self._propagated("model_mapping")  # optional -- excluded from completion_roles
        specs = {
            "a": se.new_role_spec("a", "a", "model_nomination_only"),
            "b": se.new_role_spec("b", "b", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a"], optional_roles=["b"])
        req = se.new_requirement("optprop#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"] = {"a": a, "b": b}
        req["instances"] = [inst]
        req = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertEqual(req["state"], "filled")
        self.assertTrue(se.compute_stop_search_certified(req))

    # 7. immediate candidate_source remains parent_context where appropriate
    def test_immediate_candidate_source_is_always_parent_context_regardless_of_ancestry(self):
        for source in ("model_mapping", "deterministic_mapping"):
            with self.subTest(source=source):
                provenance = sm._propagated_provenance("p#req", {"provenance": {"candidate_source": source}})
                self.assertEqual(provenance["candidate_source"], "parent_context")

    # 8. structured ancestry survives serialization/copying/recomputation
    def test_structured_ancestry_survives_deepcopy_and_recomputation(self):
        a = self._propagated("model_mapping")
        req = self._req("survive#req", {"a": a, "b": _filled("b", "p2", "t2", method="deterministic_mapping")})
        copied = copy.deepcopy(req)
        recomputed = se.recompute_requirement(copied, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        binding = recomputed["instances"][0]["role_bindings"]["a"]
        self.assertTrue(binding["provenance"]["upstream_model_dependent"])
        self.assertEqual(binding["provenance"]["source_lineage"], ["model_mapping", "parent_context"])
        self.assertFalse(se.compute_stop_search_certified(recomputed))

    # 9. no free-text detail parsing is required
    def test_certification_is_unaffected_by_corrupting_the_detail_string(self):
        """Mangling `detail` arbitrarily must never change the certification answer -- proves the
        check genuinely reads only the structured fields, never `detail`'s free text."""
        a = self._propagated("model_mapping")
        a["provenance"]["detail"] = "XXX totally mangled, unparseable, not even English XXX"
        req = self._req("detailcorrupt#req", {"a": a, "b": _filled("b", "p2", "t2", method="deterministic_mapping")})
        self.assertFalse(se.compute_stop_search_certified(req))  # unchanged: still correctly provisional
        import inspect

        source = inspect.getsource(se._instance_completion_is_model_dependent)
        self.assertNotIn('"detail"', source)
        self.assertNotIn("['detail']", source)

    # 10. frozen contract hash remains unchanged
    def test_propagated_provenance_never_affects_the_frozen_contract_hash(self):
        a = self._propagated("model_mapping")
        contract = se.new_contract(
            "h", [self._req("h#req", {"a": a, "b": _filled("b", "p2", "t2", method="deterministic_mapping")})]
        )
        before = se.contract_hash(contract)
        se.compute_stop_search_certified(contract["requirements"][0])
        after = se.contract_hash(contract)
        self.assertEqual(before, after)

    def test_phase10_c8_to_c9_shape_previously_unsafe_now_provisional(self):
        """Exact reproduction of Phase 10's own synthetic c8->c9 audit (PHASE10_LIVE_SINGLE_STAGE_
        DIAGNOSTIC_RESULTS.md): before this fix, this EXACT shape returned
        compute_stop_search_certified == True (a false certification); confirms it is now False."""
        parent_specs = {"trait": se.new_role_spec("trait", "trait", "model_nomination_only")}
        parent_completion = se.new_role_completion(required_roles=["trait"])
        parent_req = se.new_requirement("p8#req", "atomic", parent_specs, parent_completion, "exists")
        parent_inst = se.new_instance()
        parent_inst["role_bindings"]["trait"] = se.new_role_binding(
            "trait",
            state="filled",
            proposition_id="p9",
            exact_text="just-world beliefs",
            provenance={"candidate_source": "model_mapping", "detail": "model_nomination_only", "model": "qwen3.5:9b"},
        )
        parent_req["instances"] = [parent_inst]
        parent_req = se.recompute_requirement(parent_req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

        # Phase 16 retired `_parent_context_binding_for_single_instance` (the bespoke
        # `instances[0]`-only fallback); re-stamp directly via the still-current
        # `_propagated_provenance`, exactly what that helper did internally for one instance.
        parent_binding = parent_req["instances"][0]["role_bindings"]["trait"]
        propagated = {"trait": {**parent_binding, "provenance": sm._propagated_provenance("p8#req", parent_binding)}}

        child_specs = {
            "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "scale", "named_instrument_lexicon"),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        child_req = se.new_requirement("c9#req", "relational", child_specs, child_completion, "exists")
        child_inst = se.new_instance()
        child_inst["role_bindings"]["trait"] = propagated["trait"]
        child_inst["role_bindings"]["scale"] = se.new_role_binding(
            "scale",
            state="filled",
            proposition_id="p99",
            exact_text="Some Named Scale",
            provenance={
                "candidate_source": "deterministic_mapping",
                "detail": "named_instrument_lexicon",
                "model": None,
            },
        )
        child_req["instances"] = [child_inst]
        child_req = se.recompute_requirement(child_req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

        self.assertEqual(child_req["state"], "filled")
        self.assertTrue(child_req["instances"][0]["complete"])
        self.assertFalse(se.compute_stop_search_certified(child_req))  # was True before this phase's fix


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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertNotEqual(result["state"], "filled")
        self.assertEqual(result["state"], "partially_filled")

    def test_identification_plus_result_fills(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["assay"] = _filled("assay", "p1", "An HPLC assay detected compound X at 3 minutes.")
        inst["role_bindings"]["result"] = _filled("result", "p1", "An HPLC assay detected compound X at 3 minutes.")
        req["instances"] = [inst]
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertNotEqual(result["state"], "filled")

    def test_two_roles_from_unlinked_propositions_never_fill(self):
        req = self._requirement()
        inst = se.new_instance()
        inst["role_bindings"]["temperature"] = _filled("temperature", "p1", "temperature was raised in paper 1")
        inst["role_bindings"]["reaction_rate"] = _filled("reaction_rate", "p2", "reaction rate increased in paper 2")
        req["instances"] = [inst]
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        result = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
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
        req = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertEqual(req["state"], "partially_filled")
        status = se.new_search_status(req["id"], breadth_pass_used=True)
        self.assertFalse(se.compute_recovery_needed(req, status))
        # never silently promoted to "filled" just because recovery stopped
        self.assertEqual(req["state"], "partially_filled")


class EligibleParentInstancesTests(unittest.TestCase):
    """Phase 16: the shared parent-instance eligibility primitive -- role-filled AND
    instance.complete, never positional, never conflated with stop-search certification."""

    def _parent_requirement(self, instances):
        specs = {
            "region": se.new_role_spec("region", "a specific NAMED brain area", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["region", "relation"])
        req = se.new_requirement("c4#req", "atomic", specs, completion, "exists")
        req["instances"] = instances
        return se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

    def _instance(self, key, *, region_prop, relation_prop, region_text="amygdala", method="model_mapping"):
        inst = se.new_instance(key)
        inst["role_bindings"]["region"] = _filled("region", region_prop, region_text, method=method)
        inst["role_bindings"]["relation"] = _filled("relation", relation_prop, "relation evidence")
        return inst

    def test_role_filled_but_instance_incomplete_is_not_eligible(self):
        inst = se.new_instance("i1")
        inst["role_bindings"]["region"] = _filled("region", "p1", "amygdala", method="model_mapping")
        inst["role_bindings"]["relation"] = _missing("relation")
        req = self._parent_requirement([inst])
        self.assertFalse(req["instances"][0]["complete"])
        self.assertEqual(se.eligible_parent_instances(req, "region"), [])

    def test_complete_instance_with_role_filled_is_eligible(self):
        inst = self._instance("i1", region_prop="p1", relation_prop="p1")
        req = self._parent_requirement([inst])
        self.assertTrue(req["instances"][0]["complete"])
        eligible = se.eligible_parent_instances(req, "region")
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["instance_key"], "i1")

    def test_complete_instance_whose_requested_role_is_itself_missing_is_not_eligible(self):
        """An instance can be complete via an ALTERNATIVE role group without the specific
        requested parent_role ever being filled -- eligibility checks the role binding too, not
        completeness alone."""
        specs = {
            "a": se.new_role_spec("a", "a", "achieved_outcome_predicate"),
            "region": se.new_role_spec("region", "region", "model_nomination_only"),
            "region_alt": se.new_role_spec("region_alt", "region alt", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a"], alternative_role_groups=[["region", "region_alt"]])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance("i1")
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        inst["role_bindings"]["region"] = _missing("region")
        inst["role_bindings"]["region_alt"] = _filled("region_alt", "p1", "amygdala", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertTrue(req["instances"][0]["complete"])
        self.assertEqual(se.eligible_parent_instances(req, "region"), [])

    def test_complete_model_dependent_instance_is_eligible_not_gated_on_stop_search_certification(self):
        """instance.complete is a SEPARATE axis from compute_stop_search_certified -- a complete
        but model-dependent instance still propagates; its model-dependence is a provenance fact
        for the CALLER to carry forward, never a reason to withhold eligibility here."""
        inst = self._instance("i1", region_prop="p1", relation_prop="p1", method="model_mapping")
        req = self._parent_requirement([inst])
        self.assertTrue(req["instances"][0]["complete"])
        self.assertFalse(se.compute_stop_search_certified(req))  # model-dependent fill, not certified
        eligible = se.eligible_parent_instances(req, "region")
        self.assertEqual(len(eligible), 1)

    def test_multiple_eligible_returned_in_deterministic_instance_key_order_not_input_order(self):
        inst_b = self._instance("b", region_prop="pb", relation_prop="pb")
        inst_a = self._instance("a", region_prop="pa", relation_prop="pa")
        req = self._parent_requirement([inst_b, inst_a])  # input order: b, a
        eligible = se.eligible_parent_instances(req, "region")
        self.assertEqual([i["instance_key"] for i in eligible], ["a", "b"])

    def test_zero_instances_returns_empty_list(self):
        req = self._parent_requirement([])
        self.assertEqual(se.eligible_parent_instances(req, "region"), [])

    def test_order_invariance_eligible_set_identical_regardless_of_input_permutation(self):
        incomplete = se.new_instance("rtpj")
        incomplete["role_bindings"]["region"] = _filled("region", "p27", "RTPJ", method="model_mapping")
        incomplete["role_bindings"]["relation"] = _missing("relation")
        complete = self._instance("amygdala", region_prop="p11", relation_prop="p11")
        forward = self._parent_requirement([incomplete, complete])
        backward = self._parent_requirement([complete, incomplete])
        self.assertEqual(
            [i["instance_key"] for i in se.eligible_parent_instances(forward, "region")],
            [i["instance_key"] for i in se.eligible_parent_instances(backward, "region")],
        )


if __name__ == "__main__":
    unittest.main()
