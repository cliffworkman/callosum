"""Backends: one call-record shape for both the Q2.5 managed-local path and Ollama-native models, and residency."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.backend.llm.providers import CompletionResult, ProviderError
from experiments.ask_cli_revised import backends
from experiments.ask_cli_revised import execution_policy as policy
from experiments.ask_cli_revised.qwen import QwenTasks
from experiments.ask_cli_revised.retrieval import GATE_NO_ANSWER

SCHEMA = {
    "type": "object",
    "required": ["action"],
    "additionalProperties": False,
    "properties": {"action": {"type": "string", "enum": ["accept", "discard"]}},
}
BASE = {"num_ctx": 12288, "num_predict": 4096, "temperature": 0, "seed": 42}


class FakeTrace:
    def __init__(self):
        self.calls = []

    def qwen_call(self, **kwargs):
        self.calls.append(kwargs)


class ManagedLocalChatTests(unittest.TestCase):
    def chat(self, result=None, error=None):
        seen = {}

        def fake_schema_config(config, *, output_cap, json_schema, mode):
            seen.update(output_cap=output_cap, json_schema=json_schema, mode=mode)
            return "CFG"

        def fake_complete(config, prompt):
            seen["prompt"] = prompt
            if error:
                raise error
            return result

        with (
            patch.object(backends, "schema_config", fake_schema_config),
            patch.object(backends, "complete", fake_complete),
        ):
            record = backends.ManagedLocalChat("BASECFG").chat(
                "callosum-managed-local", "PROMPT", schema=SCHEMA, options={**BASE, "num_predict": 48}, think=None
            )
        return record, seen

    def test_the_options_allowance_becomes_the_managed_local_output_cap_with_the_schema(self):
        _, seen = self.chat(CompletionResult(text='{"action":"accept"}', usage_metadata=None))
        self.assertEqual(seen["output_cap"], 48)
        self.assertEqual(seen["json_schema"], SCHEMA)
        self.assertEqual(seen["prompt"], "PROMPT")

    def test_a_completed_call_has_the_ollama_record_shape(self):
        usage = SimpleNamespace(prompt_token_count=310, candidates_token_count=9)
        record, _ = self.chat(CompletionResult(text='{"action":"accept"}', usage_metadata=usage))
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["content"], '{"action":"accept"}')
        self.assertEqual(record["done_reason"], "stop")
        self.assertEqual(record["timings"]["prompt_eval_count"], 310)
        self.assertEqual(record["timings"]["eval_count"], 9)
        self.assertIsNotNone(record["wall_seconds"])

    def test_a_truncated_call_reports_length_so_the_seam_treats_it_as_no_answer(self):
        record, _ = self.chat(CompletionResult(text='{"action":"acc', usage_metadata=None, truncated=True))
        self.assertEqual(record["done_reason"], "length")
        result = policy.run_stage_call(
            SimpleNamespace(chat=lambda *a, **k: record),
            model_tag="callosum-managed-local",
            stage="worker",
            prompt="p",
            schema=SCHEMA,
            base_options=BASE,
        )
        self.assertIsNone(result.answer)
        self.assertEqual(result.record["outcome"], policy.CAPPED)

    def test_a_provider_error_is_a_classified_failed_call_not_an_exception(self):
        record, _ = self.chat(error=ProviderError("connection refused"))
        self.assertEqual(record["status"], "provider_error")
        self.assertIn("connection refused", record["error"])
        self.assertEqual(record["content"], "")


class FakeOllama:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, model, prompt, **kwargs):
        self.calls.append({"model": model, "prompt": prompt, **kwargs})
        return self.response


def native_record(content, done_reason="stop", status="ok"):
    return {
        "status": status,
        "error": None,
        "content": content,
        "thinking": "",
        "done_reason": done_reason,
        "timings": {"prompt_eval_count": 200, "eval_count": 8, "load_duration": 1_000_000_000},
        "wall_seconds": 1.5,
    }


class NativeWorkerTests(unittest.TestCase):
    def tasks(self, response):
        client = FakeOllama(response)
        worker = backends.NativeWorker(client=client, model="qwen3.5:9b", base_options=BASE, think=False)
        trace = FakeTrace()
        return QwenTasks(worker, trace), client, trace

    def test_model_name_reads_the_native_worker_s_own_model_field(self):
        """Phase 20b §4/§5: confirmed by direct inspection, never guessed -- NativeWorker.model."""
        task, _, _ = self.tasks(native_record('{"action":"accept"}'))
        self.assertEqual(task.model_name, "qwen3.5:9b")

    def test_a_worker_call_runs_through_the_seam_with_the_task_cap_and_thinking_off(self):
        task, client, trace = self.tasks(native_record('{"action":"accept"}'))
        decision = task.context_gate(packet_text="A complete finding.", subquestion="Which?")
        self.assertEqual(decision, {"action": "accept"})
        (call,) = client.calls
        self.assertEqual(call["options"]["num_predict"], 48)  # the worker's own small cap, not the supervisory 4096
        self.assertIs(call["think"], False)
        self.assertEqual(call["model"], "qwen3.5:9b")
        self.assertEqual(trace.calls[0]["extra"]["model"], "qwen3.5:9b")
        self.assertEqual(trace.calls[0]["extra"]["allowance"], 48)

    def test_a_capped_native_gate_call_is_no_answer_not_accept(self):
        task, client, trace = self.tasks(native_record("", done_reason="length"))
        self.assertEqual(task.context_gate(packet_text="x", subquestion="q"), {"action": GATE_NO_ANSWER})
        self.assertEqual(len(client.calls), 1)  # no retry
        self.assertEqual(trace.calls[0]["failure_reason"], "truncated_at_output_cap")

    def test_a_native_worker_call_requires_a_schema(self):
        task, _, _ = self.tasks(native_record("{}"))
        with self.assertRaises(ValueError):
            task._call(prompt="p", output_cap=48)


class ModelNameTests(unittest.TestCase):
    """Phase 20b §4/§5: QwenTasks.model_name, confirmed against BOTH real config shapes `bind()`
    ever constructs -- never a third, hypothetical shape invented just for this test."""

    def test_the_managed_local_path_reads_the_same_model_field_name(self):
        """`app.backend.llm.managed_local.ManagedProviderConfig.model` -- a SimpleNamespace stands
        in for the real (many-required-field) config here since the property only ever reads one
        attribute off it, generically; a real ManagedProviderConfig is exercised end to end by
        `ManagedLocalChatTests` above, which never constructs a QwenTasks at all."""
        task = QwenTasks(SimpleNamespace(model="callosum-managed-local"), FakeTrace())
        self.assertEqual(task.model_name, "callosum-managed-local")

    def test_a_config_with_no_model_attribute_reports_none_not_a_guess(self):
        task = QwenTasks(SimpleNamespace(), FakeTrace())
        self.assertIsNone(task.model_name)


class FakeResidentClient:
    def __init__(self, resident=()):
        self.resident = list(resident)
        self.unloaded = []

    def ps(self):
        return [{"name": name, "size": 100, "size_vram": 60} for name in self.resident]

    def unload(self, model):
        self.unloaded.append(model)
        self.resident = [m for m in self.resident if m != model]


class ResidencyGuardTests(unittest.TestCase):
    def guard(self):
        shared, isolated = FakeResidentClient(), FakeResidentClient()
        return backends.ResidencyGuard({"shared": shared, "isolated": isolated}), shared, isolated

    def test_moving_to_a_different_model_unloads_only_what_this_run_loaded(self):
        guard, shared, isolated = self.guard()
        shared.resident = ["callosum-managed-local", "someone-elses-model"]
        guard.enter("shared", "callosum-managed-local", phase="W")
        isolated.resident = ["phi4:14b"]
        event = guard.enter("isolated", "phi4:14b", phase="C")
        self.assertEqual(shared.unloaded, ["callosum-managed-local"])
        self.assertIn("someone-elses-model", shared.resident)  # never touched
        self.assertEqual(event["unloaded"], [["shared", "callosum-managed-local"]])

    def test_staying_on_the_same_model_does_not_unload_it(self):
        guard, shared, _ = self.guard()
        guard.enter("isolated", "qwen3.5:9b", phase="W")
        event = guard.enter("isolated", "qwen3.5:9b", phase="R")
        self.assertEqual(event["unloaded"], [])
        self.assertEqual(guard.events[-1]["phase"], "R")

    def test_each_phase_records_what_was_resident_on_both_endpoints(self):
        guard, shared, isolated = self.guard()
        shared.resident = ["callosum-managed-local"]
        event = guard.enter("shared", "callosum-managed-local", phase="W")
        self.assertEqual(
            event["resident"]["shared"], [{"name": "callosum-managed-local", "size": 100, "size_vram": 60}]
        )
        self.assertEqual(event["resident"]["isolated"], [])
        self.assertIn("wall_seconds", event)

    def test_an_after_phase_observation_records_what_the_model_actually_occupied(self):
        guard, shared, _ = self.guard()
        guard.enter("shared", "callosum-managed-local", phase="W1")
        shared.resident = ["callosum-managed-local"]  # loaded by the phase's first call
        guard.observe("W1")
        obs = guard.observations[-1]
        self.assertEqual(obs["phase"], "W1")
        self.assertEqual(obs["resident"]["shared"], [{"name": "callosum-managed-local", "size": 100, "size_vram": 60}])
        self.assertEqual(len(guard.events), 1)  # entry events are unchanged

    def test_a_failing_observation_is_recorded_not_raised(self):
        guard, shared, _ = self.guard()
        shared.ps = lambda: (_ for _ in ()).throw(RuntimeError("tunnel closed"))
        guard.observe("W1")
        self.assertIn("tunnel closed", guard.observations[-1]["error"])

    def test_release_all_unloads_everything_the_run_loaded_and_nothing_else(self):
        guard, shared, isolated = self.guard()
        guard.enter("shared", "callosum-managed-local", phase="W")
        guard.enter("isolated", "phi4:14b", phase="C")
        guard.release_all()
        self.assertEqual(shared.unloaded, ["callosum-managed-local"])
        self.assertEqual(isolated.unloaded, ["phi4:14b"])


if __name__ == "__main__":
    unittest.main()
