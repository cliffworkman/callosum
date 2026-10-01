"""Phase 9 Part H: locks in the counterfactual scripted replay's result. This is NOT evidence of
live Qwen behavior under the reformulated prompt -- see the module's own docstring. It proves the
single-stage mapping path (nomination -> grounding/admissibility -> RoleBinding, no second pass)
correctly carries a hand-scripted "what minimal-referent extraction SHOULD produce" fixture
end-to-end through real forking, anchor-dedup, same_proposition joint grounding, and parent
propagation, over the REAL preserved q_aib evidence. No live model call.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised.sufficiency_phase9_counterfactual_replay import replay, state_report


class CounterfactualReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = replay()
        cls.report = state_report(cls.result["with_model"])

    def test_c2_cannot_false_fill_from_the_circular_assertion(self):
        """The headline Phase 5/7 failure: under the counterfactual, c2 must NOT reach `filled`
        via the circular/self-referential nomination -- because that nomination was never
        produced at all (no referent to extract), not because anything vetoed it after the fact."""
        c2 = self.report["c2"]["c2#suff:behavioral-manifestation"]
        self.assertEqual(c2["state"], "partially_filled")
        self.assertEqual(c2["instance_count"], 2)
        c2_req = self.result["with_model"]["c2"]["requirements"][0]
        texts = {inst["role_bindings"]["behavior_or_behavioral_measure"]["exact_text"] for inst in c2_req["instances"]}
        self.assertEqual(
            texts,
            {
                "visual attention toward people with facial anomalies",
                "influence visual attention when looking at faces with anomalous anatomy",
            },
        )
        for text in texts:
            self.assertNotIn("behavioral manifestation", text)

    def test_c1_and_c4_survive_via_the_minimal_amygdala_referent(self):
        c1 = self.report["c1"]["c1#suff:neural-manifestation"]
        c4 = self.report["c4"]["c4#suff:specific-region"]
        self.assertEqual(c1["state"], "filled")
        self.assertEqual(c4["state"], "filled")
        c1_binding = self.result["with_model"]["c1"]["requirements"][0]["instances"][0]["role_bindings"][
            "brain_region_or_network"
        ]
        self.assertEqual(c1_binding["exact_text"], "amygdala")

    def test_c6_survives_via_the_already_minimal_ebq_referent(self):
        c6 = self.report["c6"]["c6#suff:brain-attitude"]
        self.assertEqual(c6["state"], "filled")
        self.assertEqual(c6["instance_count"], 2)

    def test_c8_survives_with_four_distinct_minimal_trait_referents(self):
        c8 = self.report["c8"]["c8#suff:trait-construct"]
        self.assertEqual(c8["state"], "partially_filled")  # unchanged from every prior phase --
        # c8's OTHER required role (relationship_to_bias_manifestation) is evidence-limited, never
        # found in any phase; this is the correct, honest state, not a regression.
        self.assertEqual(c8["instance_count"], 4)
        c8_req = self.result["with_model"]["c8"]["requirements"][0]
        traits = {
            inst["role_bindings"]["individual_difference_trait_or_construct"]["exact_text"] for inst in c8_req["instances"]
        }
        self.assertEqual(
            traits, {"IAT and EBQ", "just-world beliefs", "affective empathy", "less generosity in the DG"}
        )

    def test_c8_to_c9_propagation_survives(self):
        c9 = self.report["c9"]["c9#suff:trait-scale-pairing"]
        self.assertEqual(c9["instance_count"], 4)
        c9_req = self.result["with_model"]["c9"]["requirements"][0]
        traits = {
            inst["role_bindings"]["individual_difference_trait_or_construct"]["exact_text"] for inst in c9_req["instances"]
        }
        self.assertEqual(
            traits, {"IAT and EBQ", "just-world beliefs", "affective empathy", "less generosity in the DG"}
        )

    def test_anchor_dedup_still_collapses_the_duplicate_c8_propositions(self):
        """c8's own scripted fixture offers the SAME 4 texts from TWO propositions (p20 AND p9,
        mirroring the real duplicate-proposition shape Phase 3's anchor-dedup fix addresses) --
        the engine must still collapse these to exactly 4 distinct instances, never 8."""
        c8_req = self.result["with_model"]["c8"]["requirements"][0]
        self.assertEqual(len(c8_req["instances"]), 4)

    def test_same_proposition_joint_grounding_still_correctly_denies_c2_full_fill(self):
        """Even with the false fill gone, the genuine visual-attention instances still correctly
        fail `same_proposition` joint grounding against `behavioral_manifestation_evidence`'s own
        (different) proposition -- proving Phase 4's joint-grounding fix is untouched by this
        phase, not merely coincidentally absent because the bad candidate vanished."""
        c2_req = self.result["with_model"]["c2"]["requirements"][0]
        for inst in c2_req["instances"]:
            self.assertFalse(inst["complete"])  # filled roles, but NOT jointly grounded -> incomplete

    def test_unrelated_children_are_unaffected(self):
        for child, req_id, expected_state, expected_count in [
            ("c3", "c3#suff:attitude-manifestation", "filled", 1),
            ("c3", "c3#suff:implicit-explicit-coverage", "partially_filled", 2),
            ("c6", "c6#suff:implicit-explicit-coverage", "partially_filled", 2),
            ("c10", "c10#suff:culture-existence", "missing", 1),
            ("c11", "c11#suff:culture-operationalization-pairing", "missing", 0),
            ("c12", "c12#suff:intervention-effectiveness", "partially_filled", 2),
        ]:
            with self.subTest(child=child, req_id=req_id):
                actual = self.report[child][req_id]
                self.assertEqual(actual["state"], expected_state)
                self.assertEqual(actual["instance_count"], expected_count)

    def test_c5_remains_a_true_negative_decline_not_a_cross_call_collision(self):
        """Regression for the real collision bug this fixture's own module docstring documents:
        c5 shares BOTH its region AND behavior category_description text with c1/c2 respectively,
        but over a genuinely DIFFERENT (larger) candidate pool that never actually contains an
        extractable referent -- c5 must stay exactly where every prior phase found it."""
        c5 = self.report["c5"]["c5#suff:brain-behavior"]
        self.assertEqual(c5["state"], "partially_filled")
        self.assertEqual(c5["instance_count"], 1)

    def test_deterministic_only_pass_is_untouched(self):
        det = state_report(self.result["deterministic_only"])
        self.assertEqual(det["c2"]["c2#suff:behavioral-manifestation"]["state"], "partially_filled")
        self.assertEqual(det["c1"]["c1#suff:neural-manifestation"]["state"], "partially_filled")


if __name__ == "__main__":
    unittest.main()
