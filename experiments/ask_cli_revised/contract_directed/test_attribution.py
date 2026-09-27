import sqlite3
import unittest

from experiments.ask_cli_revised.contract_directed import abstracts, freeze
from experiments.ask_cli_revised.contract_directed import attribution as at

DB = freeze.SLICE_ROOT / "library.sqlite"

U1 = (
    "This research confirmed earlier reports that people with anomalous faces are imbued with negative personality "
    "characteristics, detected explicit biases against people with facial anomalies, and described a behavioral "
    "manifestation of the “anomalous-is- bad” stereotype affecting prosociality."
)
U2 = (
    "Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger "
    "just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality "
    "toward people with facial anomalies."
)
U3 = (
    "Nevertheless, we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people "
    "with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit "
    "Bias Questionnaire)."
)
U5 = (
    "Having knowledge about individual differences in empathy and disgust sen- sitivity might improve decision-making and "
    "reduce bias toward people with anomalous faces."
)
U6 = (
    "We suggest that dehumanization is underpinned by a suite of negative attitudes (IAT and EBQ), social cognitive biases "
    "(just-world beliefs), emotional dispositions (affective empathy), and undesirable behaviors (less generosity in the "
    "DG)—all factors associated with the functioning of the left amygdala."
)
U7 = "An “anomalous-is-bad” stereotype is expressed in negative attitudes about peo- ple with facial anomalies."
RESULTS_35041 = (
    "For prosocial behavior assessed with the Dictator Game, there was a significant interaction between face type, SES, "
    "and difference between payoffs (β = −1.002, SE = 0.464, z = −2.158, P = 0.031; see Table S6)."
)


class AbstractCleaningTests(unittest.TestCase):
    def test_jats_markup_is_stripped_and_raw_is_untouched(self):
        raw = "<jats:title>Abstract</jats:title>\n   <jats:p>People have a stereotype &amp; it matters.</jats:p>"
        self.assertEqual(abstracts.clean_abstract(raw), "People have a stereotype & it matters.")
        self.assertIn("<jats:p>", raw)
        self.assertEqual(abstracts.abstract_state(raw), "present")
        self.assertEqual(abstracts.abstract_state(None), "absent")
        self.assertEqual(abstracts.abstract_state("   "), "absent")


class AttributionCueTests(unittest.TestCase):
    def state(self, *texts, **kw):
        return at.derive_attribution(list(texts), **kw)

    def test_explicit_first_person_report_is_own_established(self):
        self.assertEqual(self.state(U3)["state"], at.OWN_ESTABLISHED)

    def test_reported_statistics_are_an_own_basis(self):
        result = self.state(RESULTS_35041)
        self.assertEqual(result["state"], at.OWN_ESTABLISHED)
        self.assertIn("result_statistics", result["bases"])

    def test_bare_declarative_recital_stays_unresolved(self):
        self.assertEqual(self.state(U7, section="introduction")["state"], at.UNRESOLVED)

    def test_hedged_proposal_without_an_own_report_is_speculation(self):
        self.assertEqual(self.state(U5)["state"], at.SPECULATION)

    def test_first_person_interpretation_is_speculation_not_a_finding(self):
        self.assertEqual(self.state(U6)["state"], at.SPECULATION)

    def test_own_report_mixed_with_a_recital_of_earlier_reports_is_mixed(self):
        result = self.state(U1)
        self.assertEqual(result["state"], at.MIXED)
        self.assertTrue(result["cues"]["own"] and result["cues"]["prior"])

    def test_recount_of_other_work_is_other_study_in_any_section(self):
        for section in ("introduction", "results", "discussion"):
            self.assertEqual(self.state("Prior studies have shown a link.", section=section)["state"], at.OTHER_STUDY)
        self.assertEqual(self.state("Smith et al. (2019) reported a strong effect.")["state"], at.OTHER_STUDY)

    def test_section_labels_are_clues_not_gates(self):
        preview = self.state("In the present study, we found a strong effect.", section="introduction")
        self.assertEqual(preview["state"], at.OWN_ESTABLISHED)
        self.assertIn("own_claim_in_introduction_preview", preview["flags"])
        recital = self.state("Earlier work has shown a strong effect.", section="discussion")
        self.assertEqual(recital["state"], at.OTHER_STUDY)
        self.assertIn("other_study_recital_in_discussion", recital["flags"])

    def test_hedge_on_an_own_result_is_kept_and_flagged_not_demoted(self):
        result = self.state("These results suggest the stereotype may be culturally shared.")
        self.assertEqual(result["state"], at.OWN_ESTABLISHED)
        self.assertIn("hedged", result["flags"])

    def test_the_model_can_downgrade_but_never_upgrade(self):
        self.assertEqual(self.state(U3, model_class="background_generic")["state"], at.UNRESOLVED)
        self.assertIn("model_disagrees_with_cues", self.state(U3, model_class="background_generic")["flags"])
        up = self.state(U7, model_class="this_study_reports")
        self.assertEqual(up["state"], at.UNRESOLVED)
        self.assertIn("model_upgrade_refused", up["flags"])

    def test_a_model_basis_phrase_must_occur_in_the_text(self):
        good = self.state(U3, basis_phrase="we found evidence")
        self.assertNotIn("model_basis_phrase_not_in_text", good["flags"])
        bad = self.state(U3, basis_phrase="we proved conclusively")
        self.assertIn("model_basis_phrase_not_in_text", bad["flags"])

    def test_authors_abstract_result_statement_is_an_own_basis_but_background_is_not(self):
        abstract = abstracts.clean_abstract(
            "<jats:p>People have a stereotype. This stereotype is hypothesized to be a byproduct of adaptations. "
            "Hadza with minimal exposure to other cultures chose at chance for both questions.</jats:p>"
        )
        result = self.state(
            "Hadza with minimal exposure to other cultures chose at chance for both questions.", abstract_clean=abstract
        )
        self.assertEqual(result["state"], at.OWN_ESTABLISHED)
        self.assertIn("authors_abstract_result_statement", result["bases"])
        background = self.state(
            "This stereotype is hypothesized to be a byproduct of adaptations.", abstract_clean=abstract
        )
        self.assertEqual(background["state"], at.SPECULATION)
        # the same result sentence is only unresolved when nothing shows it belongs to this paper
        self.assertEqual(
            self.state("Hadza with minimal exposure to other cultures chose at chance for both questions.")["state"],
            at.UNRESOLVED,
        )


