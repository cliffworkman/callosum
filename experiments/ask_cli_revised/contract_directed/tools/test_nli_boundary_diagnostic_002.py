"""Offline test of `nli_boundary_diagnostic_002.build_pairs()` and its directory-protection guard --
pure logic only. No model, no torch, no network: wrapped in `endpoint_guard.refuse_all()`.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_boundary_diagnostic_002 as diag


class BuildPairsTests(unittest.TestCase):
    def test_builds_at_most_24_distinct_pairs_offline(self):
        with endpoint_guard.refuse_all():
            pairs = diag.build_pairs()
        self.assertLessEqual(len(pairs), 24)
        keys = {(p["premise"], p["hypothesis"]) for p in pairs}
        self.assertEqual(len(keys), len(pairs), "every (premise, hypothesis) pair must be distinct")

    def test_every_pair_is_a_self_or_cross_comparison_with_declared_origin(self):
        pairs = diag.build_pairs()
        for p in pairs:
            self.assertIn(p["origin"], ("verbatim_source", "synthetic_diagnostic"))
            self.assertTrue(p["expects"])

    def test_u3_is_never_edited_in_any_synthetic_c_section_pair(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        u3 = pairs["A2_U3_self"]["premise"]
        for pid in (
            "C1_explicit_question_keep_bigram",
            "C2_declarative_remove_bigram",
            "C3_explicit_question_remove_bigram",
        ):
            self.assertTrue(pairs[pid]["premise"].endswith(u3), f"{pid} does not end with verbatim U3")

    def test_c1_and_a3_share_the_more_moral_bigram_c2_and_c3_do_not(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        self.assertIn("more moral", pairs["A3_U2U3_self_REPRO"]["premise"])
        self.assertIn("more moral", pairs["C1_explicit_question_keep_bigram"]["premise"])
        self.assertNotIn("more moral", pairs["C2_declarative_remove_bigram"]["premise"])
        self.assertNotIn("more moral", pairs["C3_explicit_question_remove_bigram"]["premise"])

    def test_a3_reproduction_pair_matches_attempt_001s_premise_exactly(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        # attempt 001's PREMISE_C11 == U2 + " " + U3 -- reconstructed independently here from the
        # frozen packet, not copy-pasted, and must match byte-for-byte.
        self.assertEqual(pairs["A3_U2U3_self_REPRO"]["premise"], pairs["A3_U2U3_self_REPRO"]["hypothesis"])
        self.assertAlmostEqual(pairs["A3_U2U3_self_REPRO"]["historical"]["support"], 0.0070, places=3)
        self.assertAlmostEqual(pairs["A3_U2U3_self_REPRO"]["historical"]["contradiction"], 0.9809, places=3)

    def test_d_ladder_is_strictly_increasing_sentence_count_same_family(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        d1, d2, d3 = (pairs[f"D{n}_neutral_{n}sentence_self"]["premise"] for n in (1, 2, 3))
        self.assertTrue(d2.startswith(d1))
        self.assertTrue(d3.startswith(d2))

    def test_write_manifest_refuses_every_protected_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in diag.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    diag.write_manifest(base / protected, diag.build_pairs())

    def test_write_manifest_refuses_an_already_populated_directory(self):
        pairs = diag.build_pairs()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-attempt"
            diag.write_manifest(run_dir, pairs)  # first write OK
            with self.assertRaises(RuntimeError):
                diag.write_manifest(run_dir, pairs)  # second write into the same populated dir refused

    def test_manifest_round_trips_through_json_byte_for_byte(self):
        pairs = diag.build_pairs()
        with tempfile.TemporaryDirectory() as tmp:
            path = diag.write_manifest(Path(tmp) / "fresh", pairs)
            reread = diag.read_manifest(path)
        self.assertEqual(reread["pairs"], pairs)
        self.assertEqual(reread["pair_count"], len(pairs))


if __name__ == "__main__":
    unittest.main()
