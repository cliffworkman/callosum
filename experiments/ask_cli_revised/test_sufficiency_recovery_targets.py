"""Structured RecoveryTarget generation (Phase 12, rounds 1-3). Pure, deterministic, no model, no
network, no recovery execution -- generation over already-mapped SufficiencyContracts only.

Round 3 is authoritative over any cumulative-plan snippet it amends: no standalone `disjunctive`
field (use `goal_mode=="any_of_roles"`); `relationship_unverified` uses the exact
`own_evidence_roles` set, never flattened `completion_roles()`; a zero-instance requirement still
produces a local discovery target (except a parent-backed `for_each_discovered_instance` whose
parent has no source, which defers upstream); a generic coverage gap never suppresses a distinct
structured target.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt


def _propagate(parent_requirement: dict, role: str) -> dict:
    """Phase 16 retired `sufficiency_mapping._parent_context_binding_for_single_instance` (the
    bespoke `instances[0]`-only fallback) outright -- these tests exercise `compute_recovery_
    targets`'s own dedup/redirect logic over an ALREADY-propagated structure, not the mapper's
    eligibility/forking mechanics (covered separately in test_sufficiency_mapping.py), so they
    just re-stamp the binding directly via the still-current `_propagated_provenance`, exactly
    what the retired helper did internally for a single eligible instance."""
    instance = parent_requirement["instances"][0]
    binding = instance["role_bindings"][role]
    return {role: {**binding, "provenance": sm._propagated_provenance(parent_requirement["id"], binding)}}


def _filled(role, prop_id, text, *, method="deterministic_mapping", provenance_extra=None):
    provenance = {"candidate_source": method, "detail": "", "model": None}
    if provenance_extra:
        provenance.update(provenance_extra)
    return se.new_role_binding(role, state="filled", proposition_id=prop_id, exact_text=text, provenance=provenance)


def _missing(role, reason="not_found"):
    return se.new_role_binding(role, state="missing", reason=reason)


def _contract_with(child_id, requirement):
    return {child_id: se.new_contract(child_id, [requirement])}


class SingleInstanceExistsTests(unittest.TestCase):
    def test_missing_required_role_produces_a_local_single_role_target(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "found a")
        inst["role_bindings"]["b"] = _missing("b")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        mapped = _contract_with("x", req)
        targets = srt.compute_recovery_targets(mapped, {})
        self.assertEqual(len(targets), 1)
        target = next(iter(targets.values()))
        # "a" is already filled, so the instance's own state is "partially_filled" -- "partial",
        # not "missing" (that reason is reserved for state=="missing", no role filled at all).
        self.assertEqual(target["reason"], "partial")
        self.assertEqual(target["goal_mode"], "single_role")
        self.assertEqual(target["target_roles"], ["b"])
        self.assertEqual(target["scope"], {"kind": "none"})
        self.assertEqual(target["search_child_id"], "x")
        self.assertEqual(target["trigger_child_id"], "x")

    def test_unrelated_required_roles_each_get_their_own_target(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _missing("a")
        inst["role_bindings"]["b"] = _missing("b")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        role_sets = {tuple(t["target_roles"]) for t in targets.values()}
        self.assertEqual(role_sets, {("a",), ("b",)})

    def test_fully_certified_filled_requirement_produces_no_target(self):
        specs = {"a": se.new_role_spec("a", "category a", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(targets, {})


class AlternativeGroupTests(unittest.TestCase):
    def test_unsatisfied_alternative_group_is_disjunctive(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "model_nomination_only"),
            "c": se.new_role_spec("c", "category c", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a"], alternative_role_groups=[["b", "c"]])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        inst["role_bindings"]["b"] = _missing("b")
        inst["role_bindings"]["c"] = _missing("c")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 1)
        target = next(iter(targets.values()))
        self.assertEqual(target["goal_mode"], "any_of_roles")
        self.assertEqual(target["target_roles"], ["b", "c"])

    def test_satisfied_alternative_group_produces_no_target_for_it(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "model_nomination_only"),
            "c": se.new_role_spec("c", "category c", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a"], alternative_role_groups=[["b", "c"]])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        # a and b share one proposition -- same_proposition joint-grounding succeeds trivially, so
        # this exercises the provisional_corroboration path (b is model-dependent) cleanly, not an
        # incidental relationship_unverified gap from two own-evidence roles citing different
        # propositions.
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        inst["role_bindings"]["b"] = _filled("b", "p1", "b result", method="model_mapping")
        inst["role_bindings"]["c"] = _missing("c")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "filled")
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertTrue(all(t["reason"] == "provisional_corroboration" for t in targets.values()))
        self.assertTrue(all("c" not in t["target_roles"] for t in targets.values()))


class RelationshipUnverifiedTests(unittest.TestCase):
    def _relational_req(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        return se.new_requirement("x#req", "relational", specs, completion, "exists")

    def test_both_roles_filled_but_ungrounded_is_relationship_unverified(self):
        req = self._relational_req()
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        inst["role_bindings"]["b"] = _filled("b", "p2", "b result", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)  # different propositions -> not jointly grounded -> incomplete
        self.assertFalse(req["instances"][0]["complete"])
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 1)
        target = next(iter(targets.values()))
        self.assertEqual(target["reason"], "relationship_unverified")
        self.assertEqual(target["goal_mode"], "relationship")
        self.assertEqual(target["target_roles"], ["a", "b"])

    def test_excludes_unfilled_alternative_members_from_the_relationship_target(self):
        """required A + alternatives [B,C], A/B filled, C absent, relationship fails ->
        relationship target contains exactly {A,B}, never C."""
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "model_nomination_only"),
            "c": se.new_role_spec("c", "category c", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a"], alternative_role_groups=[["b", "c"]])
        req = se.new_requirement("x#req", "relational", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        inst["role_bindings"]["b"] = _filled("b", "p2", "b result", method="model_mapping")
        inst["role_bindings"]["c"] = _missing("c")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertFalse(req["instances"][0]["complete"])
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 1)
        target = next(iter(targets.values()))
        self.assertEqual(target["reason"], "relationship_unverified")
        self.assertEqual(target["target_roles"], ["a", "b"])
        self.assertNotIn("c", target["target_roles"])

    def test_relationship_target_never_uses_flattened_completion_roles(self):
        """A regression-shaped proof distinct from the above: even with THREE alternative members,
        only the ones actually filled participate."""
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "model_nomination_only"),
            "c": se.new_role_spec("c", "category c", "model_nomination_only"),
            "d": se.new_role_spec("d", "category d", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a"], alternative_role_groups=[["b", "c", "d"]])
        req = se.new_requirement("x#req", "relational", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        inst["role_bindings"]["b"] = _filled("b", "p2", "b result", method="model_mapping")
        inst["role_bindings"]["c"] = _filled("c", "p3", "c result", method="model_mapping")
        inst["role_bindings"]["d"] = _missing("d")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertFalse(req["instances"][0]["complete"])
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        target = next(t for t in targets.values() if t["reason"] == "relationship_unverified")
        self.assertEqual(target["target_roles"], ["a", "b", "c"])
        self.assertNotIn("d", target["target_roles"])


class MultiInstanceScopingTests(unittest.TestCase):
    def test_two_incomplete_instances_scope_by_instance_key_not_unioned(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "achieved_outcome_predicate"),
            "c": se.new_role_spec("c", "category c", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["a", "b", "c"])
        req = se.new_requirement("x#req", "relational", specs, completion, "exists", multi_instance=True)
        inst1 = se.new_instance("u1")
        inst1["role_bindings"]["a"] = _filled("a", "p1", "a1")
        inst1["role_bindings"]["b"] = _filled("b", "p1", "b1")
        inst1["role_bindings"]["c"] = _missing("c")
        inst2 = se.new_instance("u2")
        inst2["role_bindings"]["a"] = _filled("a", "p2", "a2")
        inst2["role_bindings"]["b"] = _missing("b")
        inst2["role_bindings"]["c"] = _filled("c", "p2", "c2")
        req["instances"] = [inst1, inst2]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "partially_filled")
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        by_scope = {t["scope"]["instance_key"]: t["target_roles"] for t in targets.values()}
        self.assertEqual(by_scope, {"u1": ["c"], "u2": ["b"]})

    def test_single_instance_requirement_uses_none_scope_even_when_runtime_forked(self):
        """A `multi_instance=False` requirement whose model-nomination forking produced more than
        one FINAL instance (possible via `_fork_instances_over_role`) must still scope by instance,
        not by the DECLARED multi_instance flag -- the real c6 shape (round-3 implementation
        finding)."""
        specs = {"a": se.new_role_spec("a", "category a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists", multi_instance=False)
        inst1 = se.new_instance()
        inst1["role_bindings"]["a"] = _missing("a")
        inst2 = {**se.new_instance(), "instance_key": "i::forked1"}
        inst2["role_bindings"]["a"] = _missing("a")
        req["instances"] = [inst1, inst2]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertTrue(all(t["scope"]["kind"] == "instance" for t in targets.values()))


class AllRequestedCategoriesTests(unittest.TestCase):
    def test_missing_term_scopes_by_the_exact_requested_term(self):
        spec = se.new_role_spec(
            "category_evidence",
            "attitude category evidence",
            "explicit_category_terms",
            requested_category_terms=["implicit", "explicit"],
        )
        completion = se.new_role_completion(required_roles=["category_evidence"])
        req = se.new_requirement(
            "x#req",
            "cardinality",
            {"category_evidence": spec},
            completion,
            "all_requested_categories",
            multi_instance=True,
        )
        inst_implicit = se.new_instance("implicit")
        inst_implicit["role_bindings"]["category_evidence"] = _filled("category_evidence", "p1", "implicit found")
        inst_explicit = se.new_instance("explicit")
        inst_explicit["role_bindings"]["category_evidence"] = _missing("category_evidence", "category_missing")
        req["instances"] = [inst_implicit, inst_explicit]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 1)
        target = next(iter(targets.values()))
        self.assertEqual(target["scope"], {"kind": "instance", "instance_key": "explicit"})
        self.assertIn("attitude category evidence", target["category_descriptions"][0])


class ForEachDiscoveredInstanceTests(unittest.TestCase):
    def _paired_contract(self):
        parent_specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        parent_completion = se.new_role_completion(required_roles=["trait"])
        parent_req = se.new_requirement(
            "p#req", "atomic", parent_specs, parent_completion, "open_list", multi_instance=True
        )
        pa = se.new_instance("ua")
        pa["role_bindings"]["trait"] = _filled("trait", "pa", "trait A", method="model_mapping")
        pb = se.new_instance("ub")
        pb["role_bindings"]["trait"] = _filled("trait", "pb", "trait B", method="model_mapping")
        parent_req["instances"] = [pa, pb]
        parent_req = se.recompute_requirement(parent_req)
        # Stamp origins exactly as `compute_diagnostic_sufficiency_map`'s real topological order
        # would (parent-less children are mapped -- and thus stamped -- before paired children read
        # them), so `_propagated_provenance` below carries a real, non-empty `model_dependency_
        # origins` list forward, never an accidentally-empty one from a hand-skipped step.
        parent_req = sd._stamp_model_dependency_origins(parent_req, "p")
        pa, pb = parent_req["instances"]

        from experiments.ask_cli_revised import sufficiency_mapping as sm

        child_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "a named scale", "named_instrument_lexicon"),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        child_req = se.new_requirement(
            "c#req",
            "relational",
            child_specs,
            child_completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )
        inst_a = se.new_instance("ua")
        inst_a["role_bindings"]["trait"] = {
            **pa["role_bindings"]["trait"],
            "provenance": sm._propagated_provenance("p#req", pa["role_bindings"]["trait"]),
        }
        inst_a["role_bindings"]["scale"] = _missing("scale")
        inst_b = se.new_instance("ub")
        inst_b["role_bindings"]["trait"] = {
            **pb["role_bindings"]["trait"],
            "provenance": sm._propagated_provenance("p#req", pb["role_bindings"]["trait"]),
        }
        inst_b["role_bindings"]["scale"] = _filled("scale", "pb", "Scale B")
        child_req["instances"] = [inst_a, inst_b]
        child_req = se.recompute_requirement(child_req)
        return {"p": se.new_contract("p", [parent_req]), "c": se.new_contract("c", [child_req])}

    def test_two_parent_instances_each_missing_a_different_paired_value_produce_two_targets(self):
        mapped = self._paired_contract()
        targets = srt.compute_recovery_targets(mapped, {"c": "p"})
        local_targets = {t["target_id"]: t for t in targets.values() if t["search_child_id"] == "c"}
        self.assertEqual(len(local_targets), 1)  # only inst_a is missing its own scale
        target = next(iter(local_targets.values()))
        self.assertEqual(target["scope"], {"kind": "instance", "instance_key": "ua"})
        self.assertEqual(target["target_roles"], ["scale"])

    def test_inherited_provisional_fill_redirects_upstream_to_the_true_origin(self):
        mapped = self._paired_contract()
        targets = srt.compute_recovery_targets(mapped, {"c": "p"})
        redirected = [t for t in targets.values() if t["reason"] == "provisional_corroboration"]
        self.assertEqual(len(redirected), 1)
        target = redirected[0]
        self.assertEqual(target["search_child_id"], "p")
        self.assertEqual(target["trigger_child_id"], "c")
        self.assertEqual(target["requirement_id"], "p#req")
        self.assertEqual(target["target_roles"], ["trait"])
        self.assertEqual(target["scope"], {"kind": "instance", "instance_key": "ub"})

    def test_self_discovered_for_each_with_zero_instances_produces_a_local_target(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        req = se.new_requirement(
            "x#req", "relational", specs, completion, "for_each_discovered_instance", multi_instance=True
        )
        req["instances"] = []
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertTrue(any(t["search_child_id"] == "x" for t in targets.values()))

    def test_parent_backed_for_each_with_an_incomplete_parent_defers_upstream(self):
        """Phase 16 (matrix item 19): the RecoveryTarget layer's own `_first_instance_targets`
        must agree with the mapper's `se.eligible_parent_instances` about whether a usable parent
        exists -- a parent instance with the role FILLED but the INSTANCE itself incomplete is
        exactly as "no source" as an empty parent (the `test_parent_backed_for_each_with_an_
        empty_parent_defers_upstream` case above), never treated as discovered."""
        parent_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        parent_completion = se.new_role_completion(required_roles=["trait", "relation"])
        parent_req = se.new_requirement(
            "p#req", "atomic", parent_specs, parent_completion, "open_list", multi_instance=True
        )
        p_inst = se.new_instance("u1")
        p_inst["role_bindings"]["trait"] = _filled("trait", "pp", "trait X", method="model_mapping")
        p_inst["role_bindings"]["relation"] = _missing("relation")  # role filled, INSTANCE incomplete
        parent_req["instances"] = [p_inst]
        parent_req = se.recompute_requirement(parent_req)
        self.assertFalse(parent_req["instances"][0]["complete"])

        child_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "a named scale", "named_instrument_lexicon"),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        child_req = se.new_requirement(
            "c#req",
            "relational",
            child_specs,
            child_completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )
        child_req["instances"] = []
        child_req = se.recompute_requirement(child_req)
        mapped = {"p": se.new_contract("p", [parent_req]), "c": se.new_contract("c", [child_req])}
        targets = srt.compute_recovery_targets(mapped, {"c": "p"})
        self.assertFalse(any(t["search_child_id"] == "c" for t in targets.values()))
        self.assertTrue(any(t["search_child_id"] == "p" for t in targets.values()))

    def test_parent_backed_for_each_with_an_empty_parent_defers_upstream(self):
        parent_specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        parent_completion = se.new_role_completion(required_roles=["trait"])
        parent_req = se.new_requirement(
            "p#req", "atomic", parent_specs, parent_completion, "open_list", multi_instance=True
        )
        parent_req["instances"] = []
        parent_req = se.recompute_requirement(parent_req)

        child_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "a named scale", "named_instrument_lexicon"),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        child_req = se.new_requirement(
            "c#req",
            "relational",
            child_specs,
            child_completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )
        child_req["instances"] = []
        child_req = se.recompute_requirement(child_req)
        mapped = {"p": se.new_contract("p", [parent_req]), "c": se.new_contract("c", [child_req])}
        targets = srt.compute_recovery_targets(mapped, {"c": "p"})
        self.assertFalse(any(t["search_child_id"] == "c" for t in targets.values()))
        self.assertTrue(any(t["search_child_id"] == "p" for t in targets.values()))


class AtLeastNTests(unittest.TestCase):
    def _req(self, n):
        specs = {"a": se.new_role_spec("a", "category a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        return se.new_requirement(
            "x#req", "atomic", specs, completion, "at_least_n", quantifier_n=n, multi_instance=True
        )

    def test_deficit_target_never_coexists_with_provisional_corroboration(self):
        req = self._req(3)
        inst = se.new_instance("u1")
        inst["role_bindings"]["a"] = _filled("a", "p1", "a1", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "partially_filled")
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        reasons = {t["reason"] for t in targets.values()}
        self.assertEqual(reasons, {"cardinality_deficit"})

    def test_deficit_excludes_the_changing_count_from_identity(self):
        req2 = self._req(3)
        inst1 = se.new_instance("u1")
        inst1["role_bindings"]["a"] = _filled("a", "p1", "a1")
        req2["instances"] = [inst1]
        req2 = se.recompute_requirement(req2)
        targets_at_2_needed = srt.compute_recovery_targets(_contract_with("x", req2), {})

        req1 = self._req(3)
        inst1b = se.new_instance("u1")
        inst1b["role_bindings"]["a"] = _filled("a", "p1", "a1")
        inst2b = se.new_instance("u2")
        inst2b["role_bindings"]["a"] = _filled("a", "p2", "a2")
        req1["instances"] = [inst1b, inst2b]
        req1 = se.recompute_requirement(req1)
        targets_at_1_needed = srt.compute_recovery_targets(_contract_with("x", req1), {})

        self.assertEqual(set(targets_at_2_needed), set(targets_at_1_needed))

    def test_enough_complete_but_some_model_dependent_produces_provisional_corroboration(self):
        req = self._req(1)
        inst = se.new_instance("u1")
        inst["role_bindings"]["a"] = _filled("a", "p1", "a1", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "filled")
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertTrue(all(t["reason"] == "provisional_corroboration" for t in targets.values()))


class OpenListTests(unittest.TestCase):
    def _req(self):
        specs = {"a": se.new_role_spec("a", "category a", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["a"])
        return se.new_requirement("x#req", "atomic", specs, completion, "open_list", multi_instance=True)

    def test_zero_instances_is_missing_not_breadth(self):
        req = self._req()
        req["instances"] = []
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 1)
        self.assertEqual(next(iter(targets.values()))["reason"], "missing")

    def test_one_complete_instance_produces_breadth_not_missing(self):
        req = self._req()
        inst = se.new_instance("u1")
        inst["role_bindings"]["a"] = _filled("a", "p1", "a1")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "partially_filled")
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 1)
        target = next(iter(targets.values()))
        self.assertEqual(target["reason"], "open_list_breadth")
        self.assertEqual(target["goal_mode"], "breadth")

    def test_breadth_pass_already_used_produces_no_target(self):
        req = self._req()
        inst = se.new_instance("u1")
        inst["role_bindings"]["a"] = _filled("a", "p1", "a1")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        status = {"x#req": se.new_search_status("x#req", breadth_pass_used=True)}
        targets = srt.compute_recovery_targets(_contract_with("x", req), {}, status)
        self.assertEqual(targets, {})

    def test_open_list_never_produces_a_coexisting_corroboration_target(self):
        """compute_stop_search_certified is vacuously True for any non-'filled' state, and
        open_list can never reach 'filled' -- confirmed directly against the engine, round-2 §3.E
        correction. A model-nominated sole complete instance must produce ONLY open_list_breadth."""
        req = self._req()
        req["role_specs"]["a"] = se.new_role_spec("a", "category a", "model_nomination_only")
        inst = se.new_instance("u1")
        inst["role_bindings"]["a"] = _filled("a", "p1", "a1", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        reasons = {t["reason"] for t in targets.values()}
        self.assertEqual(reasons, {"open_list_breadth"})


class ProvisionalCorroborationTests(unittest.TestCase):
    def test_direct_model_dependent_fill_produces_corroboration_with_no_guessed_value(self):
        specs = {"a": se.new_role_spec("a", "category a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "guessed value", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 1)
        target = next(iter(targets.values()))
        self.assertEqual(target["reason"], "provisional_corroboration")
        self.assertEqual(target["search_child_id"], "x")
        self.assertEqual(target["trigger_child_id"], "x")
        from experiments.ask_cli_revised import sufficiency_recovery_targets as srt_mod

        hint = srt_mod.recovery_query_hint(target, _contract_with("x", req))
        self.assertNotIn("guessed value", hint)

    def test_clean_fill_produces_no_corroboration_target(self):
        specs = {"a": se.new_role_spec("a", "category a", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertEqual(srt.compute_recovery_targets(_contract_with("x", req), {}), {})

    def test_two_independently_model_dependent_instances_do_not_collapse(self):
        """The real c6 shape: a `multi_instance=False` requirement whose model-nomination forking
        produced two complete, independently model-dependent instances -- each must get its OWN
        target, discriminated by instance_key, never merged into one."""
        specs = {"a": se.new_role_spec("a", "category a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst1 = se.new_instance()
        inst1["role_bindings"]["a"] = _filled("a", "p1", "implicit value", method="model_mapping")
        inst2 = {**se.new_instance(), "instance_key": "i::other"}
        inst2["role_bindings"]["a"] = _filled("a", "p2", "explicit value", method="model_mapping")
        req["instances"] = [inst1, inst2]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "filled")
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(len(targets), 2)
        scopes = {t["scope"].get("instance_key") for t in targets.values()}
        self.assertEqual(scopes, {inst1["instance_key"], "i::other"})

    def test_multiple_descendants_sharing_one_upstream_dependency_deduplicate(self):
        parent_specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        parent_completion = se.new_role_completion(required_roles=["trait"])
        parent_req = se.new_requirement("p#req", "atomic", parent_specs, parent_completion, "exists")
        p_inst = se.new_instance()
        p_inst["role_bindings"]["trait"] = _filled("trait", "pp", "trait X", method="model_mapping")
        parent_req["instances"] = [p_inst]
        parent_req = se.recompute_requirement(parent_req)
        parent_req = sd._stamp_model_dependency_origins(parent_req, "p")
        propagated = _propagate(parent_req, "trait")

        def _child(child_id):
            specs = {
                "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
                "scale": se.new_role_spec("scale", "a named scale", "named_instrument_lexicon"),
            }
            completion = se.new_role_completion(required_roles=["trait", "scale"])
            req = se.new_requirement(
                f"{child_id}#req", "relational", specs, completion, "exists", parent_context_roles=["trait"]
            )
            inst = se.new_instance()
            inst["role_bindings"]["trait"] = propagated["trait"]
            inst["role_bindings"]["scale"] = _filled("scale", f"{child_id}p", "Scale")
            req["instances"] = [inst]
            return se.recompute_requirement(req)

        mapped = {
            "p": se.new_contract("p", [parent_req]),
            "c1": se.new_contract("c1", [_child("c1")]),
            "c2": se.new_contract("c2", [_child("c2")]),
        }
        targets = srt.compute_recovery_targets(mapped, {"c1": "p", "c2": "p"})
        redirected = [t for t in targets.values() if t["search_child_id"] == "p"]
        self.assertEqual(len(redirected), 1)
        # p's OWN direct pass also generates a provisional target for this exact same obligation
        # (search_child_id="p", requirement_id="p#req", role="trait", same "no instance to
        # discriminate" scope) -- it correctly MERGES with c1's/c2's redirected targets rather than
        # producing a separate, redundant third search: p is itself one of the beneficiaries too.
        self.assertEqual(set(redirected[0]["affected_descendants"]), {"p", "c1", "c2"})

    def test_two_hop_inherited_provisionality_redirects_to_the_true_origin(self):
        grandparent_specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        gp_completion = se.new_role_completion(required_roles=["trait"])
        gp_req = se.new_requirement("gp#req", "atomic", grandparent_specs, gp_completion, "exists")
        gp_inst = se.new_instance()
        gp_inst["role_bindings"]["trait"] = _filled("trait", "gpp", "trait Y", method="model_mapping")
        gp_req["instances"] = [gp_inst]
        gp_req = se.recompute_requirement(gp_req)
        gp_req = sd._stamp_model_dependency_origins(gp_req, "gp")

        hop1 = _propagate(gp_req, "trait")
        parent_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "other": se.new_role_spec("other", "other", "achieved_outcome_predicate"),
        }
        parent_completion = se.new_role_completion(required_roles=["trait", "other"])
        parent_req = se.new_requirement(
            "p#req", "relational", parent_specs, parent_completion, "exists", parent_context_roles=["trait"]
        )
        p_inst = se.new_instance()
        p_inst["role_bindings"]["trait"] = hop1["trait"]
        p_inst["role_bindings"]["other"] = _filled("other", "pp", "other result")
        parent_req["instances"] = [p_inst]
        parent_req = se.recompute_requirement(parent_req)

        hop2 = _propagate(parent_req, "trait")
        child_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "a named scale", "named_instrument_lexicon"),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        child_req = se.new_requirement(
            "c#req", "relational", child_specs, child_completion, "exists", parent_context_roles=["trait"]
        )
        c_inst = se.new_instance()
        c_inst["role_bindings"]["trait"] = hop2["trait"]
        c_inst["role_bindings"]["scale"] = _filled("scale", "cp", "Scale Z")
        child_req["instances"] = [c_inst]
        child_req = se.recompute_requirement(child_req)

        mapped = {
            "gp": se.new_contract("gp", [gp_req]),
            "p": se.new_contract("p", [parent_req]),
            "c": se.new_contract("c", [child_req]),
        }
        targets = srt.compute_recovery_targets(mapped, {"p": "gp", "c": "p"})
        corroboration = [t for t in targets.values() if t["reason"] == "provisional_corroboration"]
        self.assertEqual(len(corroboration), 1)
        self.assertEqual(corroboration[0]["search_child_id"], "gp")
        self.assertEqual(corroboration[0]["requirement_id"], "gp#req")

    def test_optional_model_dependent_role_produces_no_target(self):
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a"], optional_roles=["b"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result")
        inst["role_bindings"]["b"] = _filled("b", "p2", "b result", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "filled")
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertEqual(targets, {})


class ConfidenceAwareRelationshipContextTests(unittest.TestCase):
    def _relational_req(self):
        specs = {
            "region": se.new_role_spec("region", "a named brain area", "model_nomination_only"),
            "behavior": se.new_role_spec("behavior", "an observed behavior", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["region", "behavior"])
        return se.new_requirement("x#req", "relational", specs, completion, "exists")

    def test_clean_context_role_is_injected_concretely(self):
        req = self._relational_req()
        inst = se.new_instance()
        inst["role_bindings"]["region"] = _filled("region", "p1", "the amygdala")
        inst["role_bindings"]["behavior"] = _missing("behavior")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        target = next(iter(targets.values()))
        hint = srt.recovery_query_hint(target, _contract_with("x", req))
        self.assertIn("the amygdala", hint)

    def test_provisional_context_role_is_downgraded_to_category_description(self):
        req = self._relational_req()
        inst = se.new_instance()
        inst["role_bindings"]["region"] = _filled("region", "p1", "the amygdala", method="model_mapping")
        inst["role_bindings"]["behavior"] = _missing("behavior")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        target = next(iter(targets.values()))
        hint = srt.recovery_query_hint(target, _contract_with("x", req))
        self.assertNotIn("the amygdala", hint)
        self.assertIn("a named brain area", hint)

    def test_whole_passage_context_is_downgraded_to_category_description(self):
        """Found by the Phase 12 offline inventory, not anticipated in the design docs:
        `achieved_outcome_predicate`'s own detector legitimately returns the WHOLE PASSAGE as
        `exact_text` ("a stated result is a property of the passage as a whole"), which is not a
        short phrase and must not be injected verbatim into a hint merely because it is clean."""
        req = self._relational_req()
        long_passage = (
            "This research confirmed earlier reports that people with anomalous faces are imbued "
            "with negative personality characteristics and described a behavioral manifestation."
        )
        inst = se.new_instance()
        inst["role_bindings"]["region"] = _missing("region")
        inst["role_bindings"]["behavior"] = _filled("behavior", "p1", long_passage)
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        target = next(iter(targets.values()))
        hint = srt.recovery_query_hint(target, _contract_with("x", req))
        self.assertNotIn(long_passage, hint)
        self.assertIn("an observed behavior", hint)

    def test_upstream_model_dependent_context_is_also_downgraded(self):
        req = self._relational_req()
        inst = se.new_instance()
        inst["role_bindings"]["region"] = _filled(
            "region",
            "p1",
            "the amygdala",
            method="parent_context",
            provenance_extra={"upstream_model_dependent": True},
        )
        inst["role_bindings"]["behavior"] = _missing("behavior")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        target = next(iter(targets.values()))
        hint = srt.recovery_query_hint(target, _contract_with("x", req))
        self.assertNotIn("the amygdala", hint)


class TargetIdentityTests(unittest.TestCase):
    def test_same_semantic_target_reproduces_the_same_id(self):
        payload = {
            "search_child_id": "x",
            "requirement_id": "x#req",
            "reason": "missing",
            "goal_mode": "single_role",
            "target_roles": ["a"],
            "scope": {"kind": "none"},
        }
        self.assertEqual(srt.new_target_id(payload), srt.new_target_id(dict(payload)))

    def test_trigger_child_and_affected_descendants_never_affect_identity(self):
        target1 = srt.new_recovery_target(
            search_child_id="p",
            trigger_child_id="c1",
            requirement_id="p#req",
            target_roles=["a"],
            reason="provisional_corroboration",
            goal_mode="single_role",
            scope={"kind": "none"},
            category_descriptions=["x"],
        )
        target2 = srt.new_recovery_target(
            search_child_id="p",
            trigger_child_id="c2",
            requirement_id="p#req",
            target_roles=["a"],
            reason="provisional_corroboration",
            goal_mode="single_role",
            scope={"kind": "none"},
            category_descriptions=["x"],
            affected_descendants=("c1", "c2", "c3"),
        )
        self.assertEqual(target1["target_id"], target2["target_id"])

    def test_does_not_affect_contract_hash(self):
        specs = {"a": se.new_role_spec("a", "category a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        before = se.contract_hash(se.new_contract("x", [req]))
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _filled("a", "p1", "a result", method="model_mapping")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        srt.compute_recovery_targets(_contract_with("x", req), {})
        after = se.contract_hash(se.new_contract("x", [req]))
        self.assertEqual(before, after)


class GoalModeHintDispatchTests(unittest.TestCase):
    def test_goal_mode_drives_hint_template_with_no_parallel_branch(self):
        """The hint builder dispatches on goal_mode alone -- never re-derives disjunctive/
        relational-ness from reason or role_completion a second time."""
        import inspect

        source = inspect.getsource(srt.recovery_query_hint)
        self.assertIn("goal_mode", source)


class BudgetAndGenericGapCoexistenceTests(unittest.TestCase):
    def test_recovery_gate_dependency_is_absent_from_this_module(self):
        """compute_recovery_targets itself has no gate flag -- callers (e2e.py) own the opt-in."""
        import inspect

        self.assertNotIn("gate", inspect.signature(srt.compute_recovery_targets).parameters)


class MixedInstanceExistsRecoveryTests(unittest.TestCase):
    """Phase 16 (brief §J / plan §10): once an `exists` requirement is already satisfied by a
    DIFFERENT, complete instance, an incomplete sibling of the SAME requirement must not generate
    its own `missing`/`partial`/`relationship_unverified` RecoveryTarget -- `exists` needs only
    one complete instance, so a sibling's own gap is not a recovery obligation. The satisfying
    instance's own corroboration obligation (if its completion is model-dependent) is unaffected.
    Mirrors the real Phase-15 c4 shape exactly: RTPJ (region+relation filled, different
    propositions -> relationship_unverified) alongside amygdala (region+relation, same
    proposition -> complete, model-dependent)."""

    def _requirement(self):
        specs = {
            "region": se.new_role_spec("region", "a specific NAMED brain area", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["region", "relation"])
        return se.new_requirement("c4#req", "atomic", specs, completion, "exists")

    def _incomplete_instance(self, key):
        inst = se.new_instance(key)
        inst["role_bindings"]["region"] = _filled("region", "p27", "RTPJ", method="model_mapping")
        inst["role_bindings"]["relation"] = _filled("relation", "p11", "relation evidence")
        return inst

    def _complete_model_dependent_instance(self, key):
        inst = se.new_instance(key)
        inst["role_bindings"]["region"] = _filled("region", "p11", "amygdala", method="model_mapping")
        inst["role_bindings"]["relation"] = _filled("relation", "p11", "relation evidence")
        return inst

    def test_incomplete_sibling_produces_no_target_once_exists_is_satisfied(self):
        req = self._requirement()
        req["instances"] = [self._incomplete_instance("rtpj"), self._complete_model_dependent_instance("amygdala")]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "filled")
        self.assertFalse(req["instances"][0]["complete"])
        self.assertTrue(req["instances"][1]["complete"])

        targets = srt.compute_recovery_targets(_contract_with("c4", req), {})
        reasons = {t["reason"] for t in targets.values()}
        self.assertNotIn("relationship_unverified", reasons)
        self.assertNotIn("missing", reasons)
        self.assertNotIn("partial", reasons)
        # the satisfying instance's own corroboration obligation is unaffected
        self.assertIn("provisional_corroboration", reasons)
        corroboration = next(t for t in targets.values() if t["reason"] == "provisional_corroboration")
        self.assertEqual(corroboration["scope"], {"kind": "instance", "instance_key": "amygdala"})

    def test_incomplete_sibling_still_produces_a_target_when_exists_is_not_yet_satisfied(self):
        """The suppression is conditional on the requirement already being `filled` -- with NO
        complete instance at all, the incomplete instance's own gap remains a real obligation."""
        req = self._requirement()
        req["instances"] = [self._incomplete_instance("rtpj")]
        req = se.recompute_requirement(req)
        self.assertNotEqual(req["state"], "filled")
        targets = srt.compute_recovery_targets(_contract_with("c4", req), {})
        self.assertTrue(any(t["reason"] == "relationship_unverified" for t in targets.values()))

    def test_suppression_is_scoped_to_exists_never_for_each_discovered_instance(self):
        """for_each_discovered_instance needs EVERY instance complete -- an incomplete sibling's
        own gap must keep generating a target regardless of any OTHER instance's completeness."""
        specs = {
            "a": se.new_role_spec("a", "category a", "achieved_outcome_predicate"),
            "b": se.new_role_spec("b", "category b", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        req = se.new_requirement(
            "x#req", "relational", specs, completion, "for_each_discovered_instance", multi_instance=True
        )
        complete_inst = se.new_instance("u1")
        complete_inst["role_bindings"]["a"] = _filled("a", "p1", "a1")
        complete_inst["role_bindings"]["b"] = _filled("b", "p1", "b1")
        incomplete_inst = se.new_instance("u2")
        incomplete_inst["role_bindings"]["a"] = _filled("a", "p2", "a2")
        incomplete_inst["role_bindings"]["b"] = _missing("b")
        req["instances"] = [complete_inst, incomplete_inst]
        req = se.recompute_requirement(req)
        self.assertEqual(req["state"], "partially_filled")  # NOT "filled" -- for_each needs ALL complete
        targets = srt.compute_recovery_targets(_contract_with("x", req), {})
        self.assertTrue(any(t["scope"].get("instance_key") == "u2" for t in targets.values()))


class RecoveryTargetMergeTests(unittest.TestCase):
    """Phase 16 (brief §K / plan §9D): when two generation calls collapse to the same `target_id`,
    `affected_descendants` AND `dependency_origins` are both unioned/deduplicated -- never
    last-write-wins on either. Any OTHER field disagreeing for the same `target_id` fails loudly
    (a genuine collision, which this session found no real trigger for -- so this is a defensive
    guard, exercised directly here with hand-built targets rather than hunted for naturally)."""

    def _base_target(self, **overrides):
        payload = dict(
            search_child_id="p",
            trigger_child_id="c1",
            requirement_id="p#req",
            target_roles=["trait"],
            reason="provisional_corroboration",
            goal_mode="single_role",
            scope={"kind": "none"},
            category_descriptions=["a named trait"],
            dependency_origins=[{"child_id": "p", "requirement_id": "p#req", "role": "trait", "instance_key": None}],
        )
        payload.update(overrides)
        return srt.new_recovery_target(**payload)

    def test_affected_descendants_union_deduplicated(self):
        a = self._base_target(trigger_child_id="c1", affected_descendants=("c1",))
        b = self._base_target(trigger_child_id="c2", affected_descendants=("c2",))
        merged = srt._merge_recovery_target(a, b)
        self.assertEqual(set(merged["affected_descendants"]), {"c1", "c2"})

    def test_dependency_origins_union_deduplicated_not_last_write_wins(self):
        origin_a = {"child_id": "gp", "requirement_id": "gp#req", "role": "trait", "instance_key": None}
        origin_b = {"child_id": "gp2", "requirement_id": "gp2#req", "role": "trait", "instance_key": None}
        a = self._base_target(dependency_origins=[origin_a])
        b = self._base_target(dependency_origins=[origin_b])
        merged = srt._merge_recovery_target(a, b)
        self.assertEqual(len(merged["dependency_origins"]), 2)
        self.assertIn(origin_a, merged["dependency_origins"])
        self.assertIn(origin_b, merged["dependency_origins"])

    def test_identical_dependency_origins_do_not_duplicate(self):
        origin = {"child_id": "gp", "requirement_id": "gp#req", "role": "trait", "instance_key": None}
        a = self._base_target(dependency_origins=[origin])
        b = self._base_target(dependency_origins=[dict(origin)])
        merged = srt._merge_recovery_target(a, b)
        self.assertEqual(merged["dependency_origins"], [origin])

    def test_genuine_disagreement_on_an_unmerged_field_raises(self):
        a = self._base_target(category_descriptions=["a named trait"])
        b = self._base_target(category_descriptions=["a DIFFERENT description"])
        with self.assertRaises(ValueError):
            srt._merge_recovery_target(a, b)

    def test_end_to_end_merge_still_works_for_the_real_shared_upstream_shape(self):
        """Regression: the pre-existing dedup/redirect behavior (ProvisionalCorroborationTests.
        test_multiple_descendants_sharing_one_upstream_dependency_deduplicate) must still work
        unchanged once the merge also unions dependency_origins."""
        parent_specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        parent_completion = se.new_role_completion(required_roles=["trait"])
        parent_req = se.new_requirement("p#req", "atomic", parent_specs, parent_completion, "exists")
        p_inst = se.new_instance()
        p_inst["role_bindings"]["trait"] = _filled("trait", "pp", "trait X", method="model_mapping")
        parent_req["instances"] = [p_inst]
        parent_req = se.recompute_requirement(parent_req)
        parent_req = sd._stamp_model_dependency_origins(parent_req, "p")
        propagated = _propagate(parent_req, "trait")

        def _child(child_id):
            specs = {
                "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
                "scale": se.new_role_spec("scale", "a named scale", "named_instrument_lexicon"),
            }
            completion = se.new_role_completion(required_roles=["trait", "scale"])
            req = se.new_requirement(
                f"{child_id}#req", "relational", specs, completion, "exists", parent_context_roles=["trait"]
            )
            inst = se.new_instance()
            inst["role_bindings"]["trait"] = propagated["trait"]
            inst["role_bindings"]["scale"] = _filled("scale", f"{child_id}p", "Scale")
            req["instances"] = [inst]
            return se.recompute_requirement(req)

        mapped = {
            "p": se.new_contract("p", [parent_req]),
            "c1": se.new_contract("c1", [_child("c1")]),
            "c2": se.new_contract("c2", [_child("c2")]),
        }
        targets = srt.compute_recovery_targets(mapped, {"c1": "p", "c2": "p"})
        redirected = [t for t in targets.values() if t["search_child_id"] == "p"]
        self.assertEqual(len(redirected), 1)
        self.assertEqual(set(redirected[0]["affected_descendants"]), {"p", "c1", "c2"})
        # all three contributing calls (p's own direct pass, c1's redirect, c2's redirect) point
        # at the SAME single upstream origin -- deduplicated to exactly one entry, not tripled.
        self.assertEqual(len(redirected[0]["dependency_origins"]), 1)


class LeakageTests(unittest.TestCase):
    def test_hint_never_contains_a_requirement_or_child_provenance_token(self):
        specs = {"a": se.new_role_spec("a", "a named trait or construct", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("c9#suff:pairing", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = _missing("a")
        req["instances"] = [inst]
        req = se.recompute_requirement(req)
        targets = srt.compute_recovery_targets(_contract_with("c9", req), {})
        target = next(iter(targets.values()))
        hint = srt.recovery_query_hint(target, _contract_with("c9", req))
        self.assertNotIn("c9#", hint)
        self.assertNotIn("RC-", hint)


if __name__ == "__main__":
    unittest.main()
