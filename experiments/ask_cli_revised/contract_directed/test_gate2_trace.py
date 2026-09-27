"""Tests for the durable, crash-recoverable Gate 2 diagnostic trace writer (2026-09-27).

Exercises the actual call boundary -- `overview.build_overview`'s real `on_prompt_ready`/`on_raw_response`
hooks wired to a real `DiagnosticTrace` -- not just `DiagnosticTrace` in isolation. No network contact; the
model and NLI scorer are stubbed throughout.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised.contract_directed import gate2_trace
from experiments.ask_cli_revised.contract_directed import overview_bridge as bridge
from experiments.ask_cli_revised.overview_test_support import (
    GIVING,
    S1,
    Entail,
    OverviewClient,
    make_supervisor,
    sealed_ledger,
    uid,
)


class DiagnosticTraceUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gate2_trace_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_refuses_to_reuse_an_existing_run_dir(self):
        gate2_trace.DiagnosticTrace(self.tmp / "attempt-1")
        with self.assertRaises(FileExistsError):
            gate2_trace.DiagnosticTrace(self.tmp / "attempt-1")

    def test_prompt_ready_writes_immediately_and_completely(self):
        trace = gate2_trace.DiagnosticTrace(self.tmp / "attempt-2")
        trace.prompt_ready("the rendered prompt text", {"sent_unit_ids": ["U1"]})
        path = self.tmp / "attempt-2" / "02_prompt_and_manifest.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["prompt"], "the rendered prompt text")
        self.assertEqual(data["manifest"]["sent_unit_ids"], ["U1"])
        self.assertTrue(data["prompt_sha256"])

    def test_exception_receipt_never_overwrites_earlier_files(self):
        trace = gate2_trace.DiagnosticTrace(self.tmp / "attempt-3")
        trace.prompt_ready("p", {})
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            trace.exception(exc)
        prompt_path = self.tmp / "attempt-3" / "02_prompt_and_manifest.json"
        receipt_path = self.tmp / "attempt-3" / "06_exception_receipt.json"
        self.assertTrue(prompt_path.is_file())
        self.assertTrue(receipt_path.is_file())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["exception_type"], "RuntimeError")
        self.assertIn("boom", receipt["exception_message"])
        self.assertIn("RuntimeError", receipt["traceback"])


class CrashRecoveryIntegrationTests(unittest.TestCase):
    """Exercises the real call boundary: `overview.build_overview` wired to a real `DiagnosticTrace`, with a
    scripted (offline) model client -- proving the two required properties end to end."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gate2_trace_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _sealed_missing_state_on_first_field(self) -> dict:
        """A real sealed ledger (through the same `stages.seal` path every other test uses -- an `attached`
        list must name a real subquestion id, or the unit is `no_coverage_attachment`-ineligible and no call
        would be made at all), with `state` deliberately stripped from its first obligation_states row --
        exactly the field the real 2026-09-27 bug omitted, and exactly what `parts_status` needs."""
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        sealed["obligation_states"][0] = {k: v for k, v in sealed["obligation_states"][0].items() if k != "state"}
        return sealed

    def test_the_complete_pipeline_succeeds_with_real_obligation_states(self):
        """Cliff's minimum bar: the real bridge output, run through the real, hook-wired pipeline, completes
        normally with no exception."""
        if not bridge.available():
            self.skipTest("the real prior T5O run's sealed ledger is not present on this machine")
        rows = [
            {
                "child_id": "c9",
                "unit_id": "M10",
                "kind": "operation",
                "status": "source_supported",
                "accepted_spans": [
                    {
                        "paper_id": 67,
                        "chunk_id": 35019,
                        "span_id": "p1",
                        "text": "Participants completed a Just World Beliefs Scale that measures fairness beliefs.",
                        "attribution_state": "own_established",
                        "slots_accepted_for": ["instrument_named", "paired_with_construct", "on_topic"],
                    }
                ],
            }
        ]
        evidence_spans, verified_propositions = bridge.project_evidence(rows)
        question, question_hash = bridge.real_original_question()
        states = bridge.real_obligation_states(("c9", "c11"))
        sealed = {
            "request_contract": {"original_question": question, "question_hash": question_hash},
            "obligation_states": states,
            "evidence_spans": evidence_spans,
            "verified_propositions": verified_propositions,
        }
        trace = gate2_trace.DiagnosticTrace(self.tmp / "success")
        trace.manifest_ready(rows)
        client = OverviewClient(s={"overview": []})
        record, reasoning = ov.build_overview(
            sealed,
            "sealed-hash",
            supervisor=make_supervisor(client),
            entail=Entail(),
            on_prompt_ready=trace.prompt_ready,
            on_raw_response=trace.raw_response,
        )
        trace.final_record(record, reasoning)
        self.assertIn(record["state"], ov.STATES)
        for name in (
            "01_contract_directed_manifest.json",
            "02_prompt_and_manifest.json",
            "03_raw_response.json",
            "04_final_record.json",
        ):
            self.assertTrue((self.tmp / "success" / name).is_file(), name)

    def test_an_injected_post_response_exception_still_leaves_prompt_raw_response_and_receipt_recoverable(self):
        """Simulates the real 2026-09-27 incident's SHAPE (a downstream KeyError after the model already
        answered) without depending on the already-fixed bug: `parts_status` needs `state["state"]`; a caller
        that omits it (as the un-fixed bridge once did) crashes there, but only AFTER the model has answered."""
        sealed = self._sealed_missing_state_on_first_field()
        trace = gate2_trace.DiagnosticTrace(self.tmp / "crash")
        client = OverviewClient(
            s={"overview": [{"text": "a grounded statement", "unit_ids": [uid(sealed, GIVING)], "bears_on": []}]}
        )
        with self.assertRaises(KeyError):
            try:
                record, reasoning = ov.build_overview(
                    sealed,
                    "sealed-hash",
                    supervisor=make_supervisor(client),
                    entail=Entail(),
                    on_prompt_ready=trace.prompt_ready,
                    on_raw_response=trace.raw_response,
                )
            except Exception as exc:  # noqa: BLE001 -- this is exactly the catch-anything a diagnostic driver needs
                trace.exception(exc)
                raise

        # The required recovery property: everything up to the crash is on disk, even though build_overview
        # itself never returned.
        prompt_file = self.tmp / "crash" / "02_prompt_and_manifest.json"
        response_file = self.tmp / "crash" / "03_raw_response.json"
        receipt_file = self.tmp / "crash" / "06_exception_receipt.json"
        self.assertTrue(prompt_file.is_file())
        self.assertTrue(response_file.is_file())
        self.assertTrue(receipt_file.is_file())

        prompt_data = json.loads(prompt_file.read_text(encoding="utf-8"))
        self.assertIn("Original request", prompt_data["prompt"])

        response_data = json.loads(response_file.read_text(encoding="utf-8"))
        self.assertTrue(response_data["answer_parsed"])
        self.assertEqual(response_data["answer"]["overview"][0]["text"], "a grounded statement")

        receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
        self.assertEqual(receipt_data["exception_type"], "KeyError")

        # No 04_final_record.json -- build_overview never returned normally, and this test never calls
        # trace.final_record() either, matching what a real driver would (and would not) do.
        self.assertFalse((self.tmp / "crash" / "04_final_record.json").exists())


if __name__ == "__main__":
    unittest.main()
