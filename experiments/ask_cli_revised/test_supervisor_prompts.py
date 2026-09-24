"""The frozen R/C/P contracts, generalized to any question, must reproduce the frozen bakeoff prompts exactly.

The jurisdiction evidence (which model can do claim responsiveness, coverage audit, recovery planning) was produced under
the frozen prompt text and schemas, so the E2E may only change *what is filled in*, never the contract itself.
"""

import unittest

import jsonschema

from experiments.ask_cli_revised import supervisor_prompts as sp
from experiments.ask_cli_revised.calibration.run06.dataset06 import DEPRESSION_QUESTION
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.supervisor_eval import cases, prompts, schemas

SPECS = cases.build_case_specs()
QUOTES = {p["proposition_id"]: f"SYNTHETIC QUOTE FOR {p['proposition_id']}" for p in cases.PROPOSITIONS}
NOTES = {o["field_id"]: o for o in cases.OBLIGATIONS}


def obligations(order):
    return [NOTES[ob] for ob in order]


def ledger(order):
    return [
        {**p, "quote": QUOTES[p["proposition_id"]]}
        for p in (next(x for x in cases.PROPOSITIONS if x["proposition_id"] == pid) for pid in order)
    ]


class FrozenEquivalenceTests(unittest.TestCase):
    def test_claim_responsiveness_prompt_matches_every_frozen_task_a_case(self):
        checked = 0
        for spec in (s for s in SPECS if s["family"] == "A"):
            with self.subTest(case=spec["case_id"]):
                mine = sp.render_responsiveness(
                    cases.ORIGINAL_QUESTION, spec["claim"], obligations(spec["obligation_order"])
                )
                self.assertEqual(mine, prompts.render(spec))
                checked += 1
        self.assertEqual(checked, 15)

    def test_coverage_audit_prompt_matches_both_frozen_task_b_cases(self):
        for spec in (s for s in SPECS if s["family"] == "B"):
            with self.subTest(case=spec["case_id"]):
                mine = sp.render_coverage(
                    cases.ORIGINAL_QUESTION, obligations(spec["obligation_order"]), ledger(spec["proposition_order"])
                )
                self.assertEqual(mine, prompts.render(spec, QUOTES))

    def test_recovery_prompt_matches_both_frozen_task_c_cases(self):
        for spec in (s for s in SPECS if s["family"] == "C"):
            with self.subTest(case=spec["case_id"]):
                mine = sp.render_recovery(
                    cases.ORIGINAL_QUESTION,
                    obligations(spec["obligation_order"]),
                    ledger([p["proposition_id"] for p in cases.PROPOSITIONS]),
                    spec["state"],
                    spec["legal"]["actions"],
                    cases.RECOVERY_POLICY,
                )
                self.assertEqual(mine, prompts.render(spec))

    def test_schemas_equal_the_frozen_case_schemas(self):
        for spec in SPECS:
            with self.subTest(case=spec["case_id"]):
                if spec["family"] == "A":
                    mine = sp.schema_responsiveness(spec["legal"]["obligation_ids"])
                elif spec["family"] == "B":
                    mine = sp.schema_coverage(spec["legal"]["obligation_ids"], spec["legal"]["proposition_ids"])
                else:
                    mine = sp.schema_recovery(spec["legal"]["obligation_ids"], spec["legal"]["actions"])
                self.assertEqual(mine, schemas.build_schema(spec))


class GeneralizationTests(unittest.TestCase):
    def setUp(self):
        contract = build_request_contract(DEPRESSION_QUESTION)
        self.obligations = [sq["obligations"][0] for sq in request_subquestions(contract)]
        self.ids = [o["field_id"] for o in self.obligations]

    def test_a_fragment_is_shown_with_its_frame_and_the_original_request_is_verbatim(self):
        prompt = sp.render_responsiveness(DEPRESSION_QUESTION, "Amyloid burden was higher.", self.obligations)
        self.assertIn(DEPRESSION_QUESTION, prompt)
        self.assertIn("- s3-o1: amyloid [part of the request sentence:", prompt)
        self.assertIn("Amyloid burden was higher.", prompt)

    def test_the_eight_unit_schemas_are_valid_and_bounded(self):
        for schema in (
            sp.schema_responsiveness(self.ids),
            sp.schema_coverage(self.ids, ["p1", "p2"]),
            sp.schema_recovery(self.ids, {ob: [f"{ob}:DEEPEN", f"{ob}:PRESERVE_UNRESOLVED"] for ob in self.ids}),
        ):
            jsonschema.Draft202012Validator.check_schema(schema)
        self.assertEqual(sp.schema_responsiveness(self.ids)["properties"]["responsive_obligation_ids"]["maxItems"], 8)

    def test_legal_actions_per_obligation_follow_the_frozen_menu(self):
        actions = sp.legal_actions(self.ids, {"s1-o1": ["p1", "p3"]})
        self.assertEqual(
            actions["s1-o1"],
            [
                "s1-o1:DEEPEN",
                "s1-o1:NOMINATE",
                "s1-o1:MARK_COVERED:p1",
                "s1-o1:MARK_COVERED:p3",
                "s1-o1:NO_RECOVERY_NEEDED",
                "s1-o1:PRESERVE_UNRESOLVED",
            ],
        )
        self.assertEqual(
            actions["s2-o1"],
            ["s2-o1:DEEPEN", "s2-o1:NOMINATE", "s2-o1:NO_RECOVERY_NEEDED", "s2-o1:PRESERVE_UNRESOLVED"],
        )

    def test_first_round_state_has_nothing_performed(self):
        state = sp.initial_recovery_state(self.ids, support={"s1-o1": ["p1"]}, on_file={"s1-o1": ["p1"]})
        for ob in self.ids:
            self.assertEqual(state[ob]["performed"], {"DEEPEN": False, "NOMINATE": False})
        self.assertEqual(state["s1-o1"]["coverage_support"], ["p1"])
        self.assertEqual(state["s2-o1"]["coverage_support"], [])

    def test_a_prompt_with_nothing_performed_says_not_yet_performed(self):
        state = sp.initial_recovery_state(self.ids, support={}, on_file={})
        prompt = sp.render_recovery(
            DEPRESSION_QUESTION, self.obligations, [], state, sp.legal_actions(self.ids, {}), ["A policy."]
        )
        self.assertIn("- DEEPEN: not yet performed", prompt)
        self.assertNotIn("(ALREADY PERFORMED)", prompt)


if __name__ == "__main__":
    unittest.main()
