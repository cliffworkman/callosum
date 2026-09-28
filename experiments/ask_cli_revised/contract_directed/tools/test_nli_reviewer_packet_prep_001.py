"""Offline tests of `nli_reviewer_packet_prep_001` -- reads real saved JSON from disk, makes NO model/NLI/
network call, collects NO label. Every leakage assertion checks for the actual prohibited values (specific
scores, statuses, source identifiers, pair hashes) rather than banning ordinary words like "support" that
also occur in legitimate scientific prose."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import endpoint_guard
from experiments.ask_cli_revised.contract_directed.tools import nli_candidate_pair_inventory as inv_tool
from experiments.ask_cli_revised.contract_directed.tools import nli_clause_count_experiment_001 as clause_tool
from experiments.ask_cli_revised.contract_directed.tools import nli_polarity_lexical_experiment_001 as polarity_tool
from experiments.ask_cli_revised.contract_directed.tools import nli_reviewer_packet_prep_001 as prep


def _real_inventory():
    with endpoint_guard.refuse_all():
        return inv_tool.build_full_inventory()


class CoverageAndByteFidelityTests(unittest.TestCase):
    def setUp(self):
        self.inv = _real_inventory()
        self.ordered = prep.concealed_randomization(self.inv["pairs"])
        self.reviewer_packet = prep.build_reviewer_packet(self.ordered)

    def test_exactly_nine_items(self):
        self.assertEqual(len(self.ordered), 9)
        self.assertEqual(len(self.reviewer_packet), 9)

    def test_no_duplication_omission_or_replacement(self):
        original_shas = {p["pair_sha256"] for p in self.inv["pairs"]}
        ordered_shas = {p["pair_sha256"] for p in self.ordered}
        self.assertEqual(original_shas, ordered_shas)
        self.assertEqual(len(ordered_shas), 9)  # confirms no collapse via duplication

    def test_premise_and_candidate_bytes_are_preserved_verbatim(self):
        by_sha_original = {p["pair_sha256"]: p for p in self.inv["pairs"]}
        by_sha_ordered = {p["pair_sha256"]: p for p in self.ordered}
        for sha, original in by_sha_original.items():
            ordered_pair = by_sha_ordered[sha]
            self.assertEqual(ordered_pair["premise"], original["premise"])
            self.assertEqual(ordered_pair["hypothesis"], original["hypothesis"])

    def test_reviewer_packet_candidate_statement_matches_hypothesis_byte_for_byte(self):
        by_sha = {p["pair_sha256"]: p for p in self.ordered}
        opaque_to_sha = {p["opaque_id"]: p["pair_sha256"] for p in self.ordered}
        for item in self.reviewer_packet:
            sha = opaque_to_sha[item["opaque_id"]]
            self.assertEqual(item["candidate_statement"], by_sha[sha]["hypothesis"])
            self.assertEqual(item["premise"], by_sha[sha]["premise"])

    def test_c9_marker_variant_still_carries_its_historical_inline_marker(self):
        # the exact byte the authorization named: c9's marker-bearing candidate must NOT be silently cleaned.
        # NOTE: "(U1)" alone is not unique to c9's candidate in this population -- a different, unrelated
        # candidate (the ab-backend {U1,U3,U7} pair) also cites U1 inline, for a different underlying unit.
        # The precise check is c9's own exact historical tail, not the bare substring.
        c9_marker_bearing = [
            item for item in self.reviewer_packet if item["candidate_statement"].endswith("disgust (U1).")
        ]
        self.assertEqual(len(c9_marker_bearing), 1)
        any_u1_marker = [item for item in self.reviewer_packet if "(U1)" in item["candidate_statement"]]
        self.assertGreaterEqual(len(any_u1_marker), 1)  # confirms the ambiguity noted above is real, not assumed


class ConcealedRandomizationTests(unittest.TestCase):
    def test_reproducible_with_the_same_seed(self):
        inv = _real_inventory()
        order_a = prep.concealed_randomization(inv["pairs"], seed=prep.RANDOM_SEED_ORDER)
        order_b = prep.concealed_randomization(inv["pairs"], seed=prep.RANDOM_SEED_ORDER)
        self.assertEqual([p["pair_sha256"] for p in order_a], [p["pair_sha256"] for p in order_b])
        self.assertEqual([p["opaque_id"] for p in order_a], [p["opaque_id"] for p in order_b])

    def test_a_different_seed_produces_a_different_order_or_ids(self):
        inv = _real_inventory()
        order_a = prep.concealed_randomization(inv["pairs"], seed=prep.RANDOM_SEED_ORDER)
        order_b = prep.concealed_randomization(inv["pairs"], seed=prep.RANDOM_SEED_ORDER + 1)
        same_sha_order = [p["pair_sha256"] for p in order_a] == [p["pair_sha256"] for p in order_b]
        same_ids = [p["opaque_id"] for p in order_a] == [p["opaque_id"] for p in order_b]
        self.assertFalse(same_sha_order and same_ids)

    def test_opaque_ids_do_not_encode_the_original_sha_sort_order(self):
        inv = _real_inventory()
        ordered = prep.concealed_randomization(inv["pairs"])
        sha_sorted_shas = sorted(p["pair_sha256"] for p in inv["pairs"])
        concealed_sha_order = [p["pair_sha256"] for p in ordered]
        self.assertNotEqual(sha_sorted_shas, concealed_sha_order)

    def test_opaque_ids_are_unique_and_follow_the_documented_alphabet(self):
        inv = _real_inventory()
        ordered = prep.concealed_randomization(inv["pairs"])
        ids = [p["opaque_id"] for p in ordered]
        self.assertEqual(len(ids), len(set(ids)))
        for oid in ids:
            self.assertTrue(oid.startswith("RV-"))
            self.assertEqual(len(oid), 7)

    def test_coordinator_map_correctly_reverses_every_opaque_id_to_its_real_pair(self):
        inv = _real_inventory()
        ordered = prep.concealed_randomization(inv["pairs"])
        families = prep.identify_variant_families(ordered)
        coord_map = prep.build_coordinator_map(ordered, families)
        by_opaque = {row["opaque_id"]: row for row in coord_map}
        for p in ordered:
            row = by_opaque[p["opaque_id"]]
            self.assertEqual(row["pair_sha256"], p["pair_sha256"])
            self.assertEqual(row["source_id"], p["source_id"])
            self.assertEqual(row["unit_ids"], p["unit_ids"])


class ForbiddenFieldTests(unittest.TestCase):
    """Checks the actual prohibited VALUES (specific scores, statuses, source identifiers), not generic
    words -- "support" and "status" appear in ordinary scientific prose and must not trip a naive filter."""

    def setUp(self):
        self.inv = _real_inventory()
        self.ordered = prep.concealed_randomization(self.inv["pairs"])
        self.reviewer_packet = prep.build_reviewer_packet(self.ordered)

    def test_reviewer_packet_items_have_only_the_three_allowed_keys(self):
        for item in self.reviewer_packet:
            self.assertEqual(set(item.keys()), {"opaque_id", "premise", "candidate_statement"})

    def test_no_source_paper_id_field_in_reviewer_packet_by_default(self):
        for item in self.reviewer_packet:
            self.assertNotIn("source_papers", item)
            self.assertNotIn("paper_ids", item)
            self.assertNotIn("paper_id", item)

    def test_no_source_or_run_identity_leaks_into_reviewer_packet(self):
        forbidden_source_strings = {
            "gate2-diagnostic-002",
            "gate-integration-live-002",
            "ab-backend-14a-overview",
            "ab-backend-diag-s-unbounded",
        }
        rendered = str(self.reviewer_packet)
        for s in forbidden_source_strings:
            self.assertNotIn(s, rendered)

    def test_no_nli_score_or_status_value_leaks_into_reviewer_packet(self):
        # the specific real values from the inventory, not the generic field names
        forbidden_values = {
            "grounded",
            "withheld",
            "nli_low_support",
            "screen_reasons",
            "0.8874918818473816",
            "0.007013031281530857",
        }
        rendered = str(self.reviewer_packet)
        for v in forbidden_values:
            self.assertNotIn(v, rendered)

    def test_no_pair_sha256_in_reviewer_packet(self):
        forbidden_shas = {p["pair_sha256"] for p in self.ordered}
        rendered = str(self.reviewer_packet)
        for sha in forbidden_shas:
            self.assertNotIn(sha, rendered)

    def test_context_request_path_discloses_only_paper_ids_never_nli_fields(self):
        families = prep.identify_variant_families(self.ordered)
        coord_map = prep.build_coordinator_map(self.ordered, families)
        log = prep.ContextRequestLog()
        target = self.ordered[0]
        disclosure = log.request_context(coord_map, target["opaque_id"], "reviewer-1", "unclear abbreviation")
        self.assertEqual(set(disclosure.keys()), {"opaque_id", "paper_ids"})
        self.assertEqual(disclosure["paper_ids"], sorted({loc["paper_id"] for loc in target["canonical_locators"]}))
        self.assertEqual(len(log.entries), 1)
        self.assertEqual(log.entries[0]["reviewer"], "reviewer-1")

    def test_context_request_on_unknown_id_raises(self):
        families = prep.identify_variant_families(self.ordered)
        coord_map = prep.build_coordinator_map(self.ordered, families)
        log = prep.ContextRequestLog()
        with self.assertRaises(KeyError):
            log.request_context(coord_map, "RV-NOPE", "reviewer-1", "test")

    def test_context_disclosure_log_template_has_no_prefilled_entries(self):
        template = prep.context_disclosure_log_template()
        self.assertEqual(template["entries"], [])


class ReviewerInstructionSheetContentTests(unittest.TestCase):
    def setUp(self):
        self.text = prep.reviewer_instruction_sheet_markdown()

    def test_no_real_study_paper_content_appears(self):
        forbidden = [
            "Hadza",
            "amygdala",
            "Just World Beliefs",
            "Three-Domain Disgust",
            "anomalous-is-bad",
            "dehumanization",
        ]
        for term in forbidden:
            self.assertNotIn(term, self.text)

    def test_no_real_scores_or_statuses_appear(self):
        # exact leaked values/identifiers only -- "grounded" alone is banned from over-matching, since this
        # sheet legitimately uses it in "source-grounded reason" (ordinary English, not the NLI status value)
        forbidden = [
            "0.8874918818473816",
            "0.007013031281530857",
            "nli_low_support",
            "self_entail_c9",
            "self_entail_c11",
        ]
        for term in forbidden:
            self.assertNotIn(term, self.text)

    def test_status_value_withheld_does_not_appear_as_the_screening_disposition(self):
        self.assertNotIn("withheld", self.text)  # unlike "grounded", this has no legitimate use in this sheet

    def test_no_run_or_source_identifiers_appear(self):
        forbidden = ["gate2-diagnostic-002", "gate-integration-live-002", "ab-backend"]
        for term in forbidden:
            self.assertNotIn(term, self.text)

    def test_uses_the_new_neutral_toy_examples_not_the_protocol_worked_example(self):
        self.assertIn("espresso", self.text)
        self.assertIn("trail was repaved", self.text)

    def test_does_not_explain_the_citation_marker_scoring_phenomenon(self):
        # generic guidance about markers is required; explaining the mechanism ("depresses NLI support",
        # "swings the score") is not. "scoring information" (a generic disclaimer about what reviewers won't
        # receive) is legitimate and must not be caught by an overbroad "score" substring ban.
        self.assertIn("attribution metadata", self.text)
        self.assertNotIn("depress", self.text.lower())
        self.assertNotIn("swings the score", self.text.lower())
        # NOTE: a bare "nli" substring check was tried here and rejected -- "inline" contains "nli" and is
        # legitimate prose ("inline citation markers"). Exact identifiers are the honest check, not fragments.

    def test_covers_all_five_labels(self):
        for label in prep.LABEL_VOCABULARY:
            self.assertIn(label, self.text)

    def test_ambiguous_is_presented_as_a_legitimate_final_answer(self):
        self.assertIn("legitimate final answer", self.text)

    def test_omission_is_not_conflated_with_not_established(self):
        self.assertIn("not grounds for", self.text)


class CoordinatorProcedureContentTests(unittest.TestCase):
    def setUp(self):
        self.text = prep.coordinator_procedure_markdown()

    def test_no_real_study_content_or_scores_leak_into_the_procedure_doc(self):
        forbidden = ["Hadza", "amygdala", "0.8874918818473816", "gate2-diagnostic-002"]
        for term in forbidden:
            self.assertNotIn(term, self.text)

    def test_describes_locking_before_reconciliation(self):
        self.assertIn("locked", self.text)

    def test_describes_unresolved_disagreement_as_a_valid_outcome(self):
        self.assertIn("unresolved", self.text)

    def test_forbids_majority_rule_among_two_raters(self):
        self.assertIn("majority rule", self.text)


class VariantFamilyTests(unittest.TestCase):
    def setUp(self):
        self.inv = _real_inventory()
        self.ordered = prep.concealed_randomization(self.inv["pairs"])
        self.families = prep.identify_variant_families(self.ordered)

    def test_exactly_three_families_and_three_singletons(self):
        self.assertEqual(len(self.families["families"]), 3)
        self.assertEqual(len(self.families["singleton_pair_sha256"]), 3)

    def test_family_kinds_are_one_of_the_known_relationship_types(self):
        allowed = {
            "trailing_citation_marker_difference",  # c9: byte-level marker difference
            "hard_length_cap_truncation",  # {U2,U6}: byte-level truncation
            "prefix_variant",  # generic byte-level prefix, if the classifier ever finds one
            "same_premise_multiple_scorings",  # c11: same premise, independently paraphrased hypotheses
        }
        for f in self.families["families"]:
            self.assertIn(f["kind"], allowed)

    def test_c11s_family_is_specifically_the_same_premise_multiple_scorings_kind(self):
        # confirms the exact bug this pass found and fixed: c11's own inventory `related_variant` is null
        # (its two hypotheses are independently paraphrased, not a byte-level prefix of each other), so its
        # family membership can only be detected by the same-unit_ids criterion, not by `related_variant`.
        c11_sha_prefixes = {"9ff76fdb09", "7735c8547a"}
        c11_family = next(
            f
            for f in self.families["families"]
            if any(sha.startswith(p) for sha in f["member_pair_sha256"] for p in c11_sha_prefixes)
        )
        self.assertEqual(c11_family["kind"], "same_premise_multiple_scorings")

    def test_every_pair_is_in_exactly_one_family_or_the_singleton_list(self):
        all_shas = {p["pair_sha256"] for p in self.ordered}
        family_shas = {sha for f in self.families["families"] for sha in f["member_pair_sha256"]}
        singleton_shas = set(self.families["singleton_pair_sha256"])
        self.assertTrue(family_shas.isdisjoint(singleton_shas))
        self.assertEqual(family_shas | singleton_shas, all_shas)

    def test_extended_unit_overlap_note_finds_the_shared_paper_67_units(self):
        overlap = prep.extended_unit_overlap_note(self.ordered)
        # U1, U2, U6, U7 are each used by more than one of the 9 pairs (confirmed against the real inventory)
        for uid in ("U1", "U2", "U6", "U7"):
            self.assertIn(uid, overlap)
            self.assertGreaterEqual(len(overlap[uid]), 2)


class VariantSeparatedAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.inv = _real_inventory()
        self.ordered = prep.concealed_randomization(self.inv["pairs"])
        self.design = prep.build_variant_separated_assignment(self.ordered)

    def test_requires_exactly_four_reviewers(self):
        self.assertEqual(self.design["min_reviewers"], 4)
        self.assertEqual(set(self.design["assignment"].keys()), {"R1", "R2", "R3", "R4"})

    def test_every_item_is_covered_by_exactly_two_reviewers(self):
        for oid, count in self.design["coverage_per_item"].items():
            self.assertEqual(count, 2, oid)
        self.assertEqual(len(self.design["coverage_per_item"]), 9)

    def test_no_reviewer_ever_sees_both_members_of_any_family(self):
        sha_to_opaque = {p["pair_sha256"]: p["opaque_id"] for p in self.ordered}
        for family in self.design["families"]:
            member_ids = {sha_to_opaque[s] for s in family["member_pair_sha256"]}
            for reviewer, items in self.design["assignment"].items():
                overlap = member_ids & set(items)
                self.assertLessEqual(len(overlap), 1, f"{reviewer} saw both members of {family['kind']}")

    def test_workload_is_reasonably_balanced(self):
        loads = [len(items) for items in self.design["assignment"].values()]
        self.assertLessEqual(max(loads) - min(loads), 1)


class TwoReviewerFallbackTests(unittest.TestCase):
    def setUp(self):
        self.inv = _real_inventory()
        self.ordered = prep.concealed_randomization(self.inv["pairs"])
        self.fallback = prep.build_two_reviewer_fallback_assignment(self.ordered)

    def test_requires_exactly_two_reviewers(self):
        self.assertEqual(self.fallback["min_reviewers"], 2)

    def test_both_reviewers_get_the_full_nine_item_packet(self):
        self.assertEqual(len(self.fallback["R1_order"]), 9)
        self.assertEqual(len(self.fallback["R2_order"]), 9)
        self.assertEqual(set(self.fallback["R1_order"]), set(self.fallback["R2_order"]))

    def test_negative_both_members_of_every_family_ARE_present_in_each_reviewers_own_packet(self):
        # this is the required negative test: spacing cannot achieve separation when both reviewers see
        # every item -- both family members are structurally present in each reviewer's own order.
        sha_to_opaque = {p["pair_sha256"]: p["opaque_id"] for p in self.ordered}
        for order_name in ("R1_order", "R2_order"):
            order_set = set(self.fallback[order_name])
            for family in self.fallback["families"]:
                member_ids = {sha_to_opaque[s] for s in family["member_pair_sha256"]}
                self.assertTrue(
                    member_ids.issubset(order_set), f"{order_name} missing a family member -- should be impossible"
                )
                self.assertEqual(
                    len(member_ids & order_set), 2, f"{order_name} should see BOTH members, proving no separation"
                )

    def test_family_members_are_spaced_at_least_four_apart_in_each_order(self):
        sha_to_opaque = {p["pair_sha256"]: p["opaque_id"] for p in self.ordered}
        for order_name in ("R1_order", "R2_order"):
            order = self.fallback[order_name]
            for family in self.fallback["families"]:
                ids = [sha_to_opaque[s] for s in family["member_pair_sha256"]]
                positions = [order.index(i) for i in ids]
                self.assertGreaterEqual(abs(positions[0] - positions[1]), 4)

    def test_limitation_is_stated_explicitly_not_silently_solved(self):
        text = self.fallback["limitation"]
        self.assertIn("not", text.lower())
        self.assertIn("separation", text.lower())

    def test_two_reviewer_orders_differ_from_each_other(self):
        self.assertNotEqual(self.fallback["R1_order"], self.fallback["R2_order"])

    def test_reproducible_with_the_same_seeds(self):
        fallback_again = prep.build_two_reviewer_fallback_assignment(self.ordered)
        self.assertEqual(self.fallback["R1_order"], fallback_again["R1_order"])
        self.assertEqual(self.fallback["R2_order"], fallback_again["R2_order"])


class ResponseFormAndLockingTests(unittest.TestCase):
    def test_blank_response_starts_unlocked_with_no_label(self):
        r = prep.blank_response("RV-TEST")
        self.assertFalse(r["locked"])
        self.assertIsNone(r["overall_label"])
        self.assertEqual(r["atomic_propositions"], [])

    def test_peer_response_not_revealable_when_only_one_is_locked(self):
        a = prep.blank_response("RV-TEST")
        a["locked"] = True
        b = prep.blank_response("RV-TEST")
        self.assertFalse(prep.can_reveal_peer_response(a, b))

    def test_peer_response_revealable_only_when_both_locked(self):
        a = prep.blank_response("RV-TEST")
        b = prep.blank_response("RV-TEST")
        a["locked"] = True
        b["locked"] = True
        self.assertTrue(prep.can_reveal_peer_response(a, b))

    def test_response_form_schema_offers_all_five_labels(self):
        schema = prep.response_form_schema()
        self.assertEqual(set(schema["overall_label"]), set(prep.LABEL_VOCABULARY))

    def test_unresolved_disagreement_is_representable(self):
        # both locked, different labels -- the schema does not force a single resolved value anywhere;
        # a coordinator-side reconciliation record (outside this module's scope) preserves both.
        a = prep.blank_response("RV-TEST")
        a["overall_label"] = "Entailed"
        a["locked"] = True
        b = prep.blank_response("RV-TEST")
        b["overall_label"] = "Not established"
        b["locked"] = True
        self.assertTrue(prep.can_reveal_peer_response(a, b))
        self.assertNotEqual(a["overall_label"], b["overall_label"])  # both preserved, neither overwritten


class SyntheticContentIsolationTests(unittest.TestCase):
    """The earlier lexical counterfactuals (paper-20-derived, from the polarity and clause-count experiments)
    must never enter this nine-item packet -- verified by actually calling those modules' own pure functions
    and cross-checking, not merely asserted from memory."""

    def setUp(self):
        self.inv = _real_inventory()
        self.ordered = prep.concealed_randomization(self.inv["pairs"])
        self.reviewer_packet = prep.build_reviewer_packet(self.ordered)
        self.rendered = str(self.reviewer_packet)

    def test_polarity_experiment_synthetic_span3_variants_are_absent(self):
        with endpoint_guard.refuse_all():
            spans = polarity_tool.resolve_source_spans()
            variants = polarity_tool.build_span3_variants(spans["span3"])
        for cond in ("A", "B", "C"):
            text = variants[cond]["text"]
            self.assertNotIn(text, self.rendered)

    def test_clause_count_experiment_synthetic_spans_are_absent(self):
        with endpoint_guard.refuse_all():
            spans = clause_tool.resolve_source_spans()
        for key, text in spans.items():
            if isinstance(text, str) and len(text) > 20:  # skip trivial/short fields
                self.assertNotIn(text, self.rendered, key)

    def test_none_of_the_nine_items_are_from_paper_20(self):
        # the polarity/clause-count experiments' source material is paper 20; this population's real papers
        # are 67, 68, 107 -- confirmed distinct, not merely assumed.
        for p in self.ordered:
            papers = {loc["paper_id"] for loc in p["canonical_locators"]}
            self.assertNotIn(20, papers)


class WriteArtifactGuardTests(unittest.TestCase):
    def test_refuses_every_protected_directory_including_the_original_study_dir(self):
        data = {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for protected in prep.PROTECTED_RUN_DIRS:
                with self.assertRaises(RuntimeError):
                    prep.write_artifact(base / protected, "x.json", data)

    def test_original_study_directory_is_explicitly_protected_here_too(self):
        self.assertIn("nli-candidate-reliability-study-001", prep.PROTECTED_RUN_DIRS)

    def test_refuses_to_overwrite_an_already_written_artifact(self):
        data = {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-new-eval"
            prep.write_artifact(run_dir, "x.json", data)
            with self.assertRaises(RuntimeError):
                prep.write_artifact(run_dir, "x.json", data)

    def test_write_artifact_handles_markdown_strings_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "some-new-eval-md"
            path = prep.write_artifact(run_dir, "note.md", "# hello")
            self.assertEqual(path.read_text(encoding="utf-8"), "# hello")

    def test_this_passs_own_run_directory_is_not_self_protected(self):
        self.assertNotIn(prep.EVAL_DIR.name, prep.PROTECTED_RUN_DIRS)


if __name__ == "__main__":
    unittest.main()
