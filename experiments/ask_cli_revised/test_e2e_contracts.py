"""The common model-facing contract representation is frozen before comparative E2E and identical across arms."""

import json
import unittest

from experiments.ask_cli_revised import e2e_contracts as contracts


class FrozenContractTests(unittest.TestCase):
    def test_the_three_wave1_questions_are_frozen(self):
        frozen = json.loads(contracts.FROZEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(sorted(frozen["questions"]), ["aib", "builtenv", "lld"])

    def test_lld_is_the_late_life_depression_question(self):
        self.assertIn("late-life depression", contracts.E2E_QUESTIONS["lld"])

    def test_the_repaired_representation_matches_the_frozen_record_exactly(self):
        contracts.verify_frozen()  # raises on any drift in units, frames, display lines, or hashes

    def test_drift_in_a_model_facing_line_is_detected(self):
        frozen = json.loads(contracts.FROZEN_PATH.read_text(encoding="utf-8"))
        frozen["questions"]["lld"]["model_facing_sha256"] = "0" * 64
        with self.assertRaises(contracts.ContractDriftError):
            contracts.verify_frozen(frozen)

    def test_a_question_whose_text_changed_is_detected(self):
        frozen = json.loads(contracts.FROZEN_PATH.read_text(encoding="utf-8"))
        frozen["questions"]["aib"]["question_hash"] = "1" * 64
        with self.assertRaises(contracts.ContractDriftError):
            contracts.verify_frozen(frozen)

    def test_the_record_holds_no_evaluation_only_labels(self):
        text = contracts.FROZEN_PATH.read_text(encoding="utf-8").lower()
        for label in ("facet", "global head", "format directive", "catch-all", "catch_all", "unit_role"):
            self.assertNotIn(label, text)

    def test_aib_display_lines_equal_the_literal_units(self):
        record = contracts.frozen_record(contracts.E2E_QUESTIONS["aib"])
        self.assertTrue(all(row["display"] == row["note"] for row in record["obligations"]))


if __name__ == "__main__":
    unittest.main()
