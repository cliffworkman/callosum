"""The Qwen3.5 8K reasoning-budget sensitivity arm.

One experimental variable (`num_predict` 4096 -> 8192), applied only to the calls the first tranche could not observe
(`done_reason=length`). Per-case verdicts through the frozen case judges only: never a battery-wide gate, never a
Qualified flag. The 4K result and the frozen surface are not touched.
"""

import json
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.supervisor_eval import cases, models, run_eval, sensitivity
from experiments.ask_cli_revised.supervisor_eval.test_run_eval import PerfectClient, RunnerCase, rec
from experiments.ask_cli_revised.supervisor_eval.test_scoring import perfect_output

SEVEN = ["A1.original", "A7.original", "A7.reversed", "B1.original", "B1.reversed", "C1.original", "C1.reversed"]
ORDER = [s["case_id"] for s in cases.build_case_specs()]
SPECS = {s["case_id"]: s for s in cases.build_case_specs()}


def row(cid, *, done_reason="stop", status="ok", eval_count=1000, thinking="t" * 100, content=""):
    call = rec(content, status=status, done_reason=done_reason, eval_count=eval_count)
    call["thinking"] = thinking
    return {"case_id": cid, "attempt": 1, "input_sha256": "x", "call": call}


def original_rows():
    """A first-tranche-shaped result: the seven censored calls plus completed ones (incl. a completed semantic miss)."""
    rows = []
    for cid in ORDER:
        if cid in SEVEN:
            rows.append(row(cid, done_reason="length", eval_count=4096, content=""))
        else:
            rows.append(row(cid, content=json.dumps(perfect_output(SPECS[cid]))))
    return rows


class SelectionTests(unittest.TestCase):
    def test_only_ok_and_length_calls_are_selected_in_battery_order(self):
        rows = list(reversed(original_rows()))  # order in the file must not matter
        self.assertEqual(sensitivity.select_censored_cases(rows, ORDER), SEVEN)

    def test_completed_semantic_misses_and_non_length_failures_are_never_rerun(self):
        rows = original_rows()
        for r in rows:
            if r["case_id"] == "A1.reversed":  # a completed call that returned an empty selection
                r["call"]["content"] = json.dumps({"rationale": "x", "responsive_obligation_ids": []})
            if r["case_id"] == "A2.original":  # a timeout is not a token-cap censoring
                r["call"]["status"], r["call"]["done_reason"] = "timeout", None
        chosen = sensitivity.select_censored_cases(rows, ORDER)
        self.assertNotIn("A1.reversed", chosen)
        self.assertNotIn("A2.original", chosen)
        self.assertEqual(chosen, SEVEN)

    def test_the_real_first_tranche_censored_set_is_exactly_the_seven(self):
        path = run_eval.WORK_DIR / sensitivity.ORIGINAL_KEY / "battery_calls.jsonl"
        if not path.exists():
            self.skipTest("original raw results not present on this machine")
        self.assertEqual(sensitivity.select_censored_cases(run_eval._read_rows(path), ORDER), SEVEN)


class EnvelopeAndContextTests(unittest.TestCase):
    def test_the_arm_envelope_differs_from_the_frozen_one_only_in_num_predict(self):
        env = sensitivity.envelope_8k()
        self.assertEqual(env["num_predict"], 8192)
        self.assertEqual({k for k in env if env[k] != models.ENVELOPE.get(k)}, {"num_predict"})

    def test_the_frozen_envelope_is_still_4096(self):
        self.assertEqual(models.ENVELOPE["num_predict"], 4096)

    def test_any_second_difference_is_refused(self):
        with self.assertRaises(ValueError):
            sensitivity.assert_only_num_predict_changed({**sensitivity.envelope_8k(), "temperature": 0.7})
        with self.assertRaises(ValueError):
            sensitivity.assert_only_num_predict_changed({**models.ENVELOPE})  # unchanged = not the experiment

    def test_context_headroom_uses_prompt_plus_generation(self):
        ok = sensitivity.context_headroom(1748, 8192, 12288)
        self.assertEqual((ok["total"], ok["headroom"], ok["ok"]), (9940, 2348, True))
        self.assertFalse(sensitivity.context_headroom(4200, 8192, 12288)["ok"])


