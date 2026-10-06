"""Phase 18 implementation: instance-grounded, multi-observation, order-invariant
direction/effectiveness. See PHASE18_DIRECTION_EFFECTIVENESS_SEMANTICS_RESULTS.md (the audit) and
PHASE18_DIRECTION_EFFECTIVENESS_IMPLEMENTATION_RESULTS.md (this work) for the full design
rationale. Every fixture here is literal; no model call, no network call, no `.local/` dependency.
"""

import unittest

from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt

# ---------------------------------------------------------------------------------------------
# Shared fixture builders
# ---------------------------------------------------------------------------------------------


def _prop(pid, paper_id, quote, children, chunk="c1", span="s1", text=None):
    return {
        "proposition_id": pid,
        "proposition_text": text or quote,
        "paper_id": paper_id,
        "quote": quote,
        "evidence_anchor_chunk_id": chunk,
        "evidence_span_id": span,
        "responsive_obligation_ids": list(children),
        "anchors": [],
        "verification": {},
    }


def _span(paper_id, chunk_id, span_id, text):
    return {"paper_id": paper_id, "chunk_id": chunk_id, "span_id": span_id, "text": text}


def _sealed(props):
    spans = [_span(p["paper_id"], p["evidence_anchor_chunk_id"], p["evidence_span_id"], p["quote"]) for p in props]
    return {"verified_propositions": props, "evidence_spans": spans}


def _binding(role, *, proposition_id, state="filled", candidate_source="model_mapping", supporting=None):
    provenance = {"candidate_source": candidate_source, "detail": "", "model": None}
    if supporting:
        provenance["supporting_proposition_ids"] = list(supporting)
    return se.new_role_binding(role, state=state, proposition_id=proposition_id, provenance=provenance)


def _effectiveness_requirement(req_id="t#suff:effectiveness", multi_instance=True):
    specs = {
        "intervention": se.new_role_spec("intervention", "a named intervention", "model_nomination_only"),
        "target_manifestation": se.new_role_spec("target_manifestation", "target", "model_nomination_only"),
        "observed_effect_or_outcome": se.new_role_spec(
            "observed_effect_or_outcome", "outcome", "model_nomination_only"
        ),
    }
    completion = se.new_role_completion(
        required_roles=["intervention", "target_manifestation", "observed_effect_or_outcome"]
    )
    return se.new_requirement(
        req_id,
        "relational",
        specs,
        completion,
        "exists",
        multi_instance=multi_instance,
        effectiveness=se.new_effectiveness_assessment(),
    )


def _direction_requirement(req_id="t#suff:direction"):
    specs = {
        "named_brain_region_or_network": se.new_role_spec(
            "named_brain_region_or_network", "region", "model_nomination_only"
        ),
        "behavior_or_behavioral_measure": se.new_role_spec(
            "behavior_or_behavioral_measure", "behavior", "model_nomination_only"
        ),
    }
    completion = se.new_role_completion(
        required_roles=["named_brain_region_or_network", "behavior_or_behavioral_measure"]
    )
    return se.new_requirement(
        req_id,
        "relational",
        specs,
        completion,
        "exists",
        parent_context_roles=["named_brain_region_or_network"],
        direction=se.new_direction_assessment(),
    )


def _two_role_joint_requirement(req_id="t#suff:joint"):
    """A relational requirement with TWO own-evidence roles (no parent context) that must
    jointly-ground via `same_proposition` -- the directive's own adversarial shape."""
    specs = {
        "a_role": se.new_role_spec("a_role", "role a", "model_nomination_only"),
        "b_role": se.new_role_spec("b_role", "role b", "model_nomination_only"),
    }
    completion = se.new_role_completion(required_roles=["a_role", "b_role"])
    return se.new_requirement(
        req_id, "relational", specs, completion, "exists", effectiveness=se.new_effectiveness_assessment()
    )


