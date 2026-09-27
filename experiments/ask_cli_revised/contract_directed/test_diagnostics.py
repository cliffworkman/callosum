import unittest

from experiments.ask_cli_revised.contract_directed import diagnostics as dg

U1_TEXT = "This research confirmed earlier reports that people with anomalous faces are imbued with negative personality characteristics and described a behavioral manifestation of the stereotype affecting prosociality."
U3_TEXT = "We found evidence for the stereotype in explicit negative attitudes, scores on the Explicit Bias Questionnaire (EBQ)."
U6_TEXT = (
    "We suggest that dehumanization is underpinned by negative attitudes (IAT and EBQ) and less generosity in the DG."
)


class AnswerDiagnosticTests(unittest.TestCase):
    def run_diag(self, raw, packets, other=("how does the anomalous is bad bias manifest in brain",)):
        texts = dict(packets)
        prompt = "prompt text with " + " ".join(texts.values())
        return dg.answer_diagnostics(
            raw,
            prompt=prompt,
            id_map={k: f"pkt-{k}" for k in texts},
            packet_texts=texts,
            parent_question="the full parent question",
            other_wordings=list(other),
        )

    def test_the_baseline_c8_acronym_invention_is_flagged(self):
        raw = "Traits include attitudes measured by the Implicit Association Test (IAT) and the Empathy Bias Questionnaire (EBQ) [P1]."
        out = self.run_diag(raw, {"P1": U6_TEXT})
        flagged = {f["acronym"]: f for f in out["acronym_expansions_not_in_any_passage"]}
        self.assertIn("EBQ", flagged)
        self.assertIn("IAT", flagged)  # the passage never expands IAT either

    def test_an_expansion_that_the_passage_states_is_not_flagged(self):
        raw = "Scores on the Explicit Bias Questionnaire (EBQ) showed explicit negative attitudes [P1]."
        self.assertEqual(self.run_diag(raw, {"P1": U3_TEXT})["acronym_expansions_not_in_any_passage"], [])

    def test_the_baseline_c2_supplied_direction_is_flagged(self):
        raw = "The stereotype manifests behaviorally through a reduction in prosociality [P1]."
        out = self.run_diag(raw, {"P1": U1_TEXT})
        [flag] = out["directional_terms_not_in_cited_passages"]
        self.assertIn("reduc", flag["directional_terms_absent_from_cited_text"])

    def test_a_direction_the_cited_text_states_is_not_flagged(self):
        raw = "The amygdala response correlated with less prosociality [P1]."
        text = "the specific amygdala response correlated with stronger just-world beliefs and less prosociality."
        self.assertEqual(self.run_diag(raw, {"P1": text})["directional_terms_not_in_cited_passages"], [])

    def test_composite_citations_and_invalid_or_uncited_ids_are_reported(self):
        raw = "The amygdala responds to anomalies [P1][P2]. Behavior is affected [P9]. Nothing else."
        out = self.run_diag(raw, {"P1": "amygdala text", "P2": "behavior text", "P3": "never cited"})
        self.assertEqual(len(out["multi_packet_sentences"]), 1)
        self.assertEqual(out["invalid_cited_ids"], ["P9"])
        self.assertEqual(out["packets_given_but_never_cited"], ["P3"])

    def test_an_answer_citing_nothing_is_flagged(self):
        self.assertTrue(self.run_diag("The passages do not establish this.", {"P1": "x"})["answer_cites_nothing"])

    def test_prompt_leakage_checks(self):
        texts = {"P1": "x"}
        leaky = dg.answer_diagnostics(
            "a", prompt="prompt with the full parent question and how does the anomalous is bad bias manifest in brain",
            id_map={"P1": "k"}, packet_texts=texts, parent_question="the full parent question",
            other_wordings=["how does the anomalous is bad bias manifest in brain"],
        )  # fmt: skip
        self.assertTrue(leaky["prompt_leakage"]["contains_parent_question"])
        self.assertEqual(
            leaky["prompt_leakage"]["contains_other_child_wording"],
            ["how does the anomalous is bad bias manifest in brain"],
        )

    def test_diagnostics_never_gate(self):
        out = self.run_diag("An answer.", {"P1": "x"})
        self.assertFalse(out["gating"])
        self.assertEqual(out["nli_support"], "not_run")


if __name__ == "__main__":
    unittest.main()
