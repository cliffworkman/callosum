"""Execution-policy seam: the one evidence-supported allowance override, and fail-closed call outcomes.

The seam is what upcoming role binding will call; no live revised-Ask stage uses it yet, so these tests drive it through a
fake client. Nothing here touches a network, a model, or the frozen bakeoff registry: the caller supplies ordinary base
options (the values below merely mirror the bakeoff envelope) and the policy changes only the allowance.
"""

import unittest

from experiments.ask_cli_revised import execution_policy as policy

BASE = {"num_ctx": 12288, "num_predict": 4096, "temperature": 0, "seed": 42, "num_thread": 6, "num_batch": 512}

SCHEMA = {
    "type": "object",
    "required": ["rationale", "responsive_obligation_ids"],
    "additionalProperties": False,
    "properties": {
        "rationale": {"type": "string"},
        "responsive_obligation_ids": {"type": "array", "items": {"type": "string", "enum": ["s1-o1", "s2-o1"]}},
    },
}
GOOD = '{"rationale": "Answers the first item.", "responsive_obligation_ids": ["s1-o1"]}'
EMPTY = '{"rationale": "Answers none of the items.", "responsive_obligation_ids": []}'


def rec(content="", *, status="ok", done_reason="stop", eval_count=120, prompt_eval_count=600, thinking=""):
    """A call record shaped like OllamaClient.chat's return value."""
    return {
        "status": status,
        "error": None if status == "ok" else "boom",
        "content": content,
        "thinking": thinking,
        "done_reason": done_reason,
        "timings": {"prompt_eval_count": prompt_eval_count, "eval_count": eval_count},
        "wall_seconds": 7.5,
    }


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, model, prompt, **kwargs):
        self.calls.append({"model": model, "prompt": prompt, **kwargs})
        return self.response


class FakeTrace:
    def __init__(self):
        self.rows = []

    def qwen_call(self, **kwargs):
        self.rows.append(kwargs)
        return kwargs


class AllowanceTests(unittest.TestCase):
    def test_qwen35_recovery_planning_gets_8192(self):
        self.assertEqual(policy.generation_allowance(BASE, "qwen3.5:9b", policy.RECOVERY_PLANNING), 8192)

    def test_qwen35_every_other_stage_keeps_the_callers_allowance(self):
        for stage in ("claim_responsiveness", "coverage_audit", "worker", ""):
            with self.subTest(stage=stage):
                self.assertEqual(policy.generation_allowance(BASE, "qwen3.5:9b", stage), 4096)

    def test_other_families_keep_the_callers_allowance_even_for_recovery(self):
        for tag in ("gemma3:12b", "phi4:14b", "gpt-oss:20b", "qwen2.5:1.5b"):
            with self.subTest(tag=tag):
                self.assertEqual(policy.generation_allowance(BASE, tag, policy.RECOVERY_PLANNING), 4096)

    def test_family_match_is_case_insensitive_and_exact(self):
        for tag in ("Qwen3.5:9B", "qwen3.5:latest", "qwen3.5"):
            with self.subTest(tag=tag):
                self.assertEqual(policy.generation_allowance(BASE, tag, policy.RECOVERY_PLANNING), 8192)
        for tag in ("qwen3:8b", "qwen3.5x:9b", "myqwen3.5:9b"):
            with self.subTest(tag=tag):
                self.assertEqual(policy.generation_allowance(BASE, tag, policy.RECOVERY_PLANNING), 4096)

    def test_ordinary_allowance_is_whatever_the_caller_supplies(self):
        small = {**BASE, "num_predict": 2048}
        self.assertEqual(policy.generation_allowance(small, "qwen3.5:9b", "coverage_audit"), 2048)
        self.assertEqual(policy.generation_allowance(small, "qwen3.5:9b", policy.RECOVERY_PLANNING), 8192)

    def test_the_override_never_lowers_a_larger_caller_allowance(self):
        large = {**BASE, "num_predict": 16384}
        self.assertEqual(policy.generation_allowance(large, "qwen3.5:9b", policy.RECOVERY_PLANNING), 16384)

    def test_a_missing_or_invalid_base_allowance_fails_closed(self):
        without = {k: v for k, v in BASE.items() if k != "num_predict"}
        for bad in (
            without,
            {**BASE, "num_predict": 0},
            {**BASE, "num_predict": -1},
            {**BASE, "num_predict": "4096"},
            {**BASE, "num_predict": True},
            {**BASE, "num_predict": None},
        ):
            with self.subTest(bad=bad.get("num_predict", "<missing>")):
                with self.assertRaises(ValueError):
                    policy.generation_allowance(bad, "qwen3.5:9b", policy.RECOVERY_PLANNING)


