"""Tests for `sufficiency_model_scope.py` (Phase 19): the model-nomination identity/authorization/
receipt infrastructure. Pure, no model, no network -- every "fresh call" in this file is a plain
scripted callable, never a real or faked `QwenTasks`-shaped client (that duck-typed boundary is
exercised at the `sufficiency_mapping.py` integration layer instead, see
`test_sufficiency_mapping.py`'s own Phase-19 tests)."""

from __future__ import annotations

import json
import unittest

from experiments.ask_cli_revised import sufficiency_model_scope as mscope


class ModelNominationScopeTests(unittest.TestCase):
    def test_constructs_a_plain_three_tuple(self):
        scope = mscope.new_model_nomination_scope("c4", "c4#suff:specific-region", "named_brain_region_or_network")
        self.assertEqual(scope, ("c4", "c4#suff:specific-region", "named_brain_region_or_network"))

    def test_rejects_empty_child_id(self):
        with self.assertRaises(ValueError):
            mscope.new_model_nomination_scope("", "c4#suff:specific-region", "role")

    def test_rejects_empty_requirement_id(self):
        with self.assertRaises(ValueError):
            mscope.new_model_nomination_scope("c4", "", "role")

    def test_rejects_empty_role(self):
        with self.assertRaises(ValueError):
            mscope.new_model_nomination_scope("c4", "c4#suff:specific-region", "")

    def test_two_scopes_differing_only_in_child_id_are_distinct(self):
        a = mscope.new_model_nomination_scope("c5", "req", "named_brain_region_or_network")
        b = mscope.new_model_nomination_scope("c6", "req", "named_brain_region_or_network")
        self.assertNotEqual(a, b)

    def test_two_scopes_differing_only_in_requirement_id_are_distinct(self):
        a = mscope.new_model_nomination_scope("c6", "c6#suff:A", "category_evidence")
        b = mscope.new_model_nomination_scope("c6", "c6#suff:B", "category_evidence")
        self.assertNotEqual(a, b)

    def test_is_usable_as_a_dict_key(self):
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        store = {scope: "receipt"}
        self.assertEqual(store[mscope.new_model_nomination_scope("c4", "req", "role")], "receipt")


def _spec(strategy="model_nomination_only", permitted=True):
    return {"mapping_strategy": strategy, "model_nomination_permitted": permitted}


def _req(req_id, role_specs):
    return {"id": req_id, "role_specs": role_specs}


def _contract(child_id, requirements):
    return {"child_id": child_id, "requirements": requirements}


