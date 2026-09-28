"""Offline tests of `nli_premise_population_eval.inventory()` -- reads real saved JSON from disk (local file
reads only) but makes NO model/NLI/network call. `tokenize_lengths` (the only function touching a model
object, and only its tokenizer, never the full model) is exercised separately and is the one test wrapped
with an explicit offline-tokenizer check rather than `endpoint_guard.refuse_all()`, since loading a tokenizer
legitimately touches the filesystem cache -- `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` are asserted set instead.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_premise_population_eval as pop


class InventoryTests(unittest.TestCase):
    def test_finds_exactly_six_distinct_premises(self):
        with endpoint_guard.refuse_all():
            inv = pop.inventory()
        self.assertEqual(inv["distinct_premise_count"], 6)
        self.assertEqual(len(inv["premises"]), 6)

    def test_every_premise_has_at_least_one_occurrence(self):
        inv = pop.inventory()
        for p in inv["premises"]:
            self.assertGreaterEqual(len(p["occurrences"]), 1)

    def test_span_count_matches_unit_ids_length(self):
        inv = pop.inventory()
        for p in inv["premises"]:
            self.assertEqual(p["span_count"], len(p["unit_ids"]))

    def test_the_known_c9_and_c11_premises_are_present_as_controls(self):
        inv = pop.inventory()
        keys = {tuple(p["unit_ids"]) for p in inv["premises"]}
        self.assertIn(("U1",), keys)  # c9's premise, single-span
        self.assertIn(("U2", "U3"), keys)  # c11's known-failing premise, 2-span

    def test_the_replayed_c9_and_c11_premises_are_deduplicated_not_double_counted(self):
        inv = pop.inventory()
        by_key = {tuple(p["unit_ids"]): p for p in inv["premises"]}
        c9 = by_key[("U1",)]
        c11 = by_key[("U2", "U3")]
        self.assertEqual(len(c9["occurrences"]), 2, "c9 was replayed in both gate2-diagnostic-002 and live-002")
        self.assertEqual(len(c11["occurrences"]), 2, "c11 was replayed in both gate2-diagnostic-002 and live-002")

    def test_span_counts_are_a_mix_of_single_and_multi_span(self):
        inv = pop.inventory()
        span_counts = sorted(p["span_count"] for p in inv["premises"])
        self.assertEqual(span_counts, [1, 1, 1, 2, 2, 3])

    def test_excluded_sources_are_named_with_reasons(self):
        inv = pop.inventory()
        self.assertEqual(len(inv["excluded_sources"]), 4)
        for name, reason in inv["excluded_sources"]:
            self.assertTrue(name)
            self.assertTrue(reason)


class WriteManifestGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory(self):
        import tempfile
        from pathlib import Path

        inv = pop.inventory()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in pop.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    pop.write_manifest(base / protected, inv)

    def test_refuses_an_already_populated_directory(self):
        import tempfile
        from pathlib import Path

        inv = pop.inventory()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-eval"
            pop.write_manifest(run_dir, inv)
            with self.assertRaises(RuntimeError):
                pop.write_manifest(run_dir, inv)


class TokenizeLengthsTests(unittest.TestCase):
    def test_offline_env_guards_are_set(self):
        import os

        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_tokenizes_every_premise_with_no_truncation(self):
        inv = pop.inventory()
        pop.tokenize_lengths(inv["premises"])
        for p in inv["premises"]:
            self.assertIn("self_entailment_pair_tokens", p)
            self.assertFalse(p["would_truncate"], p)
            self.assertLessEqual(p["self_entailment_pair_tokens"], p["model_max_length"])


if __name__ == "__main__":
    unittest.main()
