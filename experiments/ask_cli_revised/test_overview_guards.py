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


if __name__ == "__main__":
    unittest.main()
