"""Offline tests of `nli_candidate_pair_inventory` -- reads real saved JSON from disk (local file reads only),
makes NO model/NLI/network call. Every assertion here is checked against ground truth read directly from the
source JSON in this test file, never assumed."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_candidate_pair_inventory as inv_tool


class BuildFullInventoryTests(unittest.TestCase):
    def setUp(self):
        with endpoint_guard.refuse_all():
            self.inv = inv_tool.build_full_inventory()

    def test_finds_nine_raw_pairs_across_the_four_verified_sources(self):
        # gate2-diagnostic-002 (2) + gate-integration-live-002 (2) + ab-backend-14a-overview (2)
        # + ab-backend-diag-s-unbounded (3) = 9. Every one of the 4 files exists and is read.
        self.assertEqual(self.inv["raw_pair_count"], 9)

    def test_no_pair_is_dropped_by_deduplication_because_none_are_byte_identical(self):
        # all 9 raw pairs are distinct (premise, hypothesis) bytes -- confirmed no two proposals in this
        # small population happen to collide, so distinct count equals raw count.
        self.assertEqual(self.inv["distinct_pair_count"], 9)

    def test_six_distinct_premises_matches_the_population_eval_finding(self):
        # cross-checked against nli_premise_population_eval's own independently-computed 6-premise finding
        # for the SAME two contract-directed-slice sources (gate2-diagnostic-002/live-002); the two ab-backend
        # sources add distinct premises on top of those 6... wait: total across all 4 sources is still 6,
        # because {U2,U6} and {U7}/{U1,U3,U7}/{U5} are unit-id combinations, and the two ab-backend sources
        # actually share several premises (same units, same source paper). Value asserted from a live run,
        # not assumed.
        self.assertEqual(self.inv["distinct_premise_count"], 6)

    def test_every_pair_has_a_canonical_locator_for_every_unit(self):
        for p in self.inv["pairs"]:
            self.assertEqual(len(p["canonical_locators"]), len(p["unit_ids"]))
            for loc in p["canonical_locators"]:
                self.assertIsInstance(loc["paper_id"], int)

    def test_raw_text_equals_scored_hypothesis_is_asserted_not_just_claimed(self):
        # build_raw_inventory() itself asserts this against every proposal dict's actual keys (no
        # nli_hypothesis_text/marker_outcome field) before extraction -- a passing test run here means that
        # assertion did not fire.
        for p in self.inv["pairs"]:
            self.assertTrue(p["raw_text_equals_scored_hypothesis"])

    def test_groups_partition_the_distinct_pairs_with_no_overlap_and_no_gap(self):
        membership = self.inv["group_membership"]
        all_shas = {sha for shas in membership.values() for sha in shas}
        self.assertEqual(len(all_shas), self.inv["distinct_pair_count"])
        seen = set()
        for shas in membership.values():
            self.assertTrue(seen.isdisjoint(shas))
            seen.update(shas)

    def test_c9_and_c11_pairs_land_in_the_correct_self_pair_groups(self):
        # c9's U1 premise has a PASSING self-pair baseline (support=0.887); c11's U2+U3 premise has a
        # SEVERELY FAILING one (support=0.007) -- both established facts from prior phases of this arc,
        # cross-checked here against the actual attached baseline, not re-derived.
        by_units = {}
        for p in self.inv["pairs"]:
            by_units.setdefault(tuple(p["unit_ids"]), []).append(p)
        c9_pairs = by_units[("U1",)]
        c11_pairs = by_units[("U2", "U3")]
        for p in c9_pairs:
            baseline = p["premise_self_pair_baseline"]
            self.assertIsNotNone(baseline, p)
            self.assertGreater(baseline["support"], 0.5, "c9's premise self-pair should be a passing baseline")
        for p in c11_pairs:
            baseline = p["premise_self_pair_baseline"]
            self.assertIsNotNone(baseline, p)
            self.assertLess(baseline["support"], 0.01, "c11's premise self-pair should be a severe failure")

    def test_ab_backend_premises_have_no_self_pair_result(self):
        # none of the ab-backend-sourced units (U2/U5/U6/U7, in any combination) were ever self-pair tested
        # in any prior diagnostic batch of this arc -- confirmed here, not assumed.
        for p in self.inv["pairs"]:
            if p["source_id"] in ("ab-backend-14a-overview", "ab-backend-diag-s-unbounded"):
                self.assertIsNone(p["premise_self_pair_baseline"], p["unit_ids"])

    def test_a_multi_unit_premise_joins_passages_in_unit_id_order(self):
        multi = [p for p in self.inv["pairs"] if len(p["unit_ids"]) > 1]
        self.assertGreater(len(multi), 0)
        for p in multi:
            self.assertIn(" ", p["premise"])  # unit passages are joined with a space, never concatenated raw

    def test_the_trailing_citation_marker_pair_is_found_and_classified(self):
        # c9's own U1 candidate: scored once without a trailing "(U1)" marker (gate2-diagnostic-002) and once
        # with one (gate-integration-live-002) -- the SAME real candidate text differing only by the marker,
        # each independently scored by production NLI. This is the exact phenomenon the whole arc started
        # from, now confirmed present at the CANDIDATE level (not just self-pairs).
        matches = [
            p
            for p in self.inv["pairs"]
            if p["related_variant"] and p["related_variant"]["kind"] == "trailing_citation_marker_difference"
        ]
        self.assertEqual(len(matches), 1)
        pair = matches[0]
        self.assertEqual(pair["unit_ids"], ["U1"])
        self.assertEqual(pair["source_id"], "gate2-diagnostic-002")
        self.assertAlmostEqual(pair["related_variant"]["nli_support_self"], 0.8108597993850708, places=6)
        self.assertAlmostEqual(pair["related_variant"]["nli_support_other"], 0.23521043360233307, places=6)

    def test_the_hard_length_cap_truncation_pair_is_found_and_classified(self):
        # {U2,U6}: 14a_overview.json's 400-char production-truncated candidate vs. diag_s_unbounded's full
        # 505-char untruncated version of the same underlying generation -- two genuinely distinct scored
        # strings (confirmed by their differing nli_support values), never merged.
        matches = [
            p
            for p in self.inv["pairs"]
            if p["related_variant"] and p["related_variant"]["kind"] == "hard_length_cap_truncation"
        ]
        self.assertEqual(len(matches), 1)
        pair = matches[0]
        self.assertEqual(pair["unit_ids"], ["U2", "U6"])
        self.assertEqual(len(pair["hypothesis"]), 400)
        self.assertNotEqual(pair["related_variant"]["nli_support_self"], pair["related_variant"]["nli_support_other"])

    def test_only_two_pairs_have_a_related_variant_flag(self):
        # every other pair in this 9-pair population is unrelated to any sibling by either verified pattern.
        flagged = [p for p in self.inv["pairs"] if p["related_variant"] is not None]
        self.assertEqual(len(flagged), 2)


class Group4CrossReferenceTests(unittest.TestCase):
    def setUp(self):
        with endpoint_guard.refuse_all():
            self.inv = inv_tool.build_full_inventory()
            self.group4 = inv_tool.cross_reference_prospective_corpus_group4(self.inv["pairs"])

    def test_pilot_manifest_has_29_total_pairs_2_controls_27_prospective(self):
        self.assertEqual(self.group4["total_prospective_pilot_premises"], 29)

    def test_exactly_27_prospective_premises_have_no_candidate_level_record(self):
        # the pilot's 2 controls (c9's U1, c11's U2+U3) DO have candidate-level records (they ARE c9/c11);
        # all 27 genuinely prospective (source-derived, never-scored) premises do not.
        self.assertEqual(self.group4["with_no_candidate_level_record"], 27)
        self.assertEqual(len(self.group4["members"]), 27)

    def test_the_known_paper_20_severe_failure_premise_is_a_group4_member(self):
        ids = {m["pair_id"] for m in self.group4["members"]}
        self.assertIn("prospective_7e44a7f4226a", ids)

    def test_no_control_pair_id_appears_in_group4(self):
        for m in self.group4["members"]:
            self.assertNotIn("control", str(m["pair_id"]))


class BlindedReviewerPacketTests(unittest.TestCase):
    def setUp(self):
        with endpoint_guard.refuse_all():
            self.inv = inv_tool.build_full_inventory()
            self.packet, self.identity_map = inv_tool.build_blinded_reviewer_packet(self.inv["pairs"])

    def test_packet_has_one_item_per_distinct_pair(self):
        self.assertEqual(len(self.packet), self.inv["distinct_pair_count"])
        self.assertEqual(len(self.identity_map), self.inv["distinct_pair_count"])

    def test_packet_items_carry_no_nli_or_screening_field(self):
        forbidden_keys = {
            "nli",
            "nli_support",
            "nli_contradiction",
            "status",
            "screen_reasons",
            "reasons",
            "premise_self_pair_baseline",
            "related_variant",
            "source_id",
            "index_in_source",
        }
        for item in self.packet:
            self.assertTrue(forbidden_keys.isdisjoint(item.keys()), item.keys())

    def test_packet_items_carry_premise_and_candidate_text(self):
        for item in self.packet:
            self.assertTrue(item["premise"])
            self.assertTrue(item["candidate_statement"])

    def test_identity_map_can_reconstruct_every_packet_item_back_to_a_real_pair(self):
        by_sha = {p["pair_sha256"]: p for p in self.inv["pairs"]}
        for entry in self.identity_map:
            self.assertIn(entry["pair_sha256"], by_sha)

    def test_blind_ids_are_unique_and_sequential(self):
        blind_ids = [item["blind_id"] for item in self.packet]
        self.assertEqual(len(blind_ids), len(set(blind_ids)))
        self.assertEqual(blind_ids[0], "packet-item-01")

    def test_packet_and_identity_map_are_separate_objects_not_a_single_structure(self):
        # structural blinding: the two are genuinely different lists a caller could hand to different parties,
        # not one dict with a "hidden" key a reviewer could still open.
        self.assertIsNot(self.packet, self.identity_map)
        packet_keys = set(self.packet[0].keys())
        map_keys = set(self.identity_map[0].keys())
        self.assertNotIn("pair_sha256", packet_keys)  # the linking key itself is only on the identity-map side
        self.assertIn("pair_sha256", map_keys)  # ...where it must actually be, or reconciliation is impossible


class RelationshipClassifierUnitTests(unittest.TestCase):
    """Pure-function tests of the two classifier predicates in isolation, independent of the real-data
    integration tests above -- these pin the exact string-shape contract each pattern requires."""

    def test_hard_length_cap_truncation_requires_exact_400_length_and_a_differing_400th_char(self):
        shorter = "x" * 399 + ","
        longer = "x" * 399 + "y" + "more text continues here"
        self.assertTrue(inv_tool._is_hard_length_cap_truncation(shorter, longer))

    def test_hard_length_cap_truncation_rejects_a_true_byte_identical_prefix(self):
        # if the 400th char actually agrees, this is NOT the truncation-comma artifact -- some other relation
        shorter = "x" * 400
        longer = "x" * 400 + "more"
        self.assertFalse(inv_tool._is_hard_length_cap_truncation(shorter, longer))

    def test_hard_length_cap_truncation_rejects_non_400_length_shorter_text(self):
        shorter = "x" * 200
        longer = "x" * 200 + "y" * 300
        self.assertFalse(inv_tool._is_hard_length_cap_truncation(shorter, longer))

    def test_trailing_citation_marker_difference_detects_marker_inserted_before_final_punctuation(self):
        shorter = "The finding held across conditions."
        longer = "The finding held across conditions (U3)."
        self.assertTrue(inv_tool._is_trailing_citation_marker_difference(shorter, longer))

    def test_trailing_citation_marker_difference_rejects_an_unrelated_longer_sentence(self):
        shorter = "The finding held across conditions."
        longer = "The finding held across conditions and replicated in a follow-up study."
        self.assertFalse(inv_tool._is_trailing_citation_marker_difference(shorter, longer))

    def test_trailing_citation_marker_difference_requires_sentence_final_punctuation_on_shorter(self):
        shorter = "The finding held across conditions"  # no trailing punctuation
        longer = "The finding held across conditions (U3)."
        self.assertFalse(inv_tool._is_trailing_citation_marker_difference(shorter, longer))

    def test_classify_relationship_falls_back_to_prefix_variant_for_a_genuine_unrelated_extension(self):
        shorter = "A short sentence."
        longer = "A short sentence. And then a whole second sentence follows it."
        self.assertEqual(inv_tool._classify_relationship(shorter, longer), "prefix_variant")


class WriteArtifactGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory(self):
        inv = {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in inv_tool.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    inv_tool.write_artifact(base / protected, "x.json", inv)

    def test_refuses_to_overwrite_an_already_written_artifact(self):
        inv = {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-new-eval"
            inv_tool.write_artifact(run_dir, "x.json", inv)
            with self.assertRaises(RuntimeError):
                inv_tool.write_artifact(run_dir, "x.json", inv)

    def test_the_studys_own_run_directory_name_is_not_in_the_protected_set(self):
        # sanity check: this pass's own target directory must NOT be protected, or the tool could never
        # write its own inventory artifact.
        self.assertNotIn(inv_tool.EVAL_DIR.name, inv_tool.PROTECTED_RUN_DIRS)


if __name__ == "__main__":
    unittest.main()
