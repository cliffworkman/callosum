"""Phase 27b: the parent-side ResolvedEmptyOutcome -- projector, rendering, construction record, audit, and the frozen
Phase-23 replay (artifact-backed; skipped when the frozen run directory is absent).

The outcome is an epistemic/search statement, never a ParentClaim and never an UnresolvedGap. It is re-derived from
the final map and the persisted scoped-search status, and it never reaches the S2 realization prompt.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.ask_cli_revised import parent_synthesis_audit as psa
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised.test_sufficiency_empty_result_terminal import _map, _requirement

C4 = "c4#suff:specific-region"
# A sealed ledger with no verified propositions: a zero-claim run.
EMPTY_SEALED = {"verified_propositions": [], "evidence_spans": []}
RUN_DIR = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "phase23-live-recovery-targeted-u2-remap-validation-20261003T020939Z"
)
ARTIFACTS_PRESENT = (RUN_DIR / "phase23_result.json").exists() and (
    RUN_DIR / "run" / "11_verified_ledger.json"
).exists()


def _terminal(requirement_id, *, terminal=True, completed=True):
    return {requirement_id: {"completed": completed, "terminal": terminal, "target_states": {}}}


def _record(map_, status, *, outcomes=None):
    """A construction record built the way the pipeline builds it, for a zero-claim map."""
    return psr.construction_record(
        [],
        [],
        sealed_hash="sealed",
        sufficiency_map_hash=psl.sufficiency_map_hash(map_),
        resolved_empty_outcomes=psl.build_resolved_empty_outcomes(map_, status) if outcomes is None else outcomes,
        scoped_search_status=status,
    )


class ProjectorTests(unittest.TestCase):
    def test_a_completed_terminal_zero_evidence_requirement_projects_one_outcome(self):
        req = _requirement(allowed=True)
        outcomes = psl.build_resolved_empty_outcomes(_map(req), _terminal(req["id"]))
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(
            outcomes[0],
            {
                "child_id": "x",
                "requirement_id": req["id"],
                "category_descriptions": ["category named", "category bears"],
                "outcome": "searched_no_support_established",
            },
        )

    def test_the_status_alone_cannot_create_an_outcome_for_a_requirement_with_support(self):
        req = _requirement(allowed=True, filled=("named",))
        self.assertEqual(psl.build_resolved_empty_outcomes(_map(req), _terminal(req["id"])), [])

    def test_no_outcome_without_the_permission(self):
        req = _requirement(allowed=False)
        self.assertEqual(psl.build_resolved_empty_outcomes(_map(req), _terminal(req["id"])), [])

    def test_no_outcome_without_a_completed_search(self):
        req = _requirement(allowed=True)
        self.assertEqual(
            psl.build_resolved_empty_outcomes(_map(req), _terminal(req["id"], terminal=False, completed=False)), []
        )

    def test_a_status_marked_terminal_is_rechecked_against_the_map(self):
        """The projector never trusts the status flag alone: a requirement whose map is not zero-evidence terminal is
        dropped even if its status says terminal."""
        req = _requirement(allowed=True, ambiguous=("named",))
        self.assertEqual(psl.build_resolved_empty_outcomes(_map(req), _terminal(req["id"])), [])

    def test_order_is_deterministic_across_children(self):
        a = _requirement(allowed=True, req_id="a#req")
        b = _requirement(allowed=True, req_id="b#req")
        mapped = {"c2": se.new_contract("c2", [b]), "c1": se.new_contract("c1", [a])}
        status = {**_terminal("a#req"), **_terminal("b#req")}
        keys = [(o["child_id"], o["requirement_id"]) for o in psl.build_resolved_empty_outcomes(mapped, status)]
        self.assertEqual(keys, [("c1", "a#req"), ("c2", "b#req")])

    def test_the_outcome_is_never_a_parent_claim_or_a_gap(self):
        req = _requirement(allowed=True)
        map_ = _map(req)
        status = _terminal(req["id"])
        targets = srt.compute_recovery_targets(map_, {}, srt.engine_search_status(status))
        self.assertEqual(psl.build_gap_report(targets, sufficiency_map_final=map_), [])
        self.assertEqual(psl.build_claim_ledger(map_, EMPTY_SEALED), [])
        self.assertEqual(len(psl.build_resolved_empty_outcomes(map_, status)), 1)


class RenderTests(unittest.TestCase):
    def _resolved_outcome(self):
        return {
            "child_id": "x",
            "requirement_id": "x#req",
            "category_descriptions": ["a named area", "evidence that it bears on the bias"],
            "outcome": "searched_no_support_established",
        }

    def test_without_outcomes_the_answer_is_byte_identical_to_the_default(self):
        default = psr.render_answer([], [])
        self.assertEqual(psr.render_answer([], [], resolved_empty_outcomes=[]), default)
        self.assertNotIn("Searched, no supported result", default)

    def test_with_an_outcome_the_section_is_present_with_fixed_generic_wording(self):
        answer = psr.render_answer([], [], resolved_empty_outcomes=[self._resolved_outcome()])
        self.assertIn("## Searched, no supported result established", answer)
        self.assertIn(
            "- The scoped search completed without establishing a supported result for "
            "a named area; evidence that it bears on the bias.",
            answer,
        )

    def test_the_wording_never_asserts_absence_of_an_effect_or_of_the_literature(self):
        answer = psr.render_answer([], [], resolved_empty_outcomes=[self._resolved_outcome()]).lower()
        for forbidden in ("no such", "does not exist", "proves", "evidence of absence", "literature shows there is no"):
            self.assertNotIn(forbidden, answer)

    def test_the_section_sits_before_the_unresolved_parts(self):
        answer = psr.render_answer([], [], resolved_empty_outcomes=[self._resolved_outcome()])
        self.assertLess(
            answer.index("## Searched, no supported result established"), answer.index("## Unresolved parts")
        )


class ConstructionRecordTests(unittest.TestCase):
    def test_both_orthogonal_fields_are_always_present(self):
        record = psr.construction_record([], [], sealed_hash="s", sufficiency_map_hash="m")
        self.assertEqual(record["resolved_empty_outcomes"], [])
        self.assertEqual(record["scoped_search_status"], {})
        declined = psr.declined_record(reason="no_sufficiency_map", sealed_hash="s")
        self.assertEqual(declined["resolved_empty_outcomes"], [])
        self.assertEqual(declined["scoped_search_status"], {})

    def test_outcomes_never_enter_the_claim_ledger_or_the_gap_report(self):
        req = _requirement(allowed=True)
        map_ = _map(req)
        status = _terminal(req["id"])
        with_outcome = _record(map_, status)
        without = _record(map_, status, outcomes=[])
        self.assertEqual(with_outcome["claim_ledger"], without["claim_ledger"])
        self.assertEqual(with_outcome["gap_report"], without["gap_report"])
        self.assertNotEqual(with_outcome["parent_synthesis_hash"], without["parent_synthesis_hash"])

    def test_the_hash_covers_the_outcomes_and_the_status(self):
        req = _requirement(allowed=True)
        record = _record(_map(req), _terminal(req["id"]))
        self.assertEqual(psr.record_hash(record), record["parent_synthesis_hash"])
        tampered = {**record, "resolved_empty_outcomes": []}
        self.assertNotEqual(psr.record_hash(tampered), record["parent_synthesis_hash"])


class AuditTests(unittest.TestCase):
    def _audit(self, map_, record):
        return psa.audit_parent_synthesis(map_, EMPTY_SEALED, {}, record)

    def test_a_consistent_record_passes_the_new_checks(self):
        req = _requirement(allowed=True)
        map_ = _map(req)
        audit = self._audit(map_, _record(map_, _terminal(req["id"])))
        self.assertTrue(audit["checks"]["resolved_empty_outcomes_match_rederivation"])
        self.assertTrue(audit["checks"]["scoped_search_terminal_flags_justified_by_map"])

    def test_a_tampered_outcome_list_fails_the_rederivation_check(self):
        req = _requirement(allowed=True)
        map_ = _map(req)
        record = _record(map_, _terminal(req["id"]), outcomes=[])
        audit = self._audit(map_, record)
        self.assertFalse(audit["checks"]["resolved_empty_outcomes_match_rederivation"])
        self.assertFalse(audit["ok"])

    def test_a_terminal_flag_on_a_partially_supported_requirement_is_unjustified(self):
        """Checked against the justification rule itself: a partially supported requirement yields a real ParentClaim,
        which needs a full sealed proposition to build, so the whole audit is not the unit under test here."""
        req = _requirement(allowed=True, filled=("named",))
        map_ = _map(req)
        self.assertFalse(psa._terminal_flags_justified(map_, _terminal(req["id"])))
        self.assertTrue(psa._terminal_flags_justified(map_, _terminal(req["id"], terminal=False)))

    def test_a_terminal_flag_for_a_requirement_absent_from_the_map_is_unjustified(self):
        req = _requirement(allowed=True)
        map_ = _map(req)
        record = _record(map_, _terminal("ghost#req"), outcomes=[])
        audit = self._audit(map_, record)
        self.assertFalse(audit["checks"]["scoped_search_terminal_flags_justified_by_map"])

    def test_a_malformed_record_fails_without_crashing(self):
        req = _requirement(allowed=True)
        map_ = _map(req)
        record = _record(map_, {})
        del record["scoped_search_status"]
        audit = self._audit(map_, record)
        self.assertFalse(audit["ok"])
        self.assertFalse(audit["checks"]["resolved_empty_outcomes_match_rederivation"])


@unittest.skipUnless(ARTIFACTS_PRESENT, "frozen Phase-23 run artifacts are not present in this worktree")
class FrozenPhase23ReplayTests(unittest.TestCase):
    """The real frozen final state. Read only: no execute(), no model, no recovery rerun."""

    @classmethod
    def setUpClass(cls):
        result = json.loads((RUN_DIR / "phase23_result.json").read_text(encoding="utf-8"))
        cls.sealed = json.loads((RUN_DIR / "run" / "11_verified_ledger.json").read_text(encoding="utf-8"))
        cls.initial_map = result["sufficiency_map_initial"]
        cls.final_map = result["sufficiency_map_final"]
        cls.recorded_initial = result["recovery_targets_initial"]
        cls.recorded_final = result["recovery_targets_final"]
        cls.log = result["recovery_log"]

    def test_the_round_reads_c4_as_completed_and_the_final_map_as_not_empty(self):
        round_outcomes = srt.structured_search_outcomes(self.recorded_initial, self.log)
        self.assertTrue(round_outcomes[C4]["completed"])
        status = srt.terminal_search_status(self.final_map, round_outcomes)
        self.assertFalse(status[C4]["terminal"])
        self.assertTrue(all(not entry["terminal"] for entry in status.values()))

    def test_initial_inventory_is_19_and_keeps_both_c4_search_obligations(self):
        recomputed = srt.compute_recovery_targets(self.initial_map, {})
        self.assertEqual(len(recomputed), 19)
        self.assertEqual(set(recomputed), set(self.recorded_initial))
        c4_ids = {tid for tid, t in recomputed.items() if t["requirement_id"] == C4}
        self.assertEqual(c4_ids, {"c4::16fda026555aa730", "c4::ed1c091df96fa134"})

    def test_final_inventory_is_33_unchanged_by_the_terminal_rule(self):
        round_outcomes = srt.structured_search_outcomes(self.recorded_initial, self.log)
        status = srt.terminal_search_status(self.final_map, round_outcomes)
        final = srt.compute_recovery_targets(self.final_map, {}, srt.engine_search_status(status))
        self.assertEqual(len(final), 33)
        # The recorded artifact is JSON: tuples (affected_descendants) are lists there. Compare canonical JSON.
        self.assertEqual(json.loads(json.dumps(final)), self.recorded_final)

    def test_claims_gaps_and_resolved_outcomes_are_24_33_and_zero(self):
        round_outcomes = srt.structured_search_outcomes(self.recorded_initial, self.log)
        status = srt.terminal_search_status(self.final_map, round_outcomes)
        claims = psl.build_claim_ledger(self.final_map, self.sealed)
        gaps = psl.build_gap_report(self.recorded_final, sufficiency_map_final=self.final_map)
        self.assertEqual(len(claims), 24)
        self.assertEqual(len(gaps), 33)
        self.assertEqual(psl.build_resolved_empty_outcomes(self.final_map, status), [])


if __name__ == "__main__":
    unittest.main()
