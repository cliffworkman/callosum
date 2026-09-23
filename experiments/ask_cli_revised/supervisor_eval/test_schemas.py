"""Per-case output schemas: only the grammar vocabulary already proven on this Ollama stack.

The bakeoff must compare supervisory semantics, not models' handling of an unproven grammar
keyword, so `uniqueItems` and friends are banned; duplicates are removed after parsing.
"""

import unittest

import jsonschema

from experiments.ask_cli_revised.supervisor_eval import cases, schemas

ALLOWED_KEYWORDS = {"type", "properties", "required", "additionalProperties", "items", "maxItems", "maxLength", "enum"}


def _walk(node, seen):
    """Collect every schema keyword used (skipping property *names* and enum *values*)."""
    if isinstance(node, dict):
        for key, value in node.items():
            seen.add(key)
            if key == "properties":
                for sub in value.values():
                    _walk(sub, seen)
            elif key == "enum":
                continue
            else:
                _walk(value, seen)
    elif isinstance(node, list):
        for item in node:
            _walk(item, seen)


def _spec(case_id):
    return next(s for s in cases.build_case_specs() if s["case_id"] == case_id)


class VocabularyTests(unittest.TestCase):
    def test_every_schema_uses_only_the_proven_vocabulary(self):
        for spec in cases.build_case_specs():
            seen = set()
            _walk(schemas.build_schema(spec), seen)
            self.assertLessEqual(seen, ALLOWED_KEYWORDS, f"{spec['case_id']}: {seen - ALLOWED_KEYWORDS}")

    def test_no_unique_items_anywhere(self):
        for spec in cases.build_case_specs():
            self.assertNotIn("uniqueItems", repr(schemas.build_schema(spec)), spec["case_id"])

    def test_every_object_forbids_additional_properties(self):
        def check(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                for k, v in node.items():
                    if k == "properties":
                        for sub in v.values():
                            check(sub)
                    elif k != "enum":
                        check(v)
            elif isinstance(node, list):
                for item in node:
                    check(item)

        for spec in cases.build_case_specs():
            check(schemas.build_schema(spec))

    def test_rationale_is_declared_first_and_bounded(self):
        for spec in cases.build_case_specs():
            schema = schemas.build_schema(spec)
            self.assertEqual(list(schema["properties"])[0], "rationale", spec["case_id"])
            self.assertEqual(schema["properties"]["rationale"]["maxLength"], schemas.RATIONALE_MAX_CHARS)
            self.assertEqual(schema["required"][0], "rationale")


class TaskASchemaTests(unittest.TestCase):
    def test_ids_are_enum_constrained_to_the_legal_obligations(self):
        schema = schemas.build_schema(_spec("A3.original"))
        items = schema["properties"]["responsive_obligation_ids"]
        self.assertEqual(items["type"], "array")
        self.assertEqual(items["maxItems"], 6)
        self.assertEqual(items["items"], {"type": "string", "enum": cases.OBLIGATION_IDS})

    def test_empty_list_is_valid_and_invented_id_is_not(self):
        schema = schemas.build_schema(_spec("A3.original"))
        jsonschema.validate({"rationale": "none apply", "responsive_obligation_ids": []}, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"rationale": "x", "responsive_obligation_ids": ["s7-o1"]}, schema)

    def test_presentation_order_does_not_change_the_legal_set(self):
        a = schemas.build_schema(_spec("A1.original"))["properties"]["responsive_obligation_ids"]["items"]["enum"]
        b = schemas.build_schema(_spec("A1.reversed"))["properties"]["responsive_obligation_ids"]["items"]["enum"]
        self.assertEqual(sorted(a), sorted(b))


class TaskBSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = schemas.build_schema(_spec("B1.original"))
        self.cov = self.schema["properties"]["coverage"]

    def test_one_entry_per_obligation_is_required(self):
        self.assertEqual(self.cov["required"], cases.OBLIGATION_IDS)
        self.assertEqual(list(self.cov["properties"]), cases.OBLIGATION_IDS)

    def test_entry_vocabulary_has_no_absent_from_corpus_state(self):
        entry = self.cov["properties"]["s4-o1"]
        self.assertEqual(entry["properties"]["status"]["enum"], ["responsive_support", "unresolved"])
        self.assertEqual(entry["properties"]["supporting_proposition_ids"]["items"]["enum"], cases.PROPOSITION_IDS)

    def test_a_complete_valid_answer_validates(self):
        answer = {
            "rationale": "r",
            "coverage": {ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in cases.OBLIGATION_IDS},
        }
        jsonschema.validate(answer, self.schema)

    def test_a_missing_obligation_entry_is_rejected(self):
        answer = {
            "rationale": "r",
            "coverage": {
                ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in cases.OBLIGATION_IDS[:-1]
            },
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(answer, self.schema)


class TaskCSchemaTests(unittest.TestCase):
    def test_each_obligation_gets_exactly_its_own_legal_action_enum(self):
        spec = _spec("C1.original")
        plan = schemas.build_schema(spec)["properties"]["plan"]
        self.assertEqual(plan["required"], cases.OBLIGATION_IDS)
        for ob in cases.OBLIGATION_IDS:
            self.assertEqual(plan["properties"][ob], {"type": "string", "enum": spec["legal"]["actions"][ob]})

    def test_an_action_from_another_obligation_is_invalid(self):
        spec = _spec("C1.original")
        schema = schemas.build_schema(spec)
        plan = {ob: spec["legal"]["actions"][ob][0] for ob in cases.OBLIGATION_IDS}
        jsonschema.validate({"rationale": "r", "plan": plan}, schema)
        plan["s4-o1"] = "s3-o1:PRESERVE_UNRESOLVED"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"rationale": "r", "plan": plan}, schema)


if __name__ == "__main__":
    unittest.main()
