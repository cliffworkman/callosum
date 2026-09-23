"""Stage 0 neutral mechanical preflight: fixtures, padding, probes, nonstarter rules, and the whole flow
driven by a fake client (no network, no model).

Only clear mechanical nonstarters are eliminated. CPU offload or slowness never is.
"""

import json
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.supervisor_eval import models, stage0

GOOD = '{"tag": "x", "values": [0, 0, 0, 0], "flag": true}'


def call(status="ok", content=GOOD, done_reason="stop", prompt_tokens=90, error=None):
    return {
        "status": status,
        "error": error,
        "content": content,
        "thinking": None,
        "done_reason": done_reason,
        "timings": {
            "total_duration": 2_000_000_000,
            "load_duration": 500_000_000,
            "prompt_eval_count": prompt_tokens,
            "prompt_eval_duration": 100_000_000,
            "eval_count": 20,
            "eval_duration": 1_000_000_000,
        },
        "wall_seconds": 2.0,
        "time_to_first_token": 0.5,
        "generation_tokens_per_second": 20.0,
    }


def trial(name, valid=True, **kw):
    return {"name": name, "call": call(**kw), "valid_json": valid}


class FixtureTests(unittest.TestCase):
    def test_neutral_fixtures_load_and_verify_against_the_ask_070_spec(self):
        f = stage0.load_neutral_fixtures()
        self.assertIn("format-only test", f["prompt"])
        self.assertEqual(f["schema"]["properties"]["tag"]["enum"], ["x"])

    def test_a_tampered_spec_is_rejected(self):
        src = json.loads(Path(stage0.NEUTRAL_SPEC_PATH).read_text(encoding="utf-8"))
        src["neutral_prompt_utf8"] += " tampered"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "spec.json"
            p.write_text(json.dumps(src), encoding="utf-8")
            with self.assertRaises(ValueError):
                stage0.load_neutral_fixtures(p)

    def test_valid_neutral_checks_the_schema(self):
        self.assertTrue(stage0.valid_neutral(GOOD))
        self.assertFalse(stage0.valid_neutral('{"tag": "y", "values": [0, 0, 0, 0], "flag": true}'))
        self.assertFalse(stage0.valid_neutral("not json"))


class PaddingTests(unittest.TestCase):
    def test_estimate_k_scales_linearly_from_a_small_probe(self):
        # base prompt 100 tokens; 128 blocks add 512 tokens => 4 tokens/block => (8064-100)/4 blocks
        self.assertEqual(stage0.estimate_k(100, 128, 612, target=8064), 1991)

    def test_estimate_k_needs_a_probe_that_actually_added_tokens(self):
        with self.assertRaises(ValueError):
            stage0.estimate_k(100, 128, 100)

    def test_padded_prompt_starts_with_a_cache_breaking_nonce_and_ends_with_the_instruction(self):
        text = stage0.padded_prompt(3, "n0nce", "Return JSON.\n")
        self.assertTrue(text.startswith("[n0nce]\n"))
        self.assertEqual(text.count(stage0.PADDING_BLOCK), 3)
        self.assertTrue(text.endswith("Return JSON.\n"))

    def test_padding_is_only_the_fixed_punctuation_digit_alphabet(self):
        self.assertEqual(set(stage0.PADDING_BLOCK), set(". 0 ~\n"))


class EnumProbeTests(unittest.TestCase):
    def test_constrained_output_stays_inside_the_enum(self):
        self.assertIs(stage0.judge_enum_probe('{"answer": "alpha"}'), True)
        self.assertIs(stage0.judge_enum_probe('{"answer": "beta"}'), True)

    def test_an_out_of_enum_answer_proves_the_runtime_did_not_enforce(self):
        self.assertIs(stage0.judge_enum_probe('{"answer": "gamma"}'), False)

    def test_unparseable_output_is_indeterminate(self):
        self.assertIsNone(stage0.judge_enum_probe("Sure! gamma"))


