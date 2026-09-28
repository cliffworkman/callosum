"""Tests for the offline c9+c11 partial-answer renderer (2026-09-27). No model, NLI, or embedding call anywhere
in this file -- every fixture below is a hand-built manifest row / saved-record shape."""

import unittest

from experiments.ask_cli_revised.contract_directed import evidence_identity as ident
from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as par
from experiments.ask_cli_revised.ledger_renderer import _literal

M10_SPAN = {
    "paper_id": 67, "chunk_id": 35019, "span_id": "p1",
    "text": "Participants completed a Just World Beliefs Scale that measures fairness beliefs.",
    "attribution_state": "own_established", "slots_accepted_for": ["instrument_named"],
}  # fmt: skip
P2_SPAN = {
    "paper_id": 68, "chunk_id": 43327, "span_id": "p2",
    "text": "We presented 123 Hadza across ten camps and asked who they expected to be more moral and a better forager.",
    "attribution_state": "own_established", "slots_accepted_for": ["population_named", "manner_described"],
}  # fmt: skip
P4_SPAN = {
    "paper_id": 68, "chunk_id": 43327, "span_id": "p4",
    "text": "Hadza with greater exposure to other cultures expected the scarred face to be less moral and a better forager.",
    "attribution_state": "own_established", "slots_accepted_for": ["tied_to_finding"],
}  # fmt: skip

M10_ROW = {"child_id": "c9", "unit_id": "M10", "kind": "operation", "status": "source_supported",
           "accepted_spans": [M10_SPAN]}  # fmt: skip
W21_CONSTRAINT = "The admitted evidence does not establish this tie -- a coverage limit, not a finding either way."
W21_ROW = {"child_id": "c9", "unit_id": "W21", "kind": "requested_item", "status": "unresolved_obligation",
           "accepted_spans": [], "constraint_text": W21_CONSTRAINT}  # fmt: skip
M12_ROW = {"child_id": "c11", "unit_id": "M12", "kind": "population", "status": "source_supported",
           "accepted_spans": [P2_SPAN, P4_SPAN]}  # fmt: skip
M13_ROW = {"child_id": "c11", "unit_id": "M13", "kind": "manner", "status": "source_supported",
           "accepted_spans": [P2_SPAN]}  # fmt: skip
ALL_ROWS = [M10_ROW, W21_ROW, M12_ROW, M13_ROW]


def unit(unit_id, paper_id, chunk_id, span_id, passage):
    return {
        "unit_id": unit_id,
        "paper_id": paper_id,
        "locators": [{"chunk_id": chunk_id, "span_id": span_id}],
        "passage": passage,
    }


def saved_record(proposals, units):
    return {"proposals": proposals, "units": units}


GATE2_RECORD = saved_record(
    proposals=[
        {"index": 0, "status": "grounded", "unit_ids": ["U1"], "bears_on": ["c9"], "reasons": [],
         "text": "Participants completed a Just World Beliefs Scale."},
        {"index": 1, "status": "withheld", "unit_ids": ["U2", "U3"], "bears_on": ["c11"],
         "reasons": ["nli_low_support:0.27"],
         "text": "In a study with 123 Hadza, those with greater exposure expected the scarred face to be less moral."},
    ],
    units=[
        unit("U1", 67, 35019, "p1", M10_SPAN["text"]),
        unit("U2", 68, 43327, "p2", P2_SPAN["text"]),
        unit("U3", 68, 43327, "p4", P4_SPAN["text"]),
    ],
)  # fmt: skip


class MatchUnitsByLocatorTests(unittest.TestCase):
    def test_matches_each_row_to_its_real_overview_unit(self):
        matches = par.match_units_by_locator(ALL_ROWS, GATE2_RECORD["units"])
        self.assertEqual(matches[("c9", "M10")], ["U1"])
        self.assertEqual(matches[("c11", "M12")], ["U2", "U3"])
        self.assertEqual(matches[("c11", "M13")], ["U2"])

    def test_an_unresolved_row_with_no_spans_matches_nothing(self):
        matches = par.match_units_by_locator(ALL_ROWS, GATE2_RECORD["units"])
        self.assertEqual(matches[("c9", "W21")], [])

    def test_matching_is_by_locator_first_then_cross_checked_against_saved_text(self):
        """A locator match is not trusted alone: if the saved unit's own passage text differs from the
        manifest span's text, that is exactly the kind of packet-local-key collision `evidence_identity.py`
        exists to catch -- it must raise, not silently proceed with a mismatched pair."""
        units = [unit("U1", 67, 35019, "p1", "a completely different sentence than M10's own span")]
        with self.assertRaises(ident.SavedRecordTextMismatch):
            par.match_units_by_locator([M10_ROW], units)

    def test_a_saved_unit_missing_its_own_passage_field_is_refused_not_silently_trusted(self):
        units = [{"unit_id": "U1", "paper_id": 67, "locators": [{"chunk_id": 35019, "span_id": "p1"}]}]
        with self.assertRaises(ident.SavedRecordTextMismatch):
            par.match_units_by_locator([M10_ROW], units)

    def test_a_matching_locator_with_matching_text_succeeds(self):
        units = [unit("U1", 67, 35019, "p1", M10_SPAN["text"])]
        matches = par.match_units_by_locator([M10_ROW], units)
        self.assertEqual(matches[("c9", "M10")], ["U1"])


