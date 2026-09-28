"""The deterministic sentence screen: each known failure mode is withheld, and its faithful counterpart passes.

Screening can only withhold; a pass means the rules found no fault, never that the sentence is correct.
"""

import unittest

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import overview_guards as g
from experiments.ask_cli_revised.overview_test_support import (
    GIVING,
    HEDGE,
    NULL,
    OTHER_PAPER,
    PATTERN,
    S1,
    SHAPED,
    SHARED,
    sealed_ledger,
    stmt,
)

PARTS = {"s1-o1", "s2-o1", "s3-o1"}


def screen(text, passages, bears_on=()):
    """Reasons for one statement citing ``passages`` (each a fixture tuple), built from a real sealed ledger."""
    sealed = sealed_ledger([(f"claim {i}", p, [S1]) for i, p in enumerate(passages)])
    units, _ = oe.build_units(sealed)
    by_id = {u["unit_id"]: u for u in units}
    ids = [next(u["unit_id"] for u in units if u["passage"] == p[3]) for p in passages]
    return g.screen(stmt(text, ids, bears_on), units=by_id, part_ids=PARTS)


class ActorRecipientAndDirectionTests(unittest.TestCase):
    def test_faithful_restatement_passes(self):
        self.assertEqual(
            screen(
                "In one study the insular response to pictured scarring correlated with lower generosity toward the people pictured.",
                [GIVING],
            ),
            [],
        )

    def test_toward_rewritten_as_in_is_an_actor_recipient_reversal_and_is_withheld(self):
        reasons = screen(
            "In one study the insular response to pictured scarring correlated with lower generosity in the people pictured.",
            [GIVING],
        )
        self.assertEqual(reasons, ["preposition_shift:generosity:in!=toward"])  # names the word and both prepositions

    def test_the_reverse_swap_in_to_toward_is_also_withheld(self):
        passage = (11, 111, "e1", "Avoidance was observed in people with visible scarring.")
        self.assertEqual(screen("Avoidance was observed in people with visible scarring.", [passage]), [])
        reasons = screen("Avoidance was observed toward people with visible scarring.", [passage])
        self.assertTrue(any(r.startswith("preposition_shift") for r in reasons), reasons)

    def test_a_direction_the_passage_does_not_state_is_withheld(self):
        # the p4 structure: the passage says "linked to"; the sentence invents "reduced ... in people"
        reasons = screen("Avoidance is reduced in people with visible scarring.", [PATTERN])
        self.assertIn("direction_word_not_in_passage:reduced", reasons)
        self.assertEqual(
            screen("The authors described a behavioral pattern of avoidance linked to visible scarring.", [PATTERN]), []
        )

    def test_association_may_not_become_a_cause(self):
        reasons = screen(
            "The insular response to pictured scarring causes lower generosity toward the people pictured.", [GIVING]
        )
        self.assertTrue(any(r.startswith("causal_cue_not_in_passage") for r in reasons), reasons)


class HedgeNullAndInterventionTests(unittest.TestCase):
    def test_a_hedge_must_be_kept(self):
        self.assertIn(
            "hedge_dropped",
            screen("Training in perspective taking reduces avoidance of people with visible scarring.", [HEDGE]),
        )
        self.assertEqual(
            screen(
                "One paper suggests that training in perspective taking might reduce avoidance of people with visible scarring.",
                [HEDGE],
            ),
            [],
        )

    def test_an_intervention_idea_cannot_become_an_effectiveness_claim(self):
        reasons = screen("Perspective taking training is an effective intervention against avoidance.", [HEDGE])
        self.assertIn("hedge_dropped", reasons)
        self.assertTrue(any(r.startswith("causal_cue_not_in_passage") for r in reasons), reasons)

    def test_a_null_result_must_be_kept(self):
        self.assertIn("negation_dropped", screen("Implicit dislike of people with scarring was small.", [NULL]))
        self.assertEqual(
            screen(
                "Participants reported explicit dislike of people with scarring, but implicit dislike was small and not significant.",
                [NULL],
            ),
            [],
        )

    def test_a_negation_may_not_be_introduced(self):
        self.assertIn(
            "negation_introduced", screen("People with scarring were not disliked by participants.", [GIVING])
        )


