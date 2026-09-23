"""The frozen battery's case definitions: structure, orderings, and the expected judgments.

These tests pin the *definition* of the battery (what is asked and what counts as passing) so a
later edit cannot quietly change a judgment. They use only public-safe text (claims/obligations);
no source quotes are involved.
"""

import unittest

from experiments.ask_cli_revised.supervisor_eval import cases


def _by_id(specs):
    return {s["case_id"]: s for s in specs}


class ObligationAndLedgerTests(unittest.TestCase):
    def test_six_real_obligations_with_verbatim_notes(self):
        self.assertEqual(cases.OBLIGATION_IDS, ["s1-o1", "s2-o1", "s3-o1", "s4-o1", "s5-o1", "s6-o1"])
        notes = {o["field_id"]: o["note"] for o in cases.OBLIGATIONS}
        self.assertEqual(notes["s3-o1"], "and using which scales?")
        self.assertEqual(notes["s4-o1"], "is there any cross-cultural evidence for the bias?")
        # the source's own typo is preserved verbatim, not corrected
        self.assertEqual(notes["s5-o1"], "which cultures and how was this measures?")

    def test_real_verified_ledger_has_six_propositions_with_retrieval_context(self):
        self.assertEqual(cases.PROPOSITION_IDS, ["p1", "p2", "p3", "p4", "p5", "p6"])
        props = {p["proposition_id"]: p for p in cases.PROPOSITIONS}
        self.assertEqual(props["p5"]["retrieved_for"], "s3-o1")  # dmPFC retrieved for "scales"
        self.assertEqual(props["p6"]["retrieved_for"], "s5-o1")  # mentalizing retrieved for cultures/measurement
        self.assertEqual(props["p1"]["claim"], props["p2"]["claim"])  # the same claim was retrieved twice


class OriginalQuestionTests(unittest.TestCase):
    def test_the_original_request_is_the_users_verbatim_question_pinned_by_its_hash(self):
        import hashlib

        from experiments.ask_cli_revised.supervisor_eval.build_battery import EXPECTED_QUESTION_HASH

        self.assertEqual(hashlib.sha256(cases.ORIGINAL_QUESTION.encode("utf-8")).hexdigest(), EXPECTED_QUESTION_HASH)
        self.assertTrue(cases.ORIGINAL_QUESTION.startswith("how does the anomalous is bad bias manifest"))

    def test_every_obligation_note_is_a_verbatim_span_of_the_original_question(self):
        for o in cases.OBLIGATIONS:
            self.assertIn(o["note"], cases.ORIGINAL_QUESTION, o["field_id"])


class OrderingTests(unittest.TestCase):
    def test_orderings(self):
        self.assertEqual(cases.obligation_order("original"), cases.OBLIGATION_IDS)
        self.assertEqual(cases.obligation_order("reversed"), list(reversed(cases.OBLIGATION_IDS)))
        self.assertEqual(cases.obligation_order("rotated"), ["s4-o1", "s5-o1", "s6-o1", "s1-o1", "s2-o1", "s3-o1"])

    def test_unknown_ordering_is_rejected(self):
        with self.assertRaises(KeyError):
            cases.obligation_order("shuffled")


class BatteryShapeTests(unittest.TestCase):
    def setUp(self):
        self.specs = cases.build_case_specs()
        self.by_id = _by_id(self.specs)

    def test_nineteen_calls_and_unique_ids(self):
        self.assertEqual(len(self.specs), 19)
        self.assertEqual(len(self.by_id), 19)
        counts = {f: sum(1 for s in self.specs if s["family"] == f) for f in "ABC"}
        self.assertEqual(counts, {"A": 15, "B": 2, "C": 2})

    def test_order_robustness_subset_is_A1_A2_A3_A7_with_three_orderings(self):
        robust = sorted({s["base_id"] for s in self.specs if s["family"] == "A" and s["order_robust"]})
        self.assertEqual(robust, ["A1", "A2", "A3", "A7"])
        for base in robust:
            orderings = sorted(s["ordering"] for s in self.specs if s["base_id"] == base)
            self.assertEqual(orderings, ["original", "reversed", "rotated"], base)

    def test_A4_A5_A6_run_once(self):
        for base in ("A4", "A5", "A6"):
            rows = [s for s in self.specs if s["base_id"] == base]
            self.assertEqual([r["ordering"] for r in rows], ["original"], base)
            self.assertFalse(rows[0]["order_robust"])

    def test_the_specs_carry_the_ordering_they_name(self):
        rot = self.by_id["A1.rotated"]
        self.assertEqual(rot["obligation_order"], ["s4-o1", "s5-o1", "s6-o1", "s1-o1", "s2-o1", "s3-o1"])
        self.assertEqual(self.by_id["A1.reversed"]["obligation_order"][0], "s6-o1")


