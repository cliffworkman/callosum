"""Tests for the offline replay/integration orchestrator (2026-09-27). No model, NLI, or embedding call
anywhere in this file."""

import shutil
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import evidence_identity as ident
from experiments.ask_cli_revised.contract_directed import gate_integration as integration
from experiments.ask_cli_revised.contract_directed import partial_answer_renderer as par

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


if __name__ == "__main__":
    unittest.main()
