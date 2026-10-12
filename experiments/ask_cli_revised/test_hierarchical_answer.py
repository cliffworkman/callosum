"""The reader-facing hierarchical answer: narrative parent overview, then every approved subquestion in order.

Pure renderer/view tests on literal records, then the real ``e2e.execute`` path through the frozen hierarchy
with scripted clients (no live model, no network).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from experiments.ask_cli_revised import e2e
from experiments.ask_cli_revised import hierarchical_answer as ha
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.hierarchy_test_support import (
    CHILD_IDS,
    ArtifactCopy,
    HierHarness,
    c_supports_children,
    needs_artifacts,
    p_preserve,
    r_by_claim,
)
from experiments.ask_cli_revised.overview_test_support import Entail, OverviewClient
from experiments.ask_cli_revised.overview_test_support import record as overview_record
from experiments.ask_cli_revised.test_hierarchy_child_overview_e2e import C1_CLAIM, C1_PASSAGE, _part_ids

CHILD_STATEMENT = "The insular cortex showed greater activation for anomalous faces."
PARENT_STATEMENT = "For anomalous faces the insular cortex showed greater activation than for typical faces."


def _unit(uid, number, paper, passage, pids, sent=True):
    return {
        "unit_id": uid,
        "number": number,
        "paper_id": paper,
        "passage": passage,
        "proposition_ids": pids,
        "locators": [{"chunk_id": 100 + number, "span_id": "e1"}],
        "verification": {"page_start": 4, "retrieval": 0.8, "quote": 1.0, "support": 0.9, "contradiction": 0.01},
        "flags": {},
        "eligibility": {"eligible": True, "reasons": []},
        "sent_to_model": sent,
        "not_sent_reason": None if sent else "omitted_by_prompt_cap",
    }


def _record(state, units, items=(), proposals=None):
    items = [
        {"sentence_id": f"o{n}", "text": text, "unit_ids": uids, "proposition_ids": pids, "bears_on": []}
        for n, (text, uids, pids) in enumerate(items, start=1)
    ]
    proposals = proposals if proposals is not None else [{"text": i["text"], "status": "grounded"} for i in items]
    return {
        "state": state,
        "reason_code": None,
        "units": units,
        "items": items,
        "proposals": proposals,
        "displayed": [n for n, p in enumerate(proposals) if p["status"] == "grounded"],
        "overview_hash": "h",
        "sealed_ledger_hash": "s",
    }


SUBS = [{"subquestion_id": "c1", "text": "MODEL-FACING c1"}, {"subquestion_id": "c2", "text": "MODEL-FACING c2"}]
WORDINGS = {"c1": "how does it manifest in brain", "c2": "is there cross-cultural evidence"}
FILES = {
    c: {"answer_file": f"14_final_answer.{c}.md", "detail_file": f"14b_detailed_inspection.{c}.md"} for c in WORDINGS
}
PASSAGE = "The amygdala responded to facial anomalies."


def _render(parent, children, gaps=None):
    return ha.render(
        question="the request",
        subquestions=SUBS,
        child_records=children,
        child_files=FILES,
        wordings=WORDINGS,
        parent_record=parent,
        gap_report=gaps,
        paper_labels={7: "A paper (2021)"},
    )


class ParentViewTests(unittest.TestCase):
    def test_only_passages_cited_by_displayed_child_statements_are_offered(self):
        sealed = {
            "request_contract": {"original_question": "q", "question_hash": "qh"},
            "obligation_states": [
                {"field_id": "c1", "note": "w1", "proposition_ids": ["p1", "p2"]},
                {"field_id": "c2", "note": "w2", "proposition_ids": ["p3"]},
            ],
            "verified_propositions": [
                {"proposition_id": p, "paper_id": 7, "evidence_anchor_chunk_id": n, "evidence_span_id": "e1"}
                for n, p in enumerate(["p1", "p2", "p3"], start=1)
            ],
            "evidence_spans": [{"paper_id": 7, "chunk_id": n, "span_id": "e1", "text": "t"} for n in (1, 2, 3)],
        }
        children = {
            "c1": _record("ok", [], [("s", ["U1"], ["p1"])]),
            "c2": _record("no_grounded_sentences", [], proposals=[{"text": "withheld", "status": "withheld"}]),
        }
        view = ha.parent_view(sealed, children)
        self.assertEqual([r["proposition_id"] for r in view["verified_propositions"]], ["p1"])
        self.assertEqual([s["chunk_id"] for s in view["evidence_spans"]], [1])
        # every approved child stays a request part; none names a claim the view does not hold
        self.assertEqual([s["field_id"] for s in view["obligation_states"]], ["c1", "c2"])
        self.assertEqual([s["proposition_ids"] for s in view["obligation_states"]], [["p1"], []])
        self.assertEqual(view["request_contract"]["original_question"], "q")


class RenderTests(unittest.TestCase):
    def setUp(self):
        unit = _unit("U1", 1, 7, PASSAGE, ["p1"])
        self.parent = _record("ok", [unit], [("Parent sentence one.", ["U1"], ["p1"])])
        self.children = {
            "c1": _record("ok", [unit], [("Child sentence.", ["U1"], ["p1"])]),
            "c2": _record("no_eligible_evidence", []),
        }

    def test_overview_then_every_subquestion_in_approved_order_with_exact_wording(self):
        answer, evidence, manifest = _render(self.parent, self.children)
        overview, first, second = (answer.index(h) for h in ("## Overview", "## 1. how does it", "## 2. is there"))
        self.assertTrue(overview < first < second)
        self.assertNotIn("MODEL-FACING", answer)
        self.assertEqual([c["child_id"] for c in manifest["children"]], ["c1", "c2"])
        self.assertEqual(ha.audit(answer, SUBS, WORDINGS, self.children, self.parent), [])

    def test_one_passage_keeps_one_citation_number_across_parent_and_child(self):
        answer, evidence, manifest = _render(self.parent, self.children)
        self.assertIn("Parent sentence one\\. [1]", answer)
        self.assertIn("Child sentence\\. [1]", answer)
        self.assertIn("[1] A paper \\(2021\\) (paper 7), p. 4", answer)
        self.assertEqual(len(manifest["sources"]), 1)
        # the quotation lives in the evidence companion, not in the primary narrative
        self.assertNotIn(PASSAGE.rstrip("."), answer)
        self.assertIn(PASSAGE.rstrip("."), evidence)

    def test_a_subquestion_without_a_grounded_statement_is_kept_and_says_so(self):
        answer, _, manifest = _render(self.parent, self.children)
        section = answer.split("## 2. is there cross\\-cultural evidence")[1].split("## Sources")[0]
        self.assertIn("No overview was produced: no retrieved passage was eligible", section)
        self.assertEqual(manifest["children"][1]["state"], "no_eligible_evidence")
        self.assertIn('"is there cross\\-cultural evidence"', answer.split("## 1.")[0])

    def test_open_requirements_are_listed_under_their_own_subquestion(self):
        gaps = [{"search_child_id": "c2", "reason": "missing", "category_descriptions": ["a named culture"]}]
        answer, _, _ = _render(self.parent, self.children, gaps)
        section = answer.split("## 2.")[1]
        self.assertIn("- a named culture: not established in the retrieved evidence.", section)
        self.assertNotIn("a named culture", answer.split("## 2.")[0].split("## 1.")[1])

    def test_a_withheld_parent_overview_is_stated_never_replaced_by_a_claim_list(self):
        parent = _record("no_grounded_sentences", [], proposals=[{"text": "Unsupported leap.", "status": "withheld"}])
        answer, _, manifest = _render(parent, self.children)
        head = answer.split("## 1.")[0]
        self.assertNotIn("Unsupported leap", answer)
        self.assertIn("_", head.split("## Overview")[1])
        self.assertEqual(manifest["parent_overview"]["statements"], [])
        self.assertEqual(ha.audit(answer, SUBS, WORDINGS, self.children, parent), [])

    def test_audit_catches_a_missing_subquestion_and_a_leaked_withheld_statement(self):
        answer, _, _ = _render(self.parent, self.children)
        broken = answer.replace("## 2. is there", "## 9. is there")
        self.assertTrue(any("c2" in p for p in ha.audit(broken, SUBS, WORDINGS, self.children, self.parent)))
        children = {**self.children, "c2": _record("no_grounded_sentences", [], proposals=[{"text": "Leaked text here.", "status": "withheld"}])}  # fmt: skip
        leaked = answer + "\nLeaked text here\\.\n"
        self.assertTrue(any("withheld" in p for p in ha.audit(leaked, SUBS, WORDINGS, children, self.parent)))


@needs_artifacts
class HierarchicalAnswerE2ETests(unittest.TestCase):
    """The real execute() path: child synthesis for c1, then one parent-overview S call over c1's cited passage."""

    def setUp(self):
        self.artifacts = ArtifactCopy()
        self.addCleanup(self.artifacts.close)
        self.contract = self.artifacts.load()

    def _run(self, *, parent_answer, enabled=True):
        def s(prompt, schema):
            parts = _part_ids(schema)
            if len(parts) > 1:  # the parent overview names every approved child as a request part
                return parent_answer
            return {"overview": [{"unit_ids": ["U1"], "bears_on": ["c1"], "text": CHILD_STATEMENT}]}

        harness = HierHarness(
            topo.CHILD_OVERVIEW_PROFILES["T5C"],
            self.contract,
            initial=[overview_record(C1_CLAIM, C1_PASSAGE, sid="c1")],
            clients={
                "isolated": OverviewClient(
                    r=r_by_claim({C1_CLAIM: ["c1"]}), c=c_supports_children({"c1": "p1"}), p=p_preserve, s=s
                )
            },
        )
        self.addCleanup(harness.close)
        with patch.object(e2e, "_paper_labels", lambda rt, ids: {}):
            result = harness.run(entail=Entail(), parent_narrative_enabled=enabled)
        return harness, result

    def test_off_by_default_no_parent_call_and_no_new_artifact(self):
        harness, result = self._run(parent_answer=None, enabled=False)
        self.assertNotIn("hierarchical_answer", result)
        self.assertFalse((harness.trace.dir / ha.ANSWER_FILE).exists())
        s_calls = [c for c in harness.clients["isolated"].calls if c["kind"] == "S"]
        self.assertEqual(len(s_calls), 1)

    def test_the_document_has_the_parent_overview_and_all_eleven_subquestions(self):
        harness, result = self._run(
            parent_answer={"overview": [{"unit_ids": ["U1"], "bears_on": ["c1"], "text": PARENT_STATEMENT}]}
        )
        manifest = result["hierarchical_answer"]["manifest"]
        self.assertEqual(manifest["problems"], [])
        self.assertEqual(manifest["parent_overview"]["state"], "ok")
        self.assertEqual([c["child_id"] for c in manifest["children"]], CHILD_IDS)
        answer = (harness.trace.dir / ha.ANSWER_FILE).read_text(encoding="utf-8")
        self.assertIn(PARENT_STATEMENT.rstrip("."), answer.split("## 1.")[0])
        self.assertIn(CHILD_STATEMENT.rstrip("."), answer.split("## 1.")[1].split("## 2.")[0])
        self.assertEqual(answer.count("\n## "), 1 + len(CHILD_IDS) + 2)  # overview, children, sources, inspection
        s_calls = [c for c in harness.clients["isolated"].calls if c["kind"] == "S"]
        self.assertEqual(len(s_calls), 2)  # c1's synthesis and the parent overview; no other child had evidence
        self.assertEqual([s["stage"] for s in result["stage_log"] if s["stage"] == ha.STAGE_LABEL], [ha.STAGE_LABEL])
        for name in (ha.EVIDENCE_FILE, ha.RECORD_FILE, ha.PARENT_DETAIL_FILE, ha.MANIFEST_FILE):
            self.assertTrue((harness.trace.dir / name).exists(), name)

    def test_a_parent_statement_that_fails_screening_is_withheld_not_shown(self):
        harness, result = self._run(
            parent_answer={
                "overview": [{"unit_ids": ["U1"], "bears_on": ["c1"], "text": "Oxytocin therapy cures the bias."}]
            }
        )
        manifest = result["hierarchical_answer"]["manifest"]
        self.assertEqual(manifest["parent_overview"]["state"], "no_grounded_sentences")
        answer = (harness.trace.dir / ha.ANSWER_FILE).read_text(encoding="utf-8")
        self.assertNotIn("Oxytocin", answer)
        self.assertEqual(manifest["problems"], [])
        self.assertIn(CHILD_STATEMENT.rstrip("."), answer)  # the child synthesis is unaffected
