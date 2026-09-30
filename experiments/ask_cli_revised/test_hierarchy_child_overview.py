"""Stage B (child Overview, 2026-09-29 authorization): hierarchy_contract.build_child_sealed_ledger.

Filters a hierarchical run's own full sealed ledger down to one child's own overview.build_overview
input, INCLUSIVELY: a proposition genuinely responsive to more than one child (responsive_obligation_ids
can name several) is included for every child it's actually responsive to. "Strict isolation" means
excluding evidence with no relevance to this child at all -- never arbitrarily assigning shared
evidence to only one child (Cliff's explicit correction after review). Also covers the exact-child-
question substitution (never the parent's literal text) and Stage A plural-anchor evidence-span
filtering.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import hierarchy_contract as hc


def _state(field_id, note):
    return {"field_id": field_id, "subquestion_id": field_id, "source_unit_id": field_id, "note": note,
             "display": note, "state": "judged_responsive", "proposition_ids": [], "mechanical_gaps": 0}  # fmt: skip


def _prop(pid, *, paper_id, chunk_id, span_id, quote, responsive_to, anchors=None):
    row = {
        "proposition_id": pid, "paper_id": paper_id, "evidence_anchor_chunk_id": chunk_id,
        "evidence_span_id": span_id, "proposition_text": f"claim {pid}", "quote": quote,
        "responsive_obligation_ids": list(responsive_to),
        "verification": {"status": "verified"},
    }  # fmt: skip
    if anchors:
        row["anchors"] = anchors
    return row


def _span(paper_id, chunk_id, span_id, text):
    return {"paper_id": paper_id, "chunk_id": chunk_id, "span_id": span_id, "text": text}


def _sealed(states, propositions, evidence_spans, *, question_hash="parent-hash-abc"):
    return {
        "request_contract": {"original_question": "the parent q_aib question", "question_hash": question_hash},
        "obligation_states": states,
        "verified_propositions": propositions,
        "evidence_spans": evidence_spans,
    }


class BuildChildSealedLedgerTests(unittest.TestCase):
    def test_only_evidence_responsive_to_this_child_is_included(self):
        sealed = _sealed(
            [_state("c1", "how does X manifest in brain"), _state("c2", "how does X manifest in behavior")],
            [
                _prop("p1", paper_id=1, chunk_id=10, span_id="e1", quote="brain finding", responsive_to=["c1"]),
                _prop("p2", paper_id=1, chunk_id=20, span_id="e1", quote="behavior finding", responsive_to=["c2"]),
            ],
            [_span(1, 10, "e1", "brain finding"), _span(1, 20, "e1", "behavior finding")],
        )
        child = hc.build_child_sealed_ledger(sealed, "c1")
        self.assertEqual([p["proposition_id"] for p in child["verified_propositions"]], ["p1"])
        self.assertEqual(len(child["evidence_spans"]), 1)
        self.assertEqual(child["evidence_spans"][0]["chunk_id"], 10)

    def test_evidence_shared_across_children_appears_in_both_not_exclusively_one(self):
        """The explicit correction: strict isolation excludes irrelevant evidence, it does not
        arbitrarily assign shared evidence to only one child."""
        sealed = _sealed(
            [_state("c1", "q1"), _state("c2", "q2")],
            [_prop("p1", paper_id=1, chunk_id=10, span_id="e1", quote="shared finding", responsive_to=["c1", "c2"])],
            [_span(1, 10, "e1", "shared finding")],
        )
        child1 = hc.build_child_sealed_ledger(sealed, "c1")
        child2 = hc.build_child_sealed_ledger(sealed, "c2")
        self.assertEqual([p["proposition_id"] for p in child1["verified_propositions"]], ["p1"])
        self.assertEqual([p["proposition_id"] for p in child2["verified_propositions"]], ["p1"])

    def test_evidence_exclusive_to_another_child_never_enters_this_childs_ledger(self):
        sealed = _sealed(
            [_state("c1", "q1"), _state("c2", "q2")],
            [_prop("p2", paper_id=1, chunk_id=20, span_id="e1", quote="only c2's finding", responsive_to=["c2"])],
            [_span(1, 20, "e1", "only c2's finding")],
        )
        child1 = hc.build_child_sealed_ledger(sealed, "c1")
        self.assertEqual(child1["verified_propositions"], [])
        self.assertEqual(child1["evidence_spans"], [])

    def test_original_question_is_the_childs_own_wording_never_the_parents(self):
        sealed = _sealed([_state("c1", "Please return the specific brain areas.")], [], [])
        child = hc.build_child_sealed_ledger(sealed, "c1")
        self.assertEqual(child["request_contract"]["original_question"], "Please return the specific brain areas.")
        self.assertNotEqual(child["request_contract"]["original_question"], sealed["request_contract"]["original_question"])  # fmt: skip

    def test_question_hash_is_the_childs_own_and_parent_provenance_is_preserved_separately(self):
        sealed = _sealed([_state("c1", "child wording")], [], [], question_hash="parent-hash-abc")
        child = hc.build_child_sealed_ledger(sealed, "c1")
        self.assertEqual(child["request_contract"]["question_hash"], hc.sha256_text("child wording"))
        self.assertNotEqual(child["request_contract"]["question_hash"], "parent-hash-abc")
        self.assertEqual(child["request_contract"]["parent_question_hash"], "parent-hash-abc")
        self.assertEqual(child["request_contract"]["child_id"], "c1")

    def test_plural_anchor_evidence_spans_are_fully_included_not_just_the_primary(self):
        """Stage A interop: a continuation-joined proposition's evidence_spans include every anchor's
        own row (per Stage A's stages.py::_evidence_span_rows); the child filter must keep all of them,
        not just the primary anchor's."""
        anchors = [
            {"kind": "continuation", "chunk_id": 10, "span_id": "e1a", "text": "part one"},
            {"kind": "continuation", "chunk_id": 11, "span_id": "e1b", "text": "part two"},
        ]
        sealed = _sealed(
            [_state("c1", "q1")],
            [
                _prop(
                    "p1",
                    paper_id=1,
                    chunk_id=10,
                    span_id="e1",
                    quote="part one part two",
                    responsive_to=["c1"],
                    anchors=anchors,
                )
            ],  # fmt: skip
            [_span(1, 10, "e1", "part one part two"), _span(1, 10, "e1a", "part one"), _span(1, 11, "e1b", "part two")],
        )
        child = hc.build_child_sealed_ledger(sealed, "c1")
        self.assertEqual({s["span_id"] for s in child["evidence_spans"]}, {"e1a", "e1b"})
        self.assertEqual({s["chunk_id"] for s in child["evidence_spans"]}, {10, 11})

    def test_unknown_child_id_raises(self):
        sealed = _sealed([_state("c1", "q1")], [], [])
        with self.assertRaises(ValueError):
            hc.build_child_sealed_ledger(sealed, "c99")

    def test_a_proposition_with_no_responsive_obligation_ids_is_excluded_everywhere(self):
        sealed = _sealed(
            [_state("c1", "q1")],
            [_prop("p1", paper_id=1, chunk_id=10, span_id="e1", quote="unattached", responsive_to=[])],
            [_span(1, 10, "e1", "unattached")],
        )
        child = hc.build_child_sealed_ledger(sealed, "c1")
        self.assertEqual(child["verified_propositions"], [])


if __name__ == "__main__":
    unittest.main()