class EnumerateModelNominationScopesTests(unittest.TestCase):
    """Must be fully generic -- no question/domain-specific vocabulary (Phase-19 audit test #37) --
    proven here with a synthetic, clearly-non-q_aib contract before the real v9 inventory test."""

    def test_finds_a_single_eligible_scope(self):
        contract_by_child = {
            "x1": _contract("x1", [_req("x1#r1", {"widget": _spec()})]),
        }
        scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)
        self.assertEqual(scopes, [("x1", "x1#r1", "widget")])

    def test_ignores_deterministic_strategy_roles(self):
        contract_by_child = {
            "x1": _contract(
                "x1",
                [_req("x1#r1", {"a": _spec("named_instrument_lexicon"), "b": _spec("model_nomination_only")})],
            ),
        }
        scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)
        self.assertEqual(scopes, [("x1", "x1#r1", "b")])

    def test_ignores_model_nomination_only_roles_with_permission_revoked(self):
        contract_by_child = {
            "x1": _contract("x1", [_req("x1#r1", {"widget": _spec(permitted=False)})]),
        }
        self.assertEqual(mscope.enumerate_model_nomination_scopes(contract_by_child), [])

    def test_same_role_name_across_requirements_of_one_child_both_counted(self):
        contract_by_child = {
            "x1": _contract(
                "x1",
                [_req("x1#r1", {"shared": _spec()}), _req("x1#r2", {"shared": _spec()})],
            ),
        }
        scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)
        self.assertEqual(
            sorted(scopes),
            [("x1", "x1#r1", "shared"), ("x1", "x1#r2", "shared")],
        )

    def test_same_role_name_across_children_both_counted(self):
        contract_by_child = {
            "x1": _contract("x1", [_req("x1#r1", {"shared": _spec()})]),
            "x2": _contract("x2", [_req("x2#r1", {"shared": _spec()})]),
        }
        scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)
        self.assertEqual(sorted(scopes), [("x1", "x1#r1", "shared"), ("x2", "x2#r1", "shared")])

    def test_empty_contract_set_yields_no_scopes(self):
        self.assertEqual(mscope.enumerate_model_nomination_scopes({}), [])

    def test_against_the_real_frozen_v9_contract_yields_the_exact_mechanically_confirmed_inventory(self):
        """Offline, zero model calls -- loads the already-frozen v9 contract JSON directly (no
        preserved-run env var needed) and proves the enumeration is exhaustive and matches the
        hand-verified count from the Phase-19 audit (§C): 15 scopes across 11 children."""
        from pathlib import Path

        frozen_path = Path(__file__).resolve().parent / "sufficiency_contract.aib_hier_v9.frozen.json"
        data = json.loads(frozen_path.read_text(encoding="utf-8"))
        contract_by_child = {cid: entry["frozen_view"] for cid, entry in data["per_child"].items()}

        scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)

        self.assertEqual(len(scopes), 15)
        self.assertEqual(len(scopes), len(set(scopes)), "every scope in the real v9 contract must be unique")
        expected = {
            ("c1", "c1#suff:neural-manifestation", "neural_measure_or_modality"),
            ("c1", "c1#suff:neural-manifestation", "brain_region_or_network"),
            ("c10", "c10#suff:culture-existence", "named_culture_or_population"),
            ("c11", "c11#suff:culture-operationalization-pairing", "culture_or_population"),
            ("c11", "c11#suff:culture-operationalization-pairing", "operationalization_or_measure"),
            ("c12", "c12#suff:intervention-effectiveness", "intervention"),
            ("c12", "c12#suff:intervention-effectiveness", "target_manifestation"),
            ("c2", "c2#suff:behavioral-manifestation", "behavior_or_behavioral_measure"),
            ("c4", "c4#suff:specific-region", "named_brain_region_or_network"),
            ("c5", "c5#suff:brain-behavior", "named_brain_region_or_network"),
            ("c5", "c5#suff:brain-behavior", "behavior_or_behavioral_measure"),
            ("c6", "c6#suff:brain-attitude", "named_brain_region_or_network"),
            ("c6", "c6#suff:brain-attitude", "attitude_type_or_measure"),
            ("c8", "c8#suff:trait-construct", "individual_difference_trait_or_construct"),
            ("c9", "c9#suff:trait-scale-pairing", "individual_difference_trait_or_construct"),
        }
        self.assertEqual(set(scopes), expected)

    def test_v9_inventory_demonstrates_both_same_role_disambiguation_cases_for_real(self):
        """`named_brain_region_or_network` (c1/c4/c5/c6) and
        `individual_difference_trait_or_construct` (c8/c9) each appear on >1 real child -- proving
        test #4 ("same role name across children disambiguated") against genuine contract data,
        not only the synthetic case above."""
        from pathlib import Path

        frozen_path = Path(__file__).resolve().parent / "sufficiency_contract.aib_hier_v9.frozen.json"
        data = json.loads(frozen_path.read_text(encoding="utf-8"))
        contract_by_child = {cid: entry["frozen_view"] for cid, entry in data["per_child"].items()}
        scopes = mscope.enumerate_model_nomination_scopes(contract_by_child)

        region_scopes = [s for s in scopes if s[2] == "named_brain_region_or_network"]
        trait_scopes = [s for s in scopes if s[2] == "individual_difference_trait_or_construct"]
        self.assertEqual({s[0] for s in region_scopes}, {"c4", "c5", "c6"})
        self.assertEqual({s[0] for s in trait_scopes}, {"c8", "c9"})
        # child_id alone would NOT disambiguate c5's own two roles -- requirement_id does (both
        # share one requirement here, but the two roles differ) -- role is the final discriminator.
        self.assertEqual(len(region_scopes), len(set(region_scopes)))
        self.assertEqual(len(trait_scopes), len(set(trait_scopes)))