class StageOptionsTests(unittest.TestCase):
    def test_only_num_predict_changes(self):
        for stage, expected in ((policy.RECOVERY_PLANNING, 8192), ("coverage_audit", 4096)):
            with self.subTest(stage=stage):
                options = policy.stage_options(BASE, "qwen3.5:9b", stage)
                self.assertEqual(options["num_predict"], expected)
                self.assertEqual(
                    {k: v for k, v in options.items() if k != "num_predict"},
                    {k: v for k, v in BASE.items() if k != "num_predict"},
                )
                self.assertEqual(options["num_ctx"], 12288)  # the context window is never widened by this policy

    def test_the_callers_options_are_not_mutated(self):
        before = dict(BASE)
        policy.stage_options(BASE, "qwen3.5:9b", policy.RECOVERY_PLANNING)
        self.assertEqual(BASE, before)


class RunStageCallTests(unittest.TestCase):
    def run_call(self, client, *, model="qwen3.5:9b", stage=policy.RECOVERY_PLANNING, **extra):
        return policy.run_stage_call(
            client, model_tag=model, stage=stage, prompt="PROMPT", schema=SCHEMA, base_options=BASE, **extra
        )

    def test_recovery_on_qwen35_sends_8192_in_exactly_one_call(self):
        client = FakeClient(rec(GOOD))
        self.run_call(client, think=True)
        self.assertEqual(len(client.calls), 1)
        call = client.calls[0]
        self.assertEqual(call["options"]["num_predict"], 8192)
        self.assertEqual(call["options"]["num_ctx"], 12288)
        self.assertEqual(call["model"], "qwen3.5:9b")
        self.assertEqual(call["prompt"], "PROMPT")
        self.assertIs(call["schema"], SCHEMA)
        self.assertIs(call["think"], True)

    def test_an_ordinary_qwen35_stage_sends_the_callers_allowance(self):
        client = FakeClient(rec(GOOD))
        self.run_call(client, stage="coverage_audit")
        self.assertEqual(client.calls[0]["options"]["num_predict"], 4096)

    def test_a_usable_call_returns_the_parsed_answer_and_a_full_record(self):
        result = self.run_call(FakeClient(rec(GOOD)))
        self.assertEqual(
            result.answer, {"rationale": "Answers the first item.", "responsive_obligation_ids": ["s1-o1"]}
        )
        self.assertEqual(
            result.record,
            {
                "model": "qwen3.5:9b",
                "stage": policy.RECOVERY_PLANNING,
                "allowance": 8192,
                "done_reason": "stop",
                "usable": True,
                "outcome": policy.USABLE,
                "status": "ok",
                "prompt_tokens": 600,
                "generated_tokens": 120,
                "wall_seconds": 7.5,
            },
        )

    def test_cap_exhaustion_is_no_answer_after_exactly_one_call(self):
        client = FakeClient(rec("", done_reason="length", eval_count=8192, thinking="still reasoning " * 500))
        result = self.run_call(client)
        self.assertIsNone(result.answer)  # NO ANSWER: not {}, not [], not an unresolved verdict
        self.assertFalse(result.record["usable"])
        self.assertEqual(result.record["outcome"], policy.CAPPED)
        self.assertEqual(result.record["done_reason"], "length")
        self.assertEqual(result.record["allowance"], 8192)
        self.assertEqual(len(client.calls), 1)  # no escalation, no retry

    def test_a_capped_call_is_no_answer_even_if_the_partial_content_parses(self):
        result = self.run_call(FakeClient(rec(GOOD, done_reason="length", eval_count=4096)), stage="coverage_audit")
        self.assertIsNone(result.answer)
        self.assertEqual(result.record["outcome"], policy.CAPPED)

    def test_stop_with_non_json_content_is_unparseable(self):
        result = self.run_call(FakeClient(rec("I think the answer is s1.")))
        self.assertIsNone(result.answer)
        self.assertEqual(result.record["outcome"], policy.UNPARSEABLE)

    def test_stop_with_json_outside_the_schema_is_schema_invalid(self):
        invented = '{"rationale": "x", "responsive_obligation_ids": ["s9-o1"]}'
        result = self.run_call(FakeClient(rec(invented)))
        self.assertIsNone(result.answer)
        self.assertEqual(result.record["outcome"], policy.SCHEMA_INVALID)

    def test_json_null_or_a_scalar_is_not_a_structured_answer(self):
        for content in ("null", '"s1-o1"', "3"):
            with self.subTest(content=content):
                result = self.run_call(FakeClient(rec(content)))
                self.assertIsNone(result.answer)
                self.assertFalse(result.record["usable"])
                self.assertEqual(result.record["outcome"], policy.SCHEMA_INVALID)

    def test_a_transport_failure_is_call_failed(self):
        result = self.run_call(FakeClient(rec("", status="timeout", done_reason=None)))
        self.assertIsNone(result.answer)
        self.assertEqual(result.record["outcome"], policy.CALL_FAILED)
        self.assertEqual(result.record["status"], "timeout")

    def test_a_completed_stream_with_no_stop_reason_is_call_failed(self):
        result = self.run_call(FakeClient(rec(GOOD, done_reason=None)))
        self.assertIsNone(result.answer)
        self.assertEqual(result.record["outcome"], policy.CALL_FAILED)

    def test_a_valid_empty_selection_is_an_answer_distinct_from_no_answer(self):
        result = self.run_call(FakeClient(rec(EMPTY)))
        self.assertIsNotNone(result.answer)
        self.assertEqual(result.answer["responsive_obligation_ids"], [])
        self.assertTrue(result.record["usable"])
        capped = self.run_call(FakeClient(rec("", done_reason="length")))
        self.assertIsNone(capped.answer)  # the two states must never be conflated

    def test_optional_chat_kwargs_are_forwarded_only_when_given(self):
        plain = FakeClient(rec(GOOD))
        self.run_call(plain)
        self.assertNotIn("keep_alive", plain.calls[0])
        self.assertNotIn("wall_timeout", plain.calls[0])
        tuned = FakeClient(rec(GOOD))
        self.run_call(tuned, keep_alive="5m", wall_timeout=900.0)
        self.assertEqual(tuned.calls[0]["keep_alive"], "5m")
        self.assertEqual(tuned.calls[0]["wall_timeout"], 900.0)

    def test_an_invalid_base_allowance_raises_before_any_call(self):
        client = FakeClient(rec(GOOD))
        with self.assertRaises(ValueError):
            policy.run_stage_call(
                client,
                model_tag="qwen3.5:9b",
                stage="coverage_audit",
                prompt="p",
                schema=SCHEMA,
                base_options={"num_ctx": 12288},
            )
        self.assertEqual(client.calls, [])

    def test_the_record_holds_no_model_text(self):
        result = self.run_call(FakeClient(rec(GOOD, thinking="private reasoning")))
        flattened = " ".join(str(v) for v in result.record.values())
        for text in ("PROMPT", "Answers the first item", "private reasoning"):
            self.assertNotIn(text, flattened)


