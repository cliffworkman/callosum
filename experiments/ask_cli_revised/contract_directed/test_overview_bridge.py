"""Tests for the additive, thin contract-directed -> overview evidence-adjudication bridge (Gate 2, 2026-09-27)."""

import unittest

from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge

M10_SPAN = {
    "paper_id": 67, "chunk_id": 35019, "span_id": "p1",
    "text": "Participants completed a Just World Beliefs Scale that measures beliefs about fairness.",
    "attribution_state": "own_established",
    "slots_accepted_for": ["instrument_named", "paired_with_construct", "on_topic"],
}  # fmt: skip
M12_SPAN = {
    "paper_id": 68, "chunk_id": 43327, "span_id": "p2",
    "text": "We presented Hadza participants pairs of morphed faces and asked who they expected to be more moral.",
    "attribution_state": "own_established",
    "slots_accepted_for": ["population_named", "manner_described", "on_topic", "pairing_expressed"],
}  # fmt: skip

SOURCE_SUPPORTED_ROW = {
    "child_id": "c9", "unit_id": "M10", "kind": "operation",
    "status": "source_supported", "accepted_spans": [M10_SPAN],
}  # fmt: skip
UNRESOLVED_ROW = {
    "child_id": "c9", "unit_id": "W21", "kind": "requested_item",
    "status": "unresolved_obligation", "accepted_spans": [],
    "constraint_text": (
        "The admitted evidence names the scales but does not establish that they are tied to the specific "
        "personality traits related to the bias's manifestation. This describes a limit of the admitted "
        "evidence, not a finding that no such tie exists."
    ),
}  # fmt: skip


class ProjectEvidenceTests(unittest.TestCase):
    def test_only_source_supported_rows_contribute_evidence(self):
        spans, props = bridge.project_evidence([SOURCE_SUPPORTED_ROW, UNRESOLVED_ROW])
        self.assertEqual(len(spans), 1)
        self.assertEqual(len(props), 1)
        self.assertEqual(spans[0]["text"], M10_SPAN["text"])

    def test_projected_text_is_verbatim_never_a_paraphrase(self):
        _, props = bridge.project_evidence([SOURCE_SUPPORTED_ROW])
        self.assertEqual(props[0]["proposition_text"], M10_SPAN["text"])
        self.assertEqual(props[0]["quote"], M10_SPAN["text"])
        self.assertEqual(props[0]["proposition_text"], props[0]["quote"])

    def test_verification_never_claims_nli_entailment_was_checked(self):
        _, props = bridge.project_evidence([SOURCE_SUPPORTED_ROW])
        v = props[0]["verification"]
        self.assertNotIn("status", v)  # never the original schema's "verified" string
        self.assertFalse(v["nli_entailment_checked"])
        self.assertTrue(v["exact_verbatim_match"])
        self.assertEqual(v["clause_attribution_state"], "own_established")
        self.assertEqual(set(v["slot_accepted_for"]), {"instrument_named", "paired_with_construct", "on_topic"})

    def test_responsive_obligation_ids_carry_the_owning_child_only(self):
        _, props = bridge.project_evidence([SOURCE_SUPPORTED_ROW])
        self.assertEqual(props[0]["responsive_obligation_ids"], ["c9"])

    def test_an_unresolved_rows_spans_never_reach_evidence_even_if_present(self):
        row = {**UNRESOLVED_ROW, "accepted_spans": [M10_SPAN]}  # a hypothetical mistake: spans on a non-supported row
        spans, props = bridge.project_evidence([row])
        self.assertEqual(spans, [])
        self.assertEqual(props, [])

    def test_a_shared_span_across_two_rows_is_deduplicated_in_evidence_spans(self):
        row_a = {
            "child_id": "c11",
            "unit_id": "M12",
            "kind": "population",
            "status": "source_supported",
            "accepted_spans": [M12_SPAN],
        }
        row_b = {
            "child_id": "c11",
            "unit_id": "M13",
            "kind": "manner",
            "status": "source_supported",
            "accepted_spans": [M12_SPAN],
        }
        spans, props = bridge.project_evidence([row_a, row_b])
        self.assertEqual(len(spans), 1)  # one catalog entry
        self.assertEqual(len(props), 2)  # two propositions, one per owning unit
        self.assertEqual({p["responsive_obligation_ids"][0] for p in props}, {"c11"})


