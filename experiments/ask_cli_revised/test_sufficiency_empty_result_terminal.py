"""Phase 27b: scoped-search terminality for allowed-empty requirements (Option A), at the sufficiency layer.

Pure and offline. Requirements are built from the real `sufficiency_engine` constructors and recomputed through
`recompute_requirement`, so states and reasons come from the same code the pipeline runs. The contract is:

- `empty_result_semantically_allowed=True` changes nothing about the INITIAL inventory (the search obligation stays).
- Only a genuinely empty requirement whose scoped search completed becomes terminal, and then ONLY its zero-evidence
  deficit is removed. Partial, relational, ambiguous, and corroborating obligations always remain.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt

REQ = "x#suff:req"
COMPLETED = "recovery_no_new_evidence"


def _spec(role, quantifier_hint="achieved_outcome_predicate"):
    return se.new_role_spec(role, f"category {role}", quantifier_hint)


def _filled(role, prop_id):
    return se.new_role_binding(
        role,
        state="filled",
        proposition_id=prop_id,
        exact_text=f"text for {role}",
        provenance={"candidate_source": "deterministic_mapping", "detail": "", "model": None},
    )


def _ambiguous(role):
    return se.new_role_binding(role, state="ambiguous", reason="evidence_conflicting")


def _missing(role):
    return se.new_role_binding(role, state="missing", reason="not_found")


def _requirement(
    *,
    allowed,
    filled=(),
    ambiguous=(),
    quantifier="exists",
    quantifier_n=None,
    roles=("named", "bears"),
    relational_unverified=False,
    instances=1,
    req_id=REQ,
):
    """A requirement with `instances` instances. Bindings listed in `filled`/`ambiguous` are set on instance 0; every
    other role is `missing`. `instances=0` builds a zero-instance requirement."""
    specs = {role: _spec(role) for role in roles}
    completion = se.new_role_completion(required_roles=list(roles))
    req = se.new_requirement(
        req_id,
        "atomic",
        specs,
        completion,
        quantifier,
        quantifier_n=quantifier_n,
        empty_result_semantically_allowed=allowed,
    )
    for index in range(instances):
        inst = se.new_instance(f"i{index}")
        for role in roles:
            if index == 0 and role in filled:
                inst["role_bindings"][role] = _filled(role, f"p-{role}")
            elif index == 0 and role in ambiguous:
                inst["role_bindings"][role] = _ambiguous(role)
            else:
                inst["role_bindings"][role] = _missing(role)
        req["instances"].append(inst)
    return se.recompute_requirement(req)


def _map(requirement):
    return {"x": se.new_contract("x", [requirement])}


def _status(requirement_id, *, terminal):
    return {
        requirement_id: se.new_search_status(requirement_id, scoped_search_completed_no_additional_support=terminal)
    }


def _targets(requirement, status=None):
    return srt.compute_recovery_targets(_map(requirement), {}, status)


def _log_row(target_id, reason_code, *, gap_extra=None):
    gap = {"field_id": "x", "subquestion_id": "x", "display": "", "note": "", "_recovery_target_id": target_id}
    gap.update(gap_extra or {})
    return {"gap": gap, "action": "LEGACY", "reason_code": reason_code, "new_verified": 0}


class GenuinelyEmptyPredicateTests(unittest.TestCase):
    def test_all_missing_is_genuinely_empty(self):
        self.assertTrue(srt.is_genuinely_empty(_requirement(allowed=True)))

    def test_zero_instances_is_genuinely_empty(self):
        self.assertTrue(srt.is_genuinely_empty(_requirement(allowed=True, instances=0)))

    def test_any_filled_binding_is_evidence(self):
        self.assertFalse(srt.is_genuinely_empty(_requirement(allowed=True, filled=("named",))))

    def test_any_ambiguous_binding_is_evidence_not_emptiness(self):
        self.assertFalse(srt.is_genuinely_empty(_requirement(allowed=True, ambiguous=("named",))))

    def test_terminal_eligibility_requires_the_authored_permission(self):
        self.assertFalse(srt.is_zero_evidence_terminal(_requirement(allowed=False)))
        self.assertTrue(srt.is_zero_evidence_terminal(_requirement(allowed=True)))


class StructuredSearchOutcomesTests(unittest.TestCase):
    def _initial(self):
        return srt.compute_recovery_targets(_map(_requirement(allowed=True)), {})

    def test_completed_rows_complete_the_requirement(self):
        inventory = self._initial()
        log = [_log_row(tid, COMPLETED) for tid in inventory]
        outcome = srt.structured_search_outcomes(inventory, log)[REQ]
        self.assertTrue(outcome["completed"])
        self.assertEqual({s["state"] for s in outcome["target_states"].values()}, {"completed"})

    def test_a_planned_no_search_is_not_completion(self):
        inventory = self._initial()
        log = [_log_row(tid, "plan_no_search") for tid in inventory]
        outcome = srt.structured_search_outcomes(inventory, log)[REQ]
        self.assertFalse(outcome["completed"])
        self.assertEqual({s["reason_code"] for s in outcome["target_states"].values()}, {"plan_no_search"})

    def test_a_mechanical_no_answer_query_is_not_completion(self):
        inventory = self._initial()
        log = [_log_row(tid, "recovery_query_no_answer") for tid in inventory]
        self.assertFalse(srt.structured_search_outcomes(inventory, log)[REQ]["completed"])

    def test_a_target_with_no_log_row_was_not_attempted(self):
        inventory = self._initial()
        outcome = srt.structured_search_outcomes(inventory, [])[REQ]
        self.assertFalse(outcome["completed"])
        self.assertEqual({s["state"] for s in outcome["target_states"].values()}, {"not_attempted"})

    def test_a_generic_child_gap_never_proves_structured_completion(self):
        inventory = self._initial()
        generic = [{"gap": {"field_id": "x", "subquestion_id": "x", "display": "generic"}, "reason_code": COMPLETED}]
        self.assertFalse(srt.structured_search_outcomes(inventory, generic)[REQ]["completed"])

    def test_more_than_one_row_naming_a_target_is_not_completion(self):
        inventory = self._initial()
        tid = next(iter(inventory))
        log = [_log_row(tid, COMPLETED), _log_row(tid, COMPLETED)]
        outcome = srt.structured_search_outcomes(inventory, log)[REQ]
        self.assertFalse(outcome["completed"])
        self.assertEqual(outcome["target_states"][tid]["reason_code"], "ambiguous_log_rows")

    def test_one_unfinished_target_keeps_the_whole_requirement_unterminated(self):
        """Requirement-level conservatism: one query finding nothing is not the requirement being searched enough."""
        req = _requirement(allowed=True)
        inventory = srt.compute_recovery_targets(_map(req), {})
        self.assertEqual(len(inventory), 2)
        first, second = sorted(inventory)
        log = [_log_row(first, COMPLETED)]  # `second` never ran
        outcome = srt.structured_search_outcomes(inventory, log)[REQ]
        self.assertFalse(outcome["completed"])
        self.assertEqual(outcome["target_states"][second]["state"], "not_attempted")


class TerminalSearchStatusTests(unittest.TestCase):
    def _round_outcome(self, completed):
        return {REQ: {"completed": completed, "target_states": {"t": {"state": "completed", "reason_code": COMPLETED}}}}

    def test_completed_search_on_a_genuinely_empty_allowed_requirement_is_terminal(self):
        req = _requirement(allowed=True)
        status = srt.terminal_search_status(_map(req), self._round_outcome(True))
        self.assertTrue(status[REQ]["terminal"])
        self.assertTrue(status[REQ]["completed"])

    def test_completed_search_without_the_permission_is_not_terminal(self):
        req = _requirement(allowed=False)
        self.assertFalse(srt.terminal_search_status(_map(req), self._round_outcome(True))[REQ]["terminal"])

    def test_an_incomplete_search_is_never_terminal(self):
        req = _requirement(allowed=True)
        self.assertFalse(srt.terminal_search_status(_map(req), self._round_outcome(False))[REQ]["terminal"])

    def test_a_completed_search_that_found_support_is_not_terminal(self):
        req = _requirement(allowed=True, filled=("named",))
        self.assertFalse(srt.terminal_search_status(_map(req), self._round_outcome(True))[REQ]["terminal"])

    def test_an_ambiguous_final_map_is_not_terminal(self):
        req = _requirement(allowed=True, ambiguous=("named",))
        self.assertFalse(srt.terminal_search_status(_map(req), self._round_outcome(True))[REQ]["terminal"])

    def test_outcomes_for_requirements_absent_from_the_final_map_are_never_terminal(self):
        req = _requirement(allowed=True, req_id="other#req")
        self.assertFalse(srt.terminal_search_status(_map(req), self._round_outcome(True))[REQ]["terminal"])


class FinalTargetGateTests(unittest.TestCase):
    """The initial inventory is computed with no status; the final inventory is computed with the terminal status."""

    def test_no_status_keeps_the_search_obligation(self):
        req = _requirement(allowed=True)
        self.assertEqual(len(_targets(req)), 2)
        self.assertEqual({t["reason"] for t in _targets(req).values()}, {"missing"})

    def test_an_empty_status_map_is_identical_to_no_status(self):
        req = _requirement(allowed=True)
        self.assertEqual(_targets(req), _targets(req, srt.engine_search_status({})))

    def test_terminal_zero_evidence_deficit_is_removed(self):
        req = _requirement(allowed=True)
        status = srt.engine_search_status(
            srt.terminal_search_status(_map(req), {REQ: {"completed": True, "target_states": {}}})
        )
        self.assertEqual(_targets(req, status), {})

    def test_flag_false_keeps_the_identical_target_even_with_a_completed_search(self):
        req = _requirement(allowed=False)
        status = srt.engine_search_status(
            srt.terminal_search_status(_map(req), {REQ: {"completed": True, "target_states": {}}})
        )
        self.assertEqual(_targets(req, status), _targets(req))
        self.assertEqual(len(_targets(req, status)), 2)

    def test_a_stray_flag_on_a_partial_requirement_is_ignored(self):
        """The gate ignores the scoped flag unless the requirement is zero-evidence terminal. A partial requirement keeps
        its own targets even if a status says its search completed."""
        req = _requirement(allowed=True, filled=("named",))
        before = _targets(req)
        status = _status(REQ, terminal=True)
        self.assertEqual(_targets(req, status), before)
        self.assertTrue(before)

    def test_a_stray_flag_on_an_ambiguous_requirement_is_ignored(self):
        req = _requirement(allowed=True, ambiguous=("named",))
        before = _targets(req)
        self.assertEqual(_targets(req, _status(REQ, terminal=True)), before)

    def test_unaffected_target_ids_are_unchanged(self):
        """A second, unrelated requirement's target ids are byte-identical with and without the terminal status."""
        empty = _requirement(allowed=True, req_id="a#req")
        partial = _requirement(allowed=True, filled=("named",), req_id="b#req")
        mapped = {"a": se.new_contract("a", [empty]), "b": se.new_contract("b", [partial])}
        before = srt.compute_recovery_targets(mapped, {}, None)
        after = srt.compute_recovery_targets(
            mapped,
            {},
            srt.engine_search_status(
                {
                    "a#req": {"completed": True, "terminal": True, "target_states": {}},
                }
            ),
        )
        self.assertTrue(set(after) < set(before))
        partial_ids = {tid for tid, t in before.items() if t["requirement_id"] == "b#req"}
        self.assertTrue(partial_ids)
        self.assertTrue(partial_ids <= set(after))
        self.assertEqual({tid: after[tid] for tid in partial_ids}, {tid: before[tid] for tid in partial_ids})


