"""Model-facing contract of the overview stage: schema bounds, budget arithmetic, the pinned prompt, and what must stay out of it.

Rule (CLAUDE.md, generation ceilings): every schema field that can grow needs a bound, and the worst case the schema permits
must fit the output allowance. The worst case is RECOMPUTED from the schema itself, so loosening one without the other fails here.
"""

import hashlib
import re
import unittest

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import overview_guards as guards
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.hierarchy_contract import provenance_tokens
from experiments.ask_cli_revised.overview_test_support import (
    GIVING,
    HEDGE,
    S1,
    S2,
    OverviewClient,
    build,
    sealed_ledger,
)

# Deliberately pinned: any edit to the model-facing instructions is a new contract and must be re-pinned on purpose.
PROMPT_TEMPLATE_SHA256 = "6a59dc77d6a65a1793935c4bf24db77e0dd97f014d9b45ad63be9560b1d4cf86"
IDS = [f"U{i}" for i in range(1, oe.MAX_UNITS + 1)]
PARTS = [f"c{i}" for i in range(1, 13)]


class SchemaBoundTests(unittest.TestCase):
    def test_every_growable_field_is_bounded(self):
        schema = ov.schema_overview(IDS, PARTS)
        item = schema["properties"]["overview"]["items"]["properties"]
        self.assertEqual(schema["properties"]["overview"]["maxItems"], ov.MAX_SENTENCES)
        self.assertEqual(item["text"]["maxLength"], guards.MAX_SENTENCE_CHARS)
        self.assertEqual(item["unit_ids"]["maxItems"], guards.MAX_UNIT_IDS)
        self.assertEqual(item["bears_on"]["maxItems"], guards.MAX_BEARS_ON)
        self.assertEqual(
            item["unit_ids"]["items"], {"enum": IDS}
        )  # a closed enum: the model cannot cite a passage it was not shown
        self.assertFalse(schema["additionalProperties"])

    def test_an_unbounded_node_is_refused_rather_than_estimated(self):
        with self.assertRaisesRegex(ValueError, "unbounded string"):
            ov.worst_case_output_chars({"type": "string"})
        with self.assertRaisesRegex(ValueError, "unbounded array"):
            ov.worst_case_output_chars({"type": "array", "items": {"type": "string", "maxLength": 5}})
        with self.assertRaisesRegex(ValueError, "unbounded schema node"):
            ov.worst_case_output_chars({"type": "number"})

    def test_the_worst_case_answer_fits_the_allowance_with_room_left_to_think(self):
        worst = ov.worst_case_output_chars(ov.schema_overview(IDS, PARTS))
        allowance = topo.OVERVIEW_S_OPTIONS["num_predict"]
        # counted, conservatively, at one token per character
        self.assertLessEqual(worst + ov.MIN_REASONING_HEADROOM, allowance)
        self.assertEqual(worst, 3000)

    def test_the_schema_grows_only_with_the_bounds_not_with_the_input(self):
        small = ov.worst_case_output_chars(ov.schema_overview(["U1"], ["c1"]))
        large = ov.worst_case_output_chars(ov.schema_overview(IDS, PARTS))
        self.assertLess(large - small, 200)  # only the enum id widths differ


class BudgetArithmeticTests(unittest.TestCase):
    o = topo.OVERVIEW_S_OPTIONS

    def test_prompt_cap_plus_allowance_fits_the_context_exactly_as_the_supervisor_will_count_it(self):
        estimated_prompt_tokens = ov.MAX_PROMPT_CHARS / 3.0  # the harness's own conservative chars-per-token estimate
        self.assertLessEqual(estimated_prompt_tokens + self.o["num_predict"], self.o["num_ctx"])

    def test_the_allowance_needs_a_plausible_generation_speed_to_finish_inside_the_watchdog(self):
        needed = self.o["num_predict"] / topo.WALL_TIMEOUT_SECONDS
        self.assertLess(needed, 14)  # measured 32-34 tok/s at 12,288 ctx; unmeasured at 20,480 on the 8 GB card
        self.assertGreater(needed, 13)

    def test_the_context_is_larger_than_every_other_role_and_that_is_only_for_s(self):
        self.assertGreater(self.o["num_ctx"], topo.SUPERVISOR_BASE_OPTIONS["num_ctx"])
        self.assertEqual(topo.SUPERVISOR_BASE_OPTIONS["num_ctx"], 12288)

    def test_a_prompt_at_the_cap_is_still_accepted_by_the_supervisor(self):
        specs = [
            (
                f"claim {i}",
                (100 + i, 900 + i, "e1", f"Participant group {i} reported explicit dislike of scarred faces."),
                [S1],
            )
            for i in range(15)
        ]
        client = OverviewClient(s={"overview": []})
        record, _ = build(sealed_ledger(specs), client)
        self.assertEqual(record["state"], "model_returned_empty")  # not prompt_too_large: the cap and the context agree
        self.assertLessEqual(len(client.calls[0]["prompt"]), ov.MAX_PROMPT_CHARS)