def _instance(role_bindings, *, instance_key=None, complete=True):
    inst = se.new_instance(instance_key)
    inst["role_bindings"] = role_bindings
    inst["complete"] = complete
    inst["state"] = "filled" if complete else "partially_filled"
    return inst


def _child_units(sealed, child_id):
    return sd.units_by_child(sealed)[child_id]


# ---------------------------------------------------------------------------------------------
# A. `se.relationship_witness_support_ids` -- the joint-grounding witness, not naive union
# ---------------------------------------------------------------------------------------------


class RelationshipWitnessSupportIdsTests(unittest.TestCase):
    def test_single_own_evidence_role_returns_that_roles_own_support_set(self):
        completion = se.new_role_completion(required_roles=["a_role", "parent_role"])
        bindings = {
            "a_role": _binding("a_role", proposition_id="p1", supporting=["p1", "p2"]),
            "parent_role": _binding("parent_role", proposition_id="pX", candidate_source="parent_context"),
        }
        witness = se.relationship_witness_support_ids(completion, bindings, ("same_proposition",))
        self.assertEqual(witness, {"p1", "p2"})

    def test_parent_context_binding_never_contributes(self):
        completion = se.new_role_completion(required_roles=["parent_role"])
        bindings = {"parent_role": _binding("parent_role", proposition_id="pX", candidate_source="parent_context")}
        witness = se.relationship_witness_support_ids(completion, bindings, ("same_proposition",))
        self.assertEqual(witness, set())

    def test_adversarial_joint_witness_is_the_shared_proposition_not_the_union(self):
        """A={p1,p2}, B={p1,p3}; same_proposition(A,B). Only p1 jointly witnesses the
        relationship -- p2/p3 individually support one role each but neither alone establishes
        the relationship. The witness must be {p1}, never the union {p1,p2,p3}."""
        completion = se.new_role_completion(required_roles=["a_role", "b_role"])
        bindings = {
            "a_role": _binding("a_role", proposition_id="p1", supporting=["p1", "p2"]),
            "b_role": _binding("b_role", proposition_id="p1", supporting=["p1", "p3"]),
        }
        witness = se.relationship_witness_support_ids(completion, bindings, ("same_proposition",))
        self.assertEqual(witness, {"p1"})

    def test_no_shared_proposition_among_two_own_evidence_roles_yields_empty_witness(self):
        """Joint grounding FAILED (no shared proposition) -- there is no proposition-level
        witness for this (incomplete) instance's relationship; never fall back to union."""
        completion = se.new_role_completion(required_roles=["a_role", "b_role"])
        bindings = {
            "a_role": _binding("a_role", proposition_id="p1"),
            "b_role": _binding("b_role", proposition_id="p2"),
        }
        witness = se.relationship_witness_support_ids(completion, bindings, ("same_proposition",))
        self.assertEqual(witness, set())

    def test_missing_role_binding_contributes_nothing(self):
        completion = se.new_role_completion(required_roles=["a_role"])
        bindings = {"a_role": se.new_role_binding("a_role", state="missing", reason="not_found")}
        witness = se.relationship_witness_support_ids(completion, bindings, ("same_proposition",))
        self.assertEqual(witness, set())


# ---------------------------------------------------------------------------------------------
# B. `sm.find_direction_observations` / `find_effectiveness_observations` -- plural, all-matches
# ---------------------------------------------------------------------------------------------