class SubstitutionTests(unittest.TestCase):
    def test_culturally_shared_versus_shaped_is_withheld_in_both_directions(self):
        faithful = "Results suggest that the aversion is culturally shared across the three samples."
        self.assertEqual(screen(faithful, [SHARED]), [])
        swapped = screen(faithful.replace("shared", "shaped"), [SHARED])
        self.assertTrue(any(r.startswith("lookalike_substitution:shaped~shared") for r in swapped), swapped)
        reverse = screen(faithful.replace("shared", "shaped"), [SHAPED])
        self.assertEqual(reverse, [])  # faithful to a passage that really says shaped
        back = screen(faithful, [SHAPED])
        self.assertTrue(any(r.startswith("lookalike_substitution:shared~shaped") for r in back), back)

    def test_morphological_variants_are_not_substitutions(self):
        self.assertEqual(
            oe.lookalike_substitutions("The correlation was strong.", "It correlated with generosity."), []
        )


class InventionAndCorroborationTests(unittest.TestCase):
    def test_numbers_and_acronyms_may_not_appear_from_nowhere(self):
        self.assertIn("number_not_in_passage:87%", screen("Avoidance was reported by 87% of participants.", [PATTERN]))
        self.assertIn(
            "acronym_not_in_passage:EBQ", screen("Avoidance was measured with the EBQ questionnaire.", [PATTERN])
        )

    def test_repeated_citation_of_one_paper_is_not_corroboration(self):
        self.assertTrue(
            any(
                r.startswith("corroboration_language_single_source")
                for r in screen("Several studies report explicit dislike of people with scarring.", [NULL])
            )
        )
        two = screen("Several studies report explicit dislike of people with scarring.", [NULL, OTHER_PAPER])
        self.assertFalse(any(r.startswith("corroboration_language") for r in two), two)

    def test_too_many_invented_words_are_withheld(self):
        reasons = screen("Scarring provokes profound societal revulsion everywhere, entrenching prejudice.", [PATTERN])
        self.assertTrue(any(r.startswith("too_many_novel_terms") for r in reasons), reasons)

    def test_statements_about_absence_are_withheld(self):
        for text in (
            "There is no evidence about cross-cultural aversion.",
            "No studies examined cross-cultural aversion.",
            "The literature has not been examined.",
        ):
            self.assertIn("absence_claim", screen(text, [PATTERN]), text)


class StructureTests(unittest.TestCase):
    def test_bad_ids_and_tags_and_lengths(self):
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        units, _ = oe.build_units(sealed)
        by_id = {u["unit_id"]: u for u in units}
        ok = "The authors described a behavioral pattern of avoidance linked to visible scarring."
        self.assertEqual(g.screen(stmt(ok, ["U1"], ["s1-o1"]), units=by_id, part_ids=PARTS), [])
        self.assertTrue(
            any(r.startswith("unknown_unit_id") for r in g.screen(stmt(ok, ["U9"]), units=by_id, part_ids=PARTS))
        )
        self.assertIn("bad_unit_id_list", g.screen(stmt(ok, []), units=by_id, part_ids=PARTS))
        self.assertIn("bad_unit_id_list", g.screen(stmt(ok, ["U1", "U1"]), units=by_id, part_ids=PARTS))
        self.assertIn("bad_bears_on", g.screen(stmt(ok, ["U1"], ["not-a-part"]), units=by_id, part_ids=PARTS))
        self.assertIn("text_too_long", g.screen(stmt(ok + " x" * 300, ["U1"]), units=by_id, part_ids=PARTS))
        self.assertEqual(g.screen(stmt("   ", ["U1"]), units=by_id, part_ids=PARTS), ["empty_text"])


class NliTests(unittest.TestCase):
    def test_supported_passes_and_each_failure_has_its_own_code(self):
        self.assertEqual(g.nli_reasons(0.9, 0.05), [])
        self.assertEqual(g.nli_reasons(0.3, 0.1), ["nli_low_support:0.30"])
        self.assertEqual(g.nli_reasons(0.2, 0.9), ["nli_contradicted:0.90"])

    def test_an_embedding_fallback_has_no_contradiction_score_and_fails_closed(self):
        self.assertEqual(g.nli_reasons(0.95, None), ["nli_unavailable"])
        self.assertEqual(g.nli_reasons(None, None), ["nli_unavailable"])

    def test_pairs_are_passage_first_and_join_multiple_passages(self):
        sealed = sealed_ledger([("a", GIVING, [S1]), ("b", NULL, [S1])])
        units, _ = oe.build_units(sealed)
        by_id = {u["unit_id"]: u for u in units}
        premise, hypothesis = g.nli_pair(stmt("some statement here", ["U1", "U2"]), by_id)
        self.assertEqual(premise, GIVING[3] + " " + NULL[3])
        self.assertEqual(hypothesis, "some statement here")

    def test_pairs_accept_an_explicit_hypothesis_text_override(self):
        """The citation-marker-stripped hypothesis is substituted without touching proposal["text"] or the
        premise-joining logic -- omitting the argument reproduces today's exact behavior (the test above)."""
        sealed = sealed_ledger([("a", GIVING, [S1])])
        units, _ = oe.build_units(sealed)
        by_id = {u["unit_id"]: u for u in units}
        proposal = stmt("raw text with a marker (U1).", ["U1"])
        premise, hypothesis = g.nli_pair(proposal, by_id, hypothesis_text="raw text with a marker.")
        self.assertEqual(premise, GIVING[3])
        self.assertEqual(hypothesis, "raw text with a marker.")
        self.assertEqual(proposal["text"], "raw text with a marker (U1).", "the override must not mutate proposal")


