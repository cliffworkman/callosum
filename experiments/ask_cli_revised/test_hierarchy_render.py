"""The researcher-facing answer for a hierarchical run: contract blocks and a structural reconciliation, never a verdict.

Four things are kept apart everywhere: representation accounted for; child-level responsiveness assessed; individual
obligation fulfilment NOT assessed; parent answer completeness NOT certified. The flat renderer output is unchanged
(pinned by ``test_flat_path_golden``).
"""

import re
import unittest

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.hierarchy_test_support import (
    HierHarness,
    ScriptedClient,
    needs_artifacts,
    r_by_claim,
    rec,
)
from experiments.ask_cli_revised.ledger_renderer import _literal, audit_final, render_answer
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

CLAIM_C5 = "Amygdala activity was associated with the bias in one sample."
CLAIM_C4 = "A region-of-interest analysis found no association between any area and the bias."
INITIAL = [rec("c5", CLAIM_C5, chunk=11), rec("c4", CLAIM_C4, chunk=12)]
VERDICT_WORDS = re.compile(r"\b(?:fulfilled|answered|unanswered|satisfied|covered|complete)\b", re.IGNORECASE)


def section(text: str, heading: str) -> str:
    return text.split(heading, 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]


@needs_artifacts
class HierarchicalRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)

    def rendered(self, mapping):
        h = HierHarness(
            topo.WAVE1["T0"],
            self.contract,
            initial=INITIAL,
            recovery=[],
            clients={"shared": ScriptedClient(r=r_by_claim(mapping))},
        )
        self.addCleanup(h.close)
        result = h.run()
        text, manifest = render_answer(result["sealed"])
        return result, text, manifest

    def test_nested_children_are_headed_with_their_parent_and_top_level_ones_are_not(self):
        _, text, _ = self.rendered({})
        for nested, parent in (("c5", "c4"), ("c6", "c4"), ("c9", "c8"), ("c11", "c10")):
            self.assertIn(f"### {nested} (nested under {parent}): ", text)
        for top in ("c1", "c4", "c8", "c10", "c12"):
            self.assertIn(f"### {top}: ", text)

    def test_every_item_shows_its_contract_block_and_the_item_level_disclaimer(self):
        _, text, _ = self.rendered({})
        self.assertEqual(
            text.count("Contract for this item (a record of what was asked and approved; it is not evidence):"), 11
        )
        self.assertEqual(text.count(hc.ITEM_DISCLAIMER), 11)

    def test_a_contract_block_lists_owned_obligations_as_representation_only(self):
        _, text, _ = self.rendered({})
        block = section(text, "### c11 (nested under c10)")
        self.assertIn("Owned obligations (representation only):", block)
        self.assertIn("M12 which cultures", block)
        self.assertIn("M13 how was this measures", block)
        self.assertNotIn("M11", block)  # c10 owns the existence question

    def test_c11_shows_the_scope_it_carried_and_the_recorded_text_it_did_not_show_to_the_models(self):
        _, text, _ = self.rendered({})
        block = section(text, "### c11 (nested under c10)")
        self.assertIn(_literal("is there any cross-cultural evidence for the anomalous is bad bias?"), block)
        plain = block.replace("\\", "")
        self.assertIn("Scope carried into retrieval and assessment (from c10)", plain)
        self.assertIn("Recorded, not shown to the models", plain)
        self.assertIn("c11#retained-scope:cross-cultural-evidence", plain)
        self.assertIn("Wording provenance: deterministic_scaffold; execution: researcher_approved (CD-3)", plain)

    def test_c9_shows_its_recorded_constraint_as_not_shown_with_the_reason(self):
        _, text, _ = self.rendered({})
        block = section(text, "### c9 (nested under c8)").replace("\\", "")
        self.assertIn("Recorded, not shown to the models", block)
        self.assertIn("c9#constraint:no-reask-traits", block)
        self.assertIn("provenance token", block)
        self.assertNotIn("Constraints shown to the models", block)

    def test_c4_lists_the_constraints_the_models_were_shown(self):
        _, text, _ = self.rendered({})
        block = section(text, "### c4: ").replace("\\", "")
        self.assertIn("Constraints shown to the models", block)
        self.assertIn("a downstream answer that finds no supported area must be able to say so", block)

    def test_c5_and_c6_record_the_human_review_meanings_as_not_operationalized_and_networks_as_superseded(self):
        _, text, _ = self.rendered({})
        for cid, parent, meaning in (
            ("c5", "c4", "measures of behavior"),
            ("c6", "c4", "measures of implicit and explicit attitudes"),
        ):
            block = section(text, f"### {cid} (nested under {parent})").replace("\\", "")
            self.assertIn("Recorded human-review meaning", block)
            self.assertIn(meaning, block)
            self.assertIn("documented nature or direction", block)
            self.assertIn(hc.HUMAN_REVIEW_NOTE.replace("\\", ""), block)
            self.assertIn("Superseded", block)
            self.assertIn("not asked by this run", block)
            self.assertIn("it does not presuppose that an association exists, has a direction, or is causal", block)

    def test_the_reconciliation_section_is_structural_and_states_each_label_exactly(self):
        _, text, _ = self.rendered({CLAIM_C5: ["c5"]})
        recon = section(text, "## Parent reconciliation (structural; no verdict)")
        self.assertIn("Representation: accounted", recon)
        self.assertIn("24 of 24 obligations", recon)
        self.assertIn("Child-level responsiveness: assessed per item above", recon)
        self.assertIn("Individual obligation fulfilment: NOT assessed by this run.", recon)
        self.assertIn("Parent answer completeness: NOT certified.", recon)
        self.assertEqual(recon.count("| not_assessed |"), 24)
        self.assertIsNone(VERDICT_WORDS.search(recon), VERDICT_WORDS.findall(recon))

    def test_the_report_says_once_that_omitting_the_human_review_meanings_from_the_prompts_is_not_a_finding(self):
        _, text, _ = self.rendered({})
        recon = section(text, "## Parent reconciliation (structural; no verdict)")
        self.assertIn(hc.HUMAN_REVIEW_STATEMENT, recon)
        self.assertEqual(text.count(hc.HUMAN_REVIEW_STATEMENT), 1)
        self.assertIsNone(VERDICT_WORDS.search(hc.HUMAN_REVIEW_STATEMENT))
        for claim in ("repeal", "not a finding", "not evidence"):
            self.assertIn(claim, hc.HUMAN_REVIEW_STATEMENT)

    def test_a_responsive_child_never_makes_an_individual_obligation_fulfilled(self):
        _, text, _ = self.rendered({CLAIM_C5: ["c5"]})
        recon = section(text, "## Parent reconciliation (structural; no verdict)")
        rows = [line for line in recon.splitlines() if line.startswith("| M5 ") or line.startswith("| M6 ")]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIn("| c5 | judged_responsive | not_assessed |", row)

    def test_parent_rows_show_their_own_item_and_their_subordinates_without_a_verdict(self):
        _, text, _ = self.rendered({CLAIM_C5: ["c5"]})
        recon = section(text, "## Parent reconciliation (structural; no verdict)")
        self.assertIn(
            "c4: own item no_responsive_claim; subordinate items c5 judged_responsive, c6 no_responsive_claim; parent completeness not_certified",
            recon,
        )
        self.assertIn("Background (never asked): S1", recon)
        self.assertIn("never closes its parent", recon)

    def test_the_reconciliation_precedes_the_existing_completeness_section_and_the_scope_statement_survives(self):
        _, text, _ = self.rendered({})
        self.assertLess(
            text.index("## Parent reconciliation (structural; no verdict)"),
            text.index("## Completeness remains unresolved"),
        )
        self.assertIn("makes no statement about what the library or the literature holds", text)

    def test_the_hierarchical_answer_is_deterministic_and_conforms_to_its_renderer(self):
        result, text, _ = self.rendered({CLAIM_C5: ["c5"]})
        again, _ = render_answer(result["sealed"])
        self.assertEqual(text, again)
        audit = audit_final(result["sealed"], text)
        self.assertTrue(audit["constrained_render_match"])
        self.assertEqual(audit["nonexistent_ids"], [])


if __name__ == "__main__":
    unittest.main()