class ClassifyTests(unittest.TestCase):
    def _good(self):
        return [trial("compact-cold"), trial("compact-warm-1"), trial("compact-warm-2"), trial("padded")]

    def test_a_healthy_model_is_ok(self):
        self.assertEqual(stage0.classify(self._good())["verdict"], "ok")

    def test_offload_and_slowness_are_never_disqualifying(self):
        slow = self._good()
        slow[3]["call"]["wall_seconds"] = 580.0
        slow[0]["call"]["timings"]["load_duration"] = 300_000_000_000
        self.assertEqual(stage0.classify(slow)["verdict"], "ok")

    def test_a_model_that_cannot_load_is_a_nonstarter(self):
        t = self._good()
        t[0] = trial("compact-cold", status="http_error", content="", error="HTTP 500: out of memory")
        out = stage0.classify(t)
        self.assertEqual(out["verdict"], "nonstarter")
        self.assertIn("compact-cold", out["reason"])

    def test_a_crash_mid_generation_is_a_nonstarter(self):
        t = self._good()
        t[1] = trial("compact-warm-1", status="runtime_error", content="", error="runner terminated")
        self.assertEqual(stage0.classify(t)["verdict"], "nonstarter")

    def test_a_trivial_call_that_hits_the_watchdog_is_a_nonstarter(self):
        t = self._good()
        t[2] = trial("compact-warm-2", status="timeout", content="", error="watchdog")
        self.assertEqual(stage0.classify(t)["verdict"], "nonstarter")

    def test_zero_valid_structured_outputs_is_a_nonstarter(self):
        t = [trial(n, valid=False, content="prose") for n in ("compact-cold", "compact-warm-1", "compact-warm-2")]
        t.append(trial("padded"))
        out = stage0.classify(t)
        self.assertEqual(out["verdict"], "nonstarter")
        self.assertIn("structured", out["reason"])

    def test_partly_invalid_output_is_recorded_not_eliminated(self):
        t = self._good()
        t[1]["valid_json"] = False
        self.assertEqual(stage0.classify(t)["verdict"], "ok")

    def test_failing_to_allocate_the_realistic_context_is_a_nonstarter(self):
        t = self._good()
        t[3] = trial("padded", status="runtime_error", content="", error="CUDA out of memory")
        out = stage0.classify(t)
        self.assertEqual(out["verdict"], "nonstarter")
        self.assertIn("context", out["reason"])

    def test_a_slow_padded_call_that_times_out_is_descriptive_only(self):
        t = self._good()
        t[3] = trial("padded", status="timeout", content="", error="watchdog")
        self.assertEqual(stage0.classify(t)["verdict"], "ok")

    def test_a_dropped_tunnel_is_technical_not_a_model_verdict(self):
        t = self._good()
        t[0] = trial("compact-cold", status="transport_error", content="", error="ConnectError")
        self.assertEqual(stage0.classify(t)["verdict"], "technical")


class ProgressLoggerTests(unittest.TestCase):
    def test_pull_progress_is_logged_at_coarse_steps_not_per_chunk(self):
        lines = []
        cb = stage0.progress_logger(lines.append, "m:1b")
        for done in (0, 1, 2, 9, 10, 11, 49, 50, 51, 99, 100):
            cb({"status": "pulling abc", "total": 100, "completed": done})
        cb({"status": "verifying sha256 digest"})
        self.assertLessEqual(len(lines), 8)
        self.assertTrue(any("50%" in line for line in lines))
        self.assertTrue(any("100%" in line for line in lines))
        self.assertTrue(any("verifying" in line for line in lines))

    def test_rows_without_totals_are_ignored_safely(self):
        lines = []
        cb = stage0.progress_logger(lines.append, "m:1b")
        cb({"status": "pulling manifest"})
        cb({"total": 0, "completed": 0})
        self.assertEqual(len(lines), 1)  # the status line only


class FakeClient:
    """Duck-typed stand-in for OllamaClient with scripted behavior."""

    def __init__(self, present=True, pull_result=None, enum_ok=True, capabilities=("completion",)):
        self.present, self.pull_result = present, pull_result or {"status": "success"}
        self.enum_ok, self.capabilities = enum_ok, list(capabilities)
        self.calls, self.pulled, self.unloaded = [], [], []

    def tags(self):
        return [{"name": "m:1b"}] if self.present else []

    def show(self, model):
        return {
            "details": {"family": "fam", "parameter_size": "9B", "quantization_level": "Q4_K_M"},
            "model_info": {"fam.context_length": 32768},
            "capabilities": self.capabilities,
            "license": "MIT",
        }

    def ps(self):
        return [{"name": "m:1b", "size": 100, "size_vram": 60}]

    def pull(self, model, on_progress=None):
        self.pulled.append(model)
        return self.pull_result

    def unload(self, model):
        self.unloaded.append(model)

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive="30m", wall_timeout=600.0, **_):
        self.calls.append({"prompt": prompt, "schema": schema, "options": options, "think": think})
        if "gamma" in prompt:
            return call(content='{"answer": "alpha"}' if self.enum_ok else '{"answer": "gamma"}')
        if prompt.startswith("["):
            k = prompt.count(stage0.PADDING_BLOCK)
            return call(prompt_tokens=90 + 4 * k)
        return call()


CANDIDATE = {"key": "m-1b", "tag": "m:1b", "think_level": None}


