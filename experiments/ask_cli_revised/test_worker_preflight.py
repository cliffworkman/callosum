"""The Qwen3.5 think:false worker preflight: pass/fail on three mechanical questions, nothing about quality."""

import json
import unittest

from experiments.ask_cli_revised import worker_preflight as pre


class ScriptedWorkerClient:
    """Answers the four worker tasks with schema-valid JSON, with hooks to break one property at a time."""

    def __init__(self, *, thinking="", done_reason="stop", status="ok", break_schema=False, raise_on_think=False):
        self.calls = []
        self.thinking, self.done_reason, self.status = thinking, done_reason, status
        self.break_schema, self.raise_on_think = break_schema, raise_on_think

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive=None, wall_timeout=None):
        self.calls.append({"model": model, "schema": schema, "options": dict(options), "think": think})
        props = schema.get("properties", {})
        if "action" in props:
            answer = {"action": "accept"}
        elif "span_ids" in props:
            answer = {"span_ids": ["e1"]}
        elif "claim" in props:
            answer = {"claim": "Napping improved recall."}
        else:
            answer = {"query": "nap and recall"}
        if self.break_schema:
            answer = {"unexpected": True}
        return {
            "status": self.status,
            "error": None,
            "content": json.dumps(answer),
            "thinking": self.thinking,
            "done_reason": self.done_reason,
            "timings": {"prompt_eval_count": 10, "eval_count": 5, "load_duration": 0},
            "wall_seconds": 0.1,
        }


class PreflightTests(unittest.TestCase):
    def test_a_conforming_model_passes_all_three_questions_in_about_eight_calls(self):
        client = ScriptedWorkerClient()
        result = pre.run_preflight(client, "qwen3.5:9b")
        self.assertTrue(result["pass"])
        self.assertEqual(
            result["criteria"], {"accepts_think_false": True, "worker_schemas_hold": True, "completes_under_caps": True}
        )
        self.assertEqual(len(client.calls), 8)
        self.assertEqual({c["think"] for c in client.calls}, {False})  # thinking is explicitly off on every call

    def test_all_four_worker_tasks_are_exercised_with_their_own_schemas(self):
        client = ScriptedWorkerClient()
        pre.run_preflight(client, "qwen3.5:9b")
        kinds = {
            "gate" if "action" in c["schema"]["properties"]
            else "select" if "span_ids" in c["schema"]["properties"]
            else "claim" if "claim" in c["schema"]["properties"]
            else "query"
            for c in client.calls
        }  # fmt: skip
        self.assertEqual(kinds, {"gate", "select", "claim", "query"})

    def test_calls_run_at_the_workers_own_small_caps_not_the_supervisor_allowance(self):
        client = ScriptedWorkerClient()
        pre.run_preflight(client, "qwen3.5:9b")
        self.assertTrue(all(c["options"]["num_predict"] <= 512 for c in client.calls))

    def test_reasoning_output_despite_think_false_fails_the_first_question(self):
        result = pre.run_preflight(ScriptedWorkerClient(thinking="Let me think..."), "qwen3.5:9b")
        self.assertFalse(result["pass"])
        self.assertFalse(result["criteria"]["accepts_think_false"])

    def test_a_schema_that_does_not_hold_fails_the_second_question(self):
        result = pre.run_preflight(ScriptedWorkerClient(break_schema=True), "qwen3.5:9b")
        self.assertFalse(result["pass"])
        self.assertFalse(result["criteria"]["worker_schemas_hold"])

    def test_a_call_that_hits_its_cap_fails_the_third_question(self):
        result = pre.run_preflight(ScriptedWorkerClient(done_reason="length"), "qwen3.5:9b")
        self.assertFalse(result["pass"])
        self.assertFalse(result["criteria"]["completes_under_caps"])

    def test_a_transport_failure_is_reported_as_infrastructure_not_as_a_model_failure(self):
        result = pre.run_preflight(ScriptedWorkerClient(status="transport_error"), "qwen3.5:9b")
        self.assertFalse(result["pass"])
        self.assertEqual(result["infrastructure_failures"], 8)

    def test_the_record_carries_per_call_facts_and_no_prompt_text(self):
        result = pre.run_preflight(ScriptedWorkerClient(), "qwen3.5:9b")
        call = result["calls"][0]
        for key in (
            "task",
            "outcome",
            "done_reason",
            "thinking_chars",
            "generated_tokens",
            "wall_seconds",
            "allowance",
        ):
            self.assertIn(key, call)
        self.assertNotIn("prompt_text", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
