"""Orchestration tests: sufficiency_diagnostic ties Layer A + the mapper to a small, hand-built
sealed ledger. No model, no network, no E2E.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm


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
        mapped = sd.compute_diagnostic_sufficiency_map(sealed, contracts, parent_of={"c": "p"})
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
        mapped = sd.compute_diagnostic_sufficiency_map(sealed, contracts, parent_of={"c": "p"})
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

    def verify_specific_instances(self, *, category_description, candidates):
        return [
            {"candidate_id": c["candidate_id"], "specific": True, "instance_text": c["exact_text"]} for c in candidates
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
        mapped = sd.compute_diagnostic_sufficiency_map(sealed, _small_contract(), parent_of={"c": "p"})
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
            sealed, _small_contract(), parent_of={"c": "p"}, model_client=_FakeModelClient()
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
        positional = sd.compute_diagnostic_sufficiency_map(sealed, _small_contract(), {"c": "p"})
        keyword = sd.compute_diagnostic_sufficiency_map(sealed, _small_contract(), parent_of={"c": "p"})
        self.assertEqual(positional, keyword)


class RecoveryCandidateReportingTests(unittest.TestCase):
    def test_missing_requirement_is_a_recovery_candidate(self):
        sealed = _sealed([])
        contracts = _small_contract()
        mapped = sd.compute_diagnostic_sufficiency_map(sealed, contracts, parent_of={"c": "p"})
        candidates = sd.compute_recovery_candidates(mapped)
        self.assertIn("p8#req", candidates.get("p", []))

    def test_filled_requirement_is_not_a_recovery_candidate(self):
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
        req = se.recompute_requirement(req)
        mapped = {"x": se.new_contract("x", [req])}
        candidates = sd.compute_recovery_candidates(mapped)
        self.assertNotIn("x", candidates)


class DirectionAndEffectivenessPassTests(unittest.TestCase):
    def test_populates_direction_in_place_only_when_declared(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req_with = se.new_requirement(
            "d#req", "relational", specs, completion, "exists", direction=se.new_direction_assessment()
        )
        req_without = se.new_requirement("nd#req", "atomic", specs, completion, "exists")
        contracts = {"d": se.new_contract("d", [req_with]), "nd": se.new_contract("nd", [req_without])}
        sealed = _sealed([_prop("p1", 1, "This shows a positive association overall.", ["d", "nd"])])
        sd.compute_direction_and_effectiveness(sealed, contracts)
        self.assertTrue(contracts["d"]["requirements"][0]["direction"]["reported"])
        self.assertIsNone(contracts["nd"]["requirements"][0]["effectiveness"])


class RecoveryHintTests(unittest.TestCase):
    def test_hint_uses_only_role_category_descriptions(self):
        specs = {
            "a": se.new_role_spec("a", "a named scale or instrument", "named_instrument_lexicon"),
            "b": se.new_role_spec("b", "a trait or construct", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["a", "b"])
        req = se.new_requirement(
            "c9#suff:pairing", "relational", specs, completion, "for_each_discovered_instance", multi_instance=True
        )
        hint = sm.recovery_hint(req)
        self.assertIn("named scale or instrument", hint)
        self.assertNotIn("c9#", hint)
        self.assertNotIn("RC-", hint)


if __name__ == "__main__":
    unittest.main()
