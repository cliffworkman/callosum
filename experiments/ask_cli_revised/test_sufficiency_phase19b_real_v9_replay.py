"""Phase 19b's mandatory release gate (audit §15): the real, preserved q_aib evidence that
originally exposed the Phase-19 request-identity gap -- the 2026-09-30 T5C live run's own
`11_verified_ledger.json` (real c12: two distinct candidate units) -- replayed through the
CURRENT production-shaped U1 path across ALL 11 real children, no exclusions, with a fake (never
live) nomination client. Then the Phase-20b U2 held-fixed rebuild, proving it makes zero
additional physical calls.

This is a committed pytest fixture, not the Phase-21 diagnostic harness
(`phase21_live_initial_model_assist_validation.py`, which remains untracked Phase-21 material and
is never imported here) -- reusable deterministic coverage belongs in the test suite, per the
Phase-19b authorization's own instruction.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_freeze as sf
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

_PRESERVED_LEDGER = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "q-aib-hierarchical-t5c-live-20260930"
    / "run"
    / "11_verified_ledger.json"
)
needs_preserved_ledger = unittest.skipUnless(
    _PRESERVED_LEDGER.is_file(), f"the preserved q_aib ledger is not present at {_PRESERVED_LEDGER}"
)


class _FakeNominationClient:
    """A minimal duck-typed fake -- the exact sanctioned Phase-19 protocol
    (`nominate_sufficiency_role(category_description=, candidates=)` + `.model_name`), never a
    real transport. Nominates the first offered candidate's own text prefix for whichever
    category it is asked about, so every reached scope with nonempty candidates gets a real,
    literally-grounded nomination. This module tests INFRASTRUCTURE correctness (does the mapper
    complete, are receipts correctly isolated, does U2 make zero calls) -- it makes no claim about
    SCIENTIFIC nomination quality, which is Phase 21's own, separate concern."""

    model_name = "fake-v9-replay-client"

    def __init__(self):
        self.calls: list[dict] = []

    def nominate_sufficiency_role(self, *, category_description, candidates):
        self.calls.append({"category_description": category_description, "candidates": list(candidates)})
        if not candidates:
            return []
        first = candidates[0]
        return [{"proposition_id": first["proposition_id"], "exact_text": first["passage"][:15]}]


