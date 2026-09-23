"""The battery runner: freeze verification, one observation per case, resume, retry rules, receipts.

Driven by a scripted fake client; no network, no model. The behaviors pinned here are the experimental
discipline itself: verify the freeze before any call, never observe a frozen case twice, retry only a
genuine pre-observation technical failure, and publish only text-free receipts.
"""

import json
import statistics
import tempfile
import unittest
from pathlib import Path

from experiments.ask_070.hashing import digest
from experiments.ask_cli_revised.supervisor_eval import build_battery as bb
from experiments.ask_cli_revised.supervisor_eval import cases, freeze, models, run_eval, scoring
from experiments.ask_cli_revised.supervisor_eval.test_build_battery import QH, make_run
from experiments.ask_cli_revised.supervisor_eval.test_scoring import perfect_output

CANDIDATE = {"key": "m-1b", "tag": "m:1b", "think_level": None}


def rec(content="", status="ok", wall=2.0, tps=10.0, load=0, error=None, done_reason="stop", eval_count=20):
    return {
        "status": status,
        "error": error,
        "content": content,
        "thinking": "private reasoning",
        "done_reason": done_reason,
        "timings": {
            "total_duration": int(wall * 1e9),
            "load_duration": load,
            "prompt_eval_count": 500,
            "prompt_eval_duration": 1,
            "eval_count": eval_count if status == "ok" else None,
            "eval_duration": 1,
        },
        "wall_seconds": wall,
        "time_to_first_token": 0.4,
        "generation_tokens_per_second": tps,
    }


class PerfectClient:
    def __init__(self, battery, scripted=None):
        self.by_prompt = {c["prompt"]: cid for cid, c in battery["cases"].items()}
        self.specs = {s["case_id"]: s for s in cases.build_case_specs()}
        self.scripted, self.calls, self.unloaded = dict(scripted or {}), [], []

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive="30m", wall_timeout=600.0, **_):
        cid = self.by_prompt[prompt]
        self.calls.append(
            {
                "case_id": cid,
                "model": model,
                "options": options,
                "think": think,
                "schema": schema,
                "wall_timeout": wall_timeout,
            }
        )
        if cid in self.scripted:
            item = self.scripted[cid]
            return item.pop(0) if isinstance(item, list) else item
        return rec(json.dumps(perfect_output(self.specs[cid])), load=3_000_000_000 if len(self.calls) == 1 else 0)

    def ps(self):
        return [{"name": "m:1b", "size": 100, "size_vram": 50}]

    def unload(self, model):
        self.unloaded.append(model)


class FakeSampler:
    def __init__(self):
        self.started, self.stopped = [], 0

    def start(self, tag):
        self.started.append(tag)

    def stop(self):
        self.stopped += 1
        return {"n_samples": 3, "peak_gpu_mem_mib": 7000}


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        run = make_run(self.dir / "run")
        self.manifest_path, self.private_path = (
            self.dir / "public" / bb.MANIFEST_NAME,
            self.dir / "private" / bb.PRIVATE_NAME,
        )
        bb.build(run, self.dir / "public", self.dir / "private", expected_question_hash=QH)
        self.freeze_path = self.dir / "FREEZE.txt"
        freeze.write(self.freeze_path, freeze.compute(bb.freeze_spec(self.manifest_path, self.private_path)))
        self.out = self.dir / "out"

    def battery(self):
        return run_eval.load_frozen_battery(self.manifest_path, self.private_path, self.freeze_path)

    def run_all(self, client, **kw):
        return run_eval.run_battery(
            client,
            CANDIDATE,
            battery=self.battery(),
            out_dir=self.out,
            think=kw.pop("think", None),
            log=lambda m: None,
            **kw,
        )


