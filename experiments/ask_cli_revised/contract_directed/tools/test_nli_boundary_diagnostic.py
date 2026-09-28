"""Offline test of `nli_boundary_diagnostic.build_pairs()` -- pure pair-construction logic only.

No model, no torch, no network: wrapped in `endpoint_guard.refuse_all()` as a second, independent
guarantee (matching `test_run_gate_integration_live.py`'s own convention) that nothing could reach
a socket even if this module accidentally imported something that tried to.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_boundary_diagnostic as diag


class BuildPairsTests(unittest.TestCase):
    def test_builds_at_most_24_distinct_pairs_offline(self):
        with endpoint_guard.refuse_all():
            pairs = diag.build_pairs()
        self.assertLessEqual(len(pairs), 24)
        keys = {(p["premise"], p["hypothesis"]) for p in pairs}
        self.assertEqual(len(keys), len(pairs), "every (premise, hypothesis) pair must be distinct")

    def test_a_and_b_are_a_clean_minimal_pair_differing_only_by_the_marker(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        a, b = pairs["A"], pairs["B"]
        self.assertEqual(a["premise"], b["premise"])
        self.assertEqual(b["hypothesis"], a["hypothesis"][:-1] + " (U1)" + ".")

    def test_d_minus_marker_removes_exactly_the_marker_and_nothing_else(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        d, d_minus = pairs["D"], pairs["D_minus_marker"]
        self.assertEqual(d["hypothesis"].replace(" (U2, U3).", "."), d_minus["hypothesis"])

    def test_restored_variants_contain_the_previously_omitted_finding(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        for pid in ("C_restored", "D_restored", "D_restored_no_marker", "clause2_restored_only"):
            self.assertIn("a better forager", pairs[pid]["hypothesis"])

    def test_manifest_round_trips_through_json_byte_for_byte(self):
        import tempfile
        from pathlib import Path

        pairs = diag.build_pairs()
        with tempfile.TemporaryDirectory() as tmp:
            path = diag.write_manifest(Path(tmp), pairs)
            reread = diag.read_manifest(path)
        self.assertEqual(reread["pairs"], pairs)
        self.assertEqual(reread["pair_count"], len(pairs))

    def test_historical_pairs_carry_the_exact_recorded_scores(self):
        pairs = {p["id"]: p for p in diag.build_pairs()}
        self.assertAlmostEqual(pairs["A"]["historical"]["support"], 0.8108597993850708)
        self.assertAlmostEqual(pairs["B"]["historical"]["support"], 0.23521043360233307)
        self.assertAlmostEqual(pairs["C"]["historical"]["support"], 0.2671320140361786)
        self.assertAlmostEqual(pairs["D"]["historical"]["support"], 0.013148654252290726)


if __name__ == "__main__":
    unittest.main()
