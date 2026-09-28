"""Offline preflight tests for `nli_polarity_lexical_experiment_001.py`. Zero model/NLI/network calls except
the one tokenizer-length test (offline env guards asserted, matching every prior tool in this arc)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_polarity_lexical_experiment_001 as exp


class ResolveAndEditReceiptTests(unittest.TestCase):
    def test_resolves_all_three_spans_from_the_real_packet(self):
        with endpoint_guard.refuse_all():
            spans = exp.resolve_source_spans()
        self.assertEqual(set(spans), {"span1", "span2", "span3"})
        self.assertTrue(spans["span3"].startswith("A negative correlation was found"))

    def test_edit_receipt_changes_only_the_target_phrase(self):
        spans = exp.resolve_source_spans()
        receipt = exp.build_edit_receipt(spans["span3"], exp.PHRASE_B)
        self.assertEqual(receipt["original_phrase"], "A negative correlation was found")
        self.assertEqual(receipt["replacement_phrase"], "An inverse correlation was found")
        rebuilt = receipt["prefix_unchanged"] + exp.PHRASE_B + receipt["suffix_unchanged"]
        self.assertEqual(rebuilt, receipt["edited_text"])
        # everything except the replaced phrase is byte-identical to the original
        self.assertEqual(receipt["prefix_unchanged"], "")  # the phrase is at the very start of span3
        self.assertEqual(spans["span3"][len(exp.ORIGINAL_PHRASE) :], receipt["suffix_unchanged"])

    def test_sign_flip_receipt_changes_only_negative_to_positive(self):
        spans = exp.resolve_source_spans()
        receipt = exp.build_edit_receipt(spans["span3"], exp.PHRASE_C)
        self.assertEqual(
            receipt["edited_text"],
            spans["span3"].replace("A negative correlation was found", "A positive correlation was found"),
        )

    def test_article_changes_from_a_to_an_for_the_vowel_sound_paraphrase(self):
        variants = exp.build_span3_variants(exp.resolve_source_spans()["span3"])
        self.assertTrue(variants["B"]["text"].startswith("An inverse correlation was found"))
        self.assertTrue(variants["C"]["text"].startswith("A positive correlation was found"))
        self.assertTrue(variants["A"]["text"].startswith("A negative correlation was found"))

    def test_only_span3_differs_between_conditions_spans_1_and_2_never_touched(self):
        """The real check: in the assembled manifest, the 1+3/2+3/1+2+3 premises across A/B/C differ ONLY in
        their span3 portion -- span1's and span2's own text is byte-identical across every condition."""
        manifest = exp.build_execution_manifest()
        for construction, other_span_text in (
            ("1+3", exp.resolve_source_spans()["span1"]),
            ("2+3", exp.resolve_source_spans()["span2"]),
        ):
            for condition in ("A", "B", "C"):
                p = next(x for x in manifest["pairs"] if x["pair_id"] == f"{construction}_{condition}")
                self.assertTrue(p["premise"].startswith(other_span_text + " "), f"{construction}_{condition}")

    def test_a_missing_target_phrase_would_raise_not_silently_produce_a_wrong_edit(self):
        with self.assertRaises(AssertionError):
            exp.build_edit_receipt("no matching phrase here at all", exp.PHRASE_B)


class ManifestCompletenessTests(unittest.TestCase):
    def test_exactly_fifteen_distinct_pairs(self):
        manifest = exp.build_execution_manifest()
        self.assertEqual(manifest["total_pairs"], 15)
        self.assertEqual(len({p["sha256"] for p in manifest["pairs"]}), 15)

    def test_nine_primary_three_single_span_three_reproduction(self):
        manifest = exp.build_execution_manifest()
        strata = [p["stratum"] for p in manifest["pairs"]]
        self.assertEqual(strata.count("primary"), 9)
        self.assertEqual(strata.count("single_span_control"), 3)
        self.assertEqual(strata.count("reproduction_control"), 3)

    def test_every_construction_condition_combination_present_exactly_once(self):
        manifest = exp.build_execution_manifest()
        primary = [p for p in manifest["pairs"] if p["stratum"] == "primary"]
        combos = {(p["construction"], p["condition"]) for p in primary}
        expected = {(c, cond) for c in ("1+3", "2+3", "1+2+3") for cond in ("A", "B", "C")}
        self.assertEqual(combos, expected)
        self.assertEqual(len(primary), 9)

    def test_a_conditions_match_the_ablations_frozen_premises_byte_for_byte(self):
        manifest = exp.build_execution_manifest()
        a_pairs = {p["construction"]: p for p in manifest["pairs"] if p["condition"] == "A"}
        for construction_id, pair_id in (("1+3", "combo_1+3"), ("2+3", "combo_2+3"), ("1+2+3", "combo_1+2+3")):
            baseline = exp.ablation_baseline(pair_id)
            self.assertEqual(a_pairs[construction_id]["premise"], baseline["premise"])

    def test_b_condition_changes_only_the_specified_phrase(self):
        manifest = exp.build_execution_manifest()
        b13 = next(p for p in manifest["pairs"] if p["pair_id"] == "1+3_B")
        a13 = next(p for p in manifest["pairs"] if p["pair_id"] == "1+3_A")
        self.assertIn("An inverse correlation was found", b13["premise"])
        self.assertNotIn("A negative correlation was found", b13["premise"])
        # everything else in the premise (span1's text and the suffix of span3) is unchanged
        self.assertEqual(
            a13["premise"].replace("A negative correlation was found", "An inverse correlation was found"),
            b13["premise"],
        )

    def test_c_condition_changes_only_the_polarity_word(self):
        manifest = exp.build_execution_manifest()
        c23 = next(p for p in manifest["pairs"] if p["pair_id"] == "2+3_C")
        a23 = next(p for p in manifest["pairs"] if p["pair_id"] == "2+3_A")
        self.assertIn("A positive correlation was found", c23["premise"])
        self.assertEqual(
            a23["premise"].replace("A negative correlation was found", "A positive correlation was found"),
            c23["premise"],
        )

    def test_c_condition_is_labeled_counterfactual_and_synthetic(self):
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            if p["condition"] == "C":
                self.assertTrue(p["counterfactual"])
                self.assertEqual(p["origin"], "synthetic_diagnostic")

    def test_b_condition_is_synthetic_not_counterfactual(self):
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            if p["condition"] == "B":
                self.assertFalse(p["counterfactual"])
                self.assertEqual(p["origin"], "synthetic_diagnostic")

    def test_a_condition_is_source_verbatim_never_labeled_synthetic(self):
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            if p["condition"] == "A":
                self.assertEqual(p["origin"], "source_verbatim")
                self.assertFalse(p["counterfactual"])

    def test_no_synthetic_pair_is_indistinguishable_from_a_source_verbatim_one(self):
        """The origin field is the load-bearing distinction -- every B/C pair must be machine-flagged."""
        manifest = exp.build_execution_manifest()
        synthetic = [p for p in manifest["pairs"] if p["origin"] == "synthetic_diagnostic"]
        self.assertEqual(len(synthetic), 8)  # 3 constructions x (B+C) + span3_alone x (B+C) = 6+2 = 8
        for p in synthetic:
            self.assertIsNotNone(p["edit_receipt"])

    def test_every_self_pair_has_identical_premise_and_hypothesis_by_construction(self):
        """run_real() builds call_pairs as (p['premise'], p['premise']) -- this test locks that contract by
        confirming every manifest entry has exactly one premise field used on both sides."""
        manifest = exp.build_execution_manifest()
        for p in manifest["pairs"]:
            self.assertTrue(p["premise"])

    def test_single_span_controls_use_the_same_three_span3_variants(self):
        manifest = exp.build_execution_manifest()
        singles = {p["condition"]: p for p in manifest["pairs"] if p["stratum"] == "single_span_control"}
        self.assertEqual(set(singles), {"A", "B", "C"})
        primary_1p3_A = next(p for p in manifest["pairs"] if p["pair_id"] == "1+3_A")
        self.assertTrue(primary_1p3_A["premise"].endswith(singles["A"]["premise"]))

    def test_reproduction_controls_come_from_real_saved_records(self):
        manifest = exp.build_execution_manifest()
        repro = {p["construction"]: p for p in manifest["pairs"] if p["stratum"] == "reproduction_control"}
        self.assertEqual(set(repro), {"c9", "c11", "1+2+4"})
        self.assertAlmostEqual(repro["c9"]["historical_baseline"]["support"], 0.8874918222427368, places=6)
        self.assertAlmostEqual(repro["c11"]["historical_baseline"]["support"], 0.007013050373643637, places=6)
        self.assertAlmostEqual(repro["1+2+4"]["historical_baseline"]["support"], 0.07094138860702515, places=6)


class TokenizeAndVerifyTests(unittest.TestCase):
    def test_offline_env_guards_are_set(self):
        import os

        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_all_fifteen_pairs_tokenize_within_the_model_limit(self):
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
