"""Phase 26: the minimal deterministic re-derivation audit for the parent-synthesis construction
record. Mirrors ``overview_audit.py``'s own "re-derive and compare, never crash" discipline."""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import parent_synthesis_audit as psa
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr
from experiments.ask_cli_revised import parent_synthesis_test_support as pst
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt


def _built():
    sealed = pst.sealed_with(("p1", 1, "the amygdala", ["x"]))
    specs = {"region": pst.spec("region", "a named region")}
    completion = se.new_role_completion(required_roles=["region"])
    req = pst.requirement(
        "x#req", specs, completion, "exists", [pst.instance({"region": pst.filled("region", "p1", "the amygdala")})]
    )
    smf = pst.map_with("x", req)
    claims = psl.build_claim_ledger(smf, sealed)
    gaps = psl.build_gap_report({})
    record = psr.construction_record(
        claims, gaps, sealed_hash="h-sealed", sufficiency_map_hash=psl.sufficiency_map_hash(smf)
    )
    return sealed, smf, record


class AuditTests(unittest.TestCase):
    def test_a_correctly_built_record_passes(self):
        sealed, smf, record = _built()
        result = psa.audit_parent_synthesis(smf, sealed, {}, record)
        self.assertTrue(result["ok"])
        self.assertEqual(result["problems"], [])

    def test_a_tampered_claim_ledger_fails(self):
        sealed, smf, record = _built()
        tampered = {**record, "claim_ledger": []}
        result = psa.audit_parent_synthesis(smf, sealed, {}, tampered)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["claim_ledger_matches_rederivation"])

    def test_a_tampered_gap_report_fails(self):
        sealed, smf, record = _built()
        t = srt.new_recovery_target(
            search_child_id="x",
            trigger_child_id="x",
            requirement_id="x#req",
            target_roles=["a"],
            reason="missing",
            goal_mode="single_role",
            scope={"kind": "none"},
            category_descriptions=["cat"],
        )
        tampered = {
            **record,
            "gap_report": [
                {
                    "target_id": t["target_id"],
                    "search_child_id": "x",
                    "requirement_id": "x#req",
                    "target_roles": ["a"],
                    "reason": "missing",
                    "goal_mode": "single_role",
                    "category_descriptions": ["cat"],
                }
            ],
        }
        result = psa.audit_parent_synthesis(smf, sealed, {}, tampered)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["gap_report_matches_rederivation"])

    def test_a_malformed_record_fails_the_audit_never_crashes_it(self):
        sealed, smf, _record = _built()
        malformed = {
            "claim_ledger": "not a list",
            "gap_report": [],
            "sealed_ledger_hash": "x",
            "sufficiency_map_final_hash": "y",
            "parent_synthesis_hash": "z",
        }
        result = psa.audit_parent_synthesis(smf, sealed, {}, malformed)
        self.assertFalse(result["ok"])

    def test_hash_mismatch_is_detected(self):
        sealed, smf, record = _built()
        tampered = {**record, "parent_synthesis_hash": "wrong"}
        result = psa.audit_parent_synthesis(smf, sealed, {}, tampered)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["parent_synthesis_hash_matches_content"])


if __name__ == "__main__":
    unittest.main()
