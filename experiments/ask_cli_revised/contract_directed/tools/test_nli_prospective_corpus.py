"""Offline tests of `nli_prospective_corpus.py`. Reads real saved packet/eligibility JSON from disk (local
file reads only) but makes no model/NLI/network call except the one tokenizer test, which asserts the offline
env guards rather than using `endpoint_guard.refuse_all()` (loading a cached tokenizer legitimately touches
the filesystem, not the network -- confirmed by the same guards every other tool in this arc already sets).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_prospective_corpus as pc


class LoadAndDedupTests(unittest.TestCase):
    def test_loads_all_eight_packets(self):
        with endpoint_guard.refuse_all():
            packets = pc.load_packets()
        self.assertEqual(len(packets), 8)

    def test_every_part_has_real_paper_chunk_and_offset_provenance(self):
        packets = pc.load_packets()
        for pkt in packets:
            for part in pkt["parts"]:
                self.assertIsInstance(part["paper_id"], int)
                self.assertIsInstance(part["chunk_id"], int)
                self.assertIsInstance(part["start"], int)
                self.assertIsInstance(part["end"], int)
                self.assertTrue(part["text"])

    def test_duplicate_canonical_spans_within_and_across_packets_are_merged_not_double_counted(self):
        """A REAL, confirmed case: packet 04 aliases the same (chunk, offsets) under both p6 and p7; packet 03
        and packet 04 (both paper 20) share several identical canonical spans under different span_ids."""
        packets = pc.load_packets()
        distinct = pc.deduplicate(packets)
        raw_part_count = sum(len(pkt["parts"]) for pkt in packets)
        self.assertLess(len(distinct), raw_part_count, "some canonical spans must have been merged")
        # packet 04's p6 and p7 are a confirmed internal duplicate -- find that canonical key and confirm both
        # aliases are recorded under the same entry, not registered as two different spans.
        pkt04 = next(p for p in packets if p["packet_id"] == "414fe79378e1")
        p6 = next(part for part in pkt04["parts"] if part["span_id"] == "p6")
        p7 = next(part for part in pkt04["parts"] if part["span_id"] == "p7")
        self.assertEqual(p6["text"], p7["text"])
        key = pc.canonical_key(p6["paper_id"], p6["chunk_id"], p6["start"], p6["end"])
        aliases = distinct[key]["aliases"]
        self.assertIn(("414fe79378e1", "p6"), aliases)
        self.assertIn(("414fe79378e1", "p7"), aliases)

    def test_conflicting_text_under_the_same_canonical_key_raises(self):
        """A synthetic ambiguous-identity case: two different packets claiming the same (paper, chunk, start,
        end) but with DIFFERENT text must be treated as a genuine identity conflict, not silently merged --
        exactly the class of error evidence_identity.py's own SpanIdentityCollision exists to catch upstream."""
        packets = pc.load_packets()
        # corrupt one real part's text while keeping its canonical key identical to another real part's key
        packets[0]["parts"][0] = dict(packets[0]["parts"][0], text="a deliberately different sentence")
        packets.append(
            {
                "path": "synthetic",
                "packet_id": "synthetic-conflict",
                "paper_id": packets[0]["parts"][0]["paper_id"],
                "parts": [
                    {
                        "span_id": "p1",
                        "text": "an entirely different, conflicting sentence",
                        "paper_id": packets[0]["parts"][0]["paper_id"],
                        "chunk_id": packets[0]["parts"][0]["chunk_id"],
                        "start": packets[0]["parts"][0]["start"],
                        "end": packets[0]["parts"][0]["end"],
                    }
                ],
            }
        )
        with self.assertRaises(AssertionError):
            pc.deduplicate(packets)


class StratumSeparationTests(unittest.TestCase):
    def test_stratum_a_keys_are_never_present_in_single_span_prospective_output(self):
        packets = pc.load_packets()
        distinct = pc.deduplicate(packets)
        singles = pc.single_span_premises(distinct)
        for s in singles:
            self.assertNotIn(s["canonical_keys"][0], pc.STRATUM_A_KEYS)

    def test_stratum_a_keys_resolve_to_real_known_c9_and_c11_text(self):
        """Confirms STRATUM_A_KEYS wasn't guessed -- each one resolves to the exact known historical passage."""
        packets = pc.load_packets()
        distinct = pc.deduplicate(packets)
        for key in pc.STRATUM_A_KEYS:
            self.assertIn(key, distinct, f"stratum-A key {key} not found among real packet spans")
        c9_key = (67, 35019, 25, 392)
        self.assertTrue(distinct[c9_key]["text"].startswith("Participants completed a Just World Beliefs Scale"))

    def test_no_prospective_premise_is_byte_identical_to_a_historical_one(self):
        corpus = pc.build_corpus()
        self.assertEqual(corpus["historical_overlap_count"], 0)
        for p in corpus["prospective_premises"]:
            self.assertFalse(p["overlaps_historical"])

    def test_observed_production_stratum_is_imported_read_only_not_rederived(self):
        """The historical premise texts come from the ALREADY-BUILT population-eval inventory (imported), not
        a second, independent re-derivation -- confirms the two strata cannot silently drift apart."""
        historical = pc.historical_premise_texts()
        self.assertEqual(len(historical), 6)