class FindObservationsTests(unittest.TestCase):
    def test_one_complete_instance_one_grounded_direction(self):
        req = _direction_requirement()
        sealed = _sealed(
            [_prop("p1", 1, "Activity in the amygdala correlated with a negative attitude change.", ["c"])]
        )
        units = _child_units(sealed, "c")
        # v2 is the recorded historical behaviour this test pins; v3 has its own tests.
        obs = sm.find_direction_observations(req, units, semantics_version=se.SUFFICIENCY_SEMANTICS_V2)
        self.assertEqual(len(obs), 1)
        self.assertTrue(obs[0]["reported"])
        self.assertEqual(obs[0]["sign"], "negative")
        self.assertEqual(obs[0]["proposition_id"], "p1")

    def test_one_complete_instance_one_grounded_effectiveness(self):
        req = _effectiveness_requirement()
        sealed = _sealed([_prop("p1", 1, "Intervention X showed decreased bias scores in the treatment group.", ["c"])])
        units = _child_units(sealed, "c")
        obs = sm.find_effectiveness_observations(req, units)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["conclusion"], "supported")
        self.assertEqual(obs[0]["proposition_id"], "p1")

    def test_undeclared_field_returns_empty_list_not_none(self):
        req = {"direction": None, "effectiveness": None}
        self.assertEqual(sm.find_direction_observations(req, [], semantics_version=se.SUFFICIENCY_SEMANTICS_V2), [])
        self.assertEqual(sm.find_effectiveness_observations(req, []), [])

    def test_collects_every_admissible_match_not_just_first(self):
        req = _effectiveness_requirement()
        sealed = _sealed(
            [
                _prop("p1", 1, "Intervention X showed decreased bias scores.", ["c"]),
                _prop("p2", 1, "Intervention X also showed increased accuracy on a second measure.", ["c"]),
            ]
        )
        units = _child_units(sealed, "c")
        obs = sm.find_effectiveness_observations(req, units)
        self.assertEqual(len(obs), 2)

    def test_one_physical_unit_two_admissible_proposition_ids_yields_one_observation(self):
        """Directive F: a deduplicated unit with 2 admissible proposition aliases must not create
        fake corroboration -- exactly one observation, using the lexicographically-min admissible
        id as its deterministic representative."""
        req = _effectiveness_requirement()
        unit = {
            "unit_id": "U1",
            "passage": "Intervention X showed decreased bias scores.",
            "proposition_ids": ["p9", "p2"],
            "flags": {"negated": False, "absence_statement": False},
        }
        obs = sm.find_effectiveness_observations(req, [unit])
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["proposition_id"], "p2")


# ---------------------------------------------------------------------------------------------
# C. `sd.compute_direction_and_effectiveness` -- full orchestration
# ---------------------------------------------------------------------------------------------


