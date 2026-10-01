"""Locks in Phase 6 Part F's recorded-output replay result: scripting Phase 5's OWN frozen manual
adjudication as a specificity decision must remove c2's false `filled` state while leaving every
other child's state/instance-count byte-identical to Phase 5's own live v9 run. No live model
call -- this replays `.local/sufficiency-nomination-diagnostic-v9-20260930/qwen_calls.jsonl`,
scripted, never reinterpreted.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised.sufficiency_phase5_replay import _VETOED_EXACT_TEXT, replay, state_report

# Phase 5's own live v9 result (PHASE5_V9_LIVE_RERUN_RESULTS.md, "Per-child state comparison"),
# transcribed verbatim as the expected WITH-GATE baseline for every child except c2 -- the one
# child the Phase 6 gate is specifically meant to correct.
_EXPECTED_UNCHANGED_FROM_PHASE5 = {
    ("c1", "c1#suff:neural-manifestation"): ("filled", 1),
    ("c3", "c3#suff:attitude-manifestation"): ("filled", 1),
    ("c3", "c3#suff:implicit-explicit-coverage"): ("partially_filled", 2),
    ("c4", "c4#suff:specific-region"): ("filled", 1),
    ("c5", "c5#suff:brain-behavior"): ("partially_filled", 1),
    ("c6", "c6#suff:brain-attitude"): ("filled", 2),
    ("c6", "c6#suff:implicit-explicit-coverage"): ("partially_filled", 2),
    ("c8", "c8#suff:trait-construct"): ("partially_filled", 4),
    # Phase 16 (deliberate, documented change -- NOT the Phase-6 gate's own correction this file is
    # otherwise locking in): c9 pairs against c8's own 4 discovered trait instances, but EVERY one
    # of them is itself INCOMPLETE (trait filled, `relationship_to_bias_manifestation` missing --
    # confirmed directly against this real data). Before Phase 16, `map_paired_requirement` paired
    # against any instance whose role was merely FILLED, regardless of the instance's own
    # completeness -- producing 4 premature "which scale measures this trait" obligations for
    # traits whose bias-relevance c8 had not yet established. Phase 16 made `instance.complete`
    # part of the eligibility contract uniformly (c4->c5/c6 and c8->c9 alike); with zero of c8's
    # real instances eligible, c9 correctly has zero paired instances -- the real unresolved
    # obligation is c8's own `relationship_to_bias_manifestation` role, already surfaced there.
    ("c9", "c9#suff:trait-scale-pairing"): ("missing", 0),
    ("c10", "c10#suff:culture-existence"): ("missing", 1),
    ("c11", "c11#suff:culture-operationalization-pairing"): ("missing", 0),
    ("c12", "c12#suff:intervention-effectiveness"): ("partially_filled", 2),
}


class Phase5ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = replay()
        cls.with_gate = state_report(cls.result["with_model"])

    def test_every_unrelated_child_matches_phase5s_own_live_v9_result_exactly(self):
        for (child, req_id), (expected_state, expected_count) in _EXPECTED_UNCHANGED_FROM_PHASE5.items():
            with self.subTest(child=child, req_id=req_id):
                actual = self.with_gate[child][req_id]
                self.assertEqual(actual["state"], expected_state)
                self.assertEqual(actual["instance_count"], expected_count)

    def test_c2_drops_from_phase5s_false_filled_state_to_the_honest_partially_filled(self):
        c2 = self.with_gate["c2"]["c2#suff:behavioral-manifestation"]
        # Phase 5's own live run: state="filled", instance_count=3 (the circular nomination plus
        # both "visual attention" phrasings). After the veto: 2 instances remain (the circular one
        # is gone) and the requirement is honestly partially_filled -- NOT because the gate forced
        # it, but because the two genuine "visual attention" instances legitimately fail the
        # pre-existing same_proposition joint-grounding check against a DIFFERENT proposition than
        # `behavioral_manifestation_evidence`'s own p1 (see the module docstring/handback report).
        self.assertEqual(c2["state"], "partially_filled")
        self.assertEqual(c2["instance_count"], 2)

    def test_the_surviving_c2_instances_are_the_genuine_visual_attention_findings(self):
        c2_req = self.result["with_model"]["c2"]["requirements"][0]
        exact_texts = {
            inst["role_bindings"]["behavior_or_behavioral_measure"]["exact_text"] for inst in c2_req["instances"]
        }
        self.assertEqual(
            exact_texts,
            {
                "visual attention toward people with facial anomalies",
                "influence visual attention when looking at faces with anomalous anatomy",
            },
        )
        # the vetoed text must not survive as any instance's own binding
        for inst in c2_req["instances"]:
            self.assertNotEqual(
                inst["role_bindings"]["behavior_or_behavioral_measure"]["exact_text"], _VETOED_EXACT_TEXT
            )

    def test_c2_still_has_both_roles_individually_filled_on_each_surviving_instance(self):
        """The veto removes ONE candidate nomination; it does not touch the deterministic
        `behavioral_manifestation_evidence` role, which legitimately remains filled on every
        instance -- confirming the partially_filled state comes from the joint-grounding
        verifier, never from the gate silently blanking an unrelated role."""
        c2_req = self.result["with_model"]["c2"]["requirements"][0]
        for inst in c2_req["instances"]:
            self.assertEqual(inst["role_bindings"]["behavior_or_behavioral_measure"]["state"], "filled")
            self.assertEqual(inst["role_bindings"]["behavioral_manifestation_evidence"]["state"], "filled")

    def test_deterministic_only_pass_is_untouched_by_this_replay(self):
        """The specificity gate only ever applies to model-sourced bindings -- the deterministic-
        only pass (no model_client) must be identical to what Phase 2/3/4's own replays already
        established."""
        det = state_report(self.result["deterministic_only"])
        self.assertEqual(
            det["c2"]["c2#suff:behavioral-manifestation"],
            {"state": "partially_filled", "instance_count": 1, "instance_keys": [None]},
        )
        self.assertEqual(det["c1"]["c1#suff:neural-manifestation"]["state"], "partially_filled")


if __name__ == "__main__":
    unittest.main()
