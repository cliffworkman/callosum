"""The responsiveness-aware deterministic renderer: verbatim, epistemically clean, and honest about what it cannot say."""

import copy
import re
import unittest

from experiments.ask_cli_revised import stages
from experiments.ask_cli_revised.calibration.run06.dataset06 import BUILT_ENV_QUESTION, DEPRESSION_QUESTION
from experiments.ask_cli_revised.ledger_renderer import audit_final, render_answer, render_ledger
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.supervisor_eval.scoring import corpus_absence_hits


def rec(sid, claim, *, chunk, mapping_state="mapped", obligation_ids=(), paper_id=7):
    return {
        "subquestion_id": sid,
        "proposition_text": claim,
        "quote": f"QUOTE {chunk}",
        "paper_id": paper_id,
        "evidence_anchor_chunk_id": chunk,
        "evidence_span_id": "e1",
        "obligation_ids": list(obligation_ids),
        "mapping_state": mapping_state,
        "verification": {"status": "verified"},
        "provenance": {"origin": "initial"},
    }


def build(question, records, *, authority=None, coverage=None):
    contract = build_request_contract(question)
    subquestions = request_subquestions(contract)
    packets = [
        {"paper_id": r["paper_id"], "candidate_spans": [{"chunk_id": r["evidence_anchor_chunk_id"], "span_id": "e1", "text": r["quote"]}]}
        for r in records
    ]  # fmt: skip
    coverage = coverage or stages.det_coverage(
        subquestions, records, authority=authority or {"kind": "det", "role": "R"}
    )
    return stages.seal(contract, subquestions, records, packets, coverage)


SEALED_LLD = None


def lld_ledger():
    records = [
        rec("s3", "Amyloid burden was higher in late-life depression.", chunk=11, obligation_ids=["s3-o1"]),
        rec("s4", "Cerebral glucose metabolism was lower in the temporal lobe.", chunk=12, obligation_ids=["s4-o1", "s6-o1"]),
        rec("s5", "An unrelated but source-verified statement.", chunk=13),
    ]  # fmt: skip
    return build(DEPRESSION_QUESTION, records)


class ResponsiveRenderTests(unittest.TestCase):
    def setUp(self):
        self.ledger = lld_ledger()
        self.text, self.manifest = render_answer(self.ledger)

    def test_source_verification_and_responsiveness_are_shown_as_separate_judgments(self):
        self.assertIn("source-verified", self.text)
        self.assertIn("Judged responsive to this item", self.text)
        self.assertIn("Source-verified but not judged responsive", self.text)
        for banned in ("verified as responsive", "not verified for responsiveness", "verified responsiveness"):
            self.assertNotIn(banned, self.text)

    def test_the_prose_names_no_model_or_role_the_manifest_carries_the_authority(self):
        for name in ("qwen", "gemma", "phi4", "gpt-oss", "coverage accepted", "coverage rejected"):
            self.assertNotIn(name, self.text.lower())
        self.assertIsNone(re.search(r"\bby [RCP]\b", self.text))  # role letters are a trace surface, not prose
        self.assertEqual(self.manifest["coverage_authority"], {"kind": "det", "role": "R"})

    def test_each_claim_is_verbatim_and_sits_under_the_items_it_is_judged_responsive_to(self):
        amyloid = self.text.index("### u3")
        glucose = self.text.index("### u4")
        self.assertIn("Amyloid burden was higher in late\\-life depression\\.", self.text[amyloid:glucose])
        section_u6 = self.text[self.text.index("### u6") : self.text.index("### u7")]
        self.assertIn(
            "Cerebral glucose metabolism was lower in the temporal lobe\\.", section_u6
        )  # attached to two items

    def test_an_item_with_no_judged_responsive_claim_says_only_what_was_retrieved(self):
        section = self.text[self.text.index("### u1") : self.text.index("### u2")]
        self.assertIn("No claim has been judged responsive to this item", section)
        self.assertIn("evidence retrieved", section)

    def test_a_source_verified_claim_not_judged_responsive_is_listed_separately_not_dropped(self):
        tail = self.text[self.text.index("## Source-verified but not judged responsive") :]
        self.assertIn("An unrelated but source\\-verified statement\\.", tail)
        self.assertIn("[p3]", tail)

    def test_the_rendered_text_makes_no_corpus_absence_claim(self):
        self.assertEqual(corpus_absence_hits(self.text), [])
        self.assertIn("makes no statement about what the library or the literature holds", self.text)

    def test_completeness_is_never_certified(self):
        self.assertIn("completeness", self.text.lower())
        self.assertEqual(self.manifest["completeness"], "not_certified")

    def test_markdown_in_claim_text_cannot_forge_structure_or_citations(self):
        records = [rec("s3", "# Heading [p9] <b>x</b>", chunk=11, obligation_ids=["s3-o1"])]
        text, _ = render_answer(build(DEPRESSION_QUESTION, records))
        self.assertNotIn("\n# Heading", text)
        self.assertNotIn("[p9]", text.replace("\\[p9\\]", ""))
        self.assertNotIn("<b>", text)

    def test_the_constrained_render_matches_and_a_tampered_answer_does_not(self):
        self.assertTrue(audit_final(self.ledger, self.text)["constrained_render_match"])
        self.assertFalse(audit_final(self.ledger, self.text + "\nInvented finding [p3].")["constrained_render_match"])
        self.assertEqual(audit_final(self.ledger, self.text)["nonexistent_ids"], [])

    def test_the_manifest_states_each_claims_responsiveness_and_adds_no_aggregate(self):
        by_id = {c["proposition_ids"][0]: c for c in self.manifest["claims"]}
        self.assertEqual(by_id["p1"]["responsiveness_state"], "judged_responsive")
        self.assertEqual(by_id["p1"]["responsive_obligation_ids"], ["s3-o1"])
        self.assertEqual(by_id["p3"]["responsiveness_state"], "not_judged_responsive")
        self.assertEqual(self.manifest["scientific_aggregates"], 0)


