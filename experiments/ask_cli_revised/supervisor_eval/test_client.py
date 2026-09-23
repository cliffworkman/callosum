"""Thin Ollama client: request shape, streamed aggregation, failure classification, identity helpers.

Uses httpx.MockTransport only; nothing here touches a network or a model.
"""

import json
import unittest

import httpx

from experiments.ask_cli_revised.supervisor_eval import ollama_client
from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient

SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"], "additionalProperties": False}
OPTIONS = {"num_ctx": 12288, "num_predict": 4096, "temperature": 0, "seed": 42, "num_thread": 6, "num_batch": 512}
FINAL = {
    "model": "m",
    "done": True,
    "done_reason": "stop",
    "total_duration": 5_000_000_000,
    "load_duration": 1_000_000_000,
    "prompt_eval_count": 120,
    "prompt_eval_duration": 500_000_000,
    "eval_count": 30,
    "eval_duration": 3_000_000_000,
}


def ndjson(*rows):
    return ("\n".join(json.dumps(r) for r in rows) + "\n").encode()


def client_for(handler):
    return OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))


class Recorder:
    def __init__(self, body):
        self.body, self.requests = body, []

    def __call__(self, request):
        self.requests.append(request)
        return httpx.Response(200, content=self.body)


class GuardTests(unittest.TestCase):
    def test_only_loopback_endpoints_are_accepted(self):
        for bad in ("http://example.com:11434", "http://10.0.0.123:11434", "https://api.openai.com"):
            with self.assertRaises(ValueError):
                OllamaClient(bad)
        for ok in ("http://127.0.0.1:11434", "http://localhost:11434"):
            OllamaClient(ok)


class ChatRequestShapeTests(unittest.TestCase):
    def _sent(self, **kw):
        rec = Recorder(ndjson({"message": {"content": "{}"}, "done": False}, FINAL))
        client_for(rec).chat("m", "hello", schema=SCHEMA, options=OPTIONS, **kw)
        return json.loads(rec.requests[0].content)

    def test_body_carries_schema_options_and_streams(self):
        body = self._sent()
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hello"}])
        self.assertIs(body["stream"], True)
        self.assertEqual(body["format"], SCHEMA)
        self.assertEqual(body["options"], OPTIONS)
        self.assertEqual(body["keep_alive"], "30m")

    def test_think_is_omitted_unless_requested(self):
        self.assertNotIn("think", self._sent())
        self.assertIs(self._sent(think=True)["think"], True)
        self.assertEqual(self._sent(think="medium")["think"], "medium")

    def test_posts_to_api_chat(self):
        rec = Recorder(ndjson(FINAL))
        client_for(rec).chat("m", "p", schema=SCHEMA, options=OPTIONS)
        self.assertEqual(rec.requests[0].url.path, "/api/chat")
        self.assertEqual(rec.requests[0].method, "POST")


class ChatAggregationTests(unittest.TestCase):
    def test_streamed_content_thinking_and_timings_are_aggregated(self):
        rec = Recorder(
            ndjson(
                {"message": {"thinking": "let me "}, "done": False},
                {"message": {"thinking": "think"}, "done": False},
                {"message": {"content": '{"x":'}, "done": False},
                {"message": {"content": ' "y"}'}, "done": False},
                FINAL,
            )
        )
        out = client_for(rec).chat("m", "p", schema=SCHEMA, options=OPTIONS)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["content"], '{"x": "y"}')
        self.assertEqual(out["thinking"], "let me think")
        self.assertEqual(out["done_reason"], "stop")
        self.assertEqual(out["timings"]["prompt_eval_count"], 120)
        self.assertEqual(out["timings"]["eval_count"], 30)
        self.assertEqual(out["timings"]["load_duration"], 1_000_000_000)
        self.assertGreaterEqual(out["wall_seconds"], 0)
        self.assertIsNone(out["error"])

    def test_length_stop_is_reported_verbatim(self):
        rec = Recorder(ndjson({"message": {"content": "{"}, "done": False}, {**FINAL, "done_reason": "length"}))
        self.assertEqual(client_for(rec).chat("m", "p", schema=SCHEMA, options=OPTIONS)["done_reason"], "length")

    def test_inline_think_prefix_is_split_out_of_content(self):
        rec = Recorder(ndjson({"message": {"content": '<think>pondering</think>{"x": "y"}'}, "done": False}, FINAL))
        out = client_for(rec).chat("m", "p", schema=SCHEMA, options=OPTIONS)
        self.assertEqual(out["content"], '{"x": "y"}')
        self.assertEqual(out["thinking"], "pondering")

    def test_tokens_per_second_is_derived_from_ollama_durations(self):
        rec = Recorder(ndjson({"message": {"content": "{}"}, "done": False}, FINAL))
        out = client_for(rec).chat("m", "p", schema=SCHEMA, options=OPTIONS)
        self.assertAlmostEqual(out["generation_tokens_per_second"], 10.0)  # 30 tokens / 3 s