class StripRedundantUnitMarkersTests(unittest.TestCase):
    """The citation-metadata boundary (NLI_REPAIR_DESIGN.md Section 2). Every case is pure text logic --
    zero model/NLI/network calls anywhere in this class."""

    def test_no_marker_present_is_a_no_op(self):
        r = g.strip_redundant_unit_markers("The scale measures fairness beliefs.", ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], "The scale measures fairness beliefs.")
        self.assertEqual(r["raw_text"], "The scale measures fairness beliefs.")
        self.assertIsNone(r["stripped_marker"])
        self.assertEqual(r["marker_outcome"], "none")
        self.assertIsNone(r["conflict_reason"])

    def test_exact_match_marker_is_stripped(self):
        r = g.strip_redundant_unit_markers("The scale measures fairness beliefs (U1).", ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], "The scale measures fairness beliefs.")
        self.assertEqual(r["raw_text"], "The scale measures fairness beliefs (U1).")
        self.assertEqual(r["stripped_marker"], " (U1)")
        self.assertEqual(r["marker_outcome"], "stripped_matches_unit_ids")
        self.assertIsNone(r["conflict_reason"])

    def test_exact_multi_unit_match_marker_is_stripped(self):
        r = g.strip_redundant_unit_markers("The finding held across conditions (U2, U3).", ["U2", "U3"])
        self.assertEqual(r["nli_hypothesis_text"], "The finding held across conditions.")
        self.assertEqual(r["marker_outcome"], "stripped_matches_unit_ids")

    def test_marker_order_does_not_matter_for_exact_match(self):
        r = g.strip_redundant_unit_markers("The finding held (U3, U2).", ["U2", "U3"])
        self.assertEqual(r["nli_hypothesis_text"], "The finding held.")
        self.assertEqual(r["marker_outcome"], "stripped_matches_unit_ids")

    def test_generic_non_citation_parenthetical_is_never_touched(self):
        text = "The scale measures fairness beliefs (see above)."
        r = g.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], text)
        self.assertEqual(r["marker_outcome"], "none")
        self.assertIsNone(r["conflict_reason"])

    def test_superset_marker_conflicts_and_is_not_stripped(self):
        text = "The scale measures fairness beliefs (U1, U2)."
        r = g.strip_redundant_unit_markers(text, ["U1"])  # only U1 is structurally cited
        self.assertEqual(r["nli_hypothesis_text"], text, "must not strip an inconsistent marker")
        self.assertEqual(r["marker_outcome"], "conflicts_with_unit_ids")
        self.assertIsNotNone(r["conflict_reason"])
        self.assertIn("U1,U2", r["conflict_reason"].replace(" ", ""))

    def test_subset_marker_conflicts_and_is_not_stripped(self):
        text = "The finding held across conditions (U2)."
        r = g.strip_redundant_unit_markers(text, ["U2", "U3"])  # marker is missing U3
        self.assertEqual(r["nli_hypothesis_text"], text)
        self.assertEqual(r["marker_outcome"], "conflicts_with_unit_ids")
        self.assertIsNotNone(r["conflict_reason"])

    def test_foreign_unit_id_in_marker_conflicts(self):
        text = "The scale measures fairness beliefs (U9)."
        r = g.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], text)
        self.assertEqual(r["marker_outcome"], "conflicts_with_unit_ids")
        self.assertIsNotNone(r["conflict_reason"])

    def test_duplicate_id_inside_marker_conflicts_rather_than_silently_passing(self):
        text = "The scale measures fairness beliefs (U1, U1)."
        r = g.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], text, "a malformed marker must never be stripped")
        self.assertEqual(r["marker_outcome"], "conflicts_with_unit_ids")
        self.assertIsNotNone(r["conflict_reason"], "a recognizable-but-malformed marker must fail with a reason")

    def test_marker_mixed_with_non_unit_prose_is_left_untouched_and_unflagged(self):
        """ "(U1, p. 4)" does not match the strict citation-marker shape at all -- distinguishing an ordinary
        parenthetical from something that purports to be a unit citation, per the design doc."""
        text = "The scale measures fairness beliefs (U1, p. 4)."
        r = g.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], text)
        self.assertEqual(r["marker_outcome"], "none")
        self.assertIsNone(r["conflict_reason"])

    def test_marker_embedded_mid_sentence_is_out_of_scope_and_left_untouched(self):
        """Only a TRAILING marker is recognized in this pass -- a disclosed, deliberate scope boundary (no
        real model output has ever placed one mid-sentence); see NLI_REPAIR_DESIGN.md Section 8."""
        text = "As shown (U1), the scale measures fairness beliefs in participants."
        r = g.strip_redundant_unit_markers(text, ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], text)
        self.assertEqual(r["marker_outcome"], "none")

    def test_acceptance_fixture_the_real_saved_c9_minimal_pair_strips_byte_for_byte(self):
        """The actual saved diagnostic candidates -- not retyped. Zero inference; pure text comparison only."""
        raw_b = (
            "Participants completed a Just World Beliefs Scale, which measures beliefs about interpersonal "
            "fairness toward oneself and others; the Interpersonal Reactivity Index, which measures cognitive "
            "(perspective taking) and affective (empathic concern) empathy; and a subscale from the "
            "Three-Domain Disgust scale that measures sensitivity to pathogen-related disgust (U1)."
        )
        expected_a = (
            "Participants completed a Just World Beliefs Scale, which measures beliefs about interpersonal "
            "fairness toward oneself and others; the Interpersonal Reactivity Index, which measures cognitive "
            "(perspective taking) and affective (empathic concern) empathy; and a subscale from the "
            "Three-Domain Disgust scale that measures sensitivity to pathogen-related disgust."
        )
        r = g.strip_redundant_unit_markers(raw_b, ["U1"])
        self.assertEqual(r["nli_hypothesis_text"], expected_a)
        self.assertEqual(r["raw_text"], raw_b, "raw text must be preserved byte-for-byte, unmodified")
        self.assertEqual(r["marker_outcome"], "stripped_matches_unit_ids")

    def test_the_real_saved_c11_marker_also_strips_correctly(self):
        raw_d = (
            "We presented 123 Hadza across ten camps pairs of morphed Hadza faces—each with one face "
            "altered to include a scar—and asked who they expected to be more moral and a better "
            "forager, noting that Hadza with greater exposure to other cultures expected the scarred face to "
            "be less moral (U2, U3)."
        )
        r = g.strip_redundant_unit_markers(raw_d, ["U2", "U3"])
        self.assertTrue(r["nli_hypothesis_text"].endswith("less moral."))
        self.assertNotIn("(U2, U3)", r["nli_hypothesis_text"])
        self.assertEqual(r["raw_text"], raw_d)
        self.assertEqual(r["marker_outcome"], "stripped_matches_unit_ids")