class BuiltEnvironmentHonestyTests(unittest.TestCase):
    def test_tangential_claims_that_no_authority_accepted_are_never_presented_as_answers(self):
        records = [
            rec("s3", "Spectral coherence increased in frontal EEG channels.", chunk=21),
            rec("s4", "Occipital cortex responds to scene layout.", chunk=22),
        ]
        ledger = build(BUILT_ENV_QUESTION, records)
        text, manifest = render_answer(ledger)
        self.assertNotIn("Judged responsive to this item:", text)
        self.assertEqual(text.count("No claim has been judged responsive to this item"), 8)
        self.assertTrue(all(c["responsiveness_state"] == "not_judged_responsive" for c in manifest["claims"]))
        self.assertEqual(corpus_absence_hits(text), [])


class MechanicalFailureTests(unittest.TestCase):
    def test_a_coverage_audit_with_no_answer_shows_no_judgment_and_says_why(self):
        records = [rec("s3", "Amyloid burden was higher.", chunk=11)]
        contract = build_request_contract(DEPRESSION_QUESTION)
        subquestions = request_subquestions(contract)
        coverage = {
            "authority": {"kind": "model", "role": "C"},
            "assessed": False,
            "outcome": "capped_at_allowance",
            "obligations": [stages._obligation_row(sq, stages.NOT_ASSESSED, [], 0) for sq in subquestions],
        }
        ledger = build(DEPRESSION_QUESTION, records, coverage=coverage)
        text, manifest = render_answer(ledger)
        self.assertNotIn("No claim has been judged responsive", text)  # no judgment was made, so none is reported
        self.assertIn("could not be assessed", text)
        self.assertIn("Source-verified claims whose responsiveness was not assessed", text)
        self.assertEqual(manifest["claims"][0]["responsiveness_state"], "not_assessed")

    def test_mechanical_gaps_on_an_item_are_disclosed_and_do_not_assert_absence(self):
        records = [rec("s3", "Amyloid burden was higher.", chunk=11, mapping_state="no_answer")]
        text, manifest = render_answer(build(DEPRESSION_QUESTION, records))
        section = text[text.index("### u3") : text.index("### u4")]
        self.assertIn("could not be assessed for responsiveness", section)
        self.assertEqual(manifest["claims"][0]["responsiveness_state"], "not_assessed")
        self.assertIn("Source-verified claims whose responsiveness was not assessed", text)


class LegacyCompatibilityTests(unittest.TestCase):
    def test_a_ledger_without_obligation_states_renders_exactly_as_the_legacy_renderer_does(self):
        ledger = copy.deepcopy(lld_ledger())
        for key in ("obligation_states", "coverage_authority", "coverage_assessed", "coverage_outcome"):
            ledger.pop(key)
        self.assertEqual(render_answer(ledger), render_ledger(ledger))


if __name__ == "__main__":
    unittest.main()