class RequestFingerprintTests(unittest.TestCase):
    def test_identical_inputs_produce_identical_fingerprints(self):
        rows = [{"proposition_id": "p1", "passage": "the amygdala was active"}]
        a = mscope.request_fingerprint("named brain region", rows)
        b = mscope.request_fingerprint("named brain region", rows)
        self.assertEqual(a, b)

    def test_candidate_order_does_not_affect_the_fingerprint(self):
        rows_forward = [
            {"proposition_id": "p1", "passage": "amygdala"},
            {"proposition_id": "p2", "passage": "hippocampus"},
        ]
        rows_reversed = list(reversed(rows_forward))
        a = mscope.request_fingerprint("named brain region", rows_forward)
        b = mscope.request_fingerprint("named brain region", rows_reversed)
        self.assertEqual(a, b)

    def test_different_category_description_changes_the_fingerprint(self):
        rows = [{"proposition_id": "p1", "passage": "amygdala"}]
        a = mscope.request_fingerprint("named brain region", rows)
        b = mscope.request_fingerprint("named behavioral measure", rows)
        self.assertNotEqual(a, b)

    def test_different_candidate_passage_text_changes_the_fingerprint(self):
        a = mscope.request_fingerprint("x", [{"proposition_id": "p1", "passage": "amygdala"}])
        b = mscope.request_fingerprint("x", [{"proposition_id": "p1", "passage": "hippocampus"}])
        self.assertNotEqual(a, b)

    def test_different_candidate_proposition_id_changes_the_fingerprint(self):
        a = mscope.request_fingerprint("x", [{"proposition_id": "p1", "passage": "amygdala"}])
        b = mscope.request_fingerprint("x", [{"proposition_id": "p2", "passage": "amygdala"}])
        self.assertNotEqual(a, b)

    def test_different_candidate_set_size_changes_the_fingerprint(self):
        a = mscope.request_fingerprint("x", [{"proposition_id": "p1", "passage": "amygdala"}])
        b = mscope.request_fingerprint(
            "x", [{"proposition_id": "p1", "passage": "amygdala"}, {"proposition_id": "p2", "passage": "y"}]
        )
        self.assertNotEqual(a, b)

    def test_fingerprint_is_a_stable_hex_digest(self):
        fp = mscope.request_fingerprint("x", [{"proposition_id": "p1", "passage": "y"}])
        self.assertIsInstance(fp, str)
        int(fp, 16)  # raises ValueError if not valid hex


class AuthorizationPolicyTests(unittest.TestCase):
    def test_all_eligible_authorizes_any_scope(self):
        policy = mscope.all_eligible_policy()
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        self.assertTrue(mscope.is_authorized_for_fresh_call(policy, scope))

    def test_exact_scope_set_authorizes_only_named_scopes(self):
        target = mscope.new_model_nomination_scope("c4", "req", "role")
        other = mscope.new_model_nomination_scope("c5", "req", "role")
        policy = mscope.exact_scope_set_policy([target])
        self.assertTrue(mscope.is_authorized_for_fresh_call(policy, target))
        self.assertFalse(mscope.is_authorized_for_fresh_call(policy, other))

    def test_exact_scope_set_with_empty_set_authorizes_nothing(self):
        policy = mscope.exact_scope_set_policy([])
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        self.assertFalse(mscope.is_authorized_for_fresh_call(policy, scope))

    def test_unknown_policy_kind_raises(self):
        with self.assertRaises(ValueError):
            mscope.is_authorized_for_fresh_call({"kind": "nonsense"}, ("a", "b", "c"))


def _rows(n=1):
    return [{"proposition_id": f"p{i}", "passage": f"passage {i}"} for i in range(n)]