class ScreenFlagsUnitMarkerConflictsTests(unittest.TestCase):
    """The additional fail-closed requirement: `screen()` itself must withhold a proposal whose trailing marker
    conflicts with its structured unit_ids -- an inconsistency must never merely go un-stripped, it must also
    become ineligible."""

    def test_screen_withholds_a_proposal_whose_marker_conflicts_with_unit_ids(self):
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        units, _ = oe.build_units(sealed)
        by_id = {u["unit_id"]: u for u in units}
        text = "The authors described a behavioral pattern of avoidance linked to visible scarring (U9)."
        reasons = g.screen(stmt(text, ["U1"], []), units=by_id, part_ids=PARTS)
        self.assertTrue(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in reasons), reasons)

    def test_screen_does_not_flag_a_marker_that_exactly_matches_unit_ids(self):
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        units, _ = oe.build_units(sealed)
        by_id = {u["unit_id"]: u for u in units}
        text = "The authors described a behavioral pattern of avoidance linked to visible scarring (U1)."
        reasons = g.screen(stmt(text, ["U1"], []), units=by_id, part_ids=PARTS)
        self.assertFalse(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in reasons), reasons)

    def test_screen_does_not_flag_ordinary_text_with_no_marker(self):
        sealed = sealed_ledger([("c", PATTERN, [S1])])
        units, _ = oe.build_units(sealed)
        by_id = {u["unit_id"]: u for u in units}
        text = "The authors described a behavioral pattern of avoidance linked to visible scarring."
        reasons = g.screen(stmt(text, ["U1"], []), units=by_id, part_ids=PARTS)
        self.assertFalse(any(r.startswith("unit_marker_conflicts_with_unit_ids") for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
