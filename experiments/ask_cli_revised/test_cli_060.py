"""Orchestration tests with inference/retrieval mocked, not evidence-yield tests."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised.calibration.run06.dataset06 import decomposition_cases_v06
from experiments.ask_cli_revised.ledger_renderer import audit_final
from experiments.ask_cli_revised.trace import TraceWriter
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.test_ledger_renderer import ledger_fixture


class CLI060Tests(unittest.TestCase):
    def test_frozen_rich_cases_reach_persisted_final(self):
        for case in decomposition_cases_v06():
            if not case["rich"]:
                continue
            with self.subTest(case=case["case_id"]), tempfile.TemporaryDirectory() as out, ExitStack() as stack:
                rt = MagicMock()
                qwen = MagicMock()
                qwen.interpret.side_effect = AssertionError("derived decomposition must not replace original")
                qwen.recovery_query.side_effect = AssertionError("generated recovery must not replace source")
                stack.enter_context(patch.object(cli, "build_runtime", return_value=rt))
                stack.enter_context(patch.object(cli, "QwenTasks", return_value=qwen))
                stack.enter_context(patch.object(cli.discovery, "corpus_stats", return_value={}))
                stack.enter_context(patch.object(cli.discovery, "graph_rescue_stage", return_value={}))
                nominations = stack.enter_context(patch.object(cli.discovery, "nominate_papers", return_value=([], [])))
                stack.enter_context(patch.object(cli.retrieval, "within_paper_retrieve", return_value=[]))
                terminal = stack.enter_context(patch.object(cli.synthesis, "terminal_synthesis", return_value=("Invented finding [p27].", True)))
                stack.enter_context(redirect_stdout(io.StringIO()))
                self.assertEqual(cli.run("mock-copy.sqlite", out, "qwen", question=case["text"]), 0)
                ledger = json.loads((Path(out) / "11_verified_ledger.json").read_text(encoding="utf-8"))
                self.assertEqual(ledger["request_contract"]["original_question"], case["text"])
                self.assertTrue(all(case["text"] in call.kwargs["subquestion_text"] for call in nominations.call_args_list))
                self.assertEqual(len(ledger["coverage"]["original_request"]["unresolved_unit_ids"]), len(ledger["subquestions"]))
                final = (Path(out) / "14_final_answer.md").read_text(encoding="utf-8")
                self.assertTrue(audit_final(ledger, final)["constrained_render_match"])
                self.assertTrue(json.loads((Path(out) / "14_final_audit.json").read_text())["constrained_render_match"])
                self.assertNotIn("Invented finding", final)
                self.assertTrue((Path(out) / "14a_UNVALIDATED_candidate.qwen.md").is_file())
                terminal.assert_called_once()
                rt.close.assert_called_once()

    def test_process_hits_carries_source_ancestry(self):
        with tempfile.TemporaryDirectory() as out:
            sq = request_subquestions(build_request_contract("Which scales?"))[0]
            row = ledger_fixture()["verified_propositions"][0]
            row.update(subquestion_id="s1", retrieval_anchor_chunk_id=26831, provenance={"origin": "initial"})
            all_records, hits, growth, packets, props, verifications = [], [], [], [], [], []
            with patch.object(cli.retrieval, "grow_context", return_value=MagicMock()), patch.object(cli, "marshal_and_verify", return_value=[row]):
                cli._process_hits(None, rt=MagicMock(), qwen=MagicMock(), subquestion=sq,
                                  hits=[MagicMock()], reason_by_paper={}, origin="initial", trace=TraceWriter(out),
                                  all_records=all_records, chunk_hits=hits, context_growth=growth,
                                  evidence_packets=packets, propositions=props, verifications=verifications)
            self.assertEqual(props[0]["provenance"]["request"]["source_text"], "Which scales?")
            self.assertEqual(all_records[0]["provenance"]["request"]["question_hash"], sq["question_hash"])

    def test_default_terminal_is_renderer(self):
        with patch.object(cli, "run", return_value=0) as run:
            cli.main(["--db", "copy.sqlite", "--out", "unused"])
        self.assertEqual(run.call_args.args[2], "render")

    def test_nonempty_ledger_resolves_to_offered_spans(self):
        with tempfile.TemporaryDirectory() as out, ExitStack() as stack:
            rt = MagicMock()
            packet = SimpleNamespace(subquestion_id="s1", paper_id=27, retrieval_anchor_chunk_id=26831,
                                     retrieval_score=0.8, grown=[], discarded=False, decisions=[],
                                     chunks=[{"paper_id": 27, "chunk_id": 26831, "text": "The association was null."}])
            row = ledger_fixture()["verified_propositions"][0]
            row.update(subquestion_id="s1", retrieval_anchor_chunk_id=26831, provenance={"origin": "initial"})
            stack.enter_context(patch.object(cli, "build_runtime", return_value=rt))
            stack.enter_context(patch.object(cli, "QwenTasks", return_value=MagicMock()))
            stack.enter_context(patch.object(cli.discovery, "corpus_stats", return_value={}))
            stack.enter_context(patch.object(cli.discovery, "graph_rescue_stage", return_value={}))
            stack.enter_context(patch.object(cli.discovery, "nominate_papers", return_value=([], [])))
            stack.enter_context(patch.object(cli.retrieval, "within_paper_retrieve", side_effect=[[MagicMock()], [], []]))
            stack.enter_context(patch.object(cli.retrieval, "grow_context", return_value=packet))
            stack.enter_context(patch.object(cli, "marshal_and_verify", return_value=[row]))
            terminal = stack.enter_context(patch.object(cli.synthesis, "terminal_synthesis"))
            stack.enter_context(redirect_stdout(io.StringIO()))
            self.assertEqual(cli.run("mock.sqlite", out, question="Which association?"), 0)
            terminal.assert_not_called()
            ledger = json.loads((Path(out) / "11_verified_ledger.json").read_text())
            self.assertEqual(len(ledger["evidence_spans"]), 1)
            self.assertEqual(ledger["evidence_spans"][0]["text"], row["quote"])
            self.assertTrue(audit_final(ledger, (Path(out) / "14_final_answer.md").read_text())["all_proposition_spans_resolve"])


if __name__ == "__main__":
    unittest.main()
