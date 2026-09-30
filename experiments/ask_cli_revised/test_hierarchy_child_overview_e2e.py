"""Stage B (child Overview, 2026-09-29 authorization): e2e.execute()'s per-child Overview loop,
end to end through the real frozen hierarchy, scripted clients, no live model.

Reuses the established hierarchy/overview test infrastructure as building blocks (ArtifactCopy,
HierHarness, OverviewClient, Entail, CHILD_IDS) rather than reinventing a fake contract -- a
hand-built hierarchical contract would need to satisfy hierarchy_contract.assert_executable's many
structural checks, which the real frozen artifacts already do, by construction, via the same load
path every other hierarchy E2E test in this codebase uses.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import hierarchy_contract as hc
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
from experiments.ask_cli_revised.overview_test_support import Entail, OverviewClient, OverviewHarness
from experiments.ask_cli_revised.overview_test_support import record as overview_record
from experiments.ask_cli_revised.test_e2e_run import c_supports, rec

# A real, terminal-punctuated, non-fragment passage -- overview_evidence.eligibility() rejects a
# quote shaped like test_e2e_run.rec()'s own placeholder ("QUOTE {chunk}") as a truncated fragment,
# which is correct behavior for that helper's actual purpose (plain orchestration tests that never
# reach the S stage); a real Overview-stage test needs a passage eligibility genuinely accepts.
C1_PASSAGE = (7, 101, "e1", "The insular cortex showed greater activation for anomalous faces than for typical faces.")  # fmt: skip
C1_CLAIM = "brain finding for c1"


def _part_ids(schema: dict) -> list[str]:
    """The child_id(s) an S-role call's schema names via `bears_on`'s enum (schema_overview's own
    part_ids parameter) -- a per-child call's schema always names exactly one, since
    build_child_sealed_ledger filters obligation_states to that one child. `unit_ids`'s own enum
    names ELIGIBLE UNITS ("U1", ...), a different thing -- not what this needs."""
    return schema["properties"]["overview"]["items"]["properties"]["bears_on"]["items"]["enum"]


@needs_artifacts
class ChildOverviewLoopE2ETests(unittest.TestCase):
    """A hierarchical run with evidence given to exactly one child (c1). Every other child stays
    honestly no_eligible_evidence, reached with zero model calls for those children."""

    def setUp(self):
        self.artifacts = ArtifactCopy()
        self.addCleanup(self.artifacts.close)
        self.contract = self.artifacts.load()
        self.c1_wording = next(
            sq["obligations"][0]["note"]
            for sq in hc.hierarchy_subquestions(self.contract)
            if sq["subquestion_id"] == "c1"
        )

    def _harness(self, *, s_answers: dict[str, dict | None]):
        harness = HierHarness(
            topo.CHILD_OVERVIEW_PROFILES["T5C"],
            self.contract,
            initial=[overview_record(C1_CLAIM, C1_PASSAGE, sid="c1")],
            clients={
                "isolated": OverviewClient(
                    r=r_by_claim({C1_CLAIM: ["c1"]}),
                    c=c_supports_children({"c1": "p1"}),
                    p=p_preserve,
                    s=lambda prompt, schema: s_answers.get(_part_ids(schema)[0]),
                )
            },
        )
        self.addCleanup(harness.close)
        return harness

    def test_only_the_child_with_evidence_triggers_a_real_s_role_call(self):
        harness = self._harness(s_answers={"c1": {"overview": [{"unit_ids": ["U1"], "bears_on": [], "text": "c1's finding"}]}})  # fmt: skip
        harness.run(entail=Entail())
        s_calls = [c for c in harness.clients["isolated"].calls if c["kind"] == "S"]
        self.assertEqual(len(s_calls), 1)  # only c1 had eligible evidence
        self.assertEqual(_part_ids(s_calls[0]["schema"]), ["c1"])

    def test_no_other_childs_id_or_the_parent_question_leaks_into_c1s_prompt(self):
        harness = self._harness(s_answers={"c1": None})
        harness.run(entail=Entail())
        s_call = next(c for c in harness.clients["isolated"].calls if c["kind"] == "S")
        self.assertNotIn(self.contract["original_question"], s_call["prompt"])
        for other in set(CHILD_IDS) - {"c1"}:
            self.assertNotIn(other, s_call["prompt"])

    def test_the_childs_own_wording_is_in_the_prompt_not_the_parent_question(self):
        harness = self._harness(s_answers={"c1": None})
        harness.run(entail=Entail())
        s_call = next(c for c in harness.clients["isolated"].calls if c["kind"] == "S")
        self.assertIn(self.c1_wording, s_call["prompt"])

    def test_child_overview_manifest_covers_every_child_including_those_with_no_evidence(self):
        harness = self._harness(s_answers={"c1": None})
        result = harness.run(entail=Entail())
        manifest = result["child_overview_manifest"]
        self.assertIsNotNone(manifest)
        self.assertEqual(set(manifest), set(CHILD_IDS))
        # A scripted answer of None -> OverviewClient returns empty content, done_reason="length" -> a
        # MECHANICAL failure (no usable structured answer), distinct from a model genuinely answering
        # with an empty overview list (which would be "model_returned_empty").
        self.assertEqual(manifest["c1"]["state"], "model_no_answer")
        for other in set(CHILD_IDS) - {"c1"}:
            self.assertEqual(manifest[other]["state"], "no_eligible_evidence")
            self.assertEqual(manifest[other]["record_file"], f"14a_overview.{other}.json")

    def test_a_child_with_evidence_gets_a_grounded_overview_when_the_model_answers(self):
        # Deterministic screening (overview_guards.screen) checks vocabulary overlap against the
        # cited passage -- a restatement, not an arbitrary string, matching the eligible C1_PASSAGE.
        statement = "The insular cortex showed greater activation for anomalous faces."
        harness = self._harness(
            s_answers={"c1": {"overview": [{"unit_ids": ["U1"], "bears_on": ["c1"], "text": statement}]}}
        )
        result = harness.run(entail=Entail())
        manifest = result["child_overview_manifest"]
        self.assertEqual(manifest["c1"]["state"], "ok")
        answer_text = (harness.trace.dir / manifest["c1"]["answer_file"]).read_text(encoding="utf-8")
        # _literal markdown-escapes the trailing period (\.) -- check the substring before it.
        self.assertIn(statement.rstrip("."), answer_text)

    def test_the_footer_names_the_real_per_child_detail_and_record_files_not_the_generic_ones(self):
        """Release-readiness item 2 (2026-09-29): the footer must name the file that actually
        exists on disk for this child, not overview_render's generic default."""
        harness = self._harness(
            s_answers={"c1": {"overview": [{"unit_ids": ["U1"], "bears_on": ["c1"], "text": "irrelevant"}]}}
        )
        result = harness.run(entail=Entail())
        manifest = result["child_overview_manifest"]
        answer_text = (harness.trace.dir / manifest["c1"]["answer_file"]).read_text(encoding="utf-8")
        self.assertIn(manifest["c1"]["detail_file"], answer_text)
        self.assertIn(manifest["c1"]["record_file"], answer_text)
        self.assertNotIn("`14b_detailed_inspection.md`", answer_text)  # the generic, wrong-for-this-child name
        self.assertNotIn("`14a_overview.json`", answer_text)

    def test_every_child_gets_its_own_trace_files(self):
        harness = self._harness(s_answers={"c1": None})
        harness.run(entail=Entail())
        for child_id in CHILD_IDS:
            self.assertTrue((harness.trace.dir / f"14a_overview.{child_id}.json").is_file())
            self.assertTrue((harness.trace.dir / f"14_final_answer.{child_id}.md").is_file())
            self.assertTrue((harness.trace.dir / f"14b_detailed_inspection.{child_id}.md").is_file())

    def test_no_parent_level_meta_synthesis_the_flat_whole_ledger_call_never_happens(self):
        """The flat call site (a single overview.build_overview over the whole 11-child ledger) is
        never reached for a hierarchical contract -- only the per-child loop runs."""
        harness = self._harness(s_answers={"c1": None})
        result = harness.run(entail=Entail())
        self.assertIsNone(result["overview"])  # the flat overview_record stays None


class FlatRunUnaffectedTests(unittest.TestCase):
    """The pre-existing, non-hierarchical S-stage path (T5O, flat CONTRACT) is completely
    untouched by Stage B: child_overview_manifest stays None, and the single flat overview_record
    behaves exactly as before."""

    def test_child_overview_manifest_is_none_for_a_flat_run(self):
        field_id = "s1-o1"
        harness = OverviewHarness(
            topo.OVERVIEW_PROFILES["T5O"],
            initial=[rec(field_id, "a flat finding", chunk=1)],
            clients={
                "isolated": OverviewClient(
                    r=r_by_claim({"a flat finding": []}),
                    c=c_supports({}),
                    p=p_preserve,
                    s=lambda prompt, schema: {"overview": []},
                )
            },
        )
        self.addCleanup(harness.close)
        result = harness.run(entail=Entail())
        self.assertIsNone(result["child_overview_manifest"])
        self.assertIsNotNone(result["overview"])  # the existing flat path still produces one record


if __name__ == "__main__":
    unittest.main()