class TraceTests(unittest.TestCase):
    def test_a_usable_call_is_recorded_through_the_existing_trace_seam(self):
        trace = FakeTrace()
        result = policy.run_stage_call(
            FakeClient(rec(GOOD)),
            model_tag="qwen3.5:9b",
            stage=policy.RECOVERY_PLANNING,
            prompt="PROMPT",
            schema=SCHEMA,
            base_options=BASE,
            trace=trace,
            input_text="ledger",
        )
        (row,) = trace.rows
        self.assertEqual(row["stage"], policy.RECOVERY_PLANNING)
        self.assertEqual(row["input_text"], "ledger")
        self.assertEqual(row["prompt_text"], "PROMPT")
        self.assertEqual(row["raw_output"], GOOD)
        self.assertEqual(row["output_cap"], 8192)
        self.assertTrue(row["validation_ok"])
        self.assertTrue(row["provider_ok"])
        self.assertIsNone(row["failure_reason"])
        self.assertFalse(row["deterministic_fallback_used"])
        self.assertEqual(row["extra"], result.record)

    def test_a_capped_call_is_recorded_as_a_mechanical_failure_never_a_fallback_decision(self):
        trace = FakeTrace()
        policy.run_stage_call(
            FakeClient(rec("", done_reason="length")),
            model_tag="qwen3.5:9b",
            stage="coverage_audit",
            prompt="PROMPT",
            schema=SCHEMA,
            base_options=BASE,
            trace=trace,
        )
        (row,) = trace.rows
        self.assertEqual(row["output_cap"], 4096)
        self.assertFalse(row["validation_ok"])
        self.assertFalse(row["provider_ok"])
        self.assertEqual(row["failure_reason"], policy.CAPPED)
        self.assertFalse(row["deterministic_fallback_used"])  # NO ANSWER is not a fallback verdict
        self.assertIn("NO ANSWER", row["downstream_consequence"])


if __name__ == "__main__":
    unittest.main()
