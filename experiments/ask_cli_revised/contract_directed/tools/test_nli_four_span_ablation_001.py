"""Offline preflight tests for `nli_four_span_ablation_001.py`. Zero model/NLI/network calls except the one
tokenizer-length test (offline env guards asserted, matching every prior tool in this arc)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_four_span_ablation_001 as abl


class ResolveAndReproduceTests(unittest.TestCase):
    def test_resolves_all_four_target_spans_from_the_real_packet(self):
        with endpoint_guard.refuse_all():
            texts = abl.resolve_span_texts()
        self.assertEqual(len(texts), 4)
        for t in texts:
            self.assertTrue(t)

    def test_full_premise_reproduces_the_pilots_frozen_baseline_byte_for_byte(self):
        texts = abl.resolve_span_texts()
        joined = abl.assert_full_premise_reproduces_pilot_baseline(texts)
        baseline = abl.pilot_full_premise_baseline()
        self.assertEqual(joined, baseline["premise"])

    def test_pilot_full_premise_baseline_uses_the_exact_unrounded_score(self):
        """Must not be the rounded '0.0005' figure from prose."""
        baseline = abl.pilot_full_premise_baseline()
        self.assertEqual(baseline["support"], 0.0005305781378410757)
        self.assertEqual(baseline["contradiction"], 0.9970700740814209)

    def test_a_corrupted_span_text_would_fail_the_reproduction_assertion(self):
        texts = abl.resolve_span_texts()
        corrupted = list(texts)
        corrupted[0] = "a deliberately wrong sentence that does not match the source"
        with self.assertRaises(AssertionError):
            abl.assert_full_premise_reproduces_pilot_baseline(corrupted)


class CombinationCompletenessTests(unittest.TestCase):
    def test_exactly_fifteen_combinations_built(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        self.assertEqual(len(combos), 15)

    def test_four_six_four_one_split_by_span_count(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        from collections import Counter

        counts = Counter(c["span_count"] for c in combos)
        self.assertEqual(counts, {1: 4, 2: 6, 3: 4, 4: 1})

    def test_no_duplicate_combinations(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        self.assertEqual(len({c["sha256"] for c in combos}), 15)
        self.assertEqual(len({tuple(c["spans_included"]) for c in combos}), 15)

    def test_every_expected_subset_is_present(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        actual = {tuple(c["spans_included"]) for c in combos}
        expected = {
            (1,), (2,), (3,), (4,),
            (1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4),
            (1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4),
            (1, 2, 3, 4),
        }  # fmt: skip
        self.assertEqual(actual, expected)

    def test_span_order_is_always_preserved_never_rearranged(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        for c in combos:
            self.assertEqual(c["spans_included"], sorted(c["spans_included"]))

    def test_combination_text_is_the_exact_space_join_of_its_spans_in_order(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        two_three = next(c for c in combos if c["spans_included"] == [2, 3])
        self.assertEqual(two_three["premise"], texts[1] + " " + texts[2])

    def test_gap_after_span_3_flag_is_set_only_when_both_3_and_4_present(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        for c in combos:
            expected = 3 in c["spans_included"] and 4 in c["spans_included"]
            self.assertEqual(c["includes_gap_after_span3"], expected, c["pair_id"])

    def test_the_complete_four_span_combination_matches_the_full_premise(self):
        texts = abl.resolve_span_texts()
        combos = abl.build_combinations(texts)
        full = next(c for c in combos if c["span_count"] == 4)
        self.assertEqual(full["premise"], " ".join(texts))


class HistoricalProvenanceTests(unittest.TestCase):
    def test_control_baselines_come_from_the_real_saved_diagnostic_not_prose(self):
        hist = abl.historical_control_baselines()
        self.assertEqual(hist["c9"]["support"], 0.8874918222427368)
        self.assertEqual(hist["c11"]["support"], 0.007013050373643637)
        # explicitly NOT the ~0.81 candidate-vs-premise figure
        self.assertNotAlmostEqual(hist["c9"]["support"], 0.81, places=1)

    def test_control_premises_match_the_known_historical_stratum(self):
        premises = abl.control_premises()
        self.assertTrue(premises["c9"].startswith("Participants completed a Just World Beliefs Scale"))
        self.assertIn("Hadza", premises["c11"])


class BuildExecutionManifestTests(unittest.TestCase):
    def test_builds_exactly_seventeen_distinct_pairs(self):
        manifest = abl.build_execution_manifest()
        self.assertEqual(manifest["total_pairs"], 17)
        self.assertEqual(len({p["sha256"] for p in manifest["pairs"]}), 17)

    def test_fifteen_ablation_plus_two_controls(self):
        manifest = abl.build_execution_manifest()
        strata = [p["stratum"] for p in manifest["pairs"]]
        self.assertEqual(strata.count("ablation"), 15)
        self.assertEqual(strata.count("historical_control"), 2)

    def test_only_the_complete_four_span_ablation_pair_carries_the_pilot_baseline(self):
        manifest = abl.build_execution_manifest()
        with_baseline = [p for p in manifest["pairs"] if p["stratum"] == "ablation" and p["historical_baseline"]]
        self.assertEqual(len(with_baseline), 1)
        self.assertEqual(with_baseline[0]["span_count"], 4)

    def test_pair_to_locator_alignment_is_exact(self):
        manifest = abl.build_execution_manifest()
        manifest["target_locators"] = [tuple(x) for x in manifest["target_locators"]]
        self.assertEqual(manifest["target_locators"], abl.TARGET_LOCATORS)


class TokenizeAndVerifyTests(unittest.TestCase):
    def test_offline_env_guards_are_set(self):
        import os

        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_all_seventeen_pairs_tokenize_within_the_model_limit(self):
        manifest = abl.build_execution_manifest()
        abl.tokenize_and_verify(manifest["pairs"])
        for p in manifest["pairs"]:
            self.assertFalse(p["would_truncate"], p["pair_id"])
            self.assertLessEqual(p["self_entailment_pair_tokens"], p["model_max_length"])


class WriteManifestGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory(self):
        manifest = abl.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in abl.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    abl.write_manifest(base / protected, manifest)

    def test_refuses_an_already_populated_directory(self):
        manifest = abl.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-ablation"
            abl.write_manifest(run_dir, manifest)
            with self.assertRaises(RuntimeError):
                abl.write_manifest(run_dir, manifest)

    def test_write_then_read_back_round_trips_byte_for_byte(self):
        manifest = abl.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = abl.write_manifest(Path(tmp) / "fresh", manifest)
            reread = abl.read_manifest(path)
        self.assertEqual(reread["pairs"], manifest["pairs"])


if __name__ == "__main__":
    unittest.main()