class FreezeGuardTests(RunnerCase):
    def test_an_intact_freeze_loads(self):
        self.assertEqual(len(self.battery()["manifest"]["cases"]), 19)

    def test_a_tampered_private_prompt_is_refused_before_any_call(self):
        text = self.private_path.read_text(encoding="utf-8")
        self.private_path.write_text(text.replace("Candidate claim", "Candidate CLAIM"), encoding="utf-8")
        with self.assertRaises(run_eval.FreezeError):
            self.battery()

    def test_edited_frozen_code_is_refused(self):
        spec = bb.freeze_spec(self.manifest_path, self.private_path)
        frozen = freeze.compute(spec)
        frozen["code_files"]["scoring.py"] = "0" * 64
        frozen["freeze_sha256"] = digest({k: v for k, v in frozen.items() if k != "freeze_sha256"})
        freeze.write(self.freeze_path, frozen)
        with self.assertRaises(run_eval.FreezeError):
            self.battery()

    def test_a_prompt_that_does_not_match_the_public_manifest_hash_is_refused_even_if_refrozen(self):
        priv = json.loads(self.private_path.read_text(encoding="utf-8"))
        priv["cases"][0]["prompt"] += " sneaky change"
        self.private_path.write_text(
            json.dumps(priv, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        freeze.write(self.freeze_path, freeze.compute(bb.freeze_spec(self.manifest_path, self.private_path)))
        with self.assertRaises(run_eval.FreezeError) as ctx:
            self.battery()
        self.assertIn("input hash", str(ctx.exception))


class RunBatteryTests(RunnerCase):
    def test_every_case_is_observed_exactly_once_in_the_frozen_order(self):
        client = PerfectClient(self.battery())
        result = self.run_all(client)
        order = [c["case_id"] for c in self.battery()["manifest"]["cases"]]
        self.assertEqual([c["case_id"] for c in client.calls], order)
        self.assertEqual([c["case_id"] for c in result["calls"]], order)
        rows = [
            json.loads(line) for line in (self.out / "battery_calls.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(rows), 19)

    def test_the_uniform_envelope_and_thinking_setting_reach_every_call(self):
        client = PerfectClient(self.battery())
        self.run_all(client, think="medium")
        for c in client.calls:
            self.assertEqual(c["options"], models.ENVELOPE)
            self.assertEqual(c["think"], "medium")
            self.assertEqual(c["wall_timeout"], models.BATTERY_CALL_WALL_TIMEOUT_S)

    def test_schemas_sent_to_the_model_are_the_frozen_ones(self):
        battery = self.battery()
        client = PerfectClient(battery)
        self.run_all(client)
        for c in client.calls:
            self.assertEqual(c["schema"], battery["cases"][c["case_id"]]["schema"])

    def test_a_perfect_supervisor_qualifies_end_to_end(self):
        client = PerfectClient(self.battery())
        result = self.run_all(client)
        scored = scoring.score_model(
            cases.build_case_specs(), [{**c["call"], "case_id": c["case_id"]} for c in result["calls"]]
        )
        self.assertIs(scored["qualified"], True)

    def test_the_model_is_unloaded_and_the_sampler_stopped_even_when_a_call_raises(self):
        client = PerfectClient(self.battery())
        sampler = FakeSampler()
        original = client.chat

        def boom(*a, **k):
            if len(client.calls) == 3:
                raise RuntimeError("harness bug")
            return original(*a, **k)

        client.chat = boom
        with self.assertRaises(RuntimeError):
            self.run_all(client, sampler=sampler)
        self.assertEqual(client.unloaded, ["m:1b"])
        self.assertEqual((sampler.started, sampler.stopped), (["m-1b"], 1))

    def test_residency_is_captured_after_the_first_call(self):
        result = self.run_all(PerfectClient(self.battery()))
        self.assertEqual(result["residency"]["gpu_fraction"], 0.5)


class ResumeAndRetryTests(RunnerCase):
    def test_resuming_never_observes_a_recorded_case_again(self):
        battery = self.battery()
        first = PerfectClient(battery)
        self.run_all(first)
        second = PerfectClient(battery)
        result = self.run_all(second)
        self.assertEqual(second.calls, [])
        self.assertEqual(len(result["calls"]), 19)
        self.assertEqual(len((self.out / "battery_calls.jsonl").read_text(encoding="utf-8").splitlines()), 19)

    def test_a_semantic_miss_is_never_retried(self):
        wrong = rec(json.dumps({"rationale": "x", "responsive_obligation_ids": ["s2-o1"]}))
        client = PerfectClient(self.battery(), scripted={"A3.original": wrong})
        self.run_all(client)
        again = PerfectClient(self.battery())
        with self.assertRaises(run_eval.IneligibleRetry):  # a semantic miss is not a technical failure
            self.run_all(again, retry_technical={"A3.original"})
        self.assertEqual(again.calls, [])

    def test_a_dropped_connection_before_any_output_may_be_retried_and_is_documented(self):
        down = rec("", status="transport_error", error="ConnectError: refused")
        client = PerfectClient(self.battery(), scripted={"A1.original": down})
        self.run_all(client)
        retry_client = PerfectClient(self.battery())
        result = self.run_all(retry_client, retry_technical={"A1.original"})
        self.assertEqual([c["case_id"] for c in retry_client.calls], ["A1.original"])
        rows = [
            json.loads(line) for line in (self.out / "battery_calls.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        retried = [r for r in rows if r["case_id"] == "A1.original"]
        self.assertEqual([r["attempt"] for r in retried], [1, 2])
        self.assertIn("transport_error", retried[1]["retry_reason"])
        final = next(c for c in result["calls"] if c["case_id"] == "A1.original")
        self.assertEqual(final["call"]["status"], "ok")

    def test_a_timeout_or_mid_generation_crash_is_not_retryable(self):
        for status in ("timeout", "runtime_error"):
            with self.subTest(status=status):
                self.out = self.dir / f"out-{status}"
                bad = rec("partial", status=status, error="x")
                self.run_all(PerfectClient(self.battery(), scripted={"B1.original": bad}))
                with self.assertRaises(run_eval.IneligibleRetry):
                    self.run_all(PerfectClient(self.battery()), retry_technical={"B1.original"})

    def test_an_output_that_started_is_never_retried_even_if_the_status_is_an_http_error(self):
        started = rec("{", status="http_error", error="HTTP 500")
        self.run_all(PerfectClient(self.battery(), scripted={"C1.original": started}))
        with self.assertRaises(run_eval.IneligibleRetry):
            self.run_all(PerfectClient(self.battery()), retry_technical={"C1.original"})

    def test_a_retry_request_for_an_unrecorded_or_unknown_case_is_rejected(self):
        with self.assertRaises(run_eval.IneligibleRetry):
            self.run_all(PerfectClient(self.battery()), retry_technical={"Z9.original"})


class ClientTargetTests(unittest.TestCase):
    def test_defaults_to_the_isolated_bakeoff_ollama_never_the_shared_port(self):
        self.assertEqual(run_eval.ollama_url(env={}), "http://127.0.0.1:11435")

    def test_can_be_overridden_but_the_client_still_refuses_non_loopback_hosts(self):
        self.assertEqual(
            run_eval.ollama_url(env={"BAKEOFF_OLLAMA_URL": "http://127.0.0.1:9999"}), "http://127.0.0.1:9999"
        )


class PerformanceAndReceiptTests(RunnerCase):
    def _result(self):
        walls = iter([10.0] + [float(x) for x in range(1, 19)])  # first call includes the load
        scripted = {}
        specs = cases.build_case_specs()
        for s in specs:
            scripted[s["case_id"]] = rec(
                json.dumps(perfect_output(s)),
                wall=next(walls),
                tps=5.0 + len(scripted),
                load=4_000_000_000 if not scripted else 0,
            )
        return self.run_all(PerfectClient(self.battery(), scripted=scripted))

    def test_warm_latency_excludes_the_first_call_that_paid_for_the_load(self):
        perf = run_eval.summarize_performance(self._result()["calls"])
        self.assertEqual(perf["warm_calls"], 18)
        self.assertEqual(perf["warm_latency_s"]["median"], statistics.median(range(1, 19)))
        self.assertEqual((perf["warm_latency_s"]["min"], perf["warm_latency_s"]["max"]), (1.0, 18.0))
        self.assertEqual(perf["first_call_load_seconds"], 4.0)
        self.assertEqual(perf["total_battery_wall_s"], 10.0 + sum(range(1, 19)))

    def test_receipts_are_text_free(self):
        result = self._result()
        specs = cases.build_case_specs()
        scored = scoring.score_model(specs, [{**c["call"], "case_id": c["case_id"]} for c in result["calls"]])
        stage0 = {
            "model": "m:1b",
            "verdict": "ok",
            "identity": {"family": "f"},
            "residency": {"gpu_fraction": 0.5},
            "envelope": models.ENVELOPE,
            "think_setting": None,
            "runtime": {"api_version": "0.34.3"},
            "store": {"ok": True, "store_path": "/media/brain/JUNO/x"},
        }
        receipt = run_eval.make_receipt("m-1b", stage0, result, scored)
        self.assertEqual(receipt["stage0"]["runtime"], {"api_version": "0.34.3"})
        self.assertEqual(receipt["stage0"]["store"], {"ok": True, "store_path": "/media/brain/JUNO/x"})
        blob = json.dumps(receipt)
        for private in ("private reasoning", "responsive_obligation_ids", "rationale"):
            self.assertNotIn(private, blob)
        self.assertEqual(receipt["qualified"], True)
        self.assertEqual(receipt["gates"]["G3"]["status"], "PASS")
        self.assertIn("performance", receipt)

    def test_the_corpus_absence_snippets_stay_out_of_the_committed_receipt(self):
        specs = cases.build_case_specs()
        calls = []
        for s in specs:
            out = perfect_output(s)
            if s["case_id"] == "B1.original":
                out["rationale"] = "There is no cross-cultural evidence in the literature."
            calls.append({**rec(json.dumps(out)), "case_id": s["case_id"]})
        scored = scoring.score_model(specs, calls)
        receipt = run_eval.make_receipt(
            "m-1b",
            {"model": "m:1b", "verdict": "ok"},
            {"calls": [{"case_id": c["case_id"], "call": c} for c in calls], "residency": {}, "resources": {}},
            scored,
        )
        self.assertEqual(receipt["gates"]["G8"]["status"], "NEEDS_ADJUDICATION")
        self.assertNotIn("literature", json.dumps(receipt))
        self.assertEqual(receipt["gates"]["G8"]["hits"], 1)


if __name__ == "__main__":
    unittest.main()
