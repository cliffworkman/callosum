"""Orchestration tests: sufficiency_diagnostic ties Layer A + the mapper to a small, hand-built
sealed ledger. No model, no network, no E2E.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt


def _sealed(propositions):
    evidence_spans = [
        {
            "paper_id": p["paper_id"],
            "chunk_id": p["evidence_anchor_chunk_id"],
            "span_id": p["evidence_span_id"],
            "text": p["quote"],
        }
        for p in propositions
    ]
    return {"verified_propositions": propositions, "evidence_spans": evidence_spans}


def _prop(pid, paper_id, quote, responsive):
    return {
        "proposition_id": pid,
        "paper_id": paper_id,
        "evidence_anchor_chunk_id": 1,
        "evidence_span_id": "e1",
        "quote": quote,
        "proposition_text": quote,
        "verification": {"status": "verified"},
        "responsive_obligation_ids": responsive,
        "anchors": [],
    }


def _small_contract():
    parent_specs = {
        "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
        "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
    }
    parent_completion = se.new_role_completion(required_roles=["trait", "relation"])
    parent_req = se.new_requirement(
        "p8#req", "atomic", parent_specs, parent_completion, "open_list", multi_instance=True
    )
    parent_contract = se.new_contract("p", [parent_req])

    child_specs = {
        "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
        "scale": se.new_role_spec("scale", "named scale", "named_instrument_lexicon", disqualifying_guards=[]),
    }
    child_completion = se.new_role_completion(required_roles=["trait", "scale"])
    child_req = se.new_requirement(
        "c9#req",
        "relational",
        child_specs,
        child_completion,
        "for_each_discovered_instance",
        multi_instance=True,
        parent_context_roles=["trait"],
    )
    child_contract = se.new_contract("c", [child_req])
    return {"p": parent_contract, "c": child_contract}


class UnitsByChildTests(unittest.TestCase):
    def test_groups_units_by_attached_children(self):
        sealed = _sealed(
            [
                _prop("p1", 1, "The Empathy Scale was used to assess trait empathy.", ["c"]),
                _prop("p2", 2, "This finding was found in participants.", ["p"]),
            ]
        )
        by_child = sd.units_by_child(sealed)
        self.assertEqual(len(by_child["c"]), 1)
        self.assertEqual(len(by_child["p"]), 1)


class ComputeDiagnosticSufficiencyMapTests(unittest.TestCase):
    def test_parent_is_mapped_before_paired_child_and_pairing_works(self):
        sealed = _sealed(
            [
                _prop("p1", 1, "This finding showed a strong relation to the outcome.", ["p"]),
                _prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        contracts = _small_contract()
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed, contracts, parent_of={"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        parent_req = mapped["p"]["requirements"][0]
        self.assertEqual(len(parent_req["instances"]), 1)
        child_req = mapped["c"]["requirements"][0]
        # the parent discovered no NAMED trait (model_nomination_only, no model) -- so the child
        # correctly finds no parent instance to pair against yet.
        self.assertEqual(child_req["instances"], [])
        self.assertEqual(child_req["state"], "missing")

    def test_no_candidate_units_leaves_requirement_missing(self):
        sealed = _sealed([])
        contracts = _small_contract()
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed, contracts, parent_of={"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        self.assertEqual(mapped["p"]["requirements"][0]["state"], "missing")
        self.assertEqual(mapped["c"]["requirements"][0]["state"], "missing")


class _FakeModelClient:
    """Hand-written fake -- never a real QwenTasks/network call."""

    model_name = "fake-qwen"

    def nominate_sufficiency_role(self, *, category_description, candidates):
        return [
            {"proposition_id": c["proposition_id"], "exact_text": "empathy"}
            for c in candidates
            if "empathy" in c["passage"].lower()
        ]


class ModelAssistedParentPropagationTests(unittest.TestCase):
    """The single most important correctness property the model_client threading exists to prove
    (Cliff's corrections #2/#3): a parent role the deterministic pass alone can never fill
    (`model_nomination_only`, no detector) can still be discovered via model nomination, and a
    PAIRED CHILD sees that newly-filled parent instance in THE SAME call -- no separate
    propagation step, because the existing topological order already maps the parent first and
    the child reads its CURRENT instances."""

    def test_deterministic_only_baseline_leaves_the_child_unpaired(self):
        """Restates test_parent_is_mapped_before_paired_child_and_pairing_works's own documented
        gap explicitly as a baseline, so the model-assisted test below is a direct before/after."""
        sealed = _sealed(
            [
                _prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"]),
                _prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed, _small_contract(), parent_of={"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        self.assertEqual(mapped["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]["state"], "missing")
        self.assertEqual(mapped["c"]["requirements"][0]["instances"], [])

    def test_a_trait_the_deterministic_pass_cannot_fill_is_discovered_and_paired_in_one_pass(self):
        sealed = _sealed(
            [
                _prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"]),
                _prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed,
            _small_contract(),
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        parent_req = mapped["p"]["requirements"][0]
        self.assertEqual(len(parent_req["instances"]), 1)
        trait_binding = parent_req["instances"][0]["role_bindings"]["trait"]
        self.assertEqual(trait_binding["state"], "filled")
        self.assertEqual(trait_binding["provenance"]["candidate_source"], "model_mapping")
        self.assertEqual(trait_binding["provenance"]["model"], "fake-qwen")

        child_req = mapped["c"]["requirements"][0]
        self.assertEqual(len(child_req["instances"]), 1)
        self.assertEqual(child_req["state"], "filled")

    def test_with_no_model_client_the_same_contract_is_still_byte_identical_to_the_old_signature(self):
        """Regression proof: adding model_client=None as a trailing kwarg changes nothing for a
        caller that omits it, positionally or by keyword."""
        sealed = _sealed(
            [
                _prop("p1", 1, "This finding showed a strong relation to the outcome.", ["p"]),
                _prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        positional = sd.compute_diagnostic_sufficiency_map(
            sealed, _small_contract(), {"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        keyword = sd.compute_diagnostic_sufficiency_map(
            sealed, _small_contract(), parent_of={"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        self.assertEqual(positional, keyword)


class ComputeDiagnosticSufficiencyMapPhase19ScopingTests(unittest.TestCase):
    """`child_id` is a per-child LOOP VARIABLE in `compute_diagnostic_sufficiency_map` -- never a
    field on an individual requirement dict (confirmed directly against `sufficiency_engine.
    new_requirement`'s own return shape during the Phase-19 audit). These tests prove it reaches
    the real model-nomination scope end-to-end through this module's own per-child loop, not only
    through a hand-threaded unit test in `test_sufficiency_mapping.py`."""

    def _sealed_and_contract(self):
        sealed = _sealed(
            [
                _prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"]),
                _prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        return sealed, _small_contract()

    def test_all_eligible_policy_produces_the_same_bindings_as_the_legacy_call_plus_a_status_tag(self):
        sealed, contracts = self._sealed_and_contract()
        legacy = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contracts,
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        scoped = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contracts,
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        legacy_trait = legacy["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]
        scoped_trait = scoped["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]
        self.assertEqual(legacy_trait["exact_text"], scoped_trait["exact_text"])
        self.assertNotIn("nomination_receipt_status", legacy_trait["provenance"])
        self.assertEqual(scoped_trait["provenance"]["nomination_receipt_status"], "fresh")

    def test_exact_scope_set_authorizes_only_the_named_childs_scope(self):
        """Two independent model_nomination_only scopes exist here: parent `p`'s own `trait`
        role, and (if it had its own independent model role) a sibling child's. We authorize only
        the PARENT's scope and confirm the parent is freshly nominated while an unrelated,
        unauthorized scope on a second, unrelated child is held fixed with no model call."""
        sealed, contracts = self._sealed_and_contract()
        # A second, wholly independent child with its own model_nomination_only role and its OWN
        # parent-less requirement -- proves the per-child loop threads the correct child_id for
        # EACH child, not just a single hard-coded one.
        other_specs = {"widget": se.new_role_spec("widget", "a widget", "model_nomination_only")}
        other_completion = se.new_role_completion(required_roles=["widget"])
        other_req = se.new_requirement("other#req", "atomic", other_specs, other_completion, "exists")
        contracts["other"] = se.new_contract("other", [other_req])
        sealed["verified_propositions"].append(
            _prop("p3", 3, "A gadget was independently observed in this study.", ["other"])
        )
        sealed["evidence_spans"].append(
            {
                "paper_id": 3,
                "chunk_id": 1,
                "span_id": "e1",
                "text": "A gadget was independently observed in this study.",
            }
        )

        parent_scope = mscope.new_model_nomination_scope("p", "p8#req", "trait")
        ctx = mscope.new_nomination_context(mscope.exact_scope_set_policy([parent_scope]))

        class _TrackingClient(_FakeModelClient):
            def __init__(self):
                self.calls = []

            def nominate_sufficiency_role(self, *, category_description, candidates):
                self.calls.append(category_description)
                return super().nominate_sufficiency_role(
                    category_description=category_description, candidates=candidates
                )

        client = _TrackingClient()
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contracts,
            parent_of={"c": "p"},
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )

        self.assertEqual(
            mapped["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]["provenance"][
                "nomination_receipt_status"
            ],
            "fresh",
        )
        self.assertEqual(
            mapped["other"]["requirements"][0]["instances"][0]["role_bindings"]["widget"]["state"], "missing"
        )
        self.assertEqual(client.calls, ["trait"], "the unauthorized 'other' child's scope must never reach the model")

    def test_without_nomination_context_behavior_is_completely_unaffected(self):
        """Confirms the production (e2e.py-shaped) call path -- model_client=None, no context at
        all -- is byte-identical to pre-Phase-19, proving Scope A's non-regression promise at the
        orchestration layer, not only inside sufficiency_mapping.py."""
        sealed, contracts = self._sealed_and_contract()
        before = sd.compute_diagnostic_sufficiency_map(
            sealed, contracts, parent_of={"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        after = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contracts,
            parent_of={"c": "p"},
            nomination_context=None,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        self.assertEqual(before, after)

    def test_model_dependency_origins_still_stamped_on_a_fresh_phase19_binding(self):
        """Test #31: `_stamp_model_dependency_origins` reads `provenance.get("candidate_source")`/
        `.get("model_dependency_origins")` only -- adding `nomination_receipt_status` alongside
        those must not interfere with origin stamping."""
        sealed, contracts = self._sealed_and_contract()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contracts,
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        trait_binding = mapped["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]
        origins = trait_binding["provenance"]["model_dependency_origins"]
        self.assertEqual(len(origins), 1)
        self.assertEqual(origins[0]["child_id"], "p")
        self.assertEqual(origins[0]["requirement_id"], "p8#req")
        self.assertEqual(origins[0]["role"], "trait")
        self.assertEqual(trait_binding["provenance"]["nomination_receipt_status"], "fresh")

    def test_same_ledger_and_replayed_receipts_produce_an_identical_mapped_tree(self):
        """Test #32: a second pass that holds EVERY scope fixed on the first pass's own recorded
        receipts (rather than making any fresh call) must reproduce the identical mapped tree --
        the stateless-rebuild + receipt-replay design is round-trip stable."""
        sealed, contracts = self._sealed_and_contract()
        first_ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        first = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contracts,
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            nomination_context=first_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )

        class _ShouldNeverBeCalledClient:
            model_name = "should-not-be-called"

            def nominate_sufficiency_role(self, *, category_description, candidates):
                raise AssertionError("a fully held-fixed second pass must never call the model")

        second_ctx = mscope.new_nomination_context(
            mscope.exact_scope_set_policy([]), prior_receipts=first_ctx["in_pass_receipts"]
        )
        second = sd.compute_diagnostic_sufficiency_map(
            sealed,
            contracts,
            parent_of={"c": "p"},
            model_client=_ShouldNeverBeCalledClient(),
            nomination_context=second_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )

        def _strip_receipt_status(mapped):
            out = {}
            for child_id, contract in mapped.items():
                out[child_id] = []
                for req in contract["requirements"]:
                    for inst in req["instances"]:
                        row = {}
                        for role, binding in inst["role_bindings"].items():
                            row[role] = {k: v for k, v in binding.items() if k != "provenance"}
                        out[child_id].append(row)
            return out

        # Bindings match exactly except the diagnostic-only status tag ("fresh" vs "held_fixed_replay").
        self.assertEqual(_strip_receipt_status(first), _strip_receipt_status(second))
        first_trait = first["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]
        second_trait = second["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]
        self.assertEqual(first_trait["provenance"]["nomination_receipt_status"], "fresh")
        self.assertEqual(second_trait["provenance"]["nomination_receipt_status"], "held_fixed_replay")


class RecoveryTargetReportingTests(unittest.TestCase):
    """`compute_recovery_candidates` is retired (Phase 12) -- `sufficiency_recovery_targets.
    compute_recovery_targets` is the replacement primitive; see test_sufficiency_recovery_targets.py
    for its own full generation test matrix. These two tests restate the ORIGINAL pair's intent
    against the new API, not duplicate the new module's own suite."""

    def test_missing_requirement_produces_a_recovery_target(self):
        sealed = _sealed([])
        contracts = _small_contract()
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed, contracts, parent_of={"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        targets = srt.compute_recovery_targets(mapped, {"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertTrue(any(t["requirement_id"] == "p8#req" for t in targets.values()))

    def test_filled_requirement_produces_no_recovery_target(self):
        specs = {"a": se.new_role_spec("a", "a", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        inst = se.new_instance()
        inst["role_bindings"]["a"] = se.new_role_binding(
            "a",
            state="filled",
            proposition_id="p1",
            exact_text="a result was found",
            provenance={"candidate_source": "deterministic_mapping", "detail": "", "model": None},
        )
        req["instances"] = [inst]
        req = se.recompute_requirement(req, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        mapped = {"x": se.new_contract("x", [req])}
        targets = srt.compute_recovery_targets(mapped, {}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertEqual(targets, {})


class StampModelDependencyOriginsTests(unittest.TestCase):
    """`compute_diagnostic_sufficiency_map` now stamps `model_dependency_origins` onto every fresh
    `model_mapping` binding via `_stamp_model_dependency_origins`, called in place inside the
    per-child loop (round 3 §7's corrected stamping site)."""

    def test_fresh_model_mapping_binding_is_stamped_with_its_own_location(self):
        """Phase 22: the origin now also carries `request_context`, read from the owning instance's
        own stamp (`sufficiency_mapping.map_requirement`) -- here the single real unit's own
        `unit_id`, coinciding with the (unforked) `instance_key` exactly as the Phase-19b/22 audits'
        own documented, non-general coincidence predicts."""
        sealed = _sealed([_prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"])])
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed,
            _small_contract(),
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        instance = mapped["p"]["requirements"][0]["instances"][0]
        trait_binding = instance["role_bindings"]["trait"]
        self.assertEqual(
            trait_binding["provenance"]["model_dependency_origins"],
            [
                {
                    "child_id": "p",
                    "requirement_id": "p8#req",
                    "role": "trait",
                    "instance_key": instance["instance_key"],
                    "request_context": instance["request_context"],
                }
            ],
        )

    def test_propagated_binding_carries_the_stamped_origin_forward_not_a_fresh_one(self):
        sealed = _sealed(
            [
                _prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"]),
                _prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed,
            _small_contract(),
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        child_trait_binding = mapped["c"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]
        self.assertEqual(child_trait_binding["provenance"]["candidate_source"], "parent_context")
        origins = child_trait_binding["provenance"]["model_dependency_origins"]
        self.assertEqual(len(origins), 1)
        self.assertEqual(origins[0]["child_id"], "p")
        self.assertEqual(origins[0]["requirement_id"], "p8#req")

    def test_deterministic_binding_is_never_stamped(self):
        sealed = _sealed([_prop("p1", 1, "This finding showed a strong relation to the outcome.", ["p"])])
        mapped = sd.compute_diagnostic_sufficiency_map(
            sealed, _small_contract(), parent_of={"c": "p"}, semantics_version=se.SUFFICIENCY_SEMANTICS_V3
        )
        relation_binding = mapped["p"]["requirements"][0]["instances"][0]["role_bindings"]["relation"]
        self.assertEqual(relation_binding["provenance"].get("model_dependency_origins"), None)

    def test_stamping_does_not_affect_the_frozen_contract_hash(self):
        before = se.contract_hash(_small_contract()["p"])
        sealed = _sealed([_prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"])])
        sd.compute_diagnostic_sufficiency_map(
            sealed,
            _small_contract(),
            parent_of={"c": "p"},
            model_client=_FakeModelClient(),
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        after = se.contract_hash(_small_contract()["p"])
        self.assertEqual(before, after)


class DirectionAndEffectivenessPassTests(unittest.TestCase):
    def test_computes_direction_summary_only_when_declared_leaves_authored_template_untouched(self):
        """Phase 18: the authored `direction`/`effectiveness` declaration/template on the
        requirement is a fixed intent marker, never mutated into a found value anymore (directive
        J) -- the actual per-run result lives on instances and the derived `direction_summary`/
        `effectiveness_summary`. This replaces the pre-Phase-18 assertion that `req["direction"]`
        itself got mutated in place, which is exactly the behavior this phase retires."""
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req_with = se.new_requirement(
            "d#req", "relational", specs, completion, "exists", direction=se.new_direction_assessment()
        )
        req_without = se.new_requirement("nd#req", "atomic", specs, completion, "exists")
        template_before = dict(req_with["direction"])
        contracts = {"d": se.new_contract("d", [req_with]), "nd": se.new_contract("nd", [req_without])}
        sealed = _sealed([_prop("p1", 1, "This shows a positive association overall.", ["d", "nd"])])
        sd.compute_direction_and_effectiveness(sealed, contracts, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION)
        self.assertEqual(contracts["d"]["requirements"][0]["direction"], template_before)
        self.assertIn("direction_summary", contracts["d"]["requirements"][0])
        self.assertIsNone(contracts["nd"]["requirements"][0]["effectiveness"])
        self.assertIsNone(contracts["nd"]["requirements"][0]["effectiveness_summary"])


if __name__ == "__main__":
    unittest.main()
