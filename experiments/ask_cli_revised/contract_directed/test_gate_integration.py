"""Tests for the offline replay/integration orchestrator (2026-09-27). No model, NLI, or embedding call
anywhere in this file."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised.contract_directed import evidence_identity as ident
from experiments.ask_cli_revised.contract_directed import gate2_trace
from experiments.ask_cli_revised.contract_directed import gate_integration as integration
from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as par
from experiments.ask_cli_revised.overview_test_support import (
    GIVING,
    S1,
    Entail,
    OverviewClient,
    make_supervisor,
    sealed_ledger,
    uid,
)

M10_SPAN = {
    "paper_id": 67, "chunk_id": 35019, "span_id": "p1", "start": 25, "end": 392,
    "text": "Participants completed a Just World Beliefs Scale that measures fairness beliefs.",
    "attribution_state": "own_established", "slots_accepted_for": ["instrument_named"],
}  # fmt: skip
M10_ROW = {
    "child_id": "c9", "unit_id": "M10", "kind": "operation", "status": "source_supported",
    "accepted_spans": [M10_SPAN], "packet_id": "1606c9d7970d",
    "provenance": {"closure_source": "live_replay_call", "note": "a live call judged this packet"},
}  # fmt: skip
W21_ROW = {
    "child_id": "c9", "unit_id": "W21", "kind": "requested_item", "status": "unresolved_obligation",
    "accepted_spans": [], "constraint_text": "not established by the admitted evidence.", "packet_id": None,
    "provenance": {"closure_source": "not_applicable_unresolved", "constraint_text_provenance": "researcher_authored_reviewed"},
}  # fmt: skip
ROWS = [M10_ROW, W21_ROW]


def unit(unit_id, paper_id, chunk_id, span_id, passage):
    return {
        "unit_id": unit_id,
        "paper_id": paper_id,
        "locators": [{"chunk_id": chunk_id, "span_id": span_id}],
        "passage": passage,
    }


GATE2_RECORD = {
    "proposals": [
        {"index": 0, "status": "grounded", "unit_ids": ["U1"], "bears_on": ["c9"], "reasons": [],
         "text": "Participants completed a Just World Beliefs Scale."},
    ],
    "units": [unit("U1", 67, 35019, "p1", M10_SPAN["text"])],
}  # fmt: skip


class Sha256FileTests(unittest.TestCase):
    def test_hashes_real_file_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.txt"
            path.write_text("hello", encoding="utf-8")
            import hashlib

            self.assertEqual(integration.sha256_file(path), hashlib.sha256(b"hello").hexdigest())

    def test_input_file_manifest_lists_label_path_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.txt"
            path.write_text("hello", encoding="utf-8")
            manifest = integration.input_file_manifest({"my_input": path})
            self.assertEqual(len(manifest), 1)
            self.assertEqual(manifest[0]["label"], "my_input")
            self.assertEqual(manifest[0]["path"], str(path))
            self.assertTrue(manifest[0]["sha256"])


class StageTransitionReceiptTests(unittest.TestCase):
    def test_names_provenance_status_and_screening_per_unit(self):
        classifications = par.build_classifications(ROWS, GATE2_RECORD)
        receipt = integration.stage_transition_receipt(ROWS, classifications)
        m10 = next(r for r in receipt if r["unit_id"] == "M10")
        self.assertEqual(m10["packet_id"], "1606c9d7970d")
        self.assertEqual(m10["closure_provenance_source"], "live_replay_call")
        self.assertEqual(m10["rendered_outcome"], par.DISPLAYED)
        self.assertEqual(m10["overview_screening"], {"decision": "grounded", "reasons": []})

        w21 = next(r for r in receipt if r["unit_id"] == "W21")
        self.assertEqual(w21["closure_provenance_source"], "not_applicable_unresolved")
        self.assertEqual(w21["rendered_outcome"], par.UNRESOLVED)
        self.assertIsNone(w21["overview_screening"])
        self.assertEqual(w21["evidence_span_count"], 0)


class BuildIntegrationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gate_integration_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.input_path = self.tmp / "input.json"
        self.input_path.write_text("{}", encoding="utf-8")

    def test_labels_itself_as_a_replay_never_a_live_e2e_run(self):
        receipt, markdown, _ = integration.build_integration_receipt(
            ROWS, GATE2_RECORD, repo=self.tmp, input_files={"x": self.input_path}
        )
        self.assertEqual(receipt["mode"], "offline_replay_integration")
        self.assertTrue(receipt["not_a_live_e2e_run"])
        self.assertIn("does not answer the original parent question", markdown)

    def test_records_input_files_code_identity_and_exclusions(self):
        receipt, _, _ = integration.build_integration_receipt(
            ROWS, GATE2_RECORD, repo=self.tmp, input_files={"x": self.input_path}
        )
        self.assertEqual(receipt["input_files"][0]["label"], "x")
        self.assertIn("code", receipt)
        self.assertEqual(set(receipt["excluded_children"]), {"c5", "c6", "c10"})
        self.assertIn("callosum_rd_ask#19", receipt["topic_anchoring_partial_facet_design"])
        self.assertIn("unresolved", receipt["c6_construct_scope_decision"])

    def test_calls_the_existing_renderer_exactly_once_never_a_second_renderer(self):
        receipt, markdown, detailed_audit_view = integration.build_integration_receipt(
            ROWS, GATE2_RECORD, repo=self.tmp, input_files={"x": self.input_path}
        )
        # the detailed audit view is exactly render_partial_slice's own manifest return value
        self.assertEqual(detailed_audit_view["mode"], "partial-answer-v1")
        self.assertEqual(len(receipt["stage_transitions"]), len(detailed_audit_view["classifications"]))

    def test_a_span_identity_collision_in_the_input_propagates_not_swallowed(self):
        colliding_row = {
            **M10_ROW,
            "accepted_spans": [
                M10_SPAN,
                {**M10_SPAN, "start": 900, "end": 950, "text": "a genuinely different sentence"},
            ],
        }
        with self.assertRaises(ident.SpanIdentityCollision):
            integration.build_integration_receipt(
                [colliding_row], GATE2_RECORD, repo=self.tmp, input_files={"x": self.input_path}
            )


# ---- live-path tests (2026-09-28): exercise run_live_overview_call / build_live_integration_receipt with a
# scripted (offline) model client -- the actual new driver functions the one authorized live call will use,
# not just overview.build_overview in isolation (that lower-level boundary is already covered by
# test_gate2_trace.py). sealed_override exists on the production functions ONLY so this can happen offline. ----

GIVING_ROW = {
    "child_id": "c9",
    "unit_id": "M99",
    "kind": "operation",
    "status": "source_supported",
    "accepted_spans": [
        {
            "paper_id": GIVING[0],
            "chunk_id": GIVING[1],
            "span_id": GIVING[2],
            "start": None,
            "end": None,
            "text": GIVING[3],
            "attribution_state": "own_established",
            "slots_accepted_for": ["instrument_named"],
        }
    ],
    "packet_id": "test-live-packet",
    "provenance": {"closure_source": "live_replay_call", "note": "scripted-test row, not real Gate 1 data"},
}


class RunLiveOverviewCallTests(unittest.TestCase):
    """Offline: a scripted client stands in for the real Qwen S-role call. Proves the actual new driver
    function (not the standalone overview.build_overview) carries a fresh record end to end."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gate_integration_live_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.input_path = self.tmp / "input.json"
        self.input_path.write_text("{}", encoding="utf-8")

    def test_a_scripted_call_produces_a_record_never_the_saved_diagnostic_002_record(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(
            s={"overview": [{"text": "a grounded statement", "unit_ids": [uid(sealed, GIVING)], "bears_on": []}]}
        )
        record, reasoning, returned_sealed = integration.run_live_overview_call(
            [GIVING_ROW], supervisor=make_supervisor(client), entail=Entail(), sealed_override=sealed
        )
        self.assertIn(record["state"], ov.STATES)
        self.assertIs(returned_sealed, sealed)
        self.assertEqual(reasoning, "")  # OverviewClient's default thinking text
        # sealed_override bypasses build_sealed_ledger entirely -- this record was built ONLY from this test's
        # own scripted response and this test's own sealed ledger, never from any file on disk (proven by
        # construction: run_live_overview_call takes no path argument at all when sealed_override is given).
        self.assertEqual(client.calls[0]["kind"], "S")

    def test_end_to_end_through_build_live_integration_receipt_labels_and_hashes_correctly(self):
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        client = OverviewClient(
            s={"overview": [{"text": "a grounded statement", "unit_ids": [uid(sealed, GIVING)], "bears_on": []}]}
        )
        trace = gate2_trace.DiagnosticTrace(self.tmp / "live-success")
        receipt, markdown, detailed_audit_view, record, reasoning = integration.build_live_integration_receipt(
            [GIVING_ROW],
            supervisor=make_supervisor(client),
            entail=Entail(),
            trace=trace,
            repo=self.tmp,
            input_files={"x": self.input_path},
            sealed_override=sealed,
        )
        self.assertEqual(receipt["mode"], integration.MODE_LIVE)
        self.assertEqual(receipt["sealed_ledger_hash"], integration.sealed_ledger_hash(sealed))
        self.assertIn(record["state"], ov.STATES)
        self.assertEqual(detailed_audit_view["mode"], "partial-answer-v1")
        # the fresh record's own evidence -- GIVING's text -- is what got rendered, not any prior saved record
        # (markdown-escaped by the renderer's own _literal(), same as every other citation text it prints)
        self.assertIn(par._literal(GIVING[3]), markdown)
        self.assertIn("a grounded statement", markdown)
        classification = next(c for c in detailed_audit_view["classifications"] if c["unit_id"] == "M99")
        self.assertEqual(classification["matched_overview_unit_ids"], [uid(sealed, GIVING)])
        # every documented hook boundary actually fired and persisted, via the real DiagnosticTrace
        for name in ("02_prompt_and_manifest.json", "03_raw_response.json", "04_final_record.json"):
            self.assertTrue((self.tmp / "live-success" / name).is_file(), name)

    def test_a_post_response_exception_still_leaves_prompt_raw_response_and_receipt_recoverable(self):
        """The same crash shape test_gate2_trace.py proves at the overview.build_overview boundary, exercised
        here one layer up -- through build_live_integration_receipt itself, matching the established driver
        convention: the caller wraps the call in its own try/except and calls trace.exception(exc)."""
        sealed = sealed_ledger([("claim", GIVING, [S1])])
        sealed["obligation_states"][0] = {k: v for k, v in sealed["obligation_states"][0].items() if k != "state"}
        client = OverviewClient(
            s={"overview": [{"text": "a grounded statement", "unit_ids": [uid(sealed, GIVING)], "bears_on": []}]}
        )
        trace = gate2_trace.DiagnosticTrace(self.tmp / "live-crash")
        with self.assertRaises(KeyError):
            try:
                integration.build_live_integration_receipt(
                    [GIVING_ROW],
                    supervisor=make_supervisor(client),
                    entail=Entail(),
                    trace=trace,
                    repo=self.tmp,
                    input_files={"x": self.input_path},
                    sealed_override=sealed,
                )
            except Exception as exc:  # noqa: BLE001 -- exactly the catch-anything a live driver needs
                trace.exception(exc)
                raise

        prompt_file = self.tmp / "live-crash" / "02_prompt_and_manifest.json"
        response_file = self.tmp / "live-crash" / "03_raw_response.json"
        receipt_file = self.tmp / "live-crash" / "06_exception_receipt.json"
        self.assertTrue(prompt_file.is_file())
        self.assertTrue(response_file.is_file())
        self.assertTrue(receipt_file.is_file())

        response_data = json.loads(response_file.read_text(encoding="utf-8"))
        self.assertTrue(response_data["answer_parsed"])
        self.assertEqual(response_data["answer"]["overview"][0]["text"], "a grounded statement")

        receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
        self.assertEqual(receipt_data["exception_type"], "KeyError")

        # build_live_integration_receipt never returned normally -- no final record, no integration receipt file
        # written by this test (there is no driver script here yet; that is the very next task).
        self.assertFalse((self.tmp / "live-crash" / "04_final_record.json").exists())


if __name__ == "__main__":
    unittest.main()