class ResolveNominationTests(unittest.TestCase):
    """Pure orchestration -- `make_fresh_call` is a plain scripted callable, never a duck-typed
    model client (that boundary lives in sufficiency_mapping.py's own integration tests)."""

    def _context(self, policy, prior_receipts=None):
        return mscope.new_nomination_context(policy, prior_receipts=prior_receipts)

    def test_fresh_call_made_exactly_once_when_authorized(self):
        calls = []

        def fresh():
            calls.append(1)
            return [{"proposition_id": "p0", "exact_text": "x", "supporting_proposition_ids": ["p0"]}]

        ctx = self._context(mscope.all_eligible_policy())
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        accepted, status = mscope.resolve_nomination(
            scope,
            candidate_rows=_rows(),
            category_description="x",
            model_name="test-model",
            make_fresh_call=fresh,
            nomination_context=ctx,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(status, "fresh")
        self.assertEqual(accepted[0]["proposition_id"], "p0")

    def test_repeated_identical_request_under_one_scope_memoizes_within_one_pass(self):
        """The audit's §D/§J mechanical proof: same scope + same fingerprint -> at most one
        physical call, every later call reuses the same accepted result."""
        calls = []

        def fresh():
            calls.append(1)
            return [{"proposition_id": "p0", "exact_text": "x", "supporting_proposition_ids": ["p0"]}]

        ctx = self._context(mscope.all_eligible_policy())
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        rows = _rows()
        first, first_status = mscope.resolve_nomination(
            scope,
            candidate_rows=rows,
            category_description="x",
            model_name="m",
            make_fresh_call=fresh,
            nomination_context=ctx,
        )
        second, second_status = mscope.resolve_nomination(
            scope,
            candidate_rows=rows,
            category_description="x",
            model_name="m",
            make_fresh_call=fresh,
            nomination_context=ctx,
        )
        third, third_status = mscope.resolve_nomination(
            scope,
            candidate_rows=rows,
            category_description="x",
            model_name="m",
            make_fresh_call=fresh,
            nomination_context=ctx,
        )
        self.assertEqual(len(calls), 1, "N repeated resolutions of the SAME scope must cost exactly one call")
        self.assertEqual(first_status, "fresh")
        self.assertEqual(second_status, "memoized_in_pass")
        self.assertEqual(third_status, "memoized_in_pass")
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_zero_candidates_makes_zero_physical_calls_and_reports_fresh_no_candidates(self):
        """Phase 20b §A: the model is never invoked merely to receive an empty answer."""
        calls = []
        ctx = self._context(mscope.all_eligible_policy())
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        accepted, status = mscope.resolve_nomination(
            scope,
            candidate_rows=[],
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: calls.append(1) or [],
            nomination_context=ctx,
        )
        self.assertEqual(calls, [])
        self.assertEqual(status, "fresh_no_candidates")
        self.assertEqual(accepted, [])
        self.assertEqual(ctx["in_pass_receipts"][scope]["candidates_offered"], [])

    def test_nonempty_candidates_with_a_successful_empty_response_is_plain_fresh(self):
        """Phase 20b §B: distinguishable from §A only by `candidates_offered`'s own length, never
        by `status` alone being mistaken for a transport failure or a skipped call."""
        ctx = self._context(mscope.all_eligible_policy())
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        accepted, status = mscope.resolve_nomination(
            scope,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: [],
            nomination_context=ctx,
        )
        self.assertEqual(status, "fresh")
        self.assertEqual(accepted, [])
        self.assertEqual(len(ctx["in_pass_receipts"][scope]["candidates_offered"]), 1)

    def test_an_unauthorized_scope_ignores_candidate_count_entirely(self):
        """`fresh_no_candidates` is scoped strictly to the fresh-call branch -- a held-fixed scope
        with zero current candidates still reports its ordinary held-fixed status, never
        `fresh_no_candidates` (which would misleadingly imply a fresh call was even considered)."""
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        ctx = self._context(mscope.exact_scope_set_policy(set()))
        accepted, status = mscope.resolve_nomination(
            scope,
            candidate_rows=[],
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: (_ for _ in ()).throw(AssertionError("must not be called")),
            nomination_context=ctx,
        )
        self.assertEqual(status, "held_fixed_no_valid_prior")
        self.assertEqual(accepted, [])

    def test_same_scope_different_request_fingerprint_fails_loudly(self):
        ctx = self._context(mscope.all_eligible_policy())
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        mscope.resolve_nomination(
            scope,
            candidate_rows=_rows(1),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: [],
            nomination_context=ctx,
        )
        with self.assertRaises(mscope.RequestFingerprintMismatch):
            mscope.resolve_nomination(
                scope,
                candidate_rows=_rows(2),
                category_description="x",
                model_name="m",
                make_fresh_call=lambda: [],
                nomination_context=ctx,
            )

    def test_candidate_order_permutation_alone_does_not_trigger_a_mismatch(self):
        ctx = self._context(mscope.all_eligible_policy())
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        rows = _rows(2)
        mscope.resolve_nomination(
            scope,
            candidate_rows=rows,
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: [],
            nomination_context=ctx,
        )
        # Should NOT raise -- same rows, reversed order.
        accepted, status = mscope.resolve_nomination(
            scope,
            candidate_rows=list(reversed(rows)),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: [],
            nomination_context=ctx,
        )
        self.assertEqual(status, "memoized_in_pass")

    def test_exact_scope_set_authorizes_only_the_named_scope(self):
        target = mscope.new_model_nomination_scope("c4", "req", "named_brain_region_or_network")
        sibling = mscope.new_model_nomination_scope("c5", "req2", "named_brain_region_or_network")
        ctx = self._context(mscope.exact_scope_set_policy([target]))

        target_calls = []
        sibling_calls = []
        t_accepted, t_status = mscope.resolve_nomination(
            target,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: (
                target_calls.append(1)
                or [{"proposition_id": "p0", "exact_text": "t", "supporting_proposition_ids": ["p0"]}]
            ),
            nomination_context=ctx,
        )
        s_accepted, s_status = mscope.resolve_nomination(
            sibling,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: (
                sibling_calls.append(1)
                or [{"proposition_id": "p0", "exact_text": "s", "supporting_proposition_ids": ["p0"]}]
            ),
            nomination_context=ctx,
        )
        self.assertEqual(len(target_calls), 1)
        self.assertEqual(t_status, "fresh")
        self.assertEqual(len(sibling_calls), 0, "an unauthorized scope must never make a fresh call")
        self.assertEqual(s_status, "held_fixed_no_valid_prior")
        self.assertEqual(s_accepted, [])

    def test_unauthorized_scope_with_valid_prior_receipt_replays_it(self):
        target = mscope.new_model_nomination_scope("c4", "req", "role")
        sibling = mscope.new_model_nomination_scope("c5", "req2", "role")
        prior_accepted = [{"proposition_id": "p0", "exact_text": "prior", "supporting_proposition_ids": ["p0"]}]
        prior_receipt = mscope.new_nomination_receipt(
            sibling,
            model_name="m",
            request_fingerprint="irrelevant",
            candidates_offered=_rows(),
            accepted=prior_accepted,
            status="fresh",
        )
        ctx = self._context(mscope.exact_scope_set_policy([target]), prior_receipts={sibling: prior_receipt})

        calls = []
        accepted, status = mscope.resolve_nomination(
            sibling,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: calls.append(1),
            validate_prior_receipt=lambda receipt: True,
            nomination_context=ctx,
        )
        self.assertEqual(calls, [])
        self.assertEqual(status, "held_fixed_replay")
        self.assertEqual(accepted, prior_accepted)

    def test_unauthorized_scope_with_invalid_prior_receipt_does_not_replay_it(self):
        target = mscope.new_model_nomination_scope("c4", "req", "role")
        sibling = mscope.new_model_nomination_scope("c5", "req2", "role")
        prior_receipt = mscope.new_nomination_receipt(
            sibling,
            model_name="m",
            request_fingerprint="irrelevant",
            candidates_offered=_rows(),
            accepted=[{"proposition_id": "stale", "exact_text": "x", "supporting_proposition_ids": ["stale"]}],
            status="fresh",
        )
        ctx = self._context(mscope.exact_scope_set_policy([target]), prior_receipts={sibling: prior_receipt})

        accepted, status = mscope.resolve_nomination(
            sibling,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: [],
            validate_prior_receipt=lambda receipt: False,
            nomination_context=ctx,
        )
        self.assertEqual(status, "held_fixed_no_valid_prior")
        self.assertEqual(accepted, [])

    def test_fresh_call_mechanical_failure_falls_back_to_valid_prior_receipt(self):
        target = mscope.new_model_nomination_scope("c4", "req", "role")
        prior_accepted = [{"proposition_id": "p0", "exact_text": "prior", "supporting_proposition_ids": ["p0"]}]
        prior_receipt = mscope.new_nomination_receipt(
            target,
            model_name="m",
            request_fingerprint="irrelevant",
            candidates_offered=_rows(),
            accepted=prior_accepted,
            status="fresh",
        )
        ctx = self._context(mscope.all_eligible_policy(), prior_receipts={target: prior_receipt})

        def raises():
            raise RuntimeError("transport failed")

        accepted, status = mscope.resolve_nomination(
            target,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=raises,
            validate_prior_receipt=lambda receipt: True,
            nomination_context=ctx,
        )
        self.assertEqual(status, "fresh_failed_fallback_to_prior")
        self.assertEqual(accepted, prior_accepted)

    def test_fresh_call_mechanical_failure_with_no_prior_receipt_degrades_to_empty(self):
        target = mscope.new_model_nomination_scope("c4", "req", "role")
        ctx = self._context(mscope.all_eligible_policy())

        def raises():
            raise RuntimeError("transport failed")

        accepted, status = mscope.resolve_nomination(
            target,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=raises,
            nomination_context=ctx,
        )
        self.assertEqual(status, "fresh_failed_no_valid_prior")
        self.assertEqual(accepted, [])

    def test_fresh_call_failure_never_raises_through_to_the_caller(self):
        """A mechanical failure must degrade gracefully, never propagate as an exception -- the
        resolve_nomination boundary is where failure handling lives (Phase-19 audit §16/§N)."""
        target = mscope.new_model_nomination_scope("c4", "req", "role")
        ctx = self._context(mscope.all_eligible_policy())
        accepted, status = mscope.resolve_nomination(
            target,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: (_ for _ in ()).throw(ValueError("boom")),
            nomination_context=ctx,
        )
        self.assertEqual(accepted, [])
        self.assertEqual(status, "fresh_failed_no_valid_prior")

    def test_no_nomination_context_raises_rather_than_silently_running_legacy_mode(self):
        """`resolve_nomination` is only ever reached once a caller has opted into Phase-19 scoping
        -- the legacy passthrough lives entirely in `sufficiency_mapping._bind_role_candidates`,
        which must bypass this function altogether rather than calling it with `nomination_context
        =None` and expecting silent legacy behavior (Phase-19 audit §A)."""
        with self.assertRaises(ValueError):
            mscope.resolve_nomination(
                mscope.new_model_nomination_scope("c4", "req", "role"),
                candidate_rows=_rows(),
                category_description="x",
                model_name="m",
                make_fresh_call=lambda: [],
                nomination_context=None,
            )

    def test_missing_scope_with_a_context_raises(self):
        ctx = self._context(mscope.all_eligible_policy())
        with self.assertRaises(ValueError):
            mscope.resolve_nomination(
                None,
                candidate_rows=_rows(),
                category_description="x",
                model_name="m",
                make_fresh_call=lambda: [],
                nomination_context=ctx,
            )

    def test_in_pass_receipt_is_recorded_and_inspectable(self):
        target = mscope.new_model_nomination_scope("c4", "req", "role")
        ctx = self._context(mscope.all_eligible_policy())
        mscope.resolve_nomination(
            target,
            candidate_rows=_rows(),
            category_description="x",
            model_name="m",
            make_fresh_call=lambda: [{"proposition_id": "p0", "exact_text": "x", "supporting_proposition_ids": ["p0"]}],
            nomination_context=ctx,
        )
        receipt = ctx["in_pass_receipts"][target]
        self.assertEqual(receipt["scope"], target)
        self.assertEqual(receipt["model_name"], "m")
        self.assertEqual(receipt["status"], "fresh")
        self.assertEqual(receipt["accepted"][0]["proposition_id"], "p0")


class NominationReceiptTests(unittest.TestCase):
    def test_builds_the_minimum_durable_shape(self):
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        receipt = mscope.new_nomination_receipt(
            scope,
            model_name="m",
            request_fingerprint="fp",
            candidates_offered=_rows(),
            accepted=[],
            status="fresh",
        )
        self.assertEqual(
            set(receipt),
            {"scope", "model_name", "request_fingerprint", "candidates_offered", "accepted", "status"},
        )

    def test_receipt_is_upstream_of_binding_construction_never_a_stored_binding(self):
        """Audit §I: a receipt's `accepted` items are `nominate_with_model`'s own pre-binding
        nomination shape (`proposition_id`/`exact_text`/`supporting_proposition_ids`/
        `proposed_role`) -- never a `RoleBinding` (`role`/`state`/`provenance`/`guard`). Proven
        structurally here so this module can never silently start storing derived bindings."""
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        accepted_nomination_shape = [
            {"proposition_id": "p0", "exact_text": "x", "supporting_proposition_ids": ["p0"], "proposed_role": "role"}
        ]
        receipt = mscope.new_nomination_receipt(
            scope,
            model_name="m",
            request_fingerprint="fp",
            candidates_offered=_rows(),
            accepted=accepted_nomination_shape,
            status="fresh",
        )
        binding_only_keys = {"state", "provenance", "guard"}
        for item in receipt["accepted"]:
            self.assertFalse(
                binding_only_keys & set(item),
                "a nomination receipt item must never carry role-binding-only fields",
            )


class RecoveryTargetProjectionTests(unittest.TestCase):
    """`model_scopes_for_recovery_target` needs only a plain dict shaped like
    `sufficiency_recovery_targets.new_recovery_target`'s own output -- no import of that module is
    needed (or taken) here, keeping `sufficiency_model_scope.py` dependency-free of both
    `sufficiency_mapping` and `sufficiency_recovery_targets` (Phase-19 audit §19's layering)."""

    def _target(self, search_child_id, requirement_id, target_roles):
        return {"search_child_id": search_child_id, "requirement_id": requirement_id, "target_roles": target_roles}

    def test_one_model_eligible_role_yields_one_scope(self):
        contract_by_child = {"c4": _contract("c4", [_req("c4#r1", {"role_a": _spec()})])}
        target = self._target("c4", "c4#r1", ["role_a"])
        scopes = mscope.model_scopes_for_recovery_target(target, contract_by_child)
        self.assertEqual(scopes, [("c4", "c4#r1", "role_a")])

    def test_deterministic_target_role_yields_zero_scopes(self):
        contract_by_child = {"c4": _contract("c4", [_req("c4#r1", {"role_a": _spec("named_instrument_lexicon")})])}
        target = self._target("c4", "c4#r1", ["role_a"])
        self.assertEqual(mscope.model_scopes_for_recovery_target(target, contract_by_child), [])

    def test_several_model_eligible_target_roles_yield_several_scopes(self):
        contract_by_child = {"c4": _contract("c4", [_req("c4#r1", {"role_a": _spec(), "role_b": _spec()})])}
        target = self._target("c4", "c4#r1", ["role_a", "role_b"])
        scopes = mscope.model_scopes_for_recovery_target(target, contract_by_child)
        self.assertEqual(sorted(scopes), [("c4", "c4#r1", "role_a"), ("c4", "c4#r1", "role_b")])

    def test_unknown_child_yields_zero_scopes(self):
        target = self._target("missing", "req", ["role"])
        self.assertEqual(mscope.model_scopes_for_recovery_target(target, {}), [])

    def test_unknown_requirement_yields_zero_scopes(self):
        contract_by_child = {"c4": _contract("c4", [_req("c4#other", {"role_a": _spec()})])}
        target = self._target("c4", "c4#missing", ["role_a"])
        self.assertEqual(mscope.model_scopes_for_recovery_target(target, contract_by_child), [])

    def test_unknown_role_in_target_roles_is_skipped_not_raised(self):
        contract_by_child = {"c4": _contract("c4", [_req("c4#r1", {"role_a": _spec()})])}
        target = self._target("c4", "c4#r1", ["role_a", "nonexistent_role"])
        scopes = mscope.model_scopes_for_recovery_target(target, contract_by_child)
        self.assertEqual(scopes, [("c4", "c4#r1", "role_a")])

    def test_mixed_deterministic_and_model_roles_yields_only_the_model_one(self):
        contract_by_child = {
            "c4": _contract("c4", [_req("c4#r1", {"role_a": _spec(), "role_b": _spec("achieved_outcome_predicate")})])
        }
        target = self._target("c4", "c4#r1", ["role_a", "role_b"])
        self.assertEqual(
            mscope.model_scopes_for_recovery_target(target, contract_by_child), [("c4", "c4#r1", "role_a")]
        )

    def test_never_uses_target_id_reason_or_goal_mode_as_scope_identity(self):
        """Confirms the audit's §17 finding structurally: a target dict with no target_id/reason/
        goal_mode keys at all still projects correctly -- those fields are never read."""
        contract_by_child = {"c4": _contract("c4", [_req("c4#r1", {"role_a": _spec()})])}
        target = {"search_child_id": "c4", "requirement_id": "c4#r1", "target_roles": ["role_a"]}
        self.assertNotIn("target_id", target)
        self.assertEqual(
            mscope.model_scopes_for_recovery_target(target, contract_by_child), [("c4", "c4#r1", "role_a")]
        )


if __name__ == "__main__":
    unittest.main()