class ClassifyRowTests(unittest.TestCase):
    def test_a_grounded_match_classifies_as_displayed(self):
        c = par.classify_row(M10_ROW, ["U1"], GATE2_RECORD["proposals"])
        self.assertEqual(c["outcome"], par.DISPLAYED)
        self.assertEqual(c["displayed_statement"]["unit_ids"], ["U1"])
        self.assertEqual(c["withheld_candidates"], [])

    def test_a_withheld_only_match_classifies_as_withheld_not_displayed(self):
        c = par.classify_row(M12_ROW, ["U2", "U3"], GATE2_RECORD["proposals"])
        self.assertEqual(c["outcome"], par.WITHHELD)
        self.assertIsNone(c["displayed_statement"])
        self.assertEqual(len(c["withheld_candidates"]), 1)
        self.assertEqual(c["withheld_candidates"][0]["reasons"], ["nli_low_support:0.27"])

    def test_an_unresolved_status_row_classifies_as_unresolved_regardless_of_matches(self):
        c = par.classify_row(W21_ROW, [], GATE2_RECORD["proposals"])
        self.assertEqual(c["outcome"], par.UNRESOLVED)
        self.assertEqual(c["constraint_text"], W21_CONSTRAINT)

    def test_a_source_supported_row_with_no_overview_candidate_at_all_is_still_withheld_not_displayed(self):
        """No candidate ever touched this unit -- must not default to "displayed" just because the row itself
        is source_supported."""
        c = par.classify_row(M10_ROW, ["U99"], [])
        self.assertEqual(c["outcome"], par.WITHHELD)
        self.assertEqual(c["withheld_candidates"], [])

    def test_an_unrecognized_proposal_status_raises_explicitly_rather_than_being_silently_dropped(self):
        """NLI_REPAIR_DESIGN.md Section 3.5: a proposal status this renderer doesn't recognize (e.g. a future
        "indeterminate") must never silently vanish from withheld_candidates -- it must be impossible to emit
        a partial answer without the renderer being explicitly taught about the new status first."""
        unknown_proposal = {
            "index": 0, "text": "some candidate text", "unit_ids": ["U1"],
            "status": "indeterminate", "reasons": ["nli_unreliable_premise:self_support=0.01"],
        }  # fmt: skip
        with self.assertRaises(par.UnknownProposalStatus):
            par.classify_row(M10_ROW, ["U1"], [unknown_proposal])

    def test_the_unknown_status_error_names_the_row_and_the_bad_status(self):
        unknown_proposal = {"index": 0, "text": "t", "unit_ids": ["U1"], "status": "mystery", "reasons": []}
        with self.assertRaisesRegex(par.UnknownProposalStatus, r"c9/M10.*mystery"):
            par.classify_row(M10_ROW, ["U1"], [unknown_proposal])

    def test_a_non_touching_unknown_status_proposal_does_not_raise(self):
        """The check only applies to proposals that actually TOUCH this row's matched units -- an unrelated
        proposal elsewhere in the same run must not block rendering rows it has nothing to do with."""
        unknown_elsewhere = {"index": 0, "text": "t", "unit_ids": ["U777"], "status": "mystery", "reasons": []}
        c = par.classify_row(M10_ROW, ["U1"], [unknown_elsewhere])  # matched_units=["U1"], proposal cites U777
        self.assertEqual(c["outcome"], par.WITHHELD)


