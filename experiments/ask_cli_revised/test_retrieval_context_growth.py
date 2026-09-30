"""Incomplete-proposition safeguard: _ends_mid_clause and grow_context's use of it.

Regression target (traced from a real recovered proposition, run7-recovery-fix p8):
source fragment "research identifying effective interventions is needed to" must never
again be able to reach form_claim() as an accepted, complete-looking packet -- it broke off
on a preposition mid-clause, and claim formation silently dropped the qualifier when asked
to paraphrase it, producing a promotable claim with an inverted meaning. This does not touch
context_gate's own prompt/schema, verification semantics, or recovery/coverage behavior.
"""
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from experiments.ask_cli_revised import retrieval
from experiments.ask_cli_revised.retrieval import RetrievalHit, _ends_mid_clause, grow_context


def _hit(chunk_id, text, attachment_id=1, paper_id=27):
    chunk = SimpleNamespace(chunk_id=chunk_id, text=text, attachment_id=attachment_id, paper_id=paper_id)
    return RetrievalHit(chunk=chunk, subquestion_id="s1", score=0.8, section=None, chunk_type=None, evidence_role=None)


def _row(chunk_id, text):
    return {"chunk_id": chunk_id, "char_start": chunk_id, "text": text, "section": None,
            "chunk_type": None, "evidence_role": None}


class EndsMidClauseTests(unittest.TestCase):
    def test_real_truncated_fragments_are_flagged(self):
        # p8's real anchor fragment (chunk 72423, run7-recovery-fix).
        self.assertTrue(_ends_mid_clause("research identifying effective interventions is needed to"))
        # p5's independently-confirmed real truncation, ending on an article.
        self.assertTrue(_ends_mid_clause("consistent with theories emphasizing the"))

    def test_complete_or_merely_unpunctuated_content_is_not_flagged(self):
        self.assertFalse(_ends_mid_clause("The association was null."))
        # p6/p7 shape: real, complete, deliberately out-of-scope propositions with no
        # trailing period -- ending on an ordinary content word must not be flagged.
        self.assertFalse(_ends_mid_clause("differences in anomalous-is-bad behavior"))
        self.assertFalse(_ends_mid_clause("cross-cultural mentalizing beliefs"))

    def test_empty_and_punctuated_edge_cases(self):
        self.assertFalse(_ends_mid_clause(""))
        self.assertFalse(_ends_mid_clause("   "))
        self.assertFalse(_ends_mid_clause("Ends with a question?"))
        self.assertFalse(_ends_mid_clause("Trailing space after the period. "))


class GrowContextIncompleteProposableTests(unittest.TestCase):
    def test_p8_regression_fails_closed_when_no_further_chunk_completes_it(self):
        """Single-chunk attachment mirroring p8: nothing to grow into -> fail closed."""
        rows = [_row(72423, "research identifying effective interventions is needed to")]
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=rows):
            packet = grow_context(
                conn=None,
                hit=_hit(72423, rows[0]["text"]),
                gate=lambda packet_text, subquestion: {"action": "accept"},
                subquestion_text="What interventions were studied?",
            )
        self.assertTrue(packet.discarded)

    def test_growth_completes_the_sentence_when_the_real_next_chunks_do(self):
        """Mirrors p8's real document shape but with neighbors that DO complete the clause."""
        rows = [
            _row(1, "research identifying effective interventions is needed to"),
            _row(2, "maintain the basic human rights of racial and ethnic minorities, keep communities safe, and"),
            _row(3, "increase the effectiveness of policing."),
        ]
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=rows):
            packet = grow_context(
                conn=None,
                hit=_hit(1, rows[0]["text"]),
                gate=lambda packet_text, subquestion: {"action": "accept"},
                subquestion_text="What interventions were studied?",
            )
        self.assertFalse(packet.discarded)
        self.assertEqual([c["chunk_id"] for c in packet.chunks], [1, 2, 3])

    def test_already_complete_evidence_is_unaffected(self):
        """Rule 1: a complete proposition's existing accept-and-stop behavior is unchanged."""
        rows = [_row(1, "The association was null.")]
        calls = []

        def gate(packet_text, subquestion):
            calls.append(packet_text)
            return {"action": "accept"}

        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=rows):
            packet = grow_context(
                conn=None, hit=_hit(1, rows[0]["text"]), gate=gate, subquestion_text="Which association?",
            )
        self.assertFalse(packet.discarded)
        self.assertEqual(len(packet.chunks), 1)  # not grown
        # Subset check, not exact-dict equality: Stage A (plural evidence anchors) added extra,
        # None-valued keys to every packet chunk (attachment_id/char_end/page_start/... -- see
        # retrieval._packet_chunk's own docstring); this test's concern is the original five.
        self.assertEqual(
            {k: packet.chunks[0][k] for k in ("chunk_id", "text", "section", "chunk_type", "evidence_role")},
            {"chunk_id": 1, "text": rows[0]["text"], "section": None, "chunk_type": None, "evidence_role": None},
        )
        self.assertEqual(len(calls), 1)  # never re-consulted; no forced growth attempted

    def test_discard_decision_is_unaffected(self):
        """Rule: an explicit discard still wins outright, same as before this change."""
        rows = [_row(1, "irrelevant boilerplate")]
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=rows):
            packet = grow_context(
                conn=None, hit=_hit(1, rows[0]["text"]),
                gate=lambda packet_text, subquestion: {"action": "discard"},
                subquestion_text="Which association?",
            )
        self.assertTrue(packet.discarded)

    def test_no_index_seam_still_fails_closed_on_an_incomplete_lone_anchor(self):
        """Rule 4: when growth is architecturally unavailable, an incomplete anchor fails closed."""
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=[]):
            packet = grow_context(
                conn=None,
                hit=_hit(999, "research identifying effective interventions is needed to"),
                gate=lambda packet_text, subquestion: {"action": "accept"},
                subquestion_text="What interventions were studied?",
            )
        self.assertTrue(packet.discarded)


if __name__ == "__main__":
    unittest.main()
