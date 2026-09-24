"""Regression tests for original referent retention (no inference)."""
import unittest

from experiments.ask_cli_revised.calibration.run06.dataset06 import (
    BUILT_ENV_QUESTION,
    DEPRESSION_QUESTION,
    decomposition_cases_v06,
)
from experiments.ask_cli_revised.calibration.run06.segment import segment_source_units_v2
from experiments.ask_cli_revised.coverage import audit_coverage
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.request_contract import (
    audit_original_request,
    build_request_contract,
    obligation_display,
    request_subquestions,
)


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


class FrameCarryingTests(unittest.TestCase):
    """A bare list fragment ("amyloid", "coherence") loses its frame; carry the exact containing sentence."""

    def obligations(self, question):
        return [sq["obligations"][0] for sq in request_subquestions(build_request_contract(question))]

    def test_fragments_carry_their_exact_containing_sentence(self):
        sentence = (
            "I am interested in aesthetic appreciation, coherence, fascination, hominess, ceiling height, "
            "visuospatial processing and more."
        )
        self.assertIn(sentence, BUILT_ENV_QUESTION)
        fragments = [o for o in self.obligations(BUILT_ENV_QUESTION) if "source_sentence" in o]
        self.assertEqual(
            [o["note"] for o in fragments],
            [
                "I am interested in aesthetic appreciation",
                "coherence",
                "fascination",
                "hominess",
                "ceiling height",
                "visuospatial processing and more.",
            ],
        )
        for obligation in fragments:
            with self.subTest(fragment=obligation["note"]):
                self.assertEqual(obligation["source_sentence"], sentence)
                self.assertIn(obligation["note"], obligation["source_sentence"])
                self.assertEqual(obligation["list_size"], 6)
        self.assertEqual([o["list_position"] for o in fragments], [1, 2, 3, 4, 5, 6])

    def test_display_shows_the_unit_and_its_frame_and_the_literal_note_is_unchanged(self):
        obligation = {o["note"]: o for o in self.obligations(DEPRESSION_QUESTION)}["amyloid"]
        display = obligation_display(obligation)
        self.assertTrue(display.startswith("amyloid"))
        self.assertIn(obligation["source_sentence"], display)
        self.assertIn("I am particularly interested in serotonergic function, amyloid", display)
        self.assertEqual(obligation["note"], "amyloid")  # provenance/evaluation text stays literal

    def test_full_sentence_units_are_not_decorated(self):
        for question in (DEPRESSION_QUESTION, BUILT_ENV_QUESTION):
            obligations = self.obligations(question)
            for obligation in (obligations[0], obligations[-1]):  # the opening and closing full sentences
                with self.subTest(unit=obligation["note"][:40]):
                    self.assertNotIn("source_sentence", obligation)
                    self.assertEqual(obligation_display(obligation), obligation["note"])

    def test_aib_model_facing_lines_are_unchanged_by_the_repair(self):
        contract = build_request_contract(BENCHMARK_QUESTION)
        self.assertEqual(contract["question_hash"], "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030")
        self.assertEqual([u["text"] for u in contract["source_units"]],
                         [u["text"] for u in segment_source_units_v2(BENCHMARK_QUESTION)])
        for obligation in self.obligations(BENCHMARK_QUESTION):
            with self.subTest(unit=obligation["source_unit_id"]):
                self.assertNotIn("source_sentence", obligation)
                self.assertEqual(obligation_display(obligation), obligation["note"])

    def test_units_ids_and_offsets_are_unchanged_for_every_frozen_case(self):
        for case in decomposition_cases_v06():
            with self.subTest(case=case["case_id"]):
                contract = build_request_contract(case["text"])
                self.assertEqual([u["text"] for u in contract["source_units"]],
                                 [u["text"] for u in segment_source_units_v2(case["text"])])
                self.assertEqual([u["source_unit_id"] for u in contract["source_units"]],
                                 [f"u{i}" for i in range(1, len(contract["source_units"]) + 1)])

    def test_obligations_carry_no_evaluation_only_labels(self):
        allowed = {"field_id", "note", "source_unit_id", "coverage_basis", "source_sentence", "list_position",
                   "list_size", "display"}
        for question in (BENCHMARK_QUESTION, DEPRESSION_QUESTION, BUILT_ENV_QUESTION):
            for obligation in self.obligations(question):
                self.assertLessEqual(set(obligation), allowed)

    def test_coverage_rows_carry_the_model_facing_display(self):
        subquestions = request_subquestions(build_request_contract(DEPRESSION_QUESTION))
        rows = audit_coverage(subquestions, [])["obligations"]
        amyloid = next(row for row in rows if row["note"] == "amyloid")
        self.assertIn("I am particularly interested in serotonergic function, amyloid", amyloid["display"])
        full = next(row for row in rows if row["note"].startswith("Synthesize"))
        self.assertEqual(full["display"], full["note"])


if __name__ == "__main__":
    unittest.main()
