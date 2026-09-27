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


if __name__ == "__main__":
    unittest.main()
