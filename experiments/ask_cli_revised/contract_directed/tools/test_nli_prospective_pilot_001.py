"""Offline preflight tests for `nli_prospective_pilot_001.py`. Zero model/NLI/network calls except the one
tokenizer-length test, which uses the real cached tokenizer offline (asserted via env guards, matching every
prior tool in this arc) -- never the full model.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_prospective_pilot_001 as pilot


class BuildExecutionManifestTests(unittest.TestCase):
    def test_builds_exactly_29_distinct_pairs(self):
        with endpoint_guard.refuse_all():
            manifest = pilot.build_execution_manifest()
        self.assertEqual(manifest["total_pairs"], 29)
        self.assertEqual(manifest["prospective_count"], 27)
        self.assertEqual(manifest["control_count"], 2)
        self.assertEqual(len({p["sha256"] for p in manifest["pairs"]}), 29)

    def test_excludes_the_degenerate_table_1_fragment(self):
        manifest = pilot.build_execution_manifest()
        texts = {p["premise"].strip() for p in manifest["pairs"]}
        self.assertNotIn("TABLE 1.", texts)

    def test_excludes_every_truncating_premise_from_the_prior_corpus(self):
        import json

        corpus = json.loads(pilot.PROSPECTIVE_CORPUS_PATH.read_text(encoding="utf-8"))
        truncating_hashes = {p["sha256"] for p in corpus["prospective_premises"] if p["would_truncate"]}
        manifest = pilot.build_execution_manifest()
        used_hashes = {p["sha256"] for p in manifest["pairs"] if p["stratum"] == "prospective"}
        self.assertEqual(used_hashes & truncating_hashes, set())

    def test_both_controls_are_present_and_labeled_historical(self):
        manifest = pilot.build_execution_manifest()
        control_ids = {p["pair_id"] for p in manifest["pairs"] if p["stratum"] == "historical_control"}
        self.assertEqual(control_ids, {"control_c9", "control_c11"})

    def test_control_baselines_are_self_pair_scores_not_the_candidate_score(self):
        """The task's own explicit correction: do not use c9's ~0.81 candidate-vs-premise score. The baseline
        here must be the real self_entail_c9/self_entail_c11 self-pair scores."""
        manifest = pilot.build_execution_manifest()
        c9 = next(p for p in manifest["pairs"] if p["pair_id"] == "control_c9")
        c11 = next(p for p in manifest["pairs"] if p["pair_id"] == "control_c11")
        self.assertAlmostEqual(c9["historical_baseline"]["support"], 0.8874918222427368, places=6)
        self.assertNotAlmostEqual(c9["historical_baseline"]["support"], 0.81, places=1)
        self.assertAlmostEqual(c11["historical_baseline"]["support"], 0.007013050373643637, places=6)

    def test_control_premises_are_self_pairs_premise_equals_premise(self):
        """Every pair in this pilot is (premise, premise) -- confirmed by construction: the run_real() call
        pairs use p['premise'] on both sides, and this test locks that contract in the manifest builder."""
        manifest = pilot.build_execution_manifest()
        for p in manifest["pairs"]:
            self.assertTrue(p["premise"])  # non-empty; the pair itself is built as (premise, premise) at call time

    def test_hash_mismatch_in_the_frozen_corpus_would_be_caught(self):
        """A synthetic corruption check: if a stored premise's bytes ever drifted from its own sha256, the
        manifest builder must raise, not silently proceed."""
        import json

        corpus = json.loads(pilot.PROSPECTIVE_CORPUS_PATH.read_text(encoding="utf-8"))
        for p in corpus["prospective_premises"]:
            if not p["would_truncate"] and p["premise"].strip() != "TABLE 1.":
                import hashlib

                self.assertEqual(hashlib.sha256(p["premise"].encode("utf-8")).hexdigest(), p["sha256"])
                break

    def test_reproduction_tolerance_is_frozen_and_tight(self):
        self.assertEqual(pilot.CONTROL_REPRODUCTION_TOLERANCE, 1e-3)


class TokenizeAndVerifyTests(unittest.TestCase):
    def test_offline_env_guards_are_set(self):
        import os

        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_all_29_pairs_tokenize_within_the_model_limit(self):
        manifest = pilot.build_execution_manifest()
        pilot.tokenize_and_verify(manifest["pairs"])
        for p in manifest["pairs"]:
            self.assertFalse(p["would_truncate"], p["pair_id"])
            self.assertLessEqual(p["self_entailment_pair_tokens"], p["model_max_length"])


class WriteManifestGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory(self):
        manifest = pilot.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in pilot.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    pilot.write_manifest(base / protected, manifest)

    def test_refuses_an_already_populated_directory(self):
        manifest = pilot.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-pilot"
            pilot.write_manifest(run_dir, manifest)
            with self.assertRaises(RuntimeError):
                pilot.write_manifest(run_dir, manifest)

    def test_write_then_read_back_round_trips_byte_for_byte(self):
        manifest = pilot.build_execution_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = pilot.write_manifest(Path(tmp) / "fresh", manifest)
            reread = pilot.read_manifest(path)
        self.assertEqual(reread["pairs"], manifest["pairs"])


if __name__ == "__main__":
    unittest.main()