class CoverageConstraintsFromManifestTests(unittest.TestCase):
    def test_only_non_claimable_rows_with_constraint_text_contribute(self):
        rows = [SOURCE_SUPPORTED_ROW, UNRESOLVED_ROW, {**UNRESOLVED_ROW, "unit_id": "X", "constraint_text": None}]
        constraints = bridge.coverage_constraints(rows)
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0], UNRESOLVED_ROW["constraint_text"])

    def test_a_valid_constraint_passes_validation_before_being_returned(self):
        constraints = bridge.coverage_constraints([UNRESOLVED_ROW])
        self.assertEqual(constraints, (UNRESOLVED_ROW["constraint_text"],))


class ValidateConstraintTextTests(unittest.TestCase):
    def test_a_clean_bound_statement_is_accepted(self):
        bridge.validate_constraint_text(
            "The admitted evidence does not establish this tie; it does not follow that no such tie exists."
        )  # raises nothing

    def test_a_provenance_token_is_rejected(self):
        with self.assertRaises(bridge.ConstraintTextInvalid):
            bridge.validate_constraint_text("W21 is not established by the admitted evidence.")
        with self.assertRaises(bridge.ConstraintTextInvalid):
            bridge.validate_constraint_text("This bears on c9's own request part.")

    def test_a_found_absent_style_finding_claim_is_rejected(self):
        with self.assertRaises(bridge.ConstraintTextInvalid):
            bridge.validate_constraint_text("This was measured and found to be absent in the admitted evidence.")
        with self.assertRaises(bridge.ConstraintTextInvalid):
            bridge.validate_constraint_text("No relationship exists between the scales and the trait.")

    def test_coverage_constraints_raises_rather_than_silently_dropping_an_invalid_row(self):
        bad_row = {**UNRESOLVED_ROW, "constraint_text": "W21 is unresolved."}
        with self.assertRaises(bridge.ConstraintTextInvalid):
            bridge.coverage_constraints([bad_row])


class RealFrozenDataTests(unittest.TestCase):
    """These read the real, external prior-run artifact this whole bridge is meant to reuse verbatim. Skipped
    when that artifact is not present on this machine (the same convention `realenv.available()` uses)."""

    @unittest.skipUnless(bridge.available(), "the real prior T5O run's sealed ledger is not present on this machine")
    def test_real_obligation_states_returns_the_exact_frozen_notes(self):
        states = bridge.real_obligation_states(("c9", "c11"))
        by_id = {s["field_id"]: s["note"] for s in states}
        self.assertIn("which scales measure", by_id["c9"])
        self.assertIn("in which cultures is there evidence", by_id["c11"])

    @unittest.skipUnless(bridge.available(), "the real prior T5O run's sealed ledger is not present on this machine")
    def test_an_unknown_field_id_raises_rather_than_silently_omitting(self):
        with self.assertRaises(KeyError):
            bridge.real_obligation_states(("c9", "not-a-real-field-id"))

    @unittest.skipUnless(bridge.available(), "the real prior T5O run's sealed ledger is not present on this machine")
    def test_real_original_question_matches_the_frozen_substrate_hash(self):
        from experiments.ask_cli_revised.contract_directed import freeze

        question, question_hash = bridge.real_original_question()
        self.assertEqual(question_hash, freeze.QUESTION_SHA256)
        self.assertTrue(question.strip())


if __name__ == "__main__":
    unittest.main()
