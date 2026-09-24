"""Two-round mechanics: mapping is deferred until after source verification, and recovery executes a plan."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised import propositions
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions

QUOTE = "The association was null."


class FakeTrace:
    def __init__(self):
        self.decisions = []

    def qwen_call(self, **kwargs):
        pass

    def decision(self, stage, reason_code, *, kept, **inputs):
        self.decisions.append((stage, reason_code, kept))


def verified_result():
    return SimpleNamespace(
        status="verified",
        retrieval_confidence=0.9,
        quote_confidence=1.0,
        support_confidence=0.8,
        contradiction_confidence=0.0,
        page_start=1,
        page_end=1,
        coordinate_precision="exact",
    )


def marshal(map_claims=None):
    packet = SimpleNamespace(
        discarded=False,
        discard_reason=None,
        chunks=[{"chunk_id": 1, "text": QUOTE, "evidence_role": None, "chunk_type": None}],
        subquestion_id="s1",
        paper_id=7,
        retrieval_anchor_chunk_id=1,
        retrieval_score=0.8,
        grown=[],
    )
    qwen = MagicMock()
    qwen.select_evidence.return_value = ["e1"]
    qwen.form_claim.return_value = QUOTE
    qwen.map_obligations.return_value = ["s1-o1"]
    verifier = SimpleNamespace(verify_many=lambda conn, items, source_chunks: [verified_result() for _ in items])
    kwargs = {} if map_claims is None else {"map_claims": map_claims}
    with patch.object(propositions, "_source_chunk_for_id", return_value=SimpleNamespace(text=QUOTE)):
        records = propositions.marshal_and_verify(
            None,
            verifier=verifier,
            qwen=qwen,
            packet=packet,
            subquestion_text="q",
            obligations=[{"field_id": "s1-o1", "note": "Which association?"}],
            nomination_reason=[],
            origin="initial",
            trace=FakeTrace(),
            **kwargs,
        )
    return records, qwen


class DeferredMappingTests(unittest.TestCase):
    def test_default_behavior_maps_inline_exactly_as_before(self):
        records, qwen = marshal()
        qwen.map_obligations.assert_called_once()
        self.assertEqual(records[0]["obligation_ids"], ["s1-o1"])
        self.assertEqual(records[0]["mapping_state"], "mapped")

    def test_deferred_mapping_never_calls_the_mapper_and_marks_the_record_pending(self):
        records, qwen = marshal(map_claims=False)
        qwen.map_obligations.assert_not_called()
        self.assertEqual(records[0]["obligation_ids"], [])
        self.assertEqual(records[0]["mapping_state"], "pending")
        self.assertEqual(records[0]["verification"]["status"], "verified")  # source verification is unaffected


def nomination(paper_id):
    return SimpleNamespace(
        paper_id=paper_id, reasons=["direct"], best_score=0.5, direct_score=0.5, axis_score=0, axis_hits=0
    )


class PlanDrivenRecoveryTests(unittest.TestCase):
    def recover(self, plan, *, query="a reformulated query"):
        subquestions = request_subquestions(build_request_contract("Which scales?"))
        gap = {"field_id": "s1-o1", "subquestion_id": "s1", "note": "Which scales?", "display": "Which scales?"}
        qwen = MagicMock()
        qwen.recovery_query.return_value = query
        retrieve = MagicMock(return_value=[])
        nominate = MagicMock(return_value=([nomination(99), nomination(5)], []))
        process = MagicMock()
        with (
            patch.object(cli.retrieval, "within_paper_retrieve", retrieve),
            patch.object(cli.discovery, "nominate_papers", nominate),
            patch.object(cli, "_process_hits", process),
        ):
            log = cli._recover(
                None, rt=MagicMock(), qwen=qwen, subquestions=subquestions, gaps=[gap],
                initial_nominations={"s1": [nomination(5)]}, all_records=[], axis_cache={}, trace=FakeTrace(),
                chunk_hits=[], context_growth=[], evidence_packets=[], propositions=[], verifications=[],
                plan=plan, map_claims=False,
            )  # fmt: skip
        return log, qwen, retrieve, nominate, process

    def test_deepen_researches_only_the_existing_candidates(self):
        log, qwen, retrieve, nominate, _ = self.recover({"s1-o1": "DEEPEN"})
        nominate.assert_not_called()
        self.assertEqual(retrieve.call_args.kwargs["paper_ids"], [5])
        self.assertEqual(log[0]["action"], "DEEPEN")

    def test_nominate_searches_only_papers_not_already_candidates(self):
        log, qwen, retrieve, nominate, _ = self.recover({"s1-o1": "NOMINATE"})
        nominate.assert_called_once()
        self.assertEqual(retrieve.call_count, 1)  # no existing-candidates re-search
        self.assertEqual(retrieve.call_args.kwargs["paper_ids"], [99])  # paper 5 was already a candidate
        self.assertEqual(log[0]["action"], "NOMINATE")

    def test_non_search_actions_create_no_search_state_and_are_recorded(self):
        for action in ("NO_RECOVERY_NEEDED", "PRESERVE_UNRESOLVED", "MARK_COVERED:p1"):
            with self.subTest(action=action):
                log, qwen, retrieve, nominate, process = self.recover({"s1-o1": action})
                qwen.recovery_query.assert_not_called()
                retrieve.assert_not_called()
                nominate.assert_not_called()
                process.assert_not_called()
                self.assertEqual(log[0]["reason_code"], "plan_no_search")
                self.assertEqual(log[0]["action"], action)
                self.assertEqual(log[0]["new_verified"], 0)

    def test_an_obligation_absent_from_the_plan_is_left_alone(self):
        log, qwen, retrieve, nominate, _ = self.recover({})
        qwen.recovery_query.assert_not_called()
        self.assertEqual(log, [])

    def test_map_claims_false_reaches_every_processing_call(self):
        _, _, _, _, process = self.recover({"s1-o1": "DEEPEN"})
        self.assertTrue(process.call_args_list)
        for call in process.call_args_list:
            self.assertIs(call.kwargs["map_claims"], False)

    def test_no_plan_is_the_legacy_sequence_unchanged(self):
        log, _, retrieve, nominate, _ = self.recover(None)
        # legacy: search the existing candidates first, then nominate because nothing new was added
        nominate.assert_called_once()
        self.assertEqual(retrieve.call_args_list[0].kwargs["paper_ids"], [5])
        self.assertEqual(log[0]["reason_code"], "recovery_no_new_evidence")


if __name__ == "__main__":
    unittest.main()