class TaskAExpectationTests(unittest.TestCase):
    def setUp(self):
        self.by_id = _by_id(cases.build_case_specs())

    def test_generic_neuroscience_must_map_to_no_obligation(self):
        # The corrected contract: NOT s1/s2 either. Nearest-category mapping is a failure.
        for base in ("A3", "A4", "A5"):
            spec = self.by_id[f"{base}.original"]
            self.assertEqual(spec["role"], "negative", base)
            self.assertEqual(spec["expected"]["required"], [], base)
            self.assertEqual(spec["expected"]["diagnostic"], [], base)
            self.assertTrue(spec["expected"]["gated"], base)

    def test_claims_are_the_stored_texts_byte_for_byte(self):
        self.assertEqual(
            self.by_id["A3.original"]["claim"],
            "The dorsomedial prefrontal cortex affects individuals' responses to social situations.",
        )
        self.assertEqual(
            self.by_id["A4.original"]["claim"],
            "Mentalizing regions represent distributed, continuous and abstract dimensions of others beliefs.",
        )
        self.assertEqual(self.by_id["A5.original"]["claim"], "how many years participants attended school")
        self.assertEqual(self.by_id["A7.original"]["claim"], "The EBQ measures explicit bias.")
        self.assertEqual(
            self.by_id["A1.original"]["claim"], "explicit negative attitudes about people with facial anomalies"
        )
        self.assertEqual(
            self.by_id["A2.original"]["claim"],
            "There is cross-cultural evidence for the bias in personality or behavior.",
        )

    def test_positive_allowed_sets_are_tight(self):
        a1 = self.by_id["A1.original"]["expected"]
        self.assertEqual((a1["required"], a1["diagnostic"]), (["s1-o1"], ["s2-o1"]))
        a2 = self.by_id["A2.original"]["expected"]
        self.assertEqual((a2["required"], a2["diagnostic"]), (["s4-o1"], ["s1-o1", "s2-o1"]))
        a7 = self.by_id["A7.original"]["expected"]
        self.assertEqual((a7["required"], a7["diagnostic"]), (["s3-o1"], ["s5-o1"]))

    def test_A6_is_diagnostic_and_ungated(self):
        a6 = self.by_id["A6.original"]
        self.assertEqual(a6["role"], "diagnostic")
        self.assertFalse(a6["expected"]["gated"])

    def test_claim_provenance_is_labeled_honestly(self):
        # EBQ / cross-cultural / years-of-school are real but NOT verified candidates; used in Task A only.
        self.assertEqual(self.by_id["A7.original"]["claim_source"]["status"], "weak")
        self.assertEqual(self.by_id["A2.original"]["claim_source"]["status"], "unverified")
        self.assertEqual(self.by_id["A5.original"]["claim_source"]["status"], "weak")
        self.assertEqual(self.by_id["A3.original"]["claim_source"]["status"], "verified")


