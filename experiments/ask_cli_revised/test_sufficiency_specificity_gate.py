"""Tests for the Phase 6 specificity-confirmation gate (the second key of the two-key model-
assisted nomination process). No model, no network, no E2E -- every client here is a
hand-written fake.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm

_UNSET = object()


def _nomination(proposition_id: str, exact_text: str, *, supporting=None) -> dict:
    return {
        "proposition_id": proposition_id,
        "exact_text": exact_text,
        "proposed_role": "role",
        "supporting_proposition_ids": supporting or [proposition_id],
    }


def _unit(proposition_id: str, passage: str, unit_id: str = "u1") -> dict:
    return {
        "unit_id": unit_id,
        "proposition_ids": [proposition_id],
        "passage": passage,
        "flags": {},
        "attached_children": [],
        "proposition_anchor": {},
    }


class _ScriptedValidator:
    """Hand-written fake -- never a real QwenTasks/network call.

    `nominations`: proposition_id -> exact_text (or list of exact_texts), same shape
    `test_sufficiency_mapping._FakeModelClient` already uses.
    `decisions_by_text`: exact_text -> (specific: bool, instance_text: str), default for any
    candidate not named here is (True, its own exact_text) -- "approve, unless scripted
    otherwise".
    `omit_texts`: exact_texts for which NO decision is returned at all (simulates the validator
    never mentioning a candidate).
    `extra_decisions`: decisions for candidate_ids that were never actually offered (simulates an
    attempt to hallucinate a new candidate).
    `malformed_response`: if set (not `_UNSET`), returned verbatim from `verify_specific_
    instances` instead of real decisions -- simulates a malformed validator response shape.
    """

    model_name = "fake-qwen"

    def __init__(
        self,
        nominations: dict | None = None,
        *,
        decisions_by_text: dict | None = None,
        omit_texts: set | None = None,
        extra_decisions: list | None = None,
        malformed_response=_UNSET,
    ):
        self.nominations = nominations or {}
        self.decisions_by_text = decisions_by_text or {}
        self.omit_texts = omit_texts or set()
        self.extra_decisions = extra_decisions or []
        self.malformed_response = malformed_response
        self.specificity_called = False
        self.specificity_calls: list[dict] = []

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        out = []
        for c in candidates:
            texts = self.nominations.get(c["proposition_id"])
            if texts is None:
                continue
            for text in texts if isinstance(texts, list) else [texts]:
                out.append({"proposition_id": c["proposition_id"], "exact_text": text})
        return out

    def verify_specific_instances(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        self.specificity_called = True
        self.specificity_calls.append({"category_description": category_description, "candidates": candidates})
        if self.malformed_response is not _UNSET:
            return self.malformed_response
        decisions = list(self.extra_decisions)
        for c in candidates:
            if c["exact_text"] in self.omit_texts:
                continue
            specific, instance_text = self.decisions_by_text.get(c["exact_text"], (True, c["exact_text"]))
            decisions.append({"candidate_id": c["candidate_id"], "specific": specific, "instance_text": instance_text})
        return decisions


class SpecificityGateDomainTests(unittest.TestCase):
    """Benchmark-neutral, cross-domain proof of the generic 'which X?' distinction -- never q_aib
    answer terms, never tuned toward a desired outcome."""

    def _confirm(self, category_description: str, exact_text: str, passage: str, specific: bool, instance_text: str):
        role_spec = se.new_role_spec("role", category_description, "model_nomination_only")
        nomination = _nomination("p1", exact_text)
        units = [_unit("p1", passage)]
        client = _ScriptedValidator(decisions_by_text={exact_text: (specific, instance_text)})
        return sm.confirm_specific_instances(role_spec, [nomination], units, client)

    def test_behavior_accept_specific(self):
        result = self._confirm(
            "an observed behavior, behavioral choice or action, or a task or measure of behavior",
            "participants donated less money",
            "In the study, participants donated less money to the charity than in the control condition.",
            True,
            "participants donated less money",
        )
        self.assertEqual(len(result), 1)

    def test_behavior_reject_generic(self):
        result = self._confirm(
            "an observed behavior, behavioral choice or action, or a task or measure of behavior",
            "a behavioral manifestation occurred",
            "The paper reported that a behavioral manifestation occurred affecting the outcome.",
            False,
            "",
        )
        self.assertEqual(result, [])

    def test_population_accept_specific(self):
        result = self._confirm(
            "a named culture or population",
            "adolescents in Japan",
            "The sample consisted of adolescents in Japan recruited from local schools.",
            True,
            "adolescents in Japan",
        )
        self.assertEqual(len(result), 1)

    def test_population_reject_generic(self):
        result = self._confirm(
            "a named culture or population",
            "a population was studied",
            "A population was studied across several sites.",
            False,
            "",
        )
        self.assertEqual(result, [])

    def test_intervention_accept_specific(self):
        result = self._confirm(
            "a named intervention",
            "mindfulness training",
            "Participants completed mindfulness training over eight weeks.",
            True,
            "mindfulness training",
        )
        self.assertEqual(len(result), 1)

    def test_intervention_reject_generic(self):
        result = self._confirm(
            "a named intervention",
            "an intervention reduced symptoms",
            "An intervention reduced symptoms significantly across the sample.",
            False,
            "",
        )
        self.assertEqual(result, [])

    def test_neural_region_accept_specific(self):
        result = self._confirm(
            "a specific named brain area",
            "amygdala",
            "Activity in the amygdala was elevated during the task.",
            True,
            "amygdala",
        )
        self.assertEqual(len(result), 1)

    def test_neural_modality_accept_specific(self):
        result = self._confirm(
            "the method or modality used to measure neural activity or structure",
            "functional MRI",
            "Functional MRI was used to measure activity during the task.",
            True,
            "functional MRI",
        )
        self.assertEqual(len(result), 1)

    def test_neural_region_reject_generic(self):
        result = self._confirm(
            "a specific named brain area",
            "a neural response was observed",
            "A neural response was observed during the task.",
            False,
            "",
        )
        self.assertEqual(result, [])

    def test_neural_modality_reject_generic(self):
        result = self._confirm(
            "the method or modality used to measure neural activity or structure",
            "a neural response was observed",
            "A neural response was observed during the task.",
            False,
            "",
        )
        self.assertEqual(result, [])


class SpecificityGateMechanicalTests(unittest.TestCase):
    """The explicit fail-closed/scope-boundary proofs."""

    def _role_spec(self):
        return se.new_role_spec("role", "a named thing", "model_nomination_only")

    def test_validator_cannot_create_a_candidate(self):
        """A decision for a candidate_id the gate never offered (hallucinated) must never produce
        a binding -- it is simply ignored, never treated as a new nomination. The real candidate's
        own decision is deliberately omitted here too, so the ONLY thing in play is the
        hallucinated one -- proving it alone can never survive."""
        nomination = _nomination("p1", "mindfulness training")
        units = [_unit("p1", "Participants completed mindfulness training over eight weeks.")]
        client = _ScriptedValidator(
            omit_texts={"mindfulness training"},
            extra_decisions=[{"candidate_id": "cand99", "specific": True, "instance_text": "phantom"}],
        )
        result = sm.confirm_specific_instances(self._role_spec(), [nomination], units, client)
        self.assertEqual(result, [])

    def test_validator_cannot_swap_proposition_id(self):
        """The validator's own schema has no proposition_id field at all -- confirm the survivor
        keeps the ORIGINAL proposition_id untouched regardless of anything in the decision."""
        nomination = _nomination("p1", "mindfulness training")
        units = [_unit("p1", "Participants completed mindfulness training over eight weeks.")]
        client = _ScriptedValidator(decisions_by_text={"mindfulness training": (True, "mindfulness training")})
        result = sm.confirm_specific_instances(self._role_spec(), [nomination], units, client)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["proposition_id"], "p1")

    def test_malformed_non_list_response_fails_closed(self):
        nomination = _nomination("p1", "mindfulness training")
        units = [_unit("p1", "Participants completed mindfulness training over eight weeks.")]
        client = _ScriptedValidator(malformed_response="not a list at all")
        result = sm.confirm_specific_instances(self._role_spec(), [nomination], units, client)
        self.assertEqual(result, [])

    def test_ungrounded_instance_text_fails_closed(self):
        """specific=True but instance_text is a fabrication -- not literally present in the
        nominated exact_text OR its own passage -- must be dropped."""
        nomination = _nomination("p1", "mindfulness training")
        units = [_unit("p1", "Participants completed mindfulness training over eight weeks.")]
        client = _ScriptedValidator(decisions_by_text={"mindfulness training": (True, "the hippocampus")})
        result = sm.confirm_specific_instances(self._role_spec(), [nomination], units, client)
        self.assertEqual(result, [])

    def test_omitted_decision_fails_closed(self):
        nomination = _nomination("p1", "mindfulness training")
        units = [_unit("p1", "Participants completed mindfulness training over eight weeks.")]
        client = _ScriptedValidator(omit_texts={"mindfulness training"})
        result = sm.confirm_specific_instances(self._role_spec(), [nomination], units, client)
        self.assertEqual(result, [])

    def test_empty_nomination_list_never_invokes_the_validator(self):
        """An already-declined nomination call (nothing to confirm) must never call
        verify_specific_instances at all."""
        client = _ScriptedValidator()
        result = sm.confirm_specific_instances(self._role_spec(), [], [], client)
        self.assertEqual(result, [])
        self.assertFalse(client.specificity_called)

    def test_rejected_nomination_cannot_fill_a_role(self):
        """End-to-end through map_requirement: a vetoed nomination leaves the role genuinely
        missing, never silently filled."""
        specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["trait"])
        req = se.new_requirement("t#req", "atomic", specs, completion, "exists")
        units = [_unit("p1", "The paper reported that a behavioral manifestation occurred.")]
        client = _ScriptedValidator(
            nominations={"p1": "a behavioral manifestation occurred"},
            decisions_by_text={"a behavioral manifestation occurred": (False, "")},
        )
        result = sm.map_requirement(req, units, model_client=client)
        self.assertEqual(result["state"], "missing")
        self.assertEqual(result["instances"][0]["role_bindings"]["trait"]["state"], "missing")

    def test_approved_nomination_still_fills_a_role(self):
        """Companion positive case -- the gate is a filter, not a universal blocker."""
        specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["trait"])
        req = se.new_requirement("t#req", "atomic", specs, completion, "exists")
        units = [_unit("p1", "Participants completed mindfulness training over eight weeks.")]
        client = _ScriptedValidator(nominations={"p1": "mindfulness training"})
        result = sm.map_requirement(req, units, model_client=client)
        self.assertEqual(result["state"], "filled")
        binding = result["instances"][0]["role_bindings"]["trait"]
        self.assertEqual(binding["exact_text"], "mindfulness training")
        self.assertEqual(binding["provenance"]["specificity_validated_instance_text"], "mindfulness training")
        self.assertEqual(binding["provenance"]["specificity_model"], "fake-qwen")

    def test_deterministic_only_mapping_is_unaffected(self):
        """model_client omitted entirely -- the specificity gate's code is never reached; proves
        the gate adds no behavior change whatsoever to the deterministic-only path."""
        specs = {"outcome": se.new_role_spec("outcome", "an outcome", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["outcome"])
        req = se.new_requirement("d#req", "atomic", specs, completion, "exists")
        units = [_unit("p1", "This finding showed a clear result.")]
        result = sm.map_requirement(req, units)  # no model_client at all
        self.assertEqual(result["state"], "filled")


class SpecificityGateParentPropagationTests(unittest.TestCase):
    """Mirrors test_sufficiency_diagnostic.ModelAssistedParentPropagationTests's own c8->c9-shaped
    fixture, now proving the specificity gate's effect on propagation specifically."""

    def _sealed(self, propositions):
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

    def _prop(self, pid, paper_id, quote, responsive):
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

    def _contracts(self):
        parent_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        parent_completion = se.new_role_completion(required_roles=["trait", "relation"])
        parent_req = se.new_requirement("p8#req", "atomic", parent_specs, parent_completion, "open_list", multi_instance=True)
        parent_contract = se.new_contract("p", [parent_req])

        child_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "named scale", "named_instrument_lexicon", disqualifying_guards=[]),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        child_req = se.new_requirement(
            "c9#req", "relational", child_specs, child_completion, "for_each_discovered_instance",
            multi_instance=True, parent_context_roles=["trait"],
        )
        child_contract = se.new_contract("c", [child_req])
        return {"p": parent_contract, "c": child_contract}

    def test_propagation_proceeds_when_the_nomination_survives_validation(self):
        sealed = self._sealed(
            [
                self._prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"]),
                self._prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        client = _ScriptedValidator(nominations={"p1": "empathy"})  # always-approve default
        mapped = sd.compute_diagnostic_sufficiency_map(sealed, self._contracts(), parent_of={"c": "p"}, model_client=client)
        parent_trait = mapped["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]
        self.assertEqual(parent_trait["state"], "filled")
        self.assertEqual(len(mapped["c"]["requirements"][0]["instances"]), 1)
        self.assertEqual(mapped["c"]["requirements"][0]["state"], "filled")

    def test_propagation_does_not_occur_when_the_nomination_is_vetoed(self):
        """Same evidence, same parent-pairing shape -- only the specificity decision differs."""
        sealed = self._sealed(
            [
                self._prop("p1", 1, "This finding showed empathy was strongly related to the outcome.", ["p"]),
                self._prop("p2", 2, "The Empathy Scale was used to assess trait empathy in participants.", ["c"]),
            ]
        )
        client = _ScriptedValidator(
            nominations={"p1": "empathy"}, decisions_by_text={"empathy": (False, "")}
        )
        mapped = sd.compute_diagnostic_sufficiency_map(sealed, self._contracts(), parent_of={"c": "p"}, model_client=client)
        parent_trait_state = mapped["p"]["requirements"][0]["instances"][0]["role_bindings"]["trait"]["state"]
        self.assertEqual(parent_trait_state, "missing")
        # no filled parent instance -- the paired child must gain nothing from it
        self.assertEqual(mapped["c"]["requirements"][0]["instances"], [])
        self.assertEqual(mapped["c"]["requirements"][0]["state"], "missing")


if __name__ == "__main__":
    unittest.main()
