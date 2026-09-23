"""Frozen prompt templates: what the supervisor is told, and what it must NOT be shown."""

import unittest

from experiments.ask_cli_revised.supervisor_eval import cases, prompts

QUOTES = {p: f"QUOTE-TEXT-{p}" for p in cases.PROPOSITION_IDS}


def _spec(case_id):
    return next(s for s in cases.build_case_specs() if s["case_id"] == case_id)


class OriginalRequestTests(unittest.TestCase):
    """A supervisor always holds the user's request; item fragments like 'and using which scales?' mean nothing alone."""

    def test_every_task_shows_the_users_original_request_verbatim(self):
        for case_id in ("A3.original", "B1.original", "C1.original"):
            text = prompts.render(_spec(case_id), quotes=QUOTES)
            self.assertIn(cases.ORIGINAL_QUESTION, text, case_id)
            self.assertIn("original request", text.lower(), case_id)

    def test_the_request_precedes_the_items_it_was_split_into(self):
        text = prompts.render(_spec("A1.original"))
        self.assertLess(text.index(cases.ORIGINAL_QUESTION), text.index("Requested items:"))


class OutputContractTests(unittest.TestCase):
    """Ollama's `format` constrains decoding but does not show the model the schema, so the prompt must name the
    fields itself (the real Qwen map prompt did: `Return only JSON: {"field_ids": [...]}`)."""

    def _names(self, schema):
        names = set(schema["properties"])
        for sub in schema["properties"].values():
            if sub.get("type") == "object":
                names |= _all_names(sub)
        return names

    def test_every_field_in_every_schema_is_named_in_its_prompt(self):
        from experiments.ask_cli_revised.supervisor_eval import schemas

        for spec in cases.build_case_specs():
            text = prompts.render(spec, quotes=QUOTES)
            for name in self._names(schemas.build_schema(spec)) - set(cases.OBLIGATION_IDS):
                self.assertIn(f'"{name}"', text, f"{spec['case_id']}: {name}")

    def test_the_rationale_is_bounded_in_words_the_model_can_follow(self):
        for case_id in ("A1.original", "B1.original", "C1.original"):
            self.assertIn("one or two sentences", prompts.render(_spec(case_id), quotes=QUOTES), case_id)

    def test_task_c_shows_the_plan_shape_with_an_action_id_per_item(self):
        text = prompts.render(_spec("C1.original"))
        self.assertIn('"plan"', text)
        self.assertIn("one legal action id", text)


def _all_names(schema):
    names = set()
    for key, sub in schema.get("properties", {}).items():
        names.add(key)
        if isinstance(sub, dict) and sub.get("type") == "object":
            names |= _all_names(sub)
    return names


class TaskAPromptTests(unittest.TestCase):
    def test_carries_the_claim_and_every_obligation_in_the_specs_order(self):
        spec = _spec("A1.rotated")
        text = prompts.render(spec)
        self.assertIn(spec["claim"], text)
        positions = [text.index(f"- {ob}: ") for ob in spec["obligation_order"]]
        self.assertEqual(positions, sorted(positions))
        notes = {o["field_id"]: o["note"] for o in cases.OBLIGATIONS}
        for ob in cases.OBLIGATION_IDS:
            self.assertIn(notes[ob], text)

    def test_keeps_the_existing_responsiveness_wording_qwen_was_tested_on(self):
        text = prompts.render(_spec("A3.original"))
        self.assertIn("Select only requested items that the claim directly helps answer.", text)
        self.assertIn("Do not infer extra relationships.", text)
        self.assertIn("If it answers none, return an empty list.", text)

    def test_states_the_supervisory_standard_including_order_independence(self):
        text = prompts.render(_spec("A3.original"))
        self.assertIn("merely on a related topic", text)
        self.assertIn("where it appears in the list", text)
        self.assertIn("outside knowledge", text)

    def test_is_claim_only_no_source_material_or_provenance(self):
        text = prompts.render(_spec("A5.original")).lower()
        for leak in ("paper", "hadza", "quote", "retrieved"):
            self.assertNotIn(leak, text)

    def test_names_no_model_or_provider(self):
        text = prompts.render(_spec("A1.original")).lower()
        for name in ("qwen", "gemma", "phi", "gpt", "ollama", "gemini"):
            self.assertNotIn(name, text)

    def test_rendering_is_deterministic(self):
        self.assertEqual(prompts.render(_spec("A2.reversed")), prompts.render(_spec("A2.reversed")))


class TaskBPromptTests(unittest.TestCase):
    def test_lists_each_proposition_with_retrieval_context_and_quote_in_the_specs_order(self):
        spec = _spec("B1.reversed")
        text = prompts.render(spec, quotes=QUOTES)
        positions = [text.index(f"- {pid}: ") for pid in spec["proposition_order"]]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("retrieved while searching for: s3-o1", text)
        self.assertIn("QUOTE-TEXT-p5", text)
        self.assertIn("paper 45", text)

    def test_quotes_are_required_for_task_B(self):
        with self.assertRaises(ValueError):
            prompts.render(_spec("B1.original"))

    def test_separates_source_support_from_responsiveness_and_denies_corpus_absence(self):
        text = prompts.render(_spec("B1.original"), quotes=QUOTES)
        self.assertIn("NOT that it answers the request item", text)
        self.assertIn("does not mean the literature has no such evidence", text)
        self.assertIn("scientifically valid", text)


class TaskCPromptTests(unittest.TestCase):
    def setUp(self):
        self.text = prompts.render(_spec("C1.original"))

    def test_states_the_recovery_policy_being_tested(self):
        for sentence in (
            "one bounded attempt to resolve each remaining gap",
            "Do not repeat an already-performed search action.",
            "unused legal recovery action is available, choose that action before giving up",
            "preserve the obligation as unresolved",
            "Never mark an obligation covered using evidence that does not directly support it.",
            "Never invent an action or an evidence item.",
        ):
            self.assertIn(sentence, self.text)

    def test_shows_state_and_the_exact_legal_action_ids(self):
        self.assertIn("s4-o1:NOMINATE", self.text)
        self.assertIn("s3-o1:MARK_COVERED:p5", self.text)
        self.assertIn("s4-o1:DEEPEN", self.text)

    def test_marks_performed_actions_and_only_those(self):
        def line(action_id):
            return next(ln for ln in self.text.splitlines() if ln.strip().startswith(f"- {action_id}"))

        self.assertIn("ALREADY PERFORMED", line("s4-o1:DEEPEN"))
        self.assertNotIn("ALREADY PERFORMED", line("s4-o1:NOMINATE"))
        self.assertIn("ALREADY PERFORMED", line("s5-o1:NOMINATE"))

    def test_reversed_variant_lists_obligations_in_reverse(self):
        text = prompts.render(_spec("C1.reversed"))
        self.assertLess(text.index("Requested item s6-o1"), text.index("Requested item s1-o1"))


if __name__ == "__main__":
    unittest.main()