class RunBatteryOverrideTests(RunnerCase):
    def test_the_override_reaches_only_the_selected_cases_in_battery_order(self):
        client = PerfectClient(self.battery())
        result = self.run_all(
            client, options=sensitivity.envelope_8k(), case_ids=["C1.reversed", "A1.original", "B1.original"]
        )
        order = ["A1.original", "B1.original", "C1.reversed"]
        self.assertEqual([c["case_id"] for c in client.calls], order)
        self.assertEqual([r["case_id"] for r in result["calls"]], order)
        for c in client.calls:
            self.assertEqual(c["options"], sensitivity.envelope_8k())

    def test_the_default_path_is_unchanged_all_19_cases_at_the_frozen_envelope(self):
        client = PerfectClient(self.battery())
        self.run_all(client)
        self.assertEqual(len(client.calls), 19)
        self.assertTrue(all(c["options"] == models.ENVELOPE for c in client.calls))

    def test_an_unknown_case_id_is_refused_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            self.run_all(PerfectClient(self.battery()), case_ids=["A1.original", "Z9.original"])

    def test_results_land_only_in_the_given_directory(self):
        other = self.dir / "original"
        other.mkdir()
        (other / "battery_calls.jsonl").write_text("ORIGINAL\n", encoding="utf-8")
        self.run_all(PerfectClient(self.battery()), options=sensitivity.envelope_8k(), case_ids=["A1.original"])
        self.assertEqual((other / "battery_calls.jsonl").read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertEqual(len((self.out / "battery_calls.jsonl").read_text(encoding="utf-8").splitlines()), 1)

    def test_the_arm_directory_can_never_be_the_original_directory(self):
        with self.assertRaises(ValueError):
            sensitivity.assert_separate_dirs(self.dir / "a", self.dir / "a")
        sensitivity.assert_separate_dirs(self.dir / "a", self.dir / "b")


class JudgeAdapterTests(unittest.TestCase):
    def test_a_completed_correct_answer_passes_without_any_battery_wide_result(self):
        for cid in ("A7.original", "B1.original", "C1.original"):
            call = row(cid, content=json.dumps(perfect_output(SPECS[cid])))["call"]
            verdict = sensitivity.judge_case(SPECS[cid], call)
            self.assertEqual(verdict["verdict"], "pass", cid)
            self.assertTrue(verdict["structured_valid"])
            self.assertFalse({"gates", "qualified"} & set(verdict))

    def test_a_length_capped_call_is_unusable_not_a_semantic_result(self):
        verdict = sensitivity.judge_case(SPECS["B1.original"], row("B1.original", done_reason="length")["call"])
        self.assertEqual(verdict["verdict"], "unusable")
        self.assertFalse(verdict["structured_valid"])

    def test_the_result_carries_ids_for_each_family(self):
        a = sensitivity.judge_case(
            SPECS["A7.original"], row("A7.original", content=json.dumps(perfect_output(SPECS["A7.original"])))["call"]
        )
        b = sensitivity.judge_case(
            SPECS["B1.original"], row("B1.original", content=json.dumps(perfect_output(SPECS["B1.original"])))["call"]
        )
        c = sensitivity.judge_case(
            SPECS["C1.original"], row("C1.original", content=json.dumps(perfect_output(SPECS["C1.original"])))["call"]
        )
        self.assertEqual(a["result"]["selected"], ["s3-o1"])
        self.assertIn("s1-o1", b["result"]["coverage"])
        self.assertIn("s4-o1", c["result"]["plan"])

    def test_a_semantically_wrong_completed_answer_fails_and_is_not_called_recovered(self):
        wrong = perfect_output(SPECS["A7.original"])
        wrong["responsive_obligation_ids"] = []
        verdict = sensitivity.judge_case(SPECS["A7.original"], row("A7.original", content=json.dumps(wrong))["call"])
        self.assertEqual(verdict["verdict"], "fail")


class DiagnosticsTests(unittest.TestCase):
    def test_the_reasoning_split_is_a_labelled_character_proportion_estimate(self):
        call = row("A1.original", eval_count=1000, thinking="a" * 900, content="b" * 100)["call"]
        split = sensitivity.approx_split(call)
        self.assertEqual((split["reasoning"], split["final"]), (900, 100))
        self.assertTrue(split["approximate"])

    def test_an_empty_call_has_no_split(self):
        self.assertIsNone(sensitivity.approx_split(row("A1.original", thinking="", content="")["call"]))

    def test_prefix_agreement_is_a_descriptive_diagnostic(self):
        same = sensitivity.prefix_agreement("abcdef", "abcdefghi")
        self.assertEqual((same["common_chars"], same["fraction_of_original"]), (6, 1.0))
        diverged = sensitivity.prefix_agreement("abcdef", "abcxyz")
        self.assertEqual((diverged["common_chars"], diverged["fraction_of_original"]), (3, 0.5))
        self.assertIsNone(sensitivity.prefix_agreement("", "abc")["fraction_of_original"])


class ArmReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.work, self.receipts = root / "work", root / "receipts"
        self.saved = (run_eval.WORK_DIR, run_eval.RECEIPT_DIR)
        run_eval.WORK_DIR, run_eval.RECEIPT_DIR = self.work, self.receipts
        self.addCleanup(lambda: setattr(run_eval, "WORK_DIR", self.saved[0]))
        self.addCleanup(lambda: setattr(run_eval, "RECEIPT_DIR", self.saved[1]))
        for key, rows in (
            (sensitivity.ORIGINAL_KEY, original_rows()),
            (
                sensitivity.ARM_KEY,
                [
                    row(
                        cid,
                        eval_count=5000 + i,
                        thinking="SECRET-REASONING " * 50,
                        content=json.dumps({**perfect_output(SPECS[cid]), "rationale": "SECRET-RATIONALE"}),
                    )
                    for i, cid in enumerate(SEVEN)
                ],
            ),
        ):
            (self.work / key).mkdir(parents=True)
            (self.work / key / "battery_calls.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )
        (self.work / sensitivity.ARM_KEY / "arm.json").write_text(
            json.dumps({"artifact": {"digest": "d", "size_bytes": 5}, "runtime": {"api_version": "0.34.3"}}),
            encoding="utf-8",
        )

    def test_the_receipt_has_seven_cases_no_gates_no_qualified_flag_and_no_text(self):
        run_eval._cmd_sensitivity_report()
        receipt = json.loads((self.receipts / f"{sensitivity.ARM_KEY}.json").read_text(encoding="utf-8"))
        self.assertEqual([c["case_id"] for c in receipt["cases"]], SEVEN)
        self.assertFalse({"gates", "qualified"} & set(receipt))
        blob = json.dumps(receipt)
        for private in ("SECRET-REASONING", "SECRET-RATIONALE", "responsive_obligation_ids"):
            self.assertNotIn(private, blob)
        self.assertEqual(receipt["changed_variable"], {"num_predict": [4096, 8192]})
        self.assertIn("not part of the frozen first tranche", receipt["kind"])

    def test_each_case_records_both_caps_the_verdict_and_the_context_check(self):
        run_eval._cmd_sensitivity_report()
        receipt = json.loads((self.receipts / f"{sensitivity.ARM_KEY}.json").read_text(encoding="utf-8"))
        first = receipt["cases"][0]
        self.assertEqual(first["cap_4096"]["done_reason"], "length")
        self.assertEqual(first["cap_8192"]["done_reason"], "stop")
        self.assertEqual(first["cap_8192"]["verdict"], "pass")
        self.assertTrue(first["cap_8192"]["context"]["ok"])
        self.assertIn("prefix", first)

    def test_the_report_writes_nothing_over_the_original_or_any_first_tranche_receipt(self):
        original = (self.work / sensitivity.ORIGINAL_KEY / "battery_calls.jsonl").read_text(encoding="utf-8")
        run_eval._cmd_sensitivity_report()
        self.assertEqual(
            (self.work / sensitivity.ORIGINAL_KEY / "battery_calls.jsonl").read_text(encoding="utf-8"), original
        )
        self.assertEqual([p.name for p in self.receipts.glob("*.json")], [f"{sensitivity.ARM_KEY}.json"])


if __name__ == "__main__":
    unittest.main()