class ObligationShapeMatrixTests(unittest.TestCase):
    """Relevant quantifiers, zero evidence, allowed-empty and completed: the zero-evidence deficit is removed. The same
    shape with the permission off keeps it. No quantifier-specific exception exists."""

    def _zero_evidence_shapes(self, *, allowed):
        yield "exists", _requirement(allowed=allowed)
        yield "exists_zero_instances", _requirement(allowed=allowed, instances=0)
        yield "at_least_n", _requirement(allowed=allowed, quantifier="at_least_n", quantifier_n=2)
        yield "open_list_zero_instances", _requirement(allowed=allowed, quantifier="open_list", instances=0)
        yield (
            "all_requested_categories_zero_instances",
            _requirement(allowed=allowed, quantifier="all_requested_categories", instances=0),
        )
        yield (
            "for_each_discovered_instance_zero_instances",
            _requirement(allowed=allowed, quantifier="for_each_discovered_instance", instances=0),
        )

    def test_every_zero_evidence_shape_with_the_permission_closes_when_completed(self):
        for name, req in self._zero_evidence_shapes(allowed=True):
            with self.subTest(shape=name):
                self.assertTrue(srt.is_genuinely_empty(req))
                status = srt.engine_search_status(
                    srt.terminal_search_status(_map(req), {REQ: {"completed": True, "target_states": {}}})
                )
                self.assertEqual(_targets(req, status), {}, name)

    def test_every_zero_evidence_shape_without_the_permission_keeps_its_targets(self):
        for name, req in self._zero_evidence_shapes(allowed=False):
            with self.subTest(shape=name):
                self.assertTrue(_targets(req), name)
                status = srt.engine_search_status(
                    srt.terminal_search_status(_map(req), {REQ: {"completed": True, "target_states": {}}})
                )
                self.assertEqual(_targets(req, status), _targets(req), name)

    def test_zero_instance_first_instance_target_exists_before_the_search(self):
        req = _requirement(allowed=True, instances=0)
        targets = _targets(req)
        self.assertEqual(len(targets), 2)
        self.assertEqual({t["scope"]["kind"] for t in targets.values()}, {"none"})

    def test_partial_evidence_is_never_suppressed_on_any_shape(self):
        for quantifier, extra in (("exists", {}), ("at_least_n", {"quantifier_n": 2})):
            with self.subTest(quantifier=quantifier):
                req = _requirement(allowed=True, filled=("named",), quantifier=quantifier, **extra)
                before = _targets(req)
                self.assertTrue(before)
                self.assertEqual(_targets(req, _status(REQ, terminal=True)), before)