class RenderPartialSliceTests(unittest.TestCase):
    def setUp(self):
        self.markdown, self.manifest = par.render_partial_slice(ALL_ROWS, GATE2_RECORD)

    # ---- the five explicit regression requirements ----

    def test_w21_is_never_rendered_as_closed_or_resolved(self):
        w21 = next(c for c in self.manifest["classifications"] if c["unit_id"] == "W21")
        self.assertEqual(w21["outcome"], par.UNRESOLVED)
        self.assertIsNone(w21["displayed_statement"])
        self.assertIn("UNRESOLVED", self.markdown)
        self.assertIn(_literal(W21_CONSTRAINT), self.markdown)
        # never anywhere claims the tie IS established
        self.assertNotIn("is tied to", self.markdown)
        self.assertNotIn("establishes the tie", self.markdown)

    def test_c11_evidence_is_never_reported_as_no_evidence_found(self):
        for unit_id in ("M12", "M13"):
            c = next(cl for cl in self.manifest["classifications"] if cl["unit_id"] == unit_id)
            self.assertTrue(c["evidence_spans"])  # the underlying evidence is present, not dropped
            self.assertNotEqual(c["outcome"], par.UNRESOLVED)
        self.assertNotIn("no evidence found", self.markdown.lower())
        self.assertNotIn("no evidence", self.markdown.lower())
        self.assertIn("123 Hadza", self.markdown)  # the actual evidence text is rendered

    def test_the_withheld_candidate_is_never_presented_as_displayed_screened_output(self):
        m12 = next(c for c in self.manifest["classifications"] if c["unit_id"] == "M12")
        self.assertEqual(m12["outcome"], par.WITHHELD)
        self.assertIsNone(m12["displayed_statement"])
        # the withheld candidate's own text appears, but only under an explicit WITHHELD label
        withheld_text = _literal(m12["withheld_candidates"][0]["text"])
        self.assertIn(withheld_text, self.markdown)
        idx = self.markdown.index(withheld_text)
        preceding = self.markdown[:idx]
        self.assertIn("WITHHELD", preceding[-400:])
        self.assertNotIn("Displayed overview statement", preceding[-400:])

    def test_the_foraging_result_is_preserved_in_the_evidence_record(self):
        """The saved overview candidate omits "a better forager"; the underlying evidence record must not."""
        m12 = next(c for c in self.manifest["classifications"] if c["unit_id"] == "M12")
        full_text = " ".join(s["text"] for s in m12["evidence_spans"])
        self.assertIn("a better forager", full_text)
        self.assertIn("a better forager", self.markdown)

    def test_no_contract_directed_span_is_ever_relabeled_as_nli_verified(self):
        for c in self.manifest["classifications"]:
            for span in c["evidence_spans"]:
                self.assertNotIn("status", span)  # never the original schema's "verified" string field
        self.assertIn("nli_entailment_checked=False", self.markdown)
        self.assertNotIn('"verified"', self.markdown)
        self.assertNotIn("NLI-verified evidence", self.markdown)

    # ---- general shape/coverage checks ----

    def test_renders_exactly_the_two_covered_children_and_names_the_exclusion(self):
        self.assertEqual(self.manifest["children_covered"], ["c9", "c11"])
        self.assertIn("c6", self.manifest["excluded_children"])
        self.assertIn("c5", self.manifest["excluded_children"])
        self.assertIn("c10", self.manifest["excluded_children"])
        self.assertIn("does not answer the original parent question", self.markdown)

    def test_completeness_is_never_certified(self):
        self.assertEqual(self.manifest["completeness"], "not_certified")
        self.assertEqual(self.manifest["scientific_aggregates"], 0)

    def test_m10_is_displayed_and_its_statement_is_shown(self):
        m10 = next(c for c in self.manifest["classifications"] if c["unit_id"] == "M10")
        self.assertEqual(m10["outcome"], par.DISPLAYED)
        self.assertIn("Just World Beliefs Scale", self.markdown)

    def test_every_manifest_row_produces_exactly_one_classification(self):
        self.assertEqual(len(self.manifest["classifications"]), len(ALL_ROWS))


class LedgerRendererIncompatibilityTests(unittest.TestCase):
    """Documents, by direct execution (not by inspection alone), exactly why this module exists rather than
    calling into `ledger_renderer.py`."""

    def test_ledger_renderer_rejects_contract_directeds_honest_verification_shape(self):
        from experiments.ask_cli_revised import ledger_renderer as lr
        from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge

        evidence_spans, verified_propositions = bridge.project_evidence([M10_ROW])
        sealed = {
            "request_contract": {"original_question": "q"},
            "obligation_states": [{"field_id": "c9", "note": "n", "state": "s"}],
            "evidence_spans": evidence_spans,
            "verified_propositions": verified_propositions,
        }
        with self.assertRaisesRegex(ValueError, "ineligible evidence"):
            lr.render_answer(sealed)


if __name__ == "__main__":
    unittest.main()
