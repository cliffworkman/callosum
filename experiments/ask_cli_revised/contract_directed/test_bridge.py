import unittest

from experiments.ask_cli_revised.contract_directed import bridge, coverage

SEED = {
    "id": 67,
    "title": "Morality is in the eye of the beholder: the neurocognitive basis of the anomalous-is-bad stereotype",
    "abstract": "<jats:p>The specific amygdala response correlated with stronger just-world beliefs and less dispositional empathic concern.</jats:p>",
}


class FakeModel:
    def encode_texts(self, texts):
        return [self._vec(t) for t in texts]

    @staticmethod
    def _vec(text):
        """Two fake concept dimensions: dispositions/traits, and neural/belief wording."""
        low = text.lower()
        trait_group = ("dispositional", "empathic", "concern", "traits", "personality")
        other_group = ("amygdala", "beliefs", "neurocognitive")
        return [1.0 if any(w in low for w in trait_group) else 0.0, 1.0 if any(w in low for w in other_group) else 0.0]


class FakeRetriever:
    model = FakeModel()

    def encode(self, text):
        return FakeModel._vec(text)


def rows(*states):
    return [{"row_type": "content", "unit_id": f"M{i}", "state": s} for i, s in enumerate(states, 1)]


class BridgeTriggerTests(unittest.TestCase):
    def test_it_triggers_only_with_an_unresolved_unit_and_an_independent_seed(self):
        self.assertTrue(bridge.bridge_trigger(rows(coverage.UNRESOLVED_SEARCHED), [67])["triggered"])
        self.assertEqual(bridge.bridge_trigger(rows(coverage.ATTACHED), [67])["reason"], "no_unresolved_unit")
        self.assertEqual(
            bridge.bridge_trigger(rows(coverage.UNRESOLVED_SEARCHED), [])["reason"], "no_independently_responsive_seed"
        )
        self.assertFalse(bridge.bridge_trigger(rows(coverage.PARTIAL_ONLY), [])["triggered"])

    def test_a_bridge_is_conditional_never_mandatory(self):
        self.assertFalse(bridge.bridge_trigger(rows(coverage.ATTACHED, coverage.ATTACHED), [67, 68])["triggered"])


class PhraseHarvestTests(unittest.TestCase):
    def test_phrases_are_verbatim_author_wording_not_already_in_the_units_words(self):
        unit = "which personality traits relate to the bias"
        found = bridge.candidate_phrases(SEED["abstract"].replace("<jats:p>", "").replace("</jats:p>", ""), unit)
        self.assertIn("dispositional empathic", found)
        self.assertTrue(all(p.lower() not in unit for p in found))

    def test_harvested_phrases_are_ranked_verified_and_bounded(self):
        out = bridge.harvest_phrases(SEED, "which personality traits relate to the bias", FakeRetriever(), top_n=3)
        self.assertLessEqual(len(out), 3)
        self.assertTrue(out)
        for entry in out:
            self.assertTrue(entry["verbatim_in_source"])
            self.assertEqual(entry["paper_id"], 67)
        self.assertIn("dispositional", out[0]["phrase"].lower())

    def test_no_new_terminology_means_no_phrases(self):
        self.assertEqual(bridge.candidate_phrases("the traits", "the traits"), [])


class BridgeReceiptTests(unittest.TestCase):
    def test_the_receipt_states_the_scope_and_that_the_contract_is_unchanged(self):
        trigger = bridge.bridge_trigger(rows(coverage.UNRESOLVED_SEARCHED), [67])
        rec = bridge.bridge_receipt(
            "c8",
            "M9",
            trigger,
            [{"phrase": "dispositional empathic"}],
            [{"nbhd_id": "n1", "paper_id": 60, "chunk_ids": [1]}],
            "candidates_found",
        )
        self.assertTrue(rec["contract_unchanged"])
        self.assertIn("never closes a unit", rec["probe_scope"])
        self.assertIn("not_available", rec["citation_context_bridge"])
        self.assertEqual(rec["neighborhoods_found"], [{"nbhd_id": "n1", "paper_id": 60}])


if __name__ == "__main__":
    unittest.main()