class PreservedObligationTests(unittest.TestCase):
    def test_relationship_unverified_is_preserved_even_with_the_permission_and_completed_search(self):
        """Two independently filled roles that are not jointly grounded: evidence exists, so the empty-result exemption
        cannot apply. Built with the joint-grounding failure the engine itself produces."""
        req = _requirement(allowed=True, filled=("named", "bears"))
        self.assertFalse(req["instances"][0]["complete"])
        before = _targets(req)
        self.assertTrue(before)
        self.assertTrue(any(t["reason"] == "relationship_unverified" for t in before.values()))
        self.assertEqual(_targets(req, _status(REQ, terminal=True)), before)

    def test_ambiguous_conflicting_evidence_keeps_its_existing_recovery_behavior(self):
        req = _requirement(allowed=True, ambiguous=("named", "bears"))
        self.assertEqual(req["state"], "ambiguous")
        before = _targets(req)
        self.assertEqual(_targets(req, _status(REQ, terminal=True)), before)

    def test_cardinality_deficit_once_qualifying_findings_exist_is_preserved(self):
        req = _requirement(allowed=True, filled=("named", "bears"), quantifier="at_least_n", quantifier_n=3)
        before = _targets(req)
        self.assertEqual(_targets(req, _status(REQ, terminal=True)), before)


class DefaultsUnchangedTests(unittest.TestCase):
    def test_default_false_requirements_are_identical_with_and_without_status_plumbing(self):
        for req in (
            _requirement(allowed=False),
            _requirement(allowed=False, filled=("named",)),
            _requirement(allowed=False, instances=0),
            _requirement(allowed=False, quantifier="at_least_n", quantifier_n=2),
        ):
            with self.subTest(state=req["state"], instances=len(req["instances"])):
                self.assertEqual(_targets(req, srt.engine_search_status({})), _targets(req))


if __name__ == "__main__":
    unittest.main()