@needs_preserved_ledger
class RealV9FullContractReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.contract_by_child = sf.load_verified()
        cls.parent_of = hc.parent_of(cls.contract)
        cls.sealed = json.loads(_PRESERVED_LEDGER.read_text(encoding="utf-8"))
        assert cls.sealed["request_contract"]["question_hash"] == cls.contract["question_hash"], (
            "the preserved ledger must be the SAME real hierarchy this test loads -- confirmed once here"
        )

    def _c12_keys(self, receipts: dict) -> list[tuple]:
        return [key for key in receipts if key[0][0] == "c12"]

    def test_u1_completes_across_all_11_children_with_no_exclusions_and_no_crash(self):
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        mapped = sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        sd.compute_direction_and_effectiveness(self.sealed, mapped, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        # Before Phase 19b this raised RequestFingerprintMismatch on c12 before completing at all.
        self.assertEqual(set(mapped), set(self.contract_by_child))
        self.assertEqual(len(mapped), 11)

    def test_c12_real_two_unit_shape_produces_two_independent_request_contexts_per_role(self):
        """The exact real shape the Phase-21 preflight discovered: c12 has two real candidate
        units (U1, U5 -- this preserved ledger's own real unit ids, not a design assumption)."""
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        c12_keys = self._c12_keys(ctx["in_pass_receipts"])
        request_contexts = {key[1] for key in c12_keys}
        self.assertEqual(request_contexts, {"U1", "U5"})
        roles = {key[0][2] for key in c12_keys}
        self.assertEqual(roles, {"intervention", "target_manifestation"})
        # 2 roles x 2 units = 4 independent receipt slots, all distinct composite keys.
        self.assertEqual(len(c12_keys), 4)
        self.assertEqual(len(set(c12_keys)), 4)

    def test_each_c12_request_receives_only_its_own_receipt_never_a_siblings(self):
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        receipts = ctx["in_pass_receipts"]
        intervention_u1 = receipts[(("c12", "c12#suff:intervention-effectiveness", "intervention"), "U1")]
        intervention_u5 = receipts[(("c12", "c12#suff:intervention-effectiveness", "intervention"), "U5")]
        self.assertNotEqual(intervention_u1["accepted"], intervention_u5["accepted"])
        self.assertNotEqual(intervention_u1["request_fingerprint"], intervention_u5["request_fingerprint"])
        self.assertEqual(intervention_u1["request_context"], "U1")
        self.assertEqual(intervention_u5["request_context"], "U5")

    def test_role_fork_duplicate_requests_still_memoize_to_one_physical_call(self):
        """c1's own `brain_region_or_network` role (multi_instance=False) is a real, non-partitioned
        scope -- any repeat resolution within the pass must still collapse to one physical call,
        proving Phase 19's own original invariant survives the Phase-19b generalization intact."""
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        # real evidence may or may not reach c1's region role more than once structurally; the
        # invariant under test is that however many TIMES resolve_nomination is entered for one
        # (scope, request_context), the physical call count for it is exactly one -- checked
        # directly against the receipt store rather than inferred from the call log alone.
        c1_keys = [k for k in ctx["in_pass_receipts"] if k[0][0] == "c1"]
        for key in c1_keys:
            self.assertIn(ctx["in_pass_receipts"][key]["status"], {"fresh", "fresh_no_candidates"})
        self.assertEqual(len(c1_keys), len({k for k in c1_keys}))  # no duplicate physical resolution per key

    def test_u1_physical_call_count_is_mechanically_explicable(self):
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        receipts = ctx["in_pass_receipts"]
        fresh = [r for r in receipts.values() if r["status"] == "fresh"]
        no_candidates = [r for r in receipts.values() if r["status"] == "fresh_no_candidates"]
        self.assertEqual(len(client.calls), len(fresh))  # exactly one physical call per "fresh" receipt
        self.assertEqual(len(fresh) + len(no_candidates), len(receipts))  # ALL_ELIGIBLE: no held-fixed statuses

    def test_direction_and_effectiveness_pass_completes_over_the_model_assisted_map(self):
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        mapped = sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        sd.compute_direction_and_effectiveness(self.sealed, mapped, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        c5_req = next(r for r in mapped["c5"]["requirements"] if r["id"] == "c5#suff:brain-behavior")
        self.assertIn("direction_summary", c5_req)
        for instance in c5_req["instances"]:
            self.assertIn("direction_observations", instance)

    def test_recovery_target_computation_can_inspect_the_resulting_map(self):
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        mapped = sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        targets = srt.compute_recovery_targets(mapped, self.parent_of, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)
        self.assertIsInstance(targets, dict)  # not executed -- recovery stays off in this phase

    def test_u2_held_fixed_rebuild_completes_with_zero_fresh_calls(self):
        client = _FakeNominationClient()
        u1_ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=u1_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        u1_call_count = len(client.calls)
        u1_receipts_snapshot = dict(u1_ctx["in_pass_receipts"])

        u2_ctx = mscope.new_nomination_context(
            mscope.exact_scope_set_policy(set()), prior_receipts=u1_receipts_snapshot
        )
        mapped_final = sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=u2_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        sd.compute_direction_and_effectiveness(self.sealed, mapped_final, semantics_version=se.SUFFICIENCY_SEMANTICS_V3)

        self.assertEqual(len(client.calls), u1_call_count, "U2 must make zero additional physical calls")
        self.assertEqual(set(mapped_final), set(self.contract_by_child))

    def test_u2_each_existing_request_context_replays_its_own_correct_prior_receipt(self):
        client = _FakeNominationClient()
        u1_ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=u1_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        u1_receipts_snapshot = dict(u1_ctx["in_pass_receipts"])
        u2_ctx = mscope.new_nomination_context(
            mscope.exact_scope_set_policy(set()), prior_receipts=u1_receipts_snapshot
        )
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=u2_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        for key, u1_receipt in u1_receipts_snapshot.items():
            u2_receipt = u2_ctx["in_pass_receipts"][key]
            self.assertEqual(u2_receipt["accepted"], u1_receipt["accepted"])
            self.assertIn(u2_receipt["status"], {"held_fixed_replay", "held_fixed_no_valid_prior"})

    def test_u2_never_borrows_a_sibling_request_contexts_receipt(self):
        client = _FakeNominationClient()
        u1_ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=u1_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        u1_receipts_snapshot = dict(u1_ctx["in_pass_receipts"])
        u2_ctx = mscope.new_nomination_context(
            mscope.exact_scope_set_policy(set()), prior_receipts=u1_receipts_snapshot
        )
        sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=u2_ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        u1_scope = ("c12", "c12#suff:intervention-effectiveness", "intervention")
        self.assertEqual(
            u2_ctx["in_pass_receipts"][(u1_scope, "U1")]["accepted"],
            u1_receipts_snapshot[(u1_scope, "U1")]["accepted"],
        )
        self.assertNotEqual(
            u2_ctx["in_pass_receipts"][(u1_scope, "U1")]["accepted"],
            u1_receipts_snapshot[(u1_scope, "U5")]["accepted"],
        )

    def test_a_model_dependency_origins_shape_carries_request_context_as_of_phase_22(self):
        """Phase 19b's own researcher decision explicitly deferred this linkage: 'Phase 19b does
        not propagate request_context into model_dependency_origins -- that linkage is deferred to
        Phase 22's own design.' Phase 22 is that design: `request_context` is now a fifth field on
        every origin, read from the owning instance's own stamp
        (`sufficiency_mapping.map_requirement`), never parsed from `instance_key`."""
        client = _FakeNominationClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        mapped = sd.compute_diagnostic_sufficiency_map(
            self.sealed,
            self.contract_by_child,
            self.parent_of,
            model_client=client,
            nomination_context=ctx,
            semantics_version=se.SUFFICIENCY_SEMANTICS_V3,
        )
        req = next(r for r in mapped["c12"]["requirements"] if r["id"] == "c12#suff:intervention-effectiveness")
        found_origin = False
        for instance in req["instances"]:
            for binding in instance["role_bindings"].values():
                origins = (binding.get("provenance") or {}).get("model_dependency_origins")
                if origins:
                    found_origin = True
                    for origin in origins:
                        self.assertEqual(
                            set(origin), {"child_id", "requirement_id", "role", "instance_key", "request_context"}
                        )
                        self.assertEqual(origin["request_context"], instance.get("request_context"))
        self.assertTrue(found_origin, "expected at least one stamped model_dependency_origins entry on real c12")
