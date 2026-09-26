"""Overview evidence units: deduplication by passage, lexical flags, eligibility, and claim-vs-passage novel terms."""

import copy
import unittest

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised.overview_test_support import (
    ABSENT,
    FRAGMENT,
    GIVING,
    HEDGE,
    NULL,
    OTHER_PAPER,
    PATTERN,
    S1,
    S2,
    STUDY,
    sealed_ledger,
)


class DeduplicationTests(unittest.TestCase):
    def test_claims_citing_one_passage_are_one_unit_not_corroboration(self):
        sealed = sealed_ledger(
            [("claim a", GIVING, [S1]), ("claim b", GIVING, [S1]), ("claim c", GIVING, [S2]), ("claim d", HEDGE, [S2])]
        )
        units, claims = oe.build_units(sealed)
        self.assertEqual(len(sealed["verified_propositions"]), 4)
        self.assertEqual(len(units), 2)  # 4 claims rest on 2 passages
        self.assertEqual(units[0]["proposition_ids"], ["p1", "p2", "p3"])
        self.assertEqual({c["unit_id"] for c in claims}, {"U1", "U2"})

    def test_attachments_are_recorded_per_passage_and_never_limit_use(self):
        sealed = sealed_ledger([("claim a", GIVING, [S1]), ("claim b", GIVING, [S2])])
        (unit,), _ = oe.build_units(sealed)
        self.assertEqual(unit["attached_children"], [S1, S2])  # the union of the coverage authority's judgments
        self.assertTrue(unit["eligibility"]["eligible"])  # eligible for use on ANY request part, not only attached ones

    def test_identical_text_in_another_chunk_of_one_paper_merges_but_another_paper_does_not(self):
        again = (GIVING[0], 999, "e1", GIVING[3])
        elsewhere = (77, 101, "e1", GIVING[3])
        sealed = sealed_ledger([("a", GIVING, [S1]), ("b", again, [S1]), ("c", elsewhere, [S1])])
        units, _ = oe.build_units(sealed)
        self.assertEqual(len(units), 2)
        self.assertEqual([loc["chunk_id"] for loc in units[0]["locators"]], [101, 999])
        self.assertEqual(units[1]["paper_id"], 77)

    def test_the_ledger_is_only_read(self):
        sealed = sealed_ledger([("a", GIVING, [S1]), ("b", FRAGMENT, [S2])])
        before = copy.deepcopy(sealed)
        oe.build_units(sealed)
        self.assertEqual(sealed, before)


class FlagTests(unittest.TestCase):
    def flags(self, text):
        return oe.passage_flags(text)

    def test_hedge_null_and_association(self):
        self.assertTrue(self.flags(HEDGE[3])["hedged"])
        self.assertTrue(self.flags(NULL[3])["negated"])
        self.assertTrue(self.flags(GIVING[3])["correlational"])
        self.assertFalse(self.flags(PATTERN[3])["hedged"])

    def test_fragment_is_a_missing_terminal_not_a_trailing_citation_or_closer(self):
        self.assertTrue(self.flags(FRAGMENT[3])["fragment"])
        self.assertTrue(self.flags("It ended on a dangling word and")["fragment"])
        for whole in (
            "A complete finding.",
            "A complete finding.12",
            "A complete finding.)",
            'He said "a complete finding."',
            "Was it complete?",
        ):
            self.assertFalse(self.flags(whole)["fragment"], whole)

    def test_a_mid_sentence_start_is_noted(self):
        self.assertTrue(self.flags(FRAGMENT[3])["starts_mid_sentence"])
        self.assertFalse(self.flags(GIVING[3])["starts_mid_sentence"])

    def test_study_description_is_not_a_finding_but_a_null_result_is_still_a_finding(self):
        self.assertTrue(self.flags(STUDY[3])["study_description"])
        self.assertFalse(self.flags(NULL[3])["study_description"])
        self.assertFalse(self.flags(GIVING[3])["study_description"])
        self.assertFalse(self.flags("This study found that dislike was stronger in older adults.")["study_description"])

    def test_absence_statement_is_a_scope_statement_not_a_null_result(self):
        self.assertTrue(self.flags(ABSENT[3])["absence_statement"])
        self.assertFalse(
            self.flags(NULL[3])["absence_statement"]
        )  # "not significant" is a result, not an absence of study

    def test_causal_wording_is_listed(self):
        # the words as written (for the reader), not stemmer output; the guards compare stems separately
        self.assertEqual(
            self.flags("Training reduced avoidance because it produced empathy.")["causal_cues"],
            ["because", "produced"],
        )
        self.assertEqual(self.flags(GIVING[3])["causal_cues"], [])


class EligibilityTests(unittest.TestCase):
    def reasons(self, passage, attached=(S1,)):
        sealed = sealed_ledger([("claim", passage, list(attached))])
        (unit,), _ = oe.build_units(sealed)
        return unit["eligibility"]["reasons"]

    def test_a_faithful_attached_finding_is_eligible(self):
        self.assertEqual(self.reasons(GIVING), [])
        self.assertEqual(self.reasons(HEDGE), [])  # hedged is eligible; the screen keeps the hedge
        self.assertEqual(self.reasons(NULL), [])

    def test_each_exclusion_has_its_own_reason(self):
        self.assertEqual(self.reasons(GIVING, attached=()), ["no_coverage_attachment"])
        self.assertEqual(self.reasons(FRAGMENT), ["truncated_passage"])
        self.assertEqual(self.reasons(STUDY), ["study_description_only"])
        self.assertEqual(self.reasons(ABSENT), ["absence_statement"])
        long_passage = (11, 601, "e1", "The response correlated with generosity. " * 20)
        self.assertEqual(self.reasons(long_passage), ["passage_too_long"])

    def test_a_catalog_mismatch_is_excluded(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        sealed["evidence_spans"][0]["text"] = "not the quote"
        (unit,), _ = oe.build_units(sealed)
        self.assertEqual(unit["eligibility"]["reasons"], ["catalog_mismatch"])


class NovelTermTests(unittest.TestCase):
    def test_a_claim_that_adds_a_direction_its_passage_lacks_is_flagged(self):
        # the p4 structure: the passage says only "linked to"; the claim adds a direction and a population
        self.assertEqual(
            oe.novel_terms("Avoidance is reduced in people with visible scarring.", PATTERN[3]), ["reduced"]
        )
        self.assertEqual(oe.novel_terms("Avoidance is linked to visible scarring.", PATTERN[3]), [])

    def test_a_soft_hyphen_line_break_is_not_a_novel_term(self):
        broken = "Knowledge of empathy and disgust sen­ sitivity might help."
        self.assertEqual(oe.novel_terms("Disgust sensitivity might help.", broken), [])

    def test_word_forms_of_one_stem_agree(self):
        self.assertEqual(
            oe.novel_terms("Prosociality manifests behaviorally.", "A behavioral manifestation of prosocial acts."), []
        )

    def test_novel_terms_are_reported_per_claim_in_the_units_output(self):
        sealed = sealed_ledger(
            [
                ("Avoidance is reduced in people with scarring.", PATTERN, [S1]),
                ("Avoidance is linked to scarring.", PATTERN, [S1]),
            ]
        )
        _, claims = oe.build_units(sealed)
        self.assertEqual([c["novel_terms"] for c in claims], [["reduced"], []])
        self.assertEqual(OTHER_PAPER[0], 15)  # fixture sanity


if __name__ == "__main__":
    unittest.main()