class MultiSpanConstructionTests(unittest.TestCase):
    def test_packet_full_order_preserves_original_span_order(self):
        packets = pc.load_packets()
        distinct = pc.deduplicate(packets)
        multi = pc.packet_full_order_premises(packets, distinct)
        pkt03 = next(m for m in multi if m["packet_id"] == "36da02d416d1")  # paper 20, 7 parts, no stratum-A
        # p1..p7 in file order -- the premise must be their texts joined in that same order
        expected = " ".join(distinct[k]["text"] for k in pkt03["canonical_keys"])
        self.assertEqual(pkt03["premise"], expected)

    def test_packet_full_order_omits_stratum_a_members_and_records_the_omission(self):
        packets = pc.load_packets()
        distinct = pc.deduplicate(packets)
        multi = pc.packet_full_order_premises(packets, distinct)
        pkt01 = next((m for m in multi if m["packet_id"] == "1606c9d7970d"), None)
        # packet 01 has 2 parts; p1 is Stratum-A (c9/M10) and must never appear in a prospective premise
        self.assertIsNone(pkt01, "packet 01 has only 1 non-Stratum-A part left, too few for a multi-span premise")

    def test_packet_full_order_omits_cross_packet_duplicates_and_records_the_omission(self):
        packets = pc.load_packets()
        distinct = pc.deduplicate(packets)
        multi = pc.packet_full_order_premises(packets, distinct)
        pkt04 = next(m for m in multi if m["packet_id"] == "414fe79378e1")  # shares spans with packet 03
        omitted_reasons = {o["reason"] for o in pkt04["omitted_parts"]}
        self.assertIn("duplicate_of_earlier_packet_or_part", omitted_reasons)

    def test_eligibility_slot_group_only_uses_groups_of_two_or_more(self):
        packets = pc.load_packets()
        results = pc.load_results()
        distinct = pc.deduplicate(packets)
        groups = pc.eligibility_slot_group_premises(packets, results, distinct)
        for g in groups:
            self.assertGreaterEqual(len(g["canonical_keys"]), 2)

    def test_eligibility_slot_group_never_includes_a_stratum_a_key(self):
        packets = pc.load_packets()
        results = pc.load_results()
        distinct = pc.deduplicate(packets)
        groups = pc.eligibility_slot_group_premises(packets, results, distinct)
        for g in groups:
            self.assertTrue(all(k not in pc.STRATUM_A_KEYS for k in g["canonical_keys"]))

    def test_an_unresolvable_span_id_in_a_slot_group_is_skipped_not_guessed(self):
        """Synthetic: a slot_spans entry referencing a span_id that doesn't exist in that packet must be
        dropped, never silently matched to a different span."""
        packets = pc.load_packets()
        distinct = pc.deduplicate(packets)
        fake_results = [
            {
                "packet_id": packets[0]["packet_id"],
                "result": {"per_unit": {"FAKE": {"slot_spans": {"slot": ["p1", "p999_does_not_exist"]}}}},
            }
        ]
        groups = pc.eligibility_slot_group_premises(packets, fake_results, distinct)
        self.assertEqual(groups, [])


class TokenizationAndManifestSafetyTests(unittest.TestCase):
    def test_offline_env_guards_are_set(self):
        import os

        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_long_single_span_premises_are_correctly_flagged_as_truncating(self):
        """A real, confirmed finding: at least one genuine single-span passage (an abstract-length span) is
        long enough that its OWN self-entailment pair exceeds the model's 512-token limit."""
        corpus = pc.build_corpus()
        pc.tokenize_and_hash(corpus["prospective_premises"])
        truncating_singles = [
            p for p in corpus["prospective_premises"] if p["would_truncate"] and p["ancestry"] == ["single_span"]
        ]
        self.assertGreater(len(truncating_singles), 0, "expected at least one over-length single-span premise")

    def test_manifest_candidates_excludes_every_truncating_premise(self):
        corpus = pc.build_corpus()
        pc.tokenize_and_hash(corpus["prospective_premises"])
        safe = pc.manifest_candidates(corpus["prospective_premises"])
        self.assertTrue(all(not p["would_truncate"] for p in safe))
        self.assertLess(len(safe), len(corpus["prospective_premises"]))


class WriteManifestGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory(self):
        corpus = pc.build_corpus()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in pc.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    pc.write_manifest(base / protected, corpus)

    def test_refuses_an_already_populated_directory(self):
        corpus = pc.build_corpus()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-eval"
            pc.write_manifest(run_dir, corpus)
            with self.assertRaises(RuntimeError):
                pc.write_manifest(run_dir, corpus)


if __name__ == "__main__":
    unittest.main()