class ChatFailureTests(unittest.TestCase):
    def test_http_error_is_classified_with_status_and_body(self):
        out = client_for(lambda r: httpx.Response(500, content=b"model requires a newer version of Ollama")).chat(
            "m", "p", schema=SCHEMA, options=OPTIONS
        )
        self.assertEqual(out["status"], "http_error")
        self.assertIn("500", out["error"])
        self.assertIn("newer version", out["error"])
        self.assertEqual(out["content"], "")

    def test_read_timeout_is_classified_as_timeout(self):
        def boom(request):
            raise httpx.ReadTimeout("slow", request=request)

        out = client_for(boom).chat("m", "p", schema=SCHEMA, options=OPTIONS)
        self.assertEqual(out["status"], "timeout")

    def test_connect_failure_is_a_transport_error(self):
        def boom(request):
            raise httpx.ConnectError("refused", request=request)

        self.assertEqual(client_for(boom).chat("m", "p", schema=SCHEMA, options=OPTIONS)["status"], "transport_error")

    def test_mid_stream_runtime_error_is_reported(self):
        rec = Recorder(
            ndjson({"message": {"content": "{"}, "done": False}, {"error": "llama runner process has terminated"})
        )
        out = client_for(rec).chat("m", "p", schema=SCHEMA, options=OPTIONS)
        self.assertEqual(out["status"], "runtime_error")
        self.assertIn("terminated", out["error"])

    def test_wall_clock_watchdog_stops_a_call_that_runs_too_long(self):
        ticks = iter([0, 1, 700, 701, 702, 703])
        rec = Recorder(ndjson(*([{"message": {"content": "x"}, "done": False}] * 4), FINAL))
        out = client_for(rec).chat(
            "m", "p", schema=SCHEMA, options=OPTIONS, wall_timeout=600, clock=lambda: next(ticks)
        )
        self.assertEqual(out["status"], "timeout")
        self.assertIn("watchdog", out["error"])


class ControlEndpointTests(unittest.TestCase):
    def test_version_tags_and_ps(self):
        def handler(request):
            return {
                "/api/version": httpx.Response(200, json={"version": "0.12.3"}),
                "/api/tags": httpx.Response(200, json={"models": [{"name": "phi4:14b", "size": 9}]}),
                "/api/ps": httpx.Response(200, json={"models": [{"name": "phi4:14b", "size": 100, "size_vram": 60}]}),
            }[request.url.path]

        c = client_for(handler)
        self.assertEqual(c.version(), "0.12.3")
        self.assertEqual([m["name"] for m in c.tags()], ["phi4:14b"])
        self.assertEqual(c.ps()[0]["size_vram"], 60)

    def test_residency_is_the_gpu_fraction(self):
        self.assertAlmostEqual(ollama_client.gpu_fraction({"size": 100, "size_vram": 60}), 0.6)
        self.assertEqual(ollama_client.gpu_fraction({"size": 0, "size_vram": 0}), 0.0)

    def test_show_summary_extracts_identity_fields(self):
        show = {
            "details": {"family": "phi3", "parameter_size": "14.7B", "quantization_level": "Q4_K_M"},
            "model_info": {"general.architecture": "phi3", "phi3.context_length": 16384},
            "capabilities": ["completion"],
            "license": "MIT License\nCopyright ...",
        }
        s = ollama_client.summarize_show(show)
        self.assertEqual(s["family"], "phi3")
        self.assertEqual(s["parameter_size"], "14.7B")
        self.assertEqual(s["quantization_level"], "Q4_K_M")
        self.assertEqual(s["context_length"], 16384)
        self.assertEqual(s["capabilities"], ["completion"])
        self.assertEqual(s["license_head"], "MIT License")

    def test_pull_streams_progress_and_reports_success(self):
        rec = Recorder(
            ndjson(
                {"status": "pulling manifest"},
                {"status": "downloading", "total": 100, "completed": 50},
                {"status": "success"},
            )
        )
        seen = []
        result = client_for(rec).pull("m", on_progress=seen.append)
        self.assertEqual(result["status"], "success")
        self.assertEqual(seen[1]["completed"], 50)
        self.assertEqual(rec.requests[0].url.path, "/api/pull")
        self.assertIs(json.loads(rec.requests[0].content)["stream"], True)

    def test_pull_failure_is_reported_not_raised(self):
        result = client_for(lambda r: httpx.Response(412, content=b"requires a newer version of Ollama")).pull("m")
        self.assertEqual(result["status"], "error")
        self.assertIn("newer version", result["error"])

    def test_unload_sends_keep_alive_zero(self):
        rec = Recorder(b"{}")
        client_for(rec).unload("m")
        body = json.loads(rec.requests[0].content)
        self.assertEqual((body["model"], body["keep_alive"]), ("m", 0))
        self.assertEqual(rec.requests[0].url.path, "/api/generate")


if __name__ == "__main__":
    unittest.main()
