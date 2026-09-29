"""Phase 2 Section 5/6: recovery-only deterministic neighborhood construction (retrieval.recovery_neighborhood_context).

Section 5 ports contract_directed/neighborhood.py's bounded, structurally-coherent +/-3 window into the flat pipeline's
recovery round, in place of grow_context's narrower model-gated +/-2 growth -- and ONLY there: the initial pass keeps
grow_context unchanged (proved in test_rounds_mechanics.py's RecoveryPassesDeterministicNeighborhoodContextTests, which
also proves _recover is the only caller that passes context_fn). This file tests recovery_neighborhood_context itself,
in isolation, against real deterministic fixtures -- no model, no live retrieval.
"""

from types import SimpleNamespace
from unittest.mock import patch
import unittest

from experiments.ask_cli_revised import retrieval
from experiments.ask_cli_revised.retrieval import RetrievalHit, recovery_neighborhood_context


def _hit(chunk_id, text, *, section=None, chunk_type=None, evidence_role=None, attachment_id=1, paper_id=27):
    chunk = SimpleNamespace(chunk_id=chunk_id, text=text, attachment_id=attachment_id, paper_id=paper_id)
    return RetrievalHit(
        chunk=chunk, subquestion_id="s1", score=0.8, section=section, chunk_type=chunk_type, evidence_role=evidence_role
    )


def _row(chunk_id, text, *, section=None):
    return {"chunk_id": chunk_id, "char_start": chunk_id, "text": text, "section": section,
            "chunk_type": None, "evidence_role": None}  # fmt: skip


class DeterministicWindowTests(unittest.TestCase):
    def test_the_window_reaches_three_chunks_on_each_side_with_no_model_call(self):
        """MAX_SIDE=3 (contract_directed's own default, unchanged): 7 chunks total around a central anchor."""
        rows = [_row(i, f"sentence {i}.") for i in range(1, 8)]
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=rows):
            packet = recovery_neighborhood_context(conn=None, hit=_hit(4, rows[3]["text"]), subquestion_text="q")
        self.assertEqual([c["chunk_id"] for c in packet.chunks], [1, 2, 3, 4, 5, 6, 7])
        self.assertFalse(packet.discarded)
        self.assertEqual(packet.decisions[0]["mechanism"], "deterministic_neighborhood")

    def test_the_window_stops_at_the_references_section_never_crossing_it(self):
        rows = [
            _row(1, "Methods text one."),
            _row(2, "Methods text two."),
            _row(3, "Smith, J. (2020). A paper.", section="references"),
            _row(4, "Jones, K. (2019). Another paper.", section="references"),
        ]
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=rows):
            packet = recovery_neighborhood_context(conn=None, hit=_hit(2, rows[1]["text"]), subquestion_text="q")
        chunk_ids = [c["chunk_id"] for c in packet.chunks]
        self.assertNotIn(3, chunk_ids)
        self.assertNotIn(4, chunk_ids)

    def test_a_single_unresolvable_index_falls_back_to_the_incomplete_clause_guard(self):
        """Mirrors grow_context's own fail-closed rule when there is no positional index to grow from."""
        with patch.object(retrieval, "_attachment_chunks_ordered", return_value=[]):
            packet = recovery_neighborhood_context(
                conn=None, hit=_hit(1, "research identifying effective interventions is needed to"), subquestion_text="q"
            )
        self.assertTrue(packet.discarded)
        self.assertEqual(packet.discard_reason, "incomplete_clause")

    def test_no_gate_is_called_the_mechanism_is_purely_structural(self):
        """recovery_neighborhood_context takes no `gate` argument at all -- unlike grow_context, nothing here is a
        model decision; only neighborhood.build_neighborhood's own deterministic clipping rules apply."""
        import inspect

        params = inspect.signature(recovery_neighborhood_context).parameters
        self.assertNotIn("gate", params)


if __name__ == "__main__":
    unittest.main()