class TaskBExpectationTests(unittest.TestCase):
    def setUp(self):
        self.by_id = _by_id(cases.build_case_specs())

    def test_two_calls_original_and_reversed_proposition_order(self):
        self.assertEqual(self.by_id["B1.original"]["proposition_order"], cases.PROPOSITION_IDS)
        self.assertEqual(self.by_id["B1.reversed"]["proposition_order"], list(reversed(cases.PROPOSITION_IDS)))
        self.assertEqual(self.by_id["B1.original"]["obligation_order"], cases.OBLIGATION_IDS)

    def test_generic_neuroscience_may_support_no_obligation_at_all(self):
        forbid = self.by_id["B1.original"]["expected"]["forbidden_attach"]
        self.assertEqual(sorted(forbid["p5"]), cases.OBLIGATION_IDS)
        self.assertEqual(sorted(forbid["p6"]), cases.OBLIGATION_IDS)

    def test_ambiguous_traits_claim_is_only_forbidden_from_s3_to_s6(self):
        forbid = self.by_id["B1.original"]["expected"]["forbidden_attach"]
        for pid in ("p1", "p2"):
            self.assertEqual(sorted(forbid[pid]), ["s3-o1", "s4-o1", "s5-o1", "s6-o1"])

    def test_clear_positive_and_preserved_gaps(self):
        exp = self.by_id["B1.original"]["expected"]
        self.assertEqual(exp["required_support"], {"s1-o1": ["p3"]})
        self.assertEqual(sorted(exp["must_be_unresolved"]), ["s4-o1", "s6-o1"])


class TaskCExpectationTests(unittest.TestCase):
    def setUp(self):
        self.by_id = _by_id(cases.build_case_specs())
        self.c = self.by_id["C1.original"]

    def test_policy_text_is_part_of_the_case(self):
        self.assertIn("Do not repeat an already-performed search action", self.c["policy"])
        self.assertIn("Never invent an action or an evidence item", self.c["policy"])

    def test_s4_has_an_unused_broadening_action_and_s5_is_exhausted(self):
        state = self.c["state"]
        self.assertFalse(state["s4-o1"]["performed"]["NOMINATE"])
        self.assertTrue(state["s4-o1"]["performed"]["DEEPEN"])
        self.assertTrue(state["s5-o1"]["performed"]["NOMINATE"])
        self.assertTrue(state["s5-o1"]["performed"]["DEEPEN"])

    def test_s4_is_disclosed_as_a_reconstruction(self):
        self.assertIn("reconstruction", self.c["state"]["s4-o1"]["state_provenance"])

    def test_traps_are_offered_as_legal_close_actions(self):
        actions = self.c["legal"]["actions"]
        self.assertIn("s3-o1:MARK_COVERED:p5", actions["s3-o1"])
        self.assertIn("s3-o1:MARK_COVERED:p2", actions["s3-o1"])
        self.assertIn("s5-o1:MARK_COVERED:p6", actions["s5-o1"])
        # closure without support must be *available* to be a testable failure
        for ob in ("s3-o1", "s4-o1", "s5-o1", "s6-o1"):
            self.assertIn(f"{ob}:NO_RECOVERY_NEEDED", actions[ob])

    def test_action_ids_are_scoped_to_their_obligation(self):
        for ob, ids in self.c["legal"]["actions"].items():
            self.assertTrue(all(i.startswith(ob + ":") for i in ids), ob)

    def test_frozen_expectations(self):
        exp = self.c["expected"]
        self.assertEqual(exp["required_choice"], {"s4-o1": "s4-o1:NOMINATE", "s5-o1": "s5-o1:PRESERVE_UNRESOLVED"})
        self.assertEqual(sorted(exp["closure_forbidden"]), ["s3-o1", "s4-o1", "s5-o1", "s6-o1"])
        self.assertEqual(sorted(exp["repeat_forbidden"]), ["s3-o1", "s4-o1", "s5-o1"])

    def test_reversed_variant_reverses_obligations_and_each_menu(self):
        r = self.by_id["C1.reversed"]
        self.assertEqual(r["obligation_order"], list(reversed(cases.OBLIGATION_IDS)))
        self.assertEqual(r["legal"]["actions"]["s3-o1"], list(reversed(self.c["legal"]["actions"]["s3-o1"])))
        self.assertEqual(r["expected"], self.c["expected"])


if __name__ == "__main__":
    unittest.main()
