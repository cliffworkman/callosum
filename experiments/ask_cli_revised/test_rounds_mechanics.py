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


class MultiChunkEvidenceCollapsesToASingleAnchorTests(unittest.TestCase):
    """Phase 2 Section 6: characterizes -- does not fix -- the Sept 29 flat-E2E finding that a recovered, multi-chunk
    neighborhood reaches claim formation as full context but is persisted downstream as one anchor chunk and one
    exact quote. This is a PRE-EXISTING structural property of propositions.marshal_and_verify's schema
    (evidence_anchor_chunk_id/evidence_span_id/quote are all singular), not something Section 5's neighborhood work
    introduces -- it existed already for grow_context's own +/-2 packets, and this test proves it holds for a
    Section-5-shaped +/-3 packet too. Per Section 15/16: this is the stop-and-report point, not a redesign to do here."""

    def test_a_three_chunk_packet_gives_form_claim_full_context_but_persists_only_one_chunks_span(self):
        chunk_a = {"chunk_id": 10, "text": "The prevalence estimate depends on the diagnostic threshold used.",
                   "evidence_role": None, "chunk_type": None}  # fmt: skip
        chunk_b = {"chunk_id": 11, "text": "At the lower threshold, prevalence was 14.2%.",
                   "evidence_role": None, "chunk_type": None}  # fmt: skip
        chunk_c = {"chunk_id": 12, "text": "At the higher threshold used by the comparison study, it was 8.1%.",
                   "evidence_role": None, "chunk_type": None}  # fmt: skip
        packet = SimpleNamespace(
            discarded=False, discard_reason=None,
            chunks=[chunk_a, chunk_b, chunk_c],  # a Section-5-shaped recovery neighborhood: three chunks, one packet
            subquestion_id="s1", paper_id=7, retrieval_anchor_chunk_id=11, retrieval_score=0.8, grown=[10, 12],
        )  # fmt: skip
        qwen = MagicMock()
        # A single selected span from chunk_b alone -- but form_claim is handed context_text built from ALL THREE
        # chunks, so the model CAN see the full comparison when interpreting that one span into a claim.
        qwen.select_evidence.return_value = ["e2"]  # chunk_b's sentence, per _candidate_spans' span numbering
        seen_context = {}

        def capture_form_claim(*, quote, context_text, subquestion):
            seen_context["context_text"] = context_text
            return "Prevalence was 14.2% at the lower threshold, versus 8.1% at the higher threshold."

        qwen.form_claim.side_effect = capture_form_claim
        qwen.map_obligations.return_value = ["s1-o1"]
        verifier = SimpleNamespace(verify_many=lambda conn, items, source_chunks: [verified_result() for _ in items])
        with patch.object(propositions, "_source_chunk_for_id", return_value=SimpleNamespace(text=chunk_b["text"])):
            records = propositions.marshal_and_verify(
                None, verifier=verifier, qwen=qwen, packet=packet, subquestion_text="What was the prevalence?",
                obligations=[{"field_id": "s1-o1", "note": "prevalence"}], nomination_reason=[], origin="recovery",
                trace=FakeTrace(),
            )  # fmt: skip

        # (a) recovered context DID reach proposition formation: all three chunks' text is in what form_claim saw.
        for chunk in (chunk_a, chunk_b, chunk_c):
            self.assertIn(chunk["text"], seen_context["context_text"])

        # (b) the CLAIM itself synthesizes across chunks (both percentages, from chunk_b and chunk_c).
        self.assertIn("14.2%", records[0]["proposition_text"])
        self.assertIn("8.1%", records[0]["proposition_text"])

        # (c) but the PERSISTED evidence anchor is singular and names only chunk_b -- chunk_c's "8.1%" fact, which
        # the claim asserts, has no persisted anchor/span/quote of its own. This is the limitation: a claim can
        # assert more than its one persisted quote verbatim-verifies.
        self.assertEqual(records[0]["evidence_anchor_chunk_id"], 11)
        self.assertNotIn("evidence_anchor_chunk_ids", records[0])  # no plural field exists to carry chunk_c too
        self.assertEqual(records[0]["quote"], chunk_b["text"])
        self.assertNotIn("8.1%", records[0]["quote"])  # the quote that gets verbatim-verified never has the C fact

        # (d) provenance.context_read is the ONLY place the wider neighborhood survives -- a diagnostic list, not an
        # additional verified anchor: verification (canonical_text_contains) only ever runs against evidence_anchor_
        # chunk_id's own single chunk text (patched above to chunk_b's text only), never against chunk_c.
        self.assertEqual(sorted(records[0]["provenance"]["context_read"]), [10, 11, 12])
        self.assertEqual(records[0]["verification"]["status"], "verified")  # verified against chunk_b alone


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


class RecoveryPassesDeterministicNeighborhoodContextTests(PlanDrivenRecoveryTests):
    """Phase 2 Section 5: the recovery round -- and only the recovery round -- builds its context packets with the
    deterministic +/-3 neighborhood, never the initial pass's model-gated grow_context. Reuses PlanDrivenRecoveryTests'
    own `recover()` harness so this proves the SAME call path the DEEPEN/NOMINATE tests above already exercise."""

    def test_every_process_hits_call_from_recovery_carries_a_context_fn(self):
        _, _, _, _, process = self.recover({"s1-o1": "NOMINATE"})
        self.assertTrue(process.call_args_list)
        for call in process.call_args_list:
            self.assertIn("context_fn", call.kwargs)
            self.assertTrue(callable(call.kwargs["context_fn"]))

    def test_the_context_fn_calls_recovery_neighborhood_context_not_grow_context(self):
        """The passed callable really resolves to recovery_neighborhood_context, not merely present but inert:
        calling it produces recovery_neighborhood_context's own distinctive marker
        (`decisions[0]["mechanism"] == "deterministic_neighborhood"`), which grow_context never sets."""
        _, _, _, _, process = self.recover({"s1-o1": "DEEPEN"})
        context_fn = process.call_args_list[0].kwargs["context_fn"]
        fake_hit = SimpleNamespace(chunk=SimpleNamespace(chunk_id=1, text="x", attachment_id=1, paper_id=1),
                                    subquestion_id="s1", score=0.5, section=None, chunk_type=None, evidence_role=None)  # fmt: skip
        with patch.object(cli.retrieval, "_attachment_chunks_ordered", return_value=[
            {"chunk_id": 1, "char_start": 0, "text": "x", "section": None, "chunk_type": None, "evidence_role": None}
        ]):
            packet = context_fn(fake_hit)
        self.assertEqual(packet.decisions[0]["mechanism"], "deterministic_neighborhood")

    def test_initial_pass_never_passes_context_fn_so_grow_context_stays_the_default(self):
        """e2e._initial_pass calls cli._process_hits without context_fn at all -- confirmed by reading the call site
        (e2e.py's _initial_pass), and confirmed here structurally: _process_hits's own default falls back to
        grow_context whenever context_fn is None, which is exactly what an omitted kwarg produces."""
        import inspect

        default = inspect.signature(cli._process_hits).parameters["context_fn"].default
        self.assertIsNone(default)


if __name__ == "__main__":
    unittest.main()
