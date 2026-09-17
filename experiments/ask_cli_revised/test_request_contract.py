"""Regression tests for original referent retention (no inference)."""
import unittest

from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions, audit_original_request
from experiments.ask_cli_revised.calibration.run06.dataset06 import decomposition_cases_v06
from experiments.ask_cli_revised.coverage import audit_coverage


class RequestContractTests(unittest.TestCase):
    def test_frozen_cases_context_and_offsets(self):
        for case in decomposition_cases_v06():
            with self.subTest(case=case["case_id"]):
                raw = case["text"]
                contract = build_request_contract(raw)
                subquestions = request_subquestions(contract)
                self.assertEqual(contract["original_question"], raw)
                for unit, sq in zip(contract["source_units"], subquestions, strict=True):
                    self.assertEqual(raw[unit["start"]:unit["end"]], unit["text"])
                    self.assertIn(raw, sq["text"])
                    self.assertEqual(sq["obligations"][0]["note"], unit["text"])
                self.assertEqual(len(audit_original_request(contract, [], [])["source_units"]), len(subquestions))

    def test_repeated_spans_and_raw_whitespace(self):
        raw = "  Which? Which?  "
        contract = build_request_contract(raw)
        self.assertEqual(contract["original_question"], raw)
        self.assertEqual([u["start"] for u in contract["source_units"]], [2, 9])

    def test_verified_mapping_cannot_certify_compound_unit(self):
        contract = build_request_contract("Which areas and how do they relate to behavior?")
        sq = request_subquestions(contract)
        records = [{"obligation_ids": ["s1-o1"], "verification": {"status": "verified"}}]
        self.assertNotEqual(audit_coverage(sq, records)["obligations"][0]["state"], "answered")
        self.assertEqual(len(audit_coverage(sq, records)["gaps"]), 1)
        audit = audit_original_request(contract, sq, records)
        self.assertEqual(audit["unresolved_unit_ids"], ["u1"])
        self.assertEqual(audit["source_units"][0]["verified_mapped_records"], 1)


if __name__ == "__main__":
    unittest.main()
