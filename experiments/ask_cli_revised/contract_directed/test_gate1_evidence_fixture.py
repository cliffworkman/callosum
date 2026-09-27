"""Tests for the reusable c9+c11 manifest fixture (2026-09-27)."""

import unittest

from experiments.ask_cli_revised.contract_directed import gate1_evidence_fixture as fixture
from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge


@unittest.skipUnless(fixture.available(), "the frozen c9/c11 packet files are not present on this machine")
class BuildC9C11ManifestTests(unittest.TestCase):
    def setUp(self):
        self.rows = fixture.build_c9_c11_manifest()

    def test_exactly_four_rows_in_the_expected_shape(self):
        self.assertEqual(len(self.rows), 4)
        keys = {(r["child_id"], r["unit_id"]) for r in self.rows}
        self.assertEqual(keys, {("c9", "M10"), ("c9", "W21"), ("c11", "M12"), ("c11", "M13")})

    def test_three_source_supported_rows_one_unresolved(self):
        statuses = [r["status"] for r in self.rows]
        self.assertEqual(statuses.count("source_supported"), 3)
        self.assertEqual(statuses.count("unresolved_obligation"), 1)

    def test_w21_constraint_text_is_present_and_valid(self):
        w21 = next(r for r in self.rows if r["unit_id"] == "W21")
        self.assertTrue(w21["constraint_text"])
        bridge.validate_constraint_text(w21["constraint_text"])  # raises nothing

    def test_m10_text_contains_the_real_instrument_sentence(self):
        m10 = next(r for r in self.rows if r["unit_id"] == "M10")
        self.assertIn("Just World Beliefs Scale", m10["accepted_spans"][0]["text"])

    def test_m12_carries_both_the_shared_span_and_its_own_tied_to_finding_span(self):
        m12 = next(r for r in self.rows if r["unit_id"] == "M12")
        texts = [s["text"] for s in m12["accepted_spans"]]
        self.assertTrue(any("We presented 123 Hadza" in t for t in texts))
        self.assertTrue(any("a better forager" in t for t in texts))

    def test_evidence_projects_cleanly_through_the_bridge(self):
        evidence_spans, verified_propositions = bridge.project_evidence(self.rows)
        self.assertEqual(len(evidence_spans), 3)  # deduped: M10's span, the shared p2 span, p4's span
        self.assertEqual(len(verified_propositions), 4)  # one per (row, span) pair


if __name__ == "__main__":
    unittest.main()