class ComputeDirectionAndEffectivenessTests(unittest.TestCase):
    def _run(self, sealed, req):
        contract = se.new_contract("c", [req])
        sd.compute_direction_and_effectiveness(
            sealed, {"c": contract}, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
        return contract["requirements"][0]

    def test_irrelevant_earlier_unit_cannot_hijack_instance_effectiveness(self):
        req = _effectiveness_requirement(multi_instance=False)
        p_irrelevant = _prop(
            "pZ", 2, "An unrelated aside: Intervention Z showed no effect in a different study.", ["c"]
        )
        p_target = _prop("pA", 1, "Intervention X showed decreased bias scores in the treatment group.", ["c"])
        sealed = _sealed([p_irrelevant, p_target])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                }
            )
        ]
        result = self._run(sealed, req)
        obs = result["instances"][0]["effectiveness_observations"]
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["proposition_id"], "pA")
        self.assertEqual(obs[0]["conclusion"], "supported")

    def test_irrelevant_earlier_unit_cannot_hijack_instance_direction(self):
        req = _direction_requirement()
        p_irrelevant = _prop("pZ", 2, "An unrelated aside reports a negative trend elsewhere.", ["c"])
        p_region = _prop("pR", 1, "The amygdala was examined.", ["c"])
        p_target = _prop("pA", 1, "Amygdala activity correlated with a positive attitude shift.", ["c"])
        sealed = _sealed([p_irrelevant, p_region, p_target])
        req["instances"] = [
            _instance(
                {
                    "named_brain_region_or_network": _binding(
                        "named_brain_region_or_network", proposition_id="pR", candidate_source="parent_context"
                    ),
                    "behavior_or_behavioral_measure": _binding("behavior_or_behavioral_measure", proposition_id="pA"),
                }
            )
        ]
        result = self._run(sealed, req)
        obs = result["instances"][0]["direction_observations"]
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["proposition_id"], "pA")
        self.assertEqual(obs[0]["sign"], "positive")

    def test_parent_context_cannot_supply_childs_direction(self):
        """Directive D: inherited parent proposition has STRONG directional language; the child's
        own relationship evidence does not. Expected: child direction stays missing."""
        req = _direction_requirement()
        p_region = _prop("pR", 1, "The amygdala showed a strongly negative and dramatic decrease overall.", ["c"])
        p_behavior = _prop("pB", 1, "A behavioral measure was also collected from the same sample.", ["c"])
        sealed = _sealed([p_region, p_behavior])
        req["instances"] = [
            _instance(
                {
                    "named_brain_region_or_network": _binding(
                        "named_brain_region_or_network", proposition_id="pR", candidate_source="parent_context"
                    ),
                    "behavior_or_behavioral_measure": _binding("behavior_or_behavioral_measure", proposition_id="pB"),
                }
            )
        ]
        result = self._run(sealed, req)
        obs = result["instances"][0]["direction_observations"]
        self.assertEqual(obs, [])

    def test_adversarial_joint_witness_blocks_an_unwitnessed_directional_proposition(self):
        """Directive C's exact adversarial case, run through the full orchestration: A={p1,p2},
        B={p1,p3}, same_proposition(A,B); p2 is directional, p1 is not. p2 must NOT annotate."""
        req = _two_role_joint_requirement()
        p1 = _prop("p1", 1, "Both measures were collected from the same sample in this session.", ["c"])
        p2 = _prop("p2", 1, "Intervention X showed decreased bias scores in that session.", ["c"])
        p3 = _prop("p3", 1, "A third, unrelated measure was also logged separately.", ["c"])
        sealed = _sealed([p1, p2, p3])
        req["instances"] = [
            _instance(
                {
                    "a_role": _binding("a_role", proposition_id="p1", supporting=["p1", "p2"]),
                    "b_role": _binding("b_role", proposition_id="p1", supporting=["p1", "p3"]),
                }
            )
        ]
        result = self._run(sealed, req)
        obs = result["instances"][0]["effectiveness_observations"]
        self.assertEqual(obs, [], "p2's directional language must not leak in through the broad union")

    def test_proposition_order_permutation_invariance(self):
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 1, "No significant effect of Intervention Y was observed.", ["c"])
        req_bindings = {
            "intervention": _binding("intervention", proposition_id="pA"),
            "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
            "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
        }

        def run(order):
            r = _effectiveness_requirement(multi_instance=False)
            r["instances"] = [_instance(dict(req_bindings))]
            sd.compute_direction_and_effectiveness(
                _sealed(order), {"c": se.new_contract("c", [r])}, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
            )
            return r["instances"][0]["effectiveness_observations"]

        forward = run([pA, pB])
        reverse = run([pB, pA])
        self.assertEqual(forward, reverse)

    def test_unit_order_permutation_invariance(self):
        # Same mechanism as proposition-order invariance here (1 proposition : 1 unit in these
        # fixtures) -- kept as its own named test per the directive's own enumerated matrix.
        self.test_proposition_order_permutation_invariance()

    def test_role_binding_order_permutation_invariance(self):
        p1 = _prop("p1", 1, "Both measures were collected together.", ["c"])
        p2 = _prop("p2", 1, "Intervention X showed decreased bias scores.", ["c"])
        sealed = _sealed([p1, p2])

        def run(bindings):
            r = _two_role_joint_requirement()
            r["instances"] = [_instance(bindings)]
            sd.compute_direction_and_effectiveness(
                sealed, {"c": se.new_contract("c", [r])}, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
            )
            return r["instances"][0]["effectiveness_observations"]

        b1 = {
            "a_role": _binding("a_role", proposition_id="p1", supporting=["p1", "p2"]),
            "b_role": _binding("b_role", proposition_id="p1"),
        }
        b2 = {
            "b_role": _binding("b_role", proposition_id="p1"),
            "a_role": _binding("a_role", proposition_id="p1", supporting=["p1", "p2"]),
        }
        self.assertEqual(run(b1), run(b2))

    def test_supporting_proposition_ids_order_permutation_invariance(self):
        completion = se.new_role_completion(required_roles=["a_role"])
        b_forward = {"a_role": _binding("a_role", proposition_id="p1", supporting=["p1", "p2"])}
        b_reverse = {"a_role": _binding("a_role", proposition_id="p1", supporting=["p2", "p1"])}
        w1 = se.relationship_witness_support_ids(completion, b_forward, ("same_proposition",))
        w2 = se.relationship_witness_support_ids(completion, b_reverse, ("same_proposition",))
        self.assertEqual(w1, w2)

    def test_two_agreeing_observations_same_instance_preserve_both_provenance_trails(self):
        req = _effectiveness_requirement(multi_instance=False)
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 1, "Intervention X also showed decreased reaction times on a second task.", ["c"])
        sealed = _sealed([pA, pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA", supporting=["pA", "pB"]),
                    "target_manifestation": _binding(
                        "target_manifestation", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                    "observed_effect_or_outcome": _binding(
                        "observed_effect_or_outcome", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                }
            )
        ]
        result = self._run(sealed, req)
        obs = result["instances"][0]["effectiveness_observations"]
        self.assertEqual(len(obs), 2)
        self.assertEqual({o["proposition_id"] for o in obs}, {"pA", "pB"})
        self.assertTrue(all(o["conclusion"] == "supported" for o in obs))

    def test_two_disagreeing_observations_same_instance_is_within_instance_conflict(self):
        req = _effectiveness_requirement(multi_instance=False)
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 1, "No significant effect of Intervention X was also observed on a second task.", ["c"])
        sealed = _sealed([pA, pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA", supporting=["pA", "pB"]),
                    "target_manifestation": _binding(
                        "target_manifestation", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                    "observed_effect_or_outcome": _binding(
                        "observed_effect_or_outcome", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                }
            )
        ]
        result = self._run(sealed, req)
        summary = result["effectiveness_summary"]
        self.assertTrue(summary["has_within_instance_conflict"])
        self.assertFalse(summary["has_across_instance_heterogeneity"])
        self.assertIsNone(summary["consensus_value"])

    def test_two_different_complete_instances_same_value_no_heterogeneity(self):
        req = _effectiveness_requirement()
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 2, "Intervention Y showed decreased bias scores too.", ["c"])
        sealed = _sealed([pA, pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                },
                instance_key="i1",
            ),
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pB"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pB"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pB"),
                },
                instance_key="i2",
            ),
        ]
        result = self._run(sealed, req)
        summary = result["effectiveness_summary"]
        self.assertEqual(summary["consensus_value"], "supported")
        self.assertFalse(summary["has_across_instance_heterogeneity"])

    def test_two_different_complete_instances_different_values_is_heterogeneity(self):
        req = _effectiveness_requirement()
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 2, "No significant effect of Intervention Y was observed.", ["c"])
        sealed = _sealed([pA, pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                },
                instance_key="i1",
            ),
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pB"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pB"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pB"),
                },
                instance_key="i2",
            ),
        ]
        result = self._run(sealed, req)
        summary = result["effectiveness_summary"]
        self.assertIsNone(summary["consensus_value"])
        self.assertTrue(summary["has_across_instance_heterogeneity"])
        self.assertFalse(summary["has_within_instance_conflict"])

    def test_one_conflicted_instance_only_conflict_true_heterogeneity_false(self):
        req = _effectiveness_requirement(multi_instance=False)
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 1, "No significant effect of Intervention X was also observed on a second task.", ["c"])
        sealed = _sealed([pA, pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA", supporting=["pA", "pB"]),
                    "target_manifestation": _binding(
                        "target_manifestation", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                    "observed_effect_or_outcome": _binding(
                        "observed_effect_or_outcome", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                }
            )
        ]
        result = self._run(sealed, req)
        summary = result["effectiveness_summary"]
        self.assertTrue(summary["has_within_instance_conflict"])
        self.assertFalse(summary["has_across_instance_heterogeneity"])

    def test_heterogeneity_and_within_instance_conflict_can_co_occur(self):
        # Needs THREE instances to demonstrate real co-occurrence: one internally conflicted
        # (contributes no resolved value at all) plus two OTHER resolved instances that disagree
        # with each other -- heterogeneity is about resolved values disagreeing, which a lone
        # conflicted instance (with zero resolved values of its own) cannot by itself produce.
        req = _effectiveness_requirement()
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 1, "No significant effect of Intervention X was also observed on a second task.", ["c"])
        pC = _prop("pC", 2, "Intervention Z showed decreased bias scores too.", ["c"])
        pD = _prop("pD", 3, "No significant effect of Intervention W was observed.", ["c"])
        sealed = _sealed([pA, pB, pC, pD])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA", supporting=["pA", "pB"]),
                    "target_manifestation": _binding(
                        "target_manifestation", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                    "observed_effect_or_outcome": _binding(
                        "observed_effect_or_outcome", proposition_id="pA", supporting=["pA", "pB"]
                    ),
                },
                instance_key="conflicted",
            ),
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pC"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pC"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pC"),
                },
                instance_key="clean_supported",
            ),
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pD"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pD"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pD"),
                },
                instance_key="clean_not_supported",
            ),
        ]
        result = self._run(sealed, req)
        summary = result["effectiveness_summary"]
        self.assertTrue(summary["has_within_instance_conflict"])
        self.assertTrue(summary["has_across_instance_heterogeneity"])
        self.assertIsNone(summary["consensus_value"])

    def test_one_resolved_plus_one_missing_complete_instance(self):
        req = _effectiveness_requirement()
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 2, "A plain description with no result language at all.", ["c"])
        sealed = _sealed([pA, pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                },
                instance_key="resolved",
            ),
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pB"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pB"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pB"),
                },
                instance_key="missing",
            ),
        ]
        result = self._run(sealed, req)
        summary = result["effectiveness_summary"]
        self.assertEqual(summary["consensus_value"], "supported")
        self.assertIn("missing", summary["instance_keys_missing_observations"])
        self.assertNotIn("missing", summary["instance_keys_with_observations"])

    def test_incomplete_instance_observation_does_not_enter_requirement_summary(self):
        req = _effectiveness_requirement()
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        pB = _prop("pB", 2, "No significant effect of Intervention Y was observed.", ["c"])
        sealed = _sealed([pA, pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                },
                instance_key="complete",
            ),
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pB"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pB"),
                },
                instance_key="incomplete",
                complete=False,
            ),
        ]
        result = self._run(sealed, req)
        obs_incomplete = result["instances"][1]["effectiveness_observations"]
        # Directive H: diagnostic metadata IS still computed for an incomplete instance whenever
        # admissible own evidence exists among whichever roles it DID manage to fill (here, 2 of
        # the 3 required roles are filled and jointly witness pB) -- that's correct, not a bug.
        # What must hold is that this incomplete instance's own observation never reaches the
        # trusted requirement-level summary.
        self.assertEqual(len(obs_incomplete), 1)
        self.assertEqual(obs_incomplete[0]["proposition_id"], "pB")
        summary = result["effectiveness_summary"]
        self.assertNotIn("incomplete", summary["complete_instance_keys"])
        self.assertEqual(summary["consensus_value"], "supported")

    def test_null_not_supported_remains_distinguishable_from_missing(self):
        req = _effectiveness_requirement(multi_instance=False)
        pB = _prop("pB", 1, "No significant effect of Intervention Y was observed.", ["c"])
        sealed = _sealed([pB])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pB"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pB"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pB"),
                }
            )
        ]
        result = self._run(sealed, req)
        obs = result["instances"][0]["effectiveness_observations"]
        self.assertEqual(len(obs), 1)
        self.assertTrue(obs[0]["outcome_reported"])
        self.assertEqual(obs[0]["conclusion"], "not_supported")

        empty_req = _effectiveness_requirement(multi_instance=False, req_id="t#suff:empty")
        empty_req["instances"] = [
            _instance({"intervention": se.new_role_binding("intervention", state="missing", reason="not_found")})
        ]
        empty_sealed = _sealed([])
        empty_result = self._run(empty_sealed, empty_req)
        self.assertEqual(empty_result["instances"][0]["effectiveness_observations"], [])

    def test_authored_direction_effectiveness_template_remains_unchanged(self):
        req = _effectiveness_requirement(multi_instance=False)
        template_before = dict(req["effectiveness"])
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        sealed = _sealed([pA])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                }
            )
        ]
        result = self._run(sealed, req)
        self.assertEqual(result["effectiveness"], template_before)
        self.assertIn("effectiveness_summary", result)

    def test_runtime_summary_excluded_from_frozen_hash_view(self):
        req = _effectiveness_requirement(multi_instance=False)
        req["effectiveness_summary"] = {"consensus_value": "supported"}  # simulate a populated run
        contract = se.new_contract("c", [req])
        frozen = se.frozen_view(contract)
        self.assertNotIn("effectiveness_summary", frozen["requirements"][0])

    def test_idempotence_replaces_from_scratch_never_appends(self):
        req = _effectiveness_requirement(multi_instance=False)
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        sealed = _sealed([pA])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                }
            )
        ]
        contract = se.new_contract("c", [req])
        sd.compute_direction_and_effectiveness(
            sealed, {"c": contract}, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
        first = contract["requirements"][0]["instances"][0]["effectiveness_observations"]
        sd.compute_direction_and_effectiveness(
            sealed, {"c": contract}, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
        second = contract["requirements"][0]["instances"][0]["effectiveness_observations"]
        self.assertEqual(first, second)
        self.assertEqual(len(second), 1)

    def test_aggregate_state_complete_reason_byte_identical_before_and_after(self):
        req = _effectiveness_requirement(multi_instance=False)
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        sealed = _sealed([pA])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                }
            )
        ]
        before = (req["state"], req["reason"], req["instances"][0]["complete"], req["instances"][0]["state"])
        self._run(sealed, req)
        after = (req["state"], req["reason"], req["instances"][0]["complete"], req["instances"][0]["state"])
        self.assertEqual(before, after)

    def test_recovery_target_inventory_byte_identical_before_and_after(self):
        req = _effectiveness_requirement(multi_instance=False)
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["c"])
        sealed = _sealed([pA])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": se.new_role_binding(
                        "observed_effect_or_outcome", state="missing", reason="not_found"
                    ),
                }
            )
        ]
        mapped = {"c": se.new_contract("c", [req])}
        before = srt.compute_recovery_targets(mapped, {})
        self._run(sealed, req)
        after = srt.compute_recovery_targets(mapped, {})
        self.assertEqual(before, after)

    def test_no_q_aib_specific_runtime_vocabulary(self):
        """The new functions are generic over any requirement shape -- confirmed here with a
        wholly invented child/requirement id that doesn't exist in the real q_aib contract."""
        req = _effectiveness_requirement(req_id="zzz_custom#suff:made-up")
        pA = _prop("pA", 1, "Intervention X showed decreased bias scores.", ["zzz"])
        sealed = _sealed([pA])
        req["instances"] = [
            _instance(
                {
                    "intervention": _binding("intervention", proposition_id="pA"),
                    "target_manifestation": _binding("target_manifestation", proposition_id="pA"),
                    "observed_effect_or_outcome": _binding("observed_effect_or_outcome", proposition_id="pA"),
                }
            )
        ]
        contract = se.new_contract("zzz", [req])
        sd.compute_direction_and_effectiveness(
            sealed, {"zzz": contract}, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
        self.assertEqual(len(contract["requirements"][0]["instances"][0]["effectiveness_observations"]), 1)


if __name__ == "__main__":
    unittest.main()