@unittest.skipUnless(DB.is_file(), "disposable library copy not present")
class RealAbstractTests(unittest.TestCase):
    def test_u2_is_an_own_result_because_it_is_in_the_authors_abstract(self):
        con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro&immutable=1", uri=True)
        try:
            raw = con.execute("select abstract from papers where id=67").fetchone()[0]
            chunk = con.execute("select text from chunks where id=34974").fetchone()[0]
        finally:
            con.close()
        clean = abstracts.clean_abstract(raw)
        self.assertNotIn("<jats", clean)
        self.assertTrue(at.in_abstract(U2, clean), "U2 must be recognised as a sentence of the authors' abstract")
        result = at.derive_attribution([U2], abstract_clean=clean)
        self.assertEqual(result["state"], at.OWN_ESTABLISHED, result)
        self.assertIn("authors_abstract_result_statement", result["bases"])
        self.assertIn("less prosociality", chunk)
        # and the abstract's own background sentence is not an own finding
        bg = at.derive_attribution(
            [
                "An “anomalous-is-bad” stereotype is hypothesized to facilitate negative biases against people with facial anomalies (e.g., scars)."
            ],
            abstract_clean=clean,
        )
        self.assertNotEqual(bg["state"], at.OWN_ESTABLISHED)


# ---- Cliff's corrections, session 2026-09-27: clause-scoped attribution and METHODS_OWN --------------------------

# The real c11 packet d37854a6ea62's p1 — the exact sentence whose whole-span "speculation" label was the bug.
C11_HEDGE_SENTENCE = (
    "However, evidence for the anomalous-is- bad stereotype comes from studies of European and North American "
    "populations; the byproduct hypothesis would predict universality of the stereotype."
)
# The real c9 packet 2c0006d1edba's p2/p3 — "The X assessed Y" with no first-person cue.
PAPER61_IRI = (
    "The IRI assessed empathic concern (assessing feelings of sympathy and concern for others who are less "
    "fortunate) and perspective-taking (assessing tendency to adopt the psychological point of view of others)."
)
PAPER61_JWBS = (
    'The JWBS assessed "procedural" and "distributive" just world beliefs about others using a 1-7 Likert scale.'
)
# The real paper 67 localization neighborhood's s20 — the sentence Qwen failed to select in Gate 1 (F2).
PAPER67_S20 = (
    "Participants completed a Just World Beliefs Scale,31 which measures beliefs about interpersonal fairness "
    "toward oneself and others; the Interpersonal Reactivity Index,32 which mea- sures cognitive (perspective "
    "taking) and affective (empathic concern) empathy; and a subscale from the Three-Domain Disgust scale33 that "
    "measures sensitivity to pathogen-related disgust."
)


