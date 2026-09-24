"""Worker-layer validity: a mechanical failure is NO ANSWER, never an implicit semantic accept or a fallback query.

Regression target (run9, Qwen2.5 worker, AIB): 99 of 152 context-gate calls hit the 48-token cap and were silently
converted to "accept"; 3 of 6 recovery queries were truncated and silently replaced by the literal obligation text.
Both were mechanical incompletion interpreted as a semantic result. No inference here.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised import propositions, retrieval
from experiments.ask_cli_revised.calibration.run06.dataset06 import DEPRESSION_QUESTION
from experiments.ask_cli_revised.qwen import (
    _GATE_SCHEMA,
    _QUERY_SCHEMA,
    QwenTasks,
)
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.retrieval import GATE_NO_ANSWER, RetrievalHit, grow_context


class FakeTrace:
    def __init__(self):
        self.calls, self.decisions = [], []

    def qwen_call(self, **kwargs):
        self.calls.append(kwargs)

    def decision(self, stage, reason_code, *, kept, **inputs):
        self.decisions.append({"stage": stage, "reason_code": reason_code, "kept": kept, **inputs})


def call_result(raw="", ok=True, reason=None, cap=48):
    return SimpleNamespace(raw_text=raw, provider_ok=ok, failure_reason=reason, elapsed_seconds=0, output_cap=cap)


def task_with_trace():
    trace = FakeTrace()
    return QwenTasks(SimpleNamespace(), trace), trace


class ContextGateRepairTests(unittest.TestCase):
    def gate(self, result):
        task, trace = task_with_trace()
        with patch.object(task, "_call", return_value=result) as call:
            decision = task.context_gate(packet_text="Some passage.", subquestion="Which results?")
        return decision, trace, call

    def test_the_gate_call_is_schema_constrained_to_the_five_actions(self):
        _, _, call = self.gate(call_result('{"action":"accept"}'))
        self.assertEqual(call.call_args.kwargs["json_schema"], _GATE_SCHEMA)
        self.assertEqual(_GATE_SCHEMA["properties"]["action"]["enum"], ["accept", "before", "after", "both", "discard"])
        self.assertEqual(call.call_args.kwargs["output_cap"], 48)

    def test_each_valid_action_passes_through(self):
        for action in ("accept", "before", "after", "both", "discard"):
            with self.subTest(action=action):
                decision, _, _ = self.gate(call_result(f'{{"action":"{action}"}}'))
                self.assertEqual(decision, {"action": action})

    def test_a_truncated_gate_call_is_no_answer_not_accept(self):
        decision, _, _ = self.gate(call_result("", ok=False, reason="truncated_at_output_cap"))
        self.assertEqual(decision, {"action": GATE_NO_ANSWER})
        self.assertNotEqual(decision["action"], "accept")

    def test_unparseable_or_out_of_enum_gate_output_is_no_answer(self):
        for raw in ("I would accept this because it is complete.", '{"action":"maybe"}', '{"other":1}', '{"action":3}'):
            with self.subTest(raw=raw):
                decision, _, _ = self.gate(call_result(raw))
                self.assertEqual(decision, {"action": GATE_NO_ANSWER})

    def test_no_answer_is_recorded_as_a_mechanical_failure_never_a_fallback_verdict(self):
        _, trace, _ = self.gate(call_result("", ok=False, reason="truncated_at_output_cap"))
        (row,) = trace.calls
        self.assertEqual(row["task"], "context_gate")
        self.assertFalse(row["provider_ok"])
        self.assertEqual(row["failure_reason"], "truncated_at_output_cap")
        self.assertFalse(row["deterministic_fallback_used"])
        self.assertIn("NO ANSWER", row["downstream_consequence"])

    def test_a_usable_gate_decision_is_recorded_without_a_failure(self):
        _, trace, _ = self.gate(call_result('{"action":"after"}'))
        (row,) = trace.calls
        self.assertTrue(row["validation_ok"])
        self.assertIsNone(row["failure_reason"])
        self.assertEqual(row["downstream_consequence"], "action=after")


def hit(chunk_id=1, text="The association was null."):
    chunk = SimpleNamespace(chunk_id=chunk_id, text=text, attachment_id=1, paper_id=7)
    return RetrievalHit(chunk=chunk, subquestion_id="s1", score=0.8, section=None, chunk_type=None, evidence_role=None)


def rows(*texts):
    return [
        {"chunk_id": i, "char_start": i, "text": t, "section": None, "chunk_type": None, "evidence_role": None}
        for i, t in enumerate(texts, start=1)
    ]


class GrowContextNoAnswerTests(unittest.TestCase):
    def grow(self, gate, ordered=None):
        ordered = ordered or rows("The association was null.", "A second chunk.")
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=ordered):
            return grow_context(None, hit=hit(1, ordered[0]["text"]), gate=gate, subquestion_text="Which?")

    def test_no_answer_neither_accepts_nor_grows_and_excludes_the_packet(self):
        calls = []

        def gate(packet_text, subquestion):
            calls.append(packet_text)
            return {"action": GATE_NO_ANSWER}

        packet = self.grow(gate)
        self.assertTrue(packet.discarded)  # excluded from evidence extraction
        self.assertEqual(packet.discard_reason, "gate_no_answer")  # ... but distinguishable from a semantic discard
        self.assertEqual([c["chunk_id"] for c in packet.chunks], [1])  # not grown
        self.assertEqual(packet.grown, [])
        self.assertEqual(len(calls), 1)  # no retry
        self.assertEqual(packet.decisions[0]["action"], GATE_NO_ANSWER)

    def test_a_missing_action_is_no_answer_never_an_implicit_accept(self):
        packet = self.grow(lambda packet_text, subquestion: {})
        self.assertTrue(packet.discarded)
        self.assertEqual(packet.discard_reason, "gate_no_answer")

    def test_a_semantic_discard_keeps_its_own_reason(self):
        packet = self.grow(lambda packet_text, subquestion: {"action": "discard"})
        self.assertTrue(packet.discarded)
        self.assertEqual(packet.discard_reason, "gate_discard")

    def test_the_incomplete_clause_safeguard_keeps_its_own_reason(self):
        ordered = rows("research identifying effective interventions is needed to")
        packet = self.grow(lambda packet_text, subquestion: {"action": "accept"}, ordered=ordered)
        self.assertTrue(packet.discarded)
        self.assertEqual(packet.discard_reason, "incomplete_clause")

    def test_a_complete_accepted_packet_is_untouched(self):
        packet = self.grow(lambda packet_text, subquestion: {"action": "accept"})
        self.assertFalse(packet.discarded)
        self.assertIsNone(packet.discard_reason)

    def test_no_gate_at_all_is_an_explicit_accept(self):
        packet = self.grow(None)
        self.assertFalse(packet.discarded)


class DownstreamExclusionTests(unittest.TestCase):
    def test_a_gate_no_answer_packet_never_reaches_evidence_extraction_and_is_logged_by_reason(self):
        trace = FakeTrace()
        packet = SimpleNamespace(discarded=True, discard_reason="gate_no_answer", retrieval_anchor_chunk_id=9)
        qwen = MagicMock()
        records = propositions.marshal_and_verify(
            None,
            verifier=None,
            qwen=qwen,
            packet=packet,
            subquestion_text="q",
            obligations=[],
            nomination_reason=[],
            origin="initial",
            trace=trace,
        )
        self.assertEqual(records, [])
        qwen.select_evidence.assert_not_called()
        self.assertEqual(trace.decisions[0]["reason_code"], "gate_no_answer")

    def test_a_semantic_discard_keeps_the_original_reason_code(self):
        trace = FakeTrace()
        packet = SimpleNamespace(discarded=True, discard_reason="gate_discard", retrieval_anchor_chunk_id=9)
        propositions.marshal_and_verify(
            None,
            verifier=None,
            qwen=MagicMock(),
            packet=packet,
            subquestion_text="q",
            obligations=[],
            nomination_reason=[],
            origin="initial",
            trace=trace,
        )
        self.assertEqual(trace.decisions[0]["reason_code"], "context_controller_discarded_branch")


class RecoveryQueryRepairTests(unittest.TestCase):
    def query(self, result):
        task, trace = task_with_trace()
        with patch.object(task, "_call", return_value=result) as call:
            out = task.recovery_query(subquestion="q", obligation_note="amyloid")
        return out, trace, call

    def test_the_recovery_query_call_is_schema_constrained(self):
        out, _, call = self.query(call_result('{"query":"amyloid late-life depression"}', cap=64))
        self.assertEqual(out, "amyloid late-life depression")
        self.assertEqual(call.call_args.kwargs["json_schema"], _QUERY_SCHEMA)

    def test_a_failed_recovery_query_is_no_answer_not_the_literal_obligation_text(self):
        out, trace, _ = self.query(call_result("", ok=False, reason="truncated_at_output_cap", cap=64))
        self.assertIsNone(out)
        (row,) = trace.calls
        self.assertFalse(row["deterministic_fallback_used"])
        self.assertIn("NO ANSWER", row["downstream_consequence"])

    def test_an_empty_query_is_no_answer(self):
        out, _, _ = self.query(call_result('{"query":"   "}', cap=64))
        self.assertIsNone(out)

    def test_recover_skips_a_gap_whose_query_had_no_answer_and_records_why(self):
        subquestions = request_subquestions(build_request_contract("Which scales?"))
        gap = {"field_id": "s1-o1", "subquestion_id": "s1", "note": "Which scales?", "display": "Which scales?"}
        qwen = MagicMock()
        qwen.recovery_query.return_value = None
        with patch.object(cli.retrieval, "within_paper_retrieve") as retrieve:
            log = cli._recover(
                None,
                rt=MagicMock(),
                qwen=qwen,
                subquestions=subquestions,
                gaps=[gap],
                initial_nominations={},
                all_records=[],
                axis_cache={},
                trace=FakeTrace(),
                chunk_hits=[],
                context_growth=[],
                evidence_packets=[],
                propositions=[],
                verifications=[],
            )
        retrieve.assert_not_called()  # no search state was created, so none is claimed
        self.assertEqual(log[0]["reason_code"], "recovery_query_no_answer")
        self.assertEqual(log[0]["new_verified"], 0)

    def test_recover_hands_the_model_facing_display_to_the_query_writer(self):
        obligation = request_subquestions(build_request_contract(DEPRESSION_QUESTION))[2]["obligations"][0]
        self.assertEqual(obligation["note"], "amyloid")
        subquestions = request_subquestions(build_request_contract(DEPRESSION_QUESTION))
        rows_ = cli.coverage_mod.audit_coverage(subquestions, [])["obligations"]
        gap = next(r for r in rows_ if r["note"] == "amyloid")
        qwen = MagicMock()
        qwen.recovery_query.return_value = None
        cli._recover(
            None,
            rt=MagicMock(),
            qwen=qwen,
            subquestions=subquestions,
            gaps=[gap],
            initial_nominations={},
            all_records=[],
            axis_cache={},
            trace=FakeTrace(),
            chunk_hits=[],
            context_growth=[],
            evidence_packets=[],
            propositions=[],
            verifications=[],
        )
        note = qwen.recovery_query.call_args.kwargs["obligation_note"]
        self.assertIn("I am particularly interested in serotonergic function, amyloid", note)


class ModelFacingObligationTests(unittest.TestCase):
    def prompt_for(self, obligations):
        task, _ = task_with_trace()
        with patch.object(task, "_call", return_value=call_result('{"span_ids":[]}', cap=96)) as call:
            task.select_evidence(spans=[{"span_id": "e1", "text": "x"}], subquestion="q", obligations=obligations)
        return call.call_args.kwargs["prompt"]

    def test_evidence_selection_shows_a_fragments_frame(self):
        obligations = request_subquestions(build_request_contract(DEPRESSION_QUESTION))[2]["obligations"]
        prompt = self.prompt_for(obligations)
        self.assertIn("- s3-o1: amyloid [part of the request sentence:", prompt)
        self.assertIn("I am particularly interested in serotonergic function, amyloid", prompt)

    def test_evidence_selection_lines_for_full_units_are_unchanged(self):
        obligations = [{"field_id": "s3-o1", "note": "and using which scales?"}]
        self.assertIn("- s3-o1: and using which scales?\n", self.prompt_for(obligations) + "\n")


if __name__ == "__main__":
    unittest.main()
