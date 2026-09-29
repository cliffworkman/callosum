"""Offline tests of `nli_review_reconciliation_001` -- reads real saved JSON, calls exactly one real PURE
function (`overview_guards.strip_redundant_unit_markers`), makes NO model/NLI/network call."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_review_reconciliation_001 as recon


def _real_setup():
    with endpoint_guard.refuse_all():
        packet_ids = recon.load_reviewer_packet_ids()
        coordinator_map = recon.load_coordinator_map()
        inventory_pairs = recon.load_inventory_pairs()
    return packet_ids, coordinator_map, inventory_pairs


class CoverageValidationTests(unittest.TestCase):
    def test_submission_covers_exactly_the_nine_packet_ids(self):
        packet_ids, _, _ = _real_setup()
        self.assertEqual(len(packet_ids), 9)
        recon.validate_submission_coverage(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION, packet_ids)  # no raise

    def test_every_opaque_id_appears_exactly_once(self):
        # a Python dict already enforces unique keys; this confirms the submission's key SET is exactly 9
        self.assertEqual(len(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION), 9)
        self.assertEqual(len(set(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION.keys())), 9)

    def test_missing_id_is_rejected(self):
        packet_ids, _, _ = _real_setup()
        truncated = dict(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION)
        truncated.pop("RV-XV9K")
        with self.assertRaises(ValueError):
            recon.validate_submission_coverage(truncated, packet_ids)

    def test_extra_unknown_id_is_rejected(self):
        packet_ids, _, _ = _real_setup()
        extra = dict(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION)
        extra["RV-NOPE"] = extra["RV-XV9K"]
        with self.assertRaises(ValueError):
            recon.validate_submission_coverage(extra, packet_ids)

    def test_every_overall_and_atomic_label_is_in_the_five_value_vocabulary(self):
        for oid, entry in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION.items():
            self.assertIn(entry["overall_label"], recon.VALID_LABELS, oid)
            for prop in entry["atomic_propositions"]:
                self.assertIn(prop["label"], recon.VALID_LABELS, f"{oid}: {prop}")

    def test_an_invalid_label_is_rejected(self):
        packet_ids, _, _ = _real_setup()
        bad = {k: dict(v) for k, v in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION.items()}
        bad["RV-XV9K"]["overall_label"] = "Definitely True"  # not in the vocabulary
        with self.assertRaises(ValueError):
            recon.validate_submission_coverage(bad, packet_ids)

    def test_every_submitted_item_states_locked_false(self):
        # preserving the submitted fact, not a coordinator assumption
        for oid, entry in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION.items():
            self.assertFalse(entry["locked"], oid)


class TranscriptionFidelityTests(unittest.TestCase):
    """Confirms the hand transcription matches the verbatim saved file -- a testable property, not an
    assertion trusted on its own."""

    def setUp(self):
        self.transcript_text = recon.load_transcript_text()

    def test_every_opaque_id_appears_in_the_verbatim_transcript(self):
        for oid in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION:
            self.assertIn(oid, self.transcript_text)

    def test_every_atomic_proposition_sentence_appears_verbatim_in_the_transcript(self):
        for oid, entry in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION.items():
            for prop in entry["atomic_propositions"]:
                self.assertIn(prop["text"], self.transcript_text, f"{oid}: {prop['text']!r} not found verbatim")

    def test_every_reason_string_appears_verbatim_in_the_transcript(self):
        for oid, entry in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION.items():
            self.assertIn(entry["reason"], self.transcript_text, oid)

    def test_context_requested_items_match_the_transcript(self):
        requesting = {oid for oid, e in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION.items() if e["context_requested"]}
        self.assertEqual(requesting, {"RV-8G8J", "RV-UAHS"})
        for oid in requesting:
            self.assertIn("Context requested: Yes.", self.transcript_text[self.transcript_text.index(oid) :][:2000])

    def test_verbatim_ambiguous_qualifier_is_preserved_for_the_two_truncated_items(self):
        for oid in ("RV-8G8J", "RV-UAHS"):
            truncated_props = [
                p
                for p in recon.SUBMITTED_STRUCTURED_TRANSCRIPTION[oid]["atomic_propositions"]
                if p["label"] == "Ambiguous or unjudgeable"
            ]
            self.assertEqual(len(truncated_props), 1, oid)
            self.assertEqual(truncated_props[0]["label_verbatim"], "Ambiguous or unjudgeable as a complete proposition")


class HistoricalJoinTests(unittest.TestCase):
    def setUp(self):
        self.packet_ids, self.coordinator_map, self.inventory_pairs = _real_setup()
        self.records = recon.build_reconciliation_records(
            recon.SUBMITTED_STRUCTURED_TRANSCRIPTION, self.coordinator_map, self.inventory_pairs
        )

    def test_nine_records_produced(self):
        self.assertEqual(len(self.records), 9)

    def test_every_record_has_the_correct_premise_and_hypothesis_bytes(self):
        by_sha = {p["pair_sha256"]: p for p in self.inventory_pairs}
        for r in self.records:
            original = by_sha[r["pair_sha256"]]
            self.assertEqual(r["premise"], original["premise"])
            self.assertEqual(r["hypothesis"], original["hypothesis"])

    def test_c9_no_marker_variant_is_historically_grounded(self):
        r = next(r for r in self.records if r["opaque_id"] == "RV-78DB")
        self.assertEqual(r["historical"]["status"], "grounded")
        self.assertEqual(r["historical"]["reasons"], [])
        self.assertAlmostEqual(r["historical"]["nli_support"], 0.8108597993850708, places=6)

    def test_c9_marker_variant_is_historically_withheld_by_nli_alone(self):
        r = next(r for r in self.records if r["opaque_id"] == "RV-8WGZ")
        self.assertEqual(r["historical"]["status"], "withheld")
        self.assertTrue(r["reason_kinds"]["withheld_by_nli_alone"])
        self.assertEqual(r["historical"]["screen_reasons"], [])

    def test_c11_both_variants_have_a_severely_failing_self_pair_baseline(self):
        for oid in ("RV-MT5B", "RV-Y4T5"):
            r = next(r for r in self.records if r["opaque_id"] == oid)
            baseline = r["historical"]["self_pair_baseline"]
            self.assertIsNotNone(baseline, oid)
            self.assertLess(baseline["support"], 0.01, oid)
            self.assertTrue(r["reason_kinds"]["withheld_by_nli_alone"], oid)

    def test_items_with_no_self_pair_data_are_explicitly_none_not_omitted(self):
        no_self_pair_ids = {"RV-RAJY", "RV-ZPXV", "RV-8G8J", "RV-UAHS", "RV-XV9K"}
        for r in self.records:
            if r["opaque_id"] in no_self_pair_ids:
                self.assertIn("self_pair_baseline", r["historical"])
                self.assertIsNone(r["historical"]["self_pair_baseline"], r["opaque_id"])

    def test_reviewer_labels_are_preserved_exactly_as_submitted(self):
        for r in self.records:
            submitted = recon.SUBMITTED_STRUCTURED_TRANSCRIPTION[r["opaque_id"]]
            self.assertEqual(r["reviewer"]["overall_label"], submitted["overall_label"])
            self.assertEqual(r["reviewer"]["atomic_propositions"], submitted["atomic_propositions"])
            self.assertFalse(r["reviewer"]["locked"])

    def test_family_membership_is_attached_from_the_coordinator_map_not_rederived(self):
        by_id = {r["opaque_id"]: r for r in self.records}
        self.assertEqual(by_id["RV-8WGZ"]["family"], "family_1_trailing_citation_marker_difference")
        self.assertEqual(by_id["RV-78DB"]["family"], "family_1_trailing_citation_marker_difference")
        self.assertEqual(by_id["RV-MT5B"]["family"], "family_2_same_premise_multiple_scorings")
        self.assertEqual(by_id["RV-Y4T5"]["family"], "family_2_same_premise_multiple_scorings")
        self.assertEqual(by_id["RV-ZPXV"]["family"], "family_3_hard_length_cap_truncation")
        self.assertEqual(by_id["RV-UAHS"]["family"], "family_3_hard_length_cap_truncation")
        self.assertIsNone(by_id["RV-RAJY"]["family"])
        self.assertIsNone(by_id["RV-8G8J"]["family"])
        self.assertIsNone(by_id["RV-XV9K"]["family"])


class ReasonKindClassificationTests(unittest.TestCase):
    def test_purely_nli_rejection_is_flagged_alone(self):
        result = recon.classify_reason_kinds([], ["nli_low_support:0.24"])
        self.assertTrue(result["withheld_by_nli_alone"])
        self.assertEqual(result["deterministic_guard_reasons"], [])
        self.assertEqual(result["nli_score_reasons"], ["nli_low_support:0.24"])

    def test_deterministic_plus_nli_is_not_flagged_as_nli_alone(self):
        reasons = ["text_too_long", "number_not_in_passage:6", "nli_low_support:0.05"]
        result = recon.classify_reason_kinds(["text_too_long", "number_not_in_passage:6"], reasons)
        self.assertFalse(result["withheld_by_nli_alone"])
        self.assertEqual(len(result["deterministic_guard_reasons"]), 2)
        self.assertEqual(result["nli_score_reasons"], ["nli_low_support:0.05"])

    def test_grounded_item_has_no_reasons_of_either_kind(self):
        result = recon.classify_reason_kinds([], [])
        self.assertFalse(result["had_any_deterministic_reason"])
        self.assertFalse(result["had_nli_score_reason"])
        self.assertFalse(result["withheld_by_nli_alone"])

    def test_nli_contradicted_reason_is_classified_as_an_nli_reason(self):
        result = recon.classify_reason_kinds([], ["nli_contradicted:0.60"])
        self.assertTrue(result["had_nli_score_reason"])
        self.assertFalse(result["had_any_deterministic_reason"])


class TruncationStatusTests(unittest.TestCase):
    def test_a_physically_truncated_candidate_is_flagged(self):
        text = "x" * 399 + ","  # exactly 400 chars, no terminal punctuation -- the real shape observed
        status = recon.truncation_status(text)
        self.assertTrue(status["physically_truncated_mid_word"])
        self.assertEqual(status["length"], 400)

    def test_a_long_but_complete_sentence_is_not_flagged_as_truncated(self):
        text = "x" * 578 + "."  # exceeds the 400-char cap but ends cleanly -- like RV-RAJY (579 chars)
        status = recon.truncation_status(text)
        self.assertFalse(status["physically_truncated_mid_word"])
        self.assertTrue(status["exceeds_screen_cap"])

    def test_a_short_complete_sentence_is_neither_truncated_nor_over_cap(self):
        status = recon.truncation_status("A short complete sentence.")
        self.assertFalse(status["physically_truncated_mid_word"])
        self.assertFalse(status["exceeds_screen_cap"])

    def test_real_rv_8g8j_and_rv_uahs_are_the_only_physically_truncated_items(self):
        _, coordinator_map, inventory_pairs = _real_setup()
        records = recon.build_reconciliation_records(
            recon.SUBMITTED_STRUCTURED_TRANSCRIPTION, coordinator_map, inventory_pairs
        )
        truncated = {r["opaque_id"] for r in records if r["truncation_status"]["physically_truncated_mid_word"]}
        self.assertEqual(truncated, {"RV-8G8J", "RV-UAHS"})

    def test_real_rv_rajy_and_rv_zpxv_exceed_cap_but_are_not_physically_truncated(self):
        _, coordinator_map, inventory_pairs = _real_setup()
        records = recon.build_reconciliation_records(
            recon.SUBMITTED_STRUCTURED_TRANSCRIPTION, coordinator_map, inventory_pairs
        )
        by_id = {r["opaque_id"]: r for r in records}
        for oid in ("RV-RAJY", "RV-ZPXV"):
            self.assertFalse(by_id[oid]["truncation_status"]["physically_truncated_mid_word"], oid)
            self.assertTrue(by_id[oid]["truncation_status"]["exceeds_screen_cap"], oid)


class MarkerRepairStatusTests(unittest.TestCase):
    def setUp(self):
        _, self.coordinator_map, self.inventory_pairs = _real_setup()
        self.records = recon.build_reconciliation_records(
            recon.SUBMITTED_STRUCTURED_TRANSCRIPTION, self.coordinator_map, self.inventory_pairs
        )
        self.by_id = {r["opaque_id"]: r for r in self.records}

    def test_c9_marker_variant_would_be_cleanly_stripped_under_current_code(self):
        m = self.by_id["RV-8WGZ"]["marker_repair_status"]
        self.assertEqual(m["marker_outcome"], "stripped_matches_unit_ids")
        self.assertTrue(m["would_change_screen_and_nli_input_under_current_code"])
        self.assertFalse(m["would_gain_new_conflict_reason_under_current_code"])

    def test_c9_no_marker_variant_is_unaffected_by_the_repair(self):
        m = self.by_id["RV-78DB"]["marker_repair_status"]
        self.assertEqual(m["marker_outcome"], "none")
        self.assertFalse(m["would_change_screen_and_nli_input_under_current_code"])

    def test_c11_live002_variant_would_also_be_cleanly_stripped(self):
        m = self.by_id["RV-MT5B"]["marker_repair_status"]
        self.assertEqual(m["marker_outcome"], "stripped_matches_unit_ids")
        self.assertTrue(m["would_change_screen_and_nli_input_under_current_code"])

    def test_c11_gate2_variant_has_no_marker_at_all(self):
        m = self.by_id["RV-Y4T5"]["marker_repair_status"]
        self.assertEqual(m["marker_outcome"], "none")

    def test_zpxv_and_rajy_have_a_marker_that_conflicts_rather_than_strips(self):
        # per-sentence, multi-marker candidates where only a SUBSET of unit_ids appears in the trailing
        # marker -- the repair does NOT clean these; it would add a NEW conflict reason under current code.
        for oid in ("RV-ZPXV", "RV-RAJY"):
            m = self.by_id[oid]["marker_repair_status"]
            self.assertEqual(m["marker_outcome"], "conflicts_with_unit_ids", oid)
            self.assertTrue(m["would_gain_new_conflict_reason_under_current_code"], oid)
            self.assertFalse(m["would_change_screen_and_nli_input_under_current_code"], oid)

    def test_xv9k_marker_would_also_be_cleanly_stripped(self):
        m = self.by_id["RV-XV9K"]["marker_repair_status"]
        self.assertEqual(m["marker_outcome"], "stripped_matches_unit_ids")
        self.assertTrue(m["would_change_screen_and_nli_input_under_current_code"])

    def test_truncated_items_have_no_trailing_marker(self):
        for oid in ("RV-8G8J", "RV-UAHS"):
            m = self.by_id[oid]["marker_repair_status"]
            self.assertEqual(m["marker_outcome"], "none", oid)

    def test_repair_status_never_claims_a_rescored_value(self):
        # structural: the returned dict has no score/support/contradiction key -- it reports INPUT change
        # only, never a predicted or claimed rescored NLI output.
        for r in self.records:
            self.assertNotIn("support", r["marker_repair_status"])
            self.assertNotIn("contradiction", r["marker_repair_status"])
            self.assertNotIn("predicted_score", r["marker_repair_status"])


class FreezeReceiptTests(unittest.TestCase):
    def test_freeze_receipt_does_not_set_locked_true(self):
        receipt = recon.build_freeze_receipt(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION)
        for oid, locked in receipt["all_submitted_locked_values"].items():
            self.assertFalse(locked, oid)

    def test_freeze_receipt_covers_all_nine_ids(self):
        receipt = recon.build_freeze_receipt(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION)
        self.assertEqual(len(receipt["frozen_opaque_ids"]), 9)

    def test_freeze_receipt_note_disclaims_confirming_a_lock(self):
        receipt = recon.build_freeze_receipt(recon.SUBMITTED_STRUCTURED_TRANSCRIPTION)
        self.assertIn("does NOT assert", receipt["note"])


class HistoricalVersusCurrentCodeDistinctionTests(unittest.TestCase):
    """Every historical record predates the citation-boundary repair -- these tests pin that no code path
    here claims an empirical rescore occurred."""

    def test_no_reconciliation_function_calls_the_nli_scorer(self):
        import inspect

        source = inspect.getsource(recon)
        # the only "entail"/model-shaped names anywhere in this module are inside docstrings/comments
        self.assertNotIn("support_and_contradiction_many(", source)
        self.assertNotIn("NLISupportScorer(", source)

    def test_historical_records_are_confirmed_to_predate_the_repair(self):
        _, coordinator_map, inventory_pairs = _real_setup()
        for p in inventory_pairs:
            self.assertTrue(p["raw_text_equals_scored_hypothesis"])  # the inventory's own predates-repair assertion


class WriteArtifactGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory(self):
        data = {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in recon.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    recon.write_artifact(base / protected, "x.json", data)

    def test_both_prior_run_directories_are_protected_here(self):
        self.assertIn("nli-candidate-reliability-study-001", recon.PROTECTED_RUN_DIRS)
        self.assertIn("nli-candidate-reliability-review-prep-001", recon.PROTECTED_RUN_DIRS)

    def test_this_passs_own_directory_is_not_self_protected(self):
        self.assertNotIn(recon.EVAL_DIR.name, recon.PROTECTED_RUN_DIRS)

    def test_refuses_to_overwrite_an_already_written_artifact(self):
        data = {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-new-eval"
            recon.write_artifact(run_dir, "x.json", data)
            with self.assertRaises(RuntimeError):
                recon.write_artifact(run_dir, "x.json", data)


if __name__ == "__main__":
    unittest.main()
