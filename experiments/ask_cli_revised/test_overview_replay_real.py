"""Offline replay of the DETERMINISTIC overview layer over the real recorded q_aib ledger. No model, no network, read-only.

Set E2E_SCORED_LEDGER to the path of a sealed ``11_verified_ledger.json`` (the hierarchical T5* run). Without it these tests skip.
They assert counts, flags and reason codes only, so no library text is copied into the repository. The point is to show, on the
evidence the real run actually produced, what the eligibility layer keeps, what it excludes and why, and which claims added
words their passage does not contain.
"""

import json
import os
import re
import unittest
from pathlib import Path

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised import overview_audit as audit
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised.hierarchy_contract import provenance_tokens

_PATH = os.environ.get("E2E_SCORED_LEDGER")
needs_ledger = unittest.skipUnless(
    _PATH and Path(_PATH).is_file(), "E2E_SCORED_LEDGER (a recorded sealed ledger) is not set"
)


@needs_ledger
class RealLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(Path(_PATH).read_text(encoding="utf-8"))
        cls.sealed = {k: v for k, v in cls.raw.items() if k != "sealed_hash"}
        cls.units, cls.claims = oe.build_units(cls.sealed)
        cls.by_id = {u["unit_id"]: u for u in cls.units}

    def test_my_hash_of_the_sealed_ledger_reproduces_the_hash_the_live_run_recorded(self):
        self.assertEqual(audit.sealed_hash_of(self.sealed), self.raw["sealed_hash"])

    def test_24_claims_rest_on_10_distinct_passages(self):
        self.assertEqual((len(self.claims), len(self.units)), (24, 10))
        # claims per passage, U1..U10: one passage is restated five times, and that is not five findings
        self.assertEqual([len(u["proposition_ids"]) for u in self.units], [5, 2, 4, 2, 3, 2, 3, 1, 1, 1])

    def test_seven_passages_are_eligible_and_each_exclusion_has_its_reason(self):
        eligible = [u["unit_id"] for u in self.units if u["eligibility"]["eligible"]]
        self.assertEqual(eligible, ["U1", "U2", "U3", "U5", "U6", "U7", "U8"])
        reasons = {u["unit_id"]: u["eligibility"]["reasons"] for u in self.units if not u["eligibility"]["eligible"]}
        self.assertEqual(
            reasons,
            {
                "U4": ["study_description_only"],  # "this study characterized relations..." states no finding
                "U9": ["truncated_passage"],  # cut off mid-sentence: a qualification may be missing
                "U10": ["no_coverage_attachment", "truncated_passage", "absence_statement"],
            },
        )

    def test_the_hedged_and_null_passages_are_flagged_so_the_screen_can_keep_the_hedge_and_the_null(self):
        flags = {u["unit_id"]: u["flags"] for u in self.units}
        self.assertTrue(flags["U5"]["hedged"] and flags["U6"]["hedged"])
        self.assertTrue(flags["U8"]["negated"])
        self.assertTrue(flags["U9"]["fragment"] and flags["U9"]["hedged"])

    def test_the_claim_that_invented_a_direction_and_a_population_is_flagged(self):
        novel = {c["proposition_id"]: c["novel_terms"] for c in self.claims}
        self.assertEqual(novel["p4"], ["reduced"])  # its passage states no direction at all
        self.assertIn("anomalous", novel["p9"])  # p9 replaced its passage's subject with another
        self.assertEqual(novel["p1"], [])

    def test_every_claim_is_dispositioned_and_the_original_ledger_is_untouched(self):
        self.assertEqual({c["unit_id"] for c in self.claims}, set(self.by_id))
        self.assertNotIn("overview", self.sealed)
        self.assertEqual(len(self.sealed["verified_propositions"]), 24)

    def test_the_real_prompt_fits_the_cap_and_carries_no_hierarchy_provenance_as_wording(self):
        states = self.sealed["obligation_states"]
        sent, prompt = ov.select_for_prompt(
            self.units, self.claims, self.sealed["request_contract"]["original_question"], states
        )
        self.assertEqual(sent, ["U1", "U2", "U3", "U5", "U6", "U7", "U8"])
        self.assertLessEqual(len(prompt), ov.MAX_PROMPT_CHARS)
        self.assertLess(len(prompt) / 3.0, 5000)
        wording = re.sub(r"(?m)^- \S+: ", "- ", prompt)
        wording = re.sub(r"(?m)^\[U\d+\] ", "[passage] ", wording)
        wording = re.sub(r"(?m)^- p\d+: ", "- claim: ", wording)
        self.assertEqual(provenance_tokens(wording), [])
        for excluded in ("U4", "U9", "U10"):
            self.assertNotIn(self.by_id[excluded]["passage"], prompt)  # never sent

    def test_attachments_are_the_coverage_authoritys_and_the_c9_c11_parts_have_none(self):
        attached = {c for u in self.units for c in u["attached_children"]}
        self.assertNotIn("c9", attached)
        self.assertNotIn("c11", attached)
        self.assertEqual(
            self.by_id["U2"]["attached_children"], ["c1", "c4"]
        )  # the amygdala passage was attached to c1 and c4 only


if __name__ == "__main__":
    unittest.main()