class RunFlowTests(unittest.TestCase):
    def test_a_healthy_model_produces_the_full_receipt(self):
        client = FakeClient()
        r = stage0.run(client, CANDIDATE)
        self.assertEqual(r["verdict"], "ok")
        self.assertEqual(
            [t["name"] for t in r["trials"]], ["compact-cold", "compact-warm-1", "compact-warm-2", "padded"]
        )
        self.assertEqual(r["identity"]["quantization_level"], "Q4_K_M")
        self.assertEqual(r["identity"]["context_length"], 32768)
        self.assertEqual(r["enum_probe"]["enforced"], True)
        self.assertAlmostEqual(r["residency"]["gpu_fraction"], 0.6)
        self.assertEqual(r["envelope"], models.ENVELOPE)
        self.assertEqual(client.unloaded, ["m:1b"])  # never leaves a model resident for the next candidate
        self.assertEqual(client.pulled, [])

    def test_every_call_uses_the_uniform_envelope(self):
        client = FakeClient()
        stage0.run(client, CANDIDATE)
        for c in client.calls:
            self.assertEqual(c["options"], models.ENVELOPE)

    def test_the_padded_call_lands_near_the_8k_target_via_calibration(self):
        r = stage0.run(FakeClient(), CANDIDATE)
        tokens = r["padded"]["prompt_tokens"]
        self.assertTrue(7800 <= tokens <= 8192 - 64, tokens)

    def test_native_reasoning_is_requested_only_when_the_runtime_reports_it(self):
        client = FakeClient(capabilities=("completion", "thinking"))
        r = stage0.run(client, {**CANDIDATE, "think_level": "medium"})
        self.assertEqual(r["think_setting"], "medium")
        self.assertTrue(all(c["think"] == "medium" for c in client.calls))
        plain = FakeClient()
        self.assertIsNone(stage0.run(plain, CANDIDATE)["think_setting"])

    def test_an_unenforced_enum_is_recorded_as_a_finding_not_hidden(self):
        r = stage0.run(FakeClient(enum_ok=False), CANDIDATE)
        self.assertIs(r["enum_probe"]["enforced"], False)
        self.assertEqual(r["verdict"], "ok")  # a finding for the scorer (G2), not a nonstarter

    def test_an_absent_model_is_pulled_when_the_store_is_fine(self):
        client = FakeClient(present=False)
        r = stage0.run(client, CANDIDATE, store_check={"ok": True})
        self.assertEqual(client.pulled, ["m:1b"])
        self.assertEqual(r["verdict"], "ok")

    def test_a_runtime_too_old_to_pull_marks_the_candidate_blocked_without_touching_anything(self):
        client = FakeClient(
            present=False, pull_result={"status": "error", "error": "requires a newer version of Ollama"}
        )
        r = stage0.run(client, CANDIDATE, store_check={"ok": True})
        self.assertEqual(r["verdict"], models.BLOCKED)
        self.assertIn("newer version", r["reason"])
        self.assertEqual(client.calls, [])

    def test_a_store_that_cannot_hold_the_model_blocks_before_any_pull(self):
        client = FakeClient(present=False)
        r = stage0.run(client, CANDIDATE, store_check={"ok": False, "reason": "model store is on / with 12 GB free"})
        self.assertEqual(r["verdict"], models.BLOCKED)
        self.assertEqual(client.pulled, [])
        self.assertIn("12 GB", r["reason"])

    def test_an_already_present_model_needs_no_store_check(self):
        r = stage0.run(FakeClient(present=True), CANDIDATE, store_check={"ok": False, "reason": "small disk"})
        self.assertEqual(r["verdict"], "ok")

    def test_the_runtime_and_store_identity_are_recorded_verbatim_for_reproducibility(self):
        runtime = {
            "api_version": "0.34.3",
            "binary_sha256": "ab" * 32,
            "server_env": {"OLLAMA_MODELS": "/media/brain/JUNO/x"},
        }
        store = {"ok": True, "store_path": "/media/brain/JUNO/x", "free_gb": 460.0}
        r = stage0.run(FakeClient(), CANDIDATE, runtime=runtime, store_check=store)
        self.assertEqual(r["runtime"], runtime)
        self.assertEqual(r["store"], store)

    def test_a_blocked_candidate_still_records_why_and_where(self):
        store = {"ok": False, "reason": "store full", "store_path": "/x", "free_gb": 1.0}
        r = stage0.run(FakeClient(present=False), CANDIDATE, store_check=store, runtime={"api_version": "1"})
        self.assertEqual(r["verdict"], models.BLOCKED)
        self.assertEqual(r["store"], store)
        self.assertEqual(r["runtime"], {"api_version": "1"})

    def test_a_pull_that_fails_for_another_reason_is_technical_not_blocked(self):
        client = FakeClient(present=False, pull_result={"status": "error", "error": "connection reset"})
        r = stage0.run(client, CANDIDATE, store_check={"ok": True})
        self.assertEqual(r["verdict"], "technical")


if __name__ == "__main__":
    unittest.main()
