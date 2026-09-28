"""Offline preflight tests for `nli_clause_count_experiment_001.py`. Zero model/NLI/network calls except the
one tokenizer-length test (offline env guards asserted, matching every prior tool in this arc)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_clause_count_experiment_001 as exp


class ResolveAndEditReceiptTests(unittest.TestCase):
    def test_resolves_all_three_spans_from_the_real_packet(self):
        with endpoint_guard.refuse_all():
            spans = exp.resolve_source_spans()
        self.assertEqual(set(spans), {"span1", "span2", "span3"})
        self.assertTrue(spans["span1"].startswith("A positive correlation was found"))
        self.assertIn("a positive correlation between", spans["span2"])

    def test_f1_receipt_changes_only_the_specified_phrase(self):
        spans = exp.resolve_source_spans()
        receipt = exp.build_edit_receipt(spans["span1"], exp.F1_ORIGINAL, exp.F1_REPLACEMENT)
        self.assertEqual(receipt["original_phrase"], "A positive correlation was found")
        self.assertEqual(receipt["replacement_phrase"], "An inverse correlation was found")
        self.assertEqual(receipt["prefix_unchanged"], "")  # F1 phrase is at the very start of span1
        self.assertEqual(spans["span1"][len(exp.F1_ORIGINAL) :], receipt["suffix_unchanged"])

    def test_f2_receipt_changes_only_the_specified_phrase(self):
        spans = exp.resolve_source_spans()
        receipt = exp.build_edit_receipt(spans["span2"], exp.F2_ORIGINAL, exp.F2_REPLACEMENT)
        self.assertEqual(receipt["original_phrase"], "a positive correlation between")
        self.assertEqual(receipt["replacement_phrase"], "an inverse correlation between")
        rebuilt = receipt["prefix_unchanged"] + exp.F2_REPLACEMENT + receipt["suffix_unchanged"]
        self.assertEqual(rebuilt, receipt["edited_text"])

    def test_article_changes_are_explicit_in_both_replacements(self):
        self.assertTrue(exp.F1_REPLACEMENT.startswith("An "))
        self.assertTrue(exp.F1_ORIGINAL.startswith("A "))
        self.assertTrue(exp.F2_REPLACEMENT.startswith("an "))
        self.assertTrue(exp.F2_ORIGINAL.startswith("a "))

    def test_a_missing_target_phrase_would_raise(self):
        with self.assertRaises(AssertionError):
            exp.build_edit_receipt("no matching phrase at all", exp.F1_ORIGINAL, exp.F1_REPLACEMENT)


class ManifestCompletenessTests(unittest.TestCase):
    def test_exactly_thirteen_distinct_pairs(self):
        manifest = exp.build_execution_manifest()
        self.assertEqual(manifest["total_pairs"], 13)
        self.assertEqual(len({p["sha256"] for p in manifest["pairs"]}), 13)

    def test_every_required_pair_id_present_exactly_once_no_extras(self):
        manifest = exp.build_execution_manifest()
        ids = [p["pair_id"] for p in manifest["pairs"]]
        expected = {
            "1+2+3_A", "1(F1)+2+3", "1+2(F2)+3", "1(F1)+2(F2)+3",
            "1(F1)+3", "2(F2)+3",
            "1+3", "2+3",
            "1(F1)", "2(F2)",
            "reproduction_c9", "reproduction_c11", "reproduction_1+2+4",
        }  # fmt: skip
        self.assertEqual(set(ids), expected)
        self.assertEqual(len(ids), len(set(ids)), "no pair_id may repeat")

    def test_six_reproduction_cases_match_frozen_historical_text_byte_for_byte(self):
        manifest = exp.build_execution_manifest()
        by_id = {p["pair_id"]: p for p in manifest["pairs"]}
        self.assertEqual(by_id["1+2+3_A"]["premise"], exp.ablation_baseline("combo_1+2+3")["premise"])
        self.assertEqual(by_id["1+3"]["premise"], exp.ablation_baseline("combo_1+3")["premise"])
        self.assertEqual(by_id["2+3"]["premise"], exp.ablation_baseline("combo_2+3")["premise"])
        self.assertEqual(by_id["reproduction_1+2+4"]["premise"], exp.ablation_baseline("combo_1+2+4")["premise"])
        ctrl = exp.control_premises()
        self.assertEqual(by_id["reproduction_c9"]["premise"], ctrl["c9"])
        self.assertEqual(by_id["reproduction_c11"]["premise"], ctrl["c11"])

    def test_span3_is_byte_identical_to_source_in_every_primary_condition(self):
        manifest = exp.build_execution_manifest()
        span3 = exp.resolve_source_spans()["span3"]
        by_id = {p["pair_id"]: p for p in manifest["pairs"]}
        for pid in ("1+2+3_A", "1(F1)+2+3", "1+2(F2)+3", "1(F1)+2(F2)+3", "1(F1)+3", "2(F2)+3", "1+3", "2+3"):
            self.assertTrue(by_id[pid]["premise"].endswith(span3), pid)

    def test_single_flip_triples_have_exactly_one_edited_span(self):
        manifest = exp.build_execution_manifest()
        by_id = {p["pair_id"]: p for p in manifest["pairs"]}
        self.assertEqual(by_id["1(F1)+2+3"]["edited_spans"], ["span1"])
        self.assertEqual(by_id["1+2(F2)+3"]["edited_spans"], ["span2"])

    def test_both_flipped_triple_has_exactly_two_edited_spans(self):
        manifest = exp.build_execution_manifest()
        by_id = {p["pair_id"]: p for p in manifest["pairs"]}
        self.assertEqual(set(by_id["1(F1)+2(F2)+3"]["edited_spans"]), {"span1", "span2"})

    def test_every_edited_pair_is_flagged_synthetic_and_counterfactual(self):
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            if p["edited_spans"]:
                self.assertEqual(p["origin"], "synthetic_diagnostic", p["pair_id"])
                self.assertTrue(p["counterfactual"], p["pair_id"])
                self.assertIsNotNone(p["edit_receipt"], p["pair_id"])

    def test_every_unedited_pair_is_source_verbatim_never_flagged_synthetic(self):
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            if not p["edited_spans"]:
                self.assertEqual(p["origin"], "source_verbatim", p["pair_id"])
                self.assertFalse(p["counterfactual"], p["pair_id"])
                self.assertIsNone(p["edit_receipt"], p["pair_id"])

    def test_every_self_pair_has_a_nonempty_premise(self):
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            self.assertTrue(p["premise"])

    def test_external_comparison_1_2_3_c_is_present_and_not_counted_among_the_13(self):
        manifest = exp.build_execution_manifest()
        self.assertIn("external_comparison_1_2_3_C", manifest)
        self.assertNotIn("1+2+3_C", {p["pair_id"] for p in manifest["pairs"]})
        self.assertAlmostEqual(manifest["external_comparison_1_2_3_C"]["support"], 0.6868696808815002, places=6)

    def test_no_negative_wording_variant_is_introduced(self):
        """The authorization explicitly excludes introducing a 'negative' wording variant in this pass --
        both replacements use "inverse", never a fresh "negative" phrasing."""
        self.assertNotIn("negative", exp.F1_REPLACEMENT.lower())
        self.assertNotIn("negative", exp.F2_REPLACEMENT.lower())

    def test_unedited_pairs_never_contain_the_word_inverse(self):
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            if not p["edited_spans"]:
                self.assertNotIn("inverse", p["premise"].lower(), p["pair_id"])


class TokenizeAndVerifyTests(unittest.TestCase):
    def test_offline_env_guards_are_set(self):
        import os

        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_all_thirteen_pairs_tokenize_within_the_model_limit(self):
        manifest = exp.build_execution_manifest()
        exp.tokenize_and_verify(manifest["pairs"])
        for p in manifest["pairs"]:
            self.assertFalse(p["would_truncate"], p["pair_id"])
            self.assertLessEqual(p["self_entailment_pair_tokens"], p["model_max_length"])


class WriteManifestGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory(self):
        manifest = exp.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in exp.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    exp.write_manifest(base / protected, manifest)

    def test_refuses_an_already_populated_directory(self):
        manifest = exp.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-experiment"
            exp.write_manifest(run_dir, manifest)
            with self.assertRaises(RuntimeError):
                exp.write_manifest(run_dir, manifest)

    def test_write_then_read_back_round_trips_byte_for_byte(self):
        manifest = exp.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = exp.write_manifest(Path(tmp) / "fresh", manifest)
            reread = exp.read_manifest(path)
        self.assertEqual(reread["pairs"], manifest["pairs"])


if __name__ == "__main__":
    unittest.main()