class ClauseScopedAttributionTests(unittest.TestCase):
    def test_the_hedge_in_one_clause_does_not_contaminate_a_different_factual_clause(self):
        clauses = at.split_clauses(C11_HEDGE_SENTENCE)
        self.assertEqual(len(clauses), 2)
        for start, end, text in clauses:
            self.assertEqual(C11_HEDGE_SENTENCE[start:end], text)  # exact offsets, never re-typed
        result = at.derive_attribution([C11_HEDGE_SENTENCE])
        states = [c["state"] for c in result["clauses"]]
        self.assertEqual(states[1], at.SPECULATION)  # "the byproduct hypothesis would predict..."
        self.assertNotEqual(states[0], at.SPECULATION)  # the factual framing clause is not itself speculative

    def test_a_semicolon_inside_a_parenthetical_citation_is_not_a_clause_boundary(self):
        # "(β = -1.002, SE = 0.464, z = -2.158, P = 0.031; see Table S6)" — the real reported-statistics shape.
        text = "There was a significant interaction (β = -1.002, SE = 0.464, z = -2.158, P = 0.031; see Table S6)."
        self.assertEqual(len(at.split_clauses(text)), 1)
        self.assertEqual(at.derive_attribution([text])["state"], at.OWN_ESTABLISHED)

    def test_a_methods_instrument_description_with_no_first_person_cue_is_methods_own_not_own_established(self):
        """The closed-class pattern matches a FULL instrument name ("...Index", "...Scale", ...) as subject; the
        real paper-61 wording (`PAPER61_IRI`/`PAPER61_JWBS`, a bare acronym as subject) is the documented gap
        covered separately below — this test uses the full-name form the pattern is actually built for."""
        for text in (
            "The Interpersonal Reactivity Index assessed empathic concern and perspective-taking.",
            'The Just World Beliefs Scale assessed "procedural" and "distributive" just world beliefs about others.',
        ):
            result = at.derive_attribution([text], section="methods")
            self.assertEqual(result["state"], at.METHODS_OWN, text)
            self.assertIn("methods_instrument_description", result["bases"])

    def test_a_prior_cue_blocks_methods_own(self):
        text = "As in prior work, the Interpersonal Reactivity Index assessed empathic concern and perspective-taking."
        result = at.derive_attribution([text], section="methods")
        self.assertNotEqual(result["state"], at.METHODS_OWN)

    def test_methods_own_requires_the_methods_section(self):
        text = "The Interpersonal Reactivity Index assessed empathic concern and perspective-taking."
        result = at.derive_attribution([text], section="results")
        self.assertNotEqual(result["state"], at.METHODS_OWN)

    def test_the_real_paper_67_sentence_gets_own_or_methods_own_for_every_clause(self):
        """The exact sentence Gate 1's c9 lost to a wrong model pick (F2) — proving attribution was never the
        problem for this sentence; only localization SELECTING it was (see test_deterministic_candidates.py)."""
        result = at.derive_attribution([PAPER67_S20], section="methods")
        self.assertEqual(len(result["clauses"]), 3)
        for clause in result["clauses"]:
            self.assertIn(clause["state"], (at.OWN_ESTABLISHED, at.METHODS_OWN), clause["text"])

    def test_a_bare_acronym_subject_is_not_recognized_documented_gap(self):
        """`INSTRUMENT_DESCRIBES` only matches a full instrument-shaped name ("...Scale", "...Index", ...), not a
        bare acronym used anaphorically ("The IRI assessed X") once the full name has already been given elsewhere
        in the same packet. Extending it to bare acronyms was considered and declined in this iteration: it would
        need either a speculative acronym heuristic or access to the packet's own verified links, which this
        module's pure-text scope does not have — recorded as an open point, not silently papered over."""
        for text in (PAPER61_IRI, PAPER61_JWBS):  # the real paper-61 wording, verbatim
            result = at.derive_attribution([text], section="methods")
            self.assertNotEqual(result["state"], at.METHODS_OWN, text)


if __name__ == "__main__":
    unittest.main()