class PromptPinTests(unittest.TestCase):
    def test_the_instructions_are_pinned(self):
        self.assertEqual(hashlib.sha256(ov.PROMPT_TEMPLATE.encode("utf-8")).hexdigest(), PROMPT_TEMPLATE_SHA256)

    def test_the_contract_hash_moves_with_the_budget_and_sampling(self):
        base = ov.contract_sha256(topo.OVERVIEW_S_OPTIONS)
        self.assertEqual(base, ov.contract_sha256(dict(topo.OVERVIEW_S_OPTIONS)))
        self.assertNotEqual(base, ov.contract_sha256({**topo.OVERVIEW_S_OPTIONS, "temperature": 0}))
        self.assertNotEqual(base, ov.contract_sha256({**topo.OVERVIEW_S_OPTIONS, "num_predict": 8192}))

    def test_the_instructions_carry_each_guard_the_screen_relies_on(self):
        text = ov.PROMPT_TEMPLATE
        for needle in (
            "Never use a claim's wording unless its passage establishes it",
            "not in passage:",
            "Keep every hedge",
            "unless a passage itself says so",
            "Do not use words such as several, consistently or studies unless the cited passages come from more than one paper",
            "Say nothing about what is missing or unknown",
            "bears_on is a tag, not a claim that a part is fully answered",
        ):
            self.assertIn(needle, text)

    def test_nothing_hierarchical_or_provenance_shaped_reaches_the_model_as_wording(self):
        # Like every supervisory prompt, this one prints request-part id labels ("- c4: <wording>"); the hierarchy guard is about
        # the WORDING. So scan the prompt with the id labels and the passage ids removed.
        client = OverviewClient(s={"overview": []})
        build(sealed_ledger([("c", GIVING, [S1]), ("d", HEDGE, [S2])]), client)
        prompt = client.calls[0]["prompt"]
        wording = re.sub(r"(?m)^- \S+: ", "- ", prompt)  # request-part id labels
        wording = re.sub(r"(?m)^\[U\d+\] ", "[passage] ", wording)  # passage ids
        wording = re.sub(r"(?m)^- p\d+: ", "- claim: ", wording)  # claim ids
        self.assertEqual(provenance_tokens(wording), [])
        self.assertEqual(provenance_tokens(ov.PROMPT_TEMPLATE), [])

    def test_the_json_example_uses_placeholders_so_it_cannot_anchor_the_model_on_a_real_id(self):
        example = ov.PROMPT_TEMPLATE.rsplit("Return JSON only", 1)[1]
        self.assertIn("<passage id>", example)
        self.assertIn("<part id>", example)
        self.assertNotRegex(example, r'"U\d+"|"c\d+"|"s\d+-o\d+"')

    def test_the_preflight_shows_the_exact_prompt_budget_and_sampling_without_touching_anything(self):
        report = ov.preflight_report(topo.OVERVIEW_S_OPTIONS)
        for needle in (
            "contract sha256",
            '"num_ctx": 20480',
            '"num_predict": 16384',
            '"presence_penalty": 1.5',
            "PROMPT TEMPLATE",
            "no fallback",
        ):
            self.assertIn(needle, report)


class FixedEnvelopeTests(unittest.TestCase):
    def test_there_is_no_automatic_fallback_or_escalation_anywhere_in_the_stage(self):
        client = OverviewClient(s=None)  # every call caps
        record, _ = build(sealed_ledger([("c", GIVING, [S1])]), client)
        self.assertEqual(len(client.calls), 1)  # one attempt
        self.assertEqual(client.calls[0]["options"], topo.OVERVIEW_S_OPTIONS)
        self.assertEqual(record["options"], topo.OVERVIEW_S_OPTIONS)  # unchanged after the failure


if __name__ == "__main__":
    unittest.main()
