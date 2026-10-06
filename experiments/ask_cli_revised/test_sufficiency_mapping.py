"""Tests for the deterministic-first mapping dispatch (by declared strategy, never role-name
inspection), per-role admissibility, and the explicitly-unbound model-nomination scaffold.
No model, no network, no E2E.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm


def _unit(unit_id, paper_id, passage, proposition_ids=None, proposition_anchor=None):
    flags = oe.passage_flags(passage)
    return {
        "unit_id": unit_id,
        "paper_id": paper_id,
        "passage": passage,
        "proposition_ids": proposition_ids or [f"{unit_id}-p"],
        "flags": flags,
        "attached_children": [],
        # {proposition_id: (paper_id, chunk_id, span_id)} -- omitted (None) by default, matching
        # every pre-Finding-2 test fixture exactly (no anchor info -> nominate_with_model never
        # collapses anything, see its own docstring). Tests exercising Finding 2's anchor-based
        # dedup pass this explicitly.
        "proposition_anchor": proposition_anchor or {},
    }


class AdmissibilityTests(unittest.TestCase):
    def test_no_disqualifying_guards_admits_study_description_and_hedged(self):
        spec = se.new_role_spec("x", "x", "named_instrument_lexicon", disqualifying_guards=())
        guard = {"study_description": True, "hedged": True}
        self.assertTrue(sm.is_admissible(spec, guard))

    def test_hedged_disqualifies_an_outcome_shaped_role(self):
        spec = se.new_role_spec("outcome", "an outcome", "achieved_outcome_predicate", disqualifying_guards=["hedged"])
        self.assertFalse(sm.is_admissible(spec, {"hedged": True}))
        self.assertTrue(sm.is_admissible(spec, {"hedged": False, "absence_statement": True}))

    def test_absence_statement_never_disqualifies_by_default_convention(self):
        """An explicit, unhedged null-result statement is itself valid evidence for an outcome."""
        spec = se.new_role_spec(
            "outcome",
            "an outcome",
            "achieved_outcome_predicate",
            disqualifying_guards=list(sm.ACHIEVED_OUTCOME_DEFAULT_GUARDS),
        )
        self.assertNotIn("absence_statement", spec["disqualifying_guards"])
        self.assertTrue(sm.is_admissible(spec, {"absence_statement": True, "hedged": False}))


class DeterministicDetectorTests(unittest.TestCase):
    def test_named_instrument_lexicon_matches_a_real_instrument_phrase(self):
        text = "The Empathy Scale was used to assess dispositional empathic concern."
        found = sm._deterministic_text_for_role(se.new_role_spec("s", "scale", "named_instrument_lexicon"), text)
        self.assertIsNotNone(found)
        self.assertIn("Empathy Scale", found)

    def test_named_instrument_lexicon_does_not_match_a_bare_mention(self):
        text = "scores on the Explicit Bias Questionnaire)."
        found = sm._deterministic_text_for_role(se.new_role_spec("s", "scale", "named_instrument_lexicon"), text)
        # No trailing measurement verb -- the detector correctly finds nothing, disclosed, not guessed.
        self.assertIsNone(found)

    def test_achieved_outcome_predicate_matches_a_result_word(self):
        text = "The intervention significantly reduced bias scores and was associated with better outcomes."
        found = sm._deterministic_text_for_role(se.new_role_spec("o", "outcome", "achieved_outcome_predicate"), text)
        self.assertEqual(found, text)

    def test_achieved_outcome_predicate_finds_nothing_in_pure_methods_text(self):
        text = "We administered the task to all participants in a quiet room."
        found = sm._deterministic_text_for_role(se.new_role_spec("o", "outcome", "achieved_outcome_predicate"), text)
        self.assertIsNone(found)

    def test_explicit_category_terms_matches_literal_wording_term(self):
        spec = se.new_role_spec(
            "cat", "category", "explicit_category_terms", requested_category_terms=["implicit", "explicit"]
        )
        found = sm._deterministic_text_for_role(spec, "We measured explicit attitudes using a questionnaire.")
        self.assertEqual(found.lower(), "explicit")

    def test_explicit_category_terms_does_not_match_a_synonym_or_acronym(self):
        """Honest, disclosed limitation: a literal-term match misses domain synonyms/acronyms
        (e.g. IAT for "implicit") -- never silently expanded without explicit authorization."""
        spec = se.new_role_spec(
            "cat", "category", "explicit_category_terms", requested_category_terms=["implicit", "explicit"]
        )
        found = sm._deterministic_text_for_role(spec, "We used the IAT to measure attitudes.")
        self.assertIsNone(found)

    def test_direction_or_sign_pattern_finds_a_literal_valence_word(self):
        spec = se.new_role_spec("d", "direction", "direction_or_sign_pattern")
        found = sm._deterministic_text_for_role(spec, "This shows a positive association overall.")
        self.assertEqual(found, "positive")

    def test_direction_or_sign_pattern_is_independent_of_causal_language(self):
        """A correlational result can report a clear direction with zero causal language."""
        text = "Higher scores were associated with greater prosociality in this correlational design."
        found = sm._deterministic_text_for_role(se.new_role_spec("d", "d", "direction_or_sign_pattern"), text)
        self.assertIsNotNone(found)
        flags = oe.passage_flags(text)
        self.assertTrue(flags["correlational"])

    def test_magnitude_word_reports_direction_without_fabricating_a_sign(self):
        word = sm._match_direction_word("Scores decreased significantly after the intervention.")
        self.assertEqual(word, "decreased")
        self.assertIsNone(sm._direction_sign(word))

    def test_literal_positive_negative_words_get_a_sign(self):
        self.assertEqual(sm._direction_sign("positive"), "positive")
        self.assertEqual(sm._direction_sign("negative"), "negative")

    def test_model_nomination_only_has_no_deterministic_detector(self):
        spec = se.new_role_spec("x", "x", "model_nomination_only")
        found = sm._deterministic_text_for_role(spec, "Amygdala activity was observed during the task.")
        self.assertIsNone(found)


class MapRequirementTests(unittest.TestCase):
    def test_identification_role_alone_leaves_instance_incomplete(self):
        """Direct proof: 'HPLC was used' fills identification only, not a result role."""
        specs = {
            "assay": se.new_role_spec("assay", "assay", "named_instrument_lexicon"),
            "result": se.new_role_spec("result", "result", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["assay", "result"])
        req = se.new_requirement("t#req", "atomic", specs, completion, "exists")
        units = [_unit("U1", 1, "An HPLC Scale which measured compound concentration was used.")]
        result = sm.map_requirement(req, units)
        self.assertNotEqual(result["state"], "filled")

    def test_parent_context_alone_never_completes_a_requirement(self):
        """Phase 16: `map_requirement`'s own bespoke `parent_context_bindings` fallback is retired
        -- a parent-context requirement now always routes through `map_paired_requirement`
        (see `MapAnyRequirementDispatchTests`/`ParentEligibilityForkingTests` below). This test's
        original intent is unchanged: inheriting a role from an (eligible) parent must never, by
        itself, complete a requirement whose OTHER role has no evidence."""
        specs = {
            "region": se.new_role_spec("region", "region", "model_nomination_only"),
            "behavior": se.new_role_spec("behavior", "behavior", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["region", "behavior"])
        req = se.new_requirement("r#req", "relational", specs, completion, "exists", parent_context_roles=["region"])

        parent_specs = {"region": se.new_role_spec("region", "region", "model_nomination_only")}
        parent_completion = se.new_role_completion(required_roles=["region"])
        parent_req = se.new_requirement("parent#req", "atomic", parent_specs, parent_completion, "exists")
        parent_inst = se.new_instance()
        parent_inst["role_bindings"]["region"] = se.new_role_binding(
            "region",
            state="filled",
            proposition_id="parent-p1",
            exact_text="amygdala",
            provenance={"candidate_source": "model_mapping", "detail": "", "model": "stub"},
        )
        parent_req["instances"] = [parent_inst]
        parent_req = se.recompute_requirement(parent_req)
        self.assertTrue(parent_req["instances"][0]["complete"])  # eligible: single required role, filled

        # even with the region eligible from a COMPLETE parent instance, no behavior evidence in
        # this child's own candidate units means the requirement stays incomplete.
        units = [_unit("U1", 1, "We administered the task to all participants.")]
        result = sm.map_paired_requirement(req, parent_req, units)
        self.assertNotEqual(result["state"], "filled")

    def test_multi_instance_discovery_one_unit_per_instance(self):
        specs = {"a": se.new_role_spec("a", "a", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("m#req", "atomic", specs, completion, "open_list", multi_instance=True)
        units = [
            _unit("U1", 1, "This finding showed a significant effect."),
            _unit("U2", 2, "We administered a survey to participants."),
        ]
        result = sm.map_requirement(req, units)
        self.assertEqual(len(result["instances"]), 2)
        self.assertTrue(result["instances"][0]["complete"])
        self.assertFalse(result["instances"][1]["complete"])


class CardinalityMappingTests(unittest.TestCase):
    def test_one_category_found_other_missing(self):
        spec = se.new_role_spec(
            "cat", "attitude category", "explicit_category_terms", requested_category_terms=["implicit", "explicit"]
        )
        completion = se.new_role_completion(required_roles=["cat"])
        req = se.new_requirement(
            "c#cat", "cardinality", {"cat": spec}, completion, "all_requested_categories", multi_instance=True
        )
        units = [_unit("U1", 1, "We measured explicit attitudes toward the target group.")]
        result = sm.map_cardinality_requirement(req, units)
        self.assertEqual(result["state"], "partially_filled")
        self.assertEqual(result["reason"], "category_missing")
        keys = {i["instance_key"]: i["complete"] for i in result["instances"]}
        self.assertTrue(keys["explicit"])
        self.assertFalse(keys["implicit"])

    def test_both_categories_found_fills(self):
        spec = se.new_role_spec(
            "cat", "attitude category", "explicit_category_terms", requested_category_terms=["implicit", "explicit"]
        )
        completion = se.new_role_completion(required_roles=["cat"])
        req = se.new_requirement(
            "c#cat", "cardinality", {"cat": spec}, completion, "all_requested_categories", multi_instance=True
        )
        units = [
            _unit("U1", 1, "We measured explicit attitudes toward the target group."),
            _unit("U2", 1, "Implicit attitudes were assessed using a reaction-time task."),
        ]
        result = sm.map_cardinality_requirement(req, units)
        self.assertEqual(result["state"], "filled")

    def test_multi_term_model_nomination_only_under_scoped_authorization_fails_loudly(self):
        """Phase 22 audit finding (dormant, never triggered by any real contract today):
        `map_cardinality_requirement` has no per-term `request_context` at all -- every term's own
        call would share the bare `(child_id, requirement_id, role)` composite key with
        `request_context=None`, exactly the identity collision Phase 19b fixed for
        `build_multi_instances` but never extended here. Must refuse before any model call,
        deterministically, whenever a `model_nomination_only` category role declares more than one
        `requested_category_terms` entry AND scoped (Phase-19/22) authorization is in play."""
        spec = se.new_role_spec(
            "cat", "attitude category", "model_nomination_only", requested_category_terms=["implicit", "explicit"]
        )
        completion = se.new_role_completion(required_roles=["cat"])
        req = se.new_requirement(
            "c#cat", "cardinality", {"cat": spec}, completion, "all_requested_categories", multi_instance=True
        )
        units = [_unit("U1", 1, "We measured explicit attitudes toward the target group.")]
        client = _FakeModelClient({})
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        with self.assertRaises(ValueError):
            sm.map_cardinality_requirement(req, units, model_client=client, child_id="c", nomination_context=ctx)
        self.assertEqual(client.calls, [], "must refuse before any model call, not after one")

    def test_single_term_model_nomination_only_under_scoped_authorization_is_unaffected(self):
        """The guard is scoped to the genuinely unsupported >1-term shape -- a single requested
        term has nothing to collide with and must keep working exactly as before."""
        spec = se.new_role_spec(
            "cat", "attitude category", "model_nomination_only", requested_category_terms=["explicit"]
        )
        completion = se.new_role_completion(required_roles=["cat"])
        req = se.new_requirement(
            "c#cat", "cardinality", {"cat": spec}, completion, "all_requested_categories", multi_instance=True
        )
        units = [_unit("U1", 1, "We measured explicit attitudes toward the target group.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "explicit attitudes"})
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        result = sm.map_cardinality_requirement(req, units, model_client=client, child_id="c", nomination_context=ctx)
        self.assertEqual(result["state"], "filled")

    def test_multi_term_model_nomination_only_without_a_nomination_context_is_unaffected(self):
        """The legacy bare-client path (`nomination_context=None`) never reaches `resolve_
        nomination`'s own composite-key memoization at all, so it has nothing to collide on --
        the guard only fires once scoped authorization is actually in play."""
        spec = se.new_role_spec(
            "cat", "attitude category", "model_nomination_only", requested_category_terms=["implicit", "explicit"]
        )
        completion = se.new_role_completion(required_roles=["cat"])
        req = se.new_requirement(
            "c#cat", "cardinality", {"cat": spec}, completion, "all_requested_categories", multi_instance=True
        )
        units = [_unit("U1", 1, "We measured explicit attitudes toward the target group.")]
        client = _FakeModelClient({})
        result = sm.map_cardinality_requirement(req, units, model_client=client)
        self.assertEqual(result["reason"], "category_missing")


class PairedMappingTests(unittest.TestCase):
    def _parent_requirement_with_one_discovered_trait(self, *, relation_filled=True):
        specs = {
            "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["trait", "relation"])
        parent = se.new_requirement("parent#req", "atomic", specs, completion, "open_list", multi_instance=True)
        instance = se.new_instance("U1")
        instance["role_bindings"]["trait"] = se.new_role_binding(
            "trait",
            state="filled",
            proposition_id="p1",
            exact_text="empathy",
            provenance={"candidate_source": "model_mapping", "detail": "", "model": "stub"},
        )
        if relation_filled:
            # Phase 16: the parent instance must be COMPLETE to be eligible -- "relation" (the
            # parent's OWN other required role) is filled too, from the same proposition so joint
            # grounding trivially succeeds (same_proposition is the default verifier).
            instance["role_bindings"]["relation"] = se.new_role_binding(
                "relation",
                state="filled",
                proposition_id="p1",
                exact_text="relates to the bias",
                provenance={
                    "candidate_source": "deterministic_mapping",
                    "detail": "achieved_outcome_predicate",
                    "model": None,
                },
            )
        else:
            instance["role_bindings"]["relation"] = se.new_role_binding("relation", state="missing", reason="not_found")
        parent["instances"] = [instance]
        return se.recompute_requirement(parent)

    def _child_req(self):
        specs = {
            "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "named scale", "named_instrument_lexicon"),
        }
        completion = se.new_role_completion(required_roles=["trait", "scale"])
        return se.new_requirement(
            "child#req",
            "relational",
            specs,
            completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )

    def test_pairing_scoped_to_parents_currently_discovered_instances(self):
        """The parent instance is COMPLETE (Phase 16 eligibility: trait AND relation both
        filled -- see `test_incomplete_parent_instance_with_filled_role_does_not_propagate` below
        for the fixture this superseded). This test's own purpose is unchanged: pairing reads the
        parent's CURRENT discovered-instance list, never a hardcoded stand-in."""
        parent = self._parent_requirement_with_one_discovered_trait()
        self.assertTrue(parent["instances"][0]["complete"])
        units = [_unit("U9", 2, "The Empathy Scale was used to assess trait empathy in participants.")]
        result = sm.map_paired_requirement(self._child_req(), parent, units)
        self.assertEqual(len(result["instances"]), 1)
        self.assertEqual(result["state"], "filled")

    def test_incomplete_parent_instance_with_filled_role_does_not_propagate(self):
        """Phase 16: a deliberate behavior CHANGE, not a bug-workaround. Before Phase 16, this
        exact fixture (trait filled, relation missing -- i.e. the parent instance itself is
        INCOMPLETE) was asserted to propagate successfully. The engine's own documented rationale
        for trusting `parent_context` ("already semantically established") cannot hold for an
        instance the parent's own completion rule has not certified -- see sufficiency_engine.
        eligible_parent_instances and the Phase-16 design notes. This locks in the corrected
        behavior under its own explicit name."""
        parent = self._parent_requirement_with_one_discovered_trait(relation_filled=False)
        self.assertFalse(parent["instances"][0]["complete"])
        units = [_unit("U9", 2, "The Empathy Scale was used to assess trait empathy in participants.")]
        result = sm.map_paired_requirement(self._child_req(), parent, units)
        self.assertEqual(result["instances"], [])
        self.assertEqual(result["state"], "missing")

    def test_no_parent_discovered_instances_means_no_child_instances(self):
        specs = {
            "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["trait", "relation"])
        empty_parent = se.recompute_requirement(
            se.new_requirement("parent#req", "atomic", specs, completion, "open_list", multi_instance=True)
        )
        child_specs = {
            "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "named scale", "named_instrument_lexicon"),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        req = se.new_requirement(
            "child#req",
            "relational",
            child_specs,
            child_completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )
        result = sm.map_paired_requirement(req, empty_parent, [])
        self.assertEqual(result["instances"], [])
        self.assertEqual(result["state"], "missing")


class MapAnyRequirementDispatchTests(unittest.TestCase):
    """A requirement declaring `parent_context_roles` with no resolvable parent must FAIL LOUDLY,
    never silently fall through to the generic (non-paired) mapper -- the exact bug a role-name
    mismatch between a real child and its parent produced before this guard existed."""

    def test_parent_context_roles_declared_but_no_parent_requirement_raises(self):
        specs = {
            "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "scale", "named_instrument_lexicon"),
        }
        completion = se.new_role_completion(required_roles=["trait", "scale"])
        req = se.new_requirement(
            "c9#req",
            "relational",
            specs,
            completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )
        with self.assertRaises(ValueError):
            sm.map_any_requirement(req, [], parent_requirement=None)

    def test_cardinality_dispatches_regardless_of_parent_context(self):
        spec = se.new_role_spec("cat", "cat", "explicit_category_terms", requested_category_terms=["a", "b"])
        completion = se.new_role_completion(required_roles=["cat"])
        req = se.new_requirement(
            "x#cat", "cardinality", {"cat": spec}, completion, "all_requested_categories", multi_instance=True
        )
        result = sm.map_any_requirement(req, [])
        self.assertEqual(len(result["instances"]), 2)

    def test_no_parent_context_roles_uses_generic_mapper(self):
        specs = {"a": se.new_role_spec("a", "a", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("y#req", "atomic", specs, completion, "exists")
        units = [_unit("U1", 1, "This finding was found to be significant.")]
        result = sm.map_any_requirement(req, units)
        self.assertEqual(result["state"], "filled")


class DirectionAndEffectivenessMappingTests(unittest.TestCase):
    """Phase 18 deliberately renamed/reshaped `map_direction`/`map_effectiveness` (a single
    first-whole-child-pool-match scalar -- the actual bug this phase exists to fix) into
    `find_direction_observations`/`find_effectiveness_observations` (ALL matches from an
    already-instance-scoped unit list, as a list). These tests are updated to the new plural
    contract with the same underlying scenarios, not silently left pointing at a deleted function
    (the Phase-17 precedent for a deliberately-updated test)."""

    def test_find_direction_observations_returns_empty_list_when_not_declared(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("d#req", "relational", specs, completion, "exists")
        self.assertEqual(sm.find_direction_observations(req, [], semantics_version=se.SUFFICIENCY_SEMANTICS_V2), [])

    def test_find_direction_observations_honest_when_relationship_established_but_no_sign_reported(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement(
            "d#req", "relational", specs, completion, "exists", direction=se.new_direction_assessment()
        )
        units = [_unit("U1", 1, "A relationship was observed between the two measures.")]
        # v2: the recorded historical behaviour these tests pin. v3 has its own tests.
        result = sm.find_direction_observations(req, units, semantics_version=se.SUFFICIENCY_SEMANTICS_V2)
        self.assertEqual(result, [])  # no direction-stem word present -- never a fabricated observation

    def test_find_effectiveness_observations_null_result_is_reported_and_not_supported(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement(
            "e#req", "relational", specs, completion, "exists", effectiveness=se.new_effectiveness_assessment()
        )
        units = [_unit("U1", 1, "No significant effect on bias scores was observed for this intervention.")]
        result = sm.find_effectiveness_observations(req, units)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["outcome_reported"])
        self.assertEqual(result[0]["conclusion"], "not_supported")

    def test_find_effectiveness_observations_attempt_only_language_leaves_outcome_unreported(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement(
            "e#req", "relational", specs, completion, "exists", effectiveness=se.new_effectiveness_assessment()
        )
        units = [_unit("U1", 1, "This intervention might potentially help reduce the bias in future work.")]
        result = sm.find_effectiveness_observations(req, units)
        self.assertEqual(result, [])  # no result predicate matched -- never a fabricated observation


class _FakeModelClient:
    """Hand-written fake -- never a real QwenTasks/network call. `scripted`: proposition_id ->
    exact_text, or a proposition_id -> [exact_text, ...] to nominate SEVERAL distinct instances
    from the same proposition (correction #5)."""

    model_name = "fake-qwen"

    def __init__(self, scripted: dict | None = None, *, hallucinate_proposition_id: str | None = None):
        self.scripted = scripted or {}
        self.hallucinate_proposition_id = hallucinate_proposition_id
        self.calls: list[dict] = []

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        self.calls.append({"category_description": category_description, "candidates": candidates})
        out = []
        if self.hallucinate_proposition_id:
            out.append({"proposition_id": self.hallucinate_proposition_id, "exact_text": "anything"})
        for candidate in candidates:
            texts = self.scripted.get(candidate["proposition_id"])
            if texts is None:
                continue
            for text in texts if isinstance(texts, list) else [texts]:
                out.append({"proposition_id": candidate["proposition_id"], "exact_text": text})
        return out


class NominateWithModelTests(unittest.TestCase):
    def _role_spec(self, **kwargs):
        return se.new_role_spec(
            "brain_region_or_network", "a specific named brain area", "model_nomination_only", **kwargs
        )

    def test_empty_candidate_units_never_calls_the_model(self):
        client = _FakeModelClient()
        result = sm.nominate_with_model(self._role_spec(), [], client)
        self.assertEqual(result, [])
        self.assertEqual(client.calls, [])

    def test_accepted_nomination_is_literally_grounded_and_stamps_proposed_role(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["proposition_id"], units[0]["proposition_ids"][0])
        self.assertEqual(result[0]["exact_text"], "amygdala")
        self.assertEqual(result[0]["proposed_role"], "brain_region_or_network")

    def test_nomination_with_text_not_literally_in_the_passage_is_dropped(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "the hippocampus"})  # never in the passage
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(result, [])

    def test_nomination_naming_a_proposition_outside_the_offered_set_is_dropped(self):
        """Correction #4: the model nominates a proposition_id directly (never a unit_id needing
        translation), and an id outside the closed eligible set offered this call is dropped."""
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient(hallucinate_proposition_id="p_nonexistent")
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(result, [])

    def test_inadmissible_unit_is_never_even_offered_to_the_model(self):
        units = [_unit("u1", 1, "might involve the amygdala")]
        role_spec = self._role_spec(disqualifying_guards=["hedged"])
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        result = sm.nominate_with_model(role_spec, units, client)
        self.assertEqual(result, [])
        self.assertEqual(client.calls, [])  # the hedged unit never reached the model at all

    def test_a_single_passage_can_yield_several_distinct_nominations(self):
        """Correction #5: one passage naming two distinct instances of the same role must not be
        collapsed to one -- both are returned, deduplicated only when literally identical."""
        units = [_unit("u1", 1, "Both the amygdala and the insula showed increased activity.")]
        pid = units[0]["proposition_ids"][0]
        client = _FakeModelClient({pid: ["amygdala", "insula"]})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual({r["exact_text"] for r in result}, {"amygdala", "insula"})
        self.assertTrue(all(r["proposition_id"] == pid for r in result))

    def test_exact_duplicate_nominations_for_the_same_proposition_are_deduplicated(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        pid = units[0]["proposition_ids"][0]
        client = _FakeModelClient({pid: ["amygdala", "Amygdala", "amygdala"]})  # case/whitespace-only variants
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(result), 1)

    def test_candidates_shown_to_the_model_are_keyed_by_proposition_id_not_unit_id(self):
        """A unit carrying MULTIPLE proposition_ids shares its passage across all of them -- each
        must appear as its own candidate row, never collapsed to unit[0]."""
        units = [_unit("u1", 1, "The amygdala showed increased activity.", proposition_ids=["p1", "p2"])]
        client = _FakeModelClient()
        sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(client.calls), 1)
        seen_ids = {c["proposition_id"] for c in client.calls[0]["candidates"]}
        self.assertEqual(seen_ids, {"p1", "p2"})


class ForkingMappingTests(unittest.TestCase):
    """Proves `map_requirement`'s fork mechanic: a role yielding >1 grounded model nomination for
    one unit-scope produces >1 instance, never silently keeps only the first (correction #5)."""

    def test_deterministic_only_never_forks_regardless_of_model_client_arg(self):
        specs = {"assay": se.new_role_spec("assay", "assay", "named_instrument_lexicon")}
        completion = se.new_role_completion(required_roles=["assay"])
        req = se.new_requirement("t#req", "atomic", specs, completion, "exists")
        units = [_unit("u1", 1, "The Empathy Scale was used.")]
        result = sm.map_requirement(req, units)  # no model_client at all -- every existing call site
        self.assertEqual(len(result["instances"]), 1)

    def test_a_single_unit_naming_two_traits_forks_into_two_instances(self):
        specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["trait"])
        req = se.new_requirement("c8#req", "atomic", specs, completion, "open_list", multi_instance=True)
        units = [_unit("u1", 1, "Both neuroticism and openness were measured.")]
        pid = units[0]["proposition_ids"][0]
        client = _FakeModelClient({pid: ["neuroticism", "openness"]})
        result = sm.map_requirement(req, units, model_client=client)
        self.assertEqual(len(result["instances"]), 2)
        texts = {inst["role_bindings"]["trait"]["exact_text"] for inst in result["instances"]}
        self.assertEqual(texts, {"neuroticism", "openness"})
        keys = {inst["instance_key"] for inst in result["instances"]}
        self.assertEqual(len(keys), 2)  # distinct instance_key per fork, never collapsed

    def test_a_still_missing_role_with_no_model_client_stays_missing(self):
        specs = {"trait": se.new_role_spec("trait", "a named trait", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["trait"])
        req = se.new_requirement("c8#req", "atomic", specs, completion, "open_list", multi_instance=True)
        units = [_unit("u1", 1, "Participants showed elevated neuroticism.")]
        result = sm.map_requirement(req, units)  # model_client omitted
        self.assertEqual(len(result["instances"]), 1)
        self.assertEqual(result["instances"][0]["role_bindings"]["trait"]["state"], "missing")


class _TwoRoleForkingClient:
    """Deterministic, hand-scripted -- returns 2 distinct, non-overlapping texts per role,
    dispatched by category_description. Never a real model/network call."""

    model_name = "fake"

    def nominate_sufficiency_role(self, *, category_description, candidates):
        pid = candidates[0]["proposition_id"]
        if category_description == "role a":
            return [{"proposition_id": pid, "exact_text": "alpha"}, {"proposition_id": pid, "exact_text": "beta"}]
        return [{"proposition_id": pid, "exact_text": "gamma"}, {"proposition_id": pid, "exact_text": "delta"}]


class InstanceKeyCollisionTests(unittest.TestCase):
    """Adversarial proof for the Phase 2 diagnostic's Finding 1: two roles in one requirement that
    EACH independently fork (multiple grounded values apiece) must never produce colliding
    instance keys, and identical inputs must replay to identical keys."""

    def _requirement_and_units(self):
        specs = {
            "role_a": se.new_role_spec("role_a", "role a", "model_nomination_only"),
            "role_b": se.new_role_spec("role_b", "role b", "model_nomination_only"),
        }
        completion = se.new_role_completion(required_roles=["role_a", "role_b"])
        req = se.new_requirement("adv#req", "atomic", specs, completion, "exists")
        units = [_unit("u1", 1, "A passage naming several distinct things: alpha, beta, gamma, delta.")]
        return req, units

    def test_two_independently_forking_roles_produce_four_uniquely_keyed_instances(self):
        req, units = self._requirement_and_units()
        result = sm.map_requirement(req, units, model_client=_TwoRoleForkingClient())
        self.assertEqual(len(result["instances"]), 4)
        keys = [inst["instance_key"] for inst in result["instances"]]
        self.assertEqual(len(set(keys)), 4, f"instance_key collision: {keys}")
        # every one of the 4 role_a x role_b combinations is present, each exactly once
        combos = {
            (inst["role_bindings"]["role_a"]["exact_text"], inst["role_bindings"]["role_b"]["exact_text"])
            for inst in result["instances"]
        }
        self.assertEqual(combos, {("alpha", "gamma"), ("alpha", "delta"), ("beta", "gamma"), ("beta", "delta")})

    def test_replay_of_identical_inputs_produces_identical_keys(self):
        req, units = self._requirement_and_units()
        client = _TwoRoleForkingClient()
        keys_first = {inst["instance_key"] for inst in sm.map_requirement(req, units, model_client=client)["instances"]}
        keys_second = {
            inst["instance_key"] for inst in sm.map_requirement(req, units, model_client=client)["instances"]
        }
        self.assertEqual(keys_first, keys_second)

    def test_a_single_forking_role_never_changes_the_original_key(self):
        """When exactly one fork results (the overwhelmingly common case -- including every
        deterministic-only call, since model_client=None never forks), the original instance_key
        (unit_id, or None for a single-instance requirement) is left completely untouched."""
        specs = {"role_a": se.new_role_spec("role_a", "role a", "achieved_outcome_predicate")}
        completion = se.new_role_completion(required_roles=["role_a"])
        req = se.new_requirement("single#req", "atomic", specs, completion, "exists")
        units = [_unit("u1", 1, "This produced a clear result.")]
        result = sm.map_requirement(req, units)
        self.assertEqual(len(result["instances"]), 1)
        self.assertIsNone(result["instances"][0]["instance_key"])


class AnchorDedupTests(unittest.TestCase):
    """Adversarial proof for the Phase 2 diagnostic's Finding 2: proposition_ids sharing one
    physical evidence anchor must collapse to one semantic candidate for instance-count purposes,
    while every supporting proposition_id is preserved in provenance and genuinely distinct
    anchors/values are never merged."""

    def _role_spec(self):
        return se.new_role_spec("trait", "a named trait", "model_nomination_only")

    def test_duplicate_proposition_ids_over_one_anchor_do_not_multiply_instances(self):
        anchor = (1, 999, "e1")
        units = [
            _unit(
                "u1",
                1,
                "Participants showed elevated neuroticism.",
                proposition_ids=["p1", "p2"],
                proposition_anchor={"p1": anchor, "p2": anchor},
            )
        ]
        client = _FakeModelClient({"p1": "neuroticism", "p2": "neuroticism"})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(result), 1)

    def test_provenance_retains_every_supporting_proposition_id(self):
        anchor = (1, 999, "e1")
        units = [
            _unit(
                "u1",
                1,
                "Participants showed elevated neuroticism.",
                proposition_ids=["p1", "p2", "p3"],
                proposition_anchor={"p1": anchor, "p2": anchor, "p3": anchor},
            )
        ]
        client = _FakeModelClient({"p1": "neuroticism", "p2": "neuroticism", "p3": "neuroticism"})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["supporting_proposition_ids"], ["p1", "p2", "p3"])
        self.assertEqual(result[0]["proposition_id"], "p1")  # deterministic primary: lowest sorted

    def test_distinct_semantic_values_within_one_anchor_still_fork(self):
        anchor = (1, 999, "e1")
        units = [
            _unit(
                "u1",
                1,
                "Both neuroticism and openness were measured.",
                proposition_ids=["p1", "p2"],
                proposition_anchor={"p1": anchor, "p2": anchor},
            )
        ]
        # BOTH propositions (same anchor) independently offer BOTH distinct traits -- realistic
        # shape, since they share identical passage text.
        client = _FakeModelClient({"p1": ["neuroticism", "openness"], "p2": ["neuroticism", "openness"]})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        texts = {r["exact_text"] for r in result}
        self.assertEqual(texts, {"neuroticism", "openness"})
        self.assertEqual(len(result), 2)  # 2 distinct values, each collapsed across its own anchor duplicate
        for r in result:
            self.assertEqual(r["supporting_proposition_ids"], ["p1", "p2"])

    def test_genuinely_distinct_anchors_are_not_accidentally_collapsed(self):
        units = [
            _unit(
                "u1",
                1,
                "Participants showed elevated neuroticism.",
                proposition_ids=["p1", "p2"],
                proposition_anchor={"p1": (1, 100, "e1"), "p2": (1, 200, "e1")},  # different chunk_id
            )
        ]
        client = _FakeModelClient({"p1": "neuroticism", "p2": "neuroticism"})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(result), 2)  # never merged -- different physical anchors
        proposition_ids = {r["proposition_id"] for r in result}
        self.assertEqual(proposition_ids, {"p1", "p2"})

    def test_propositions_with_no_known_anchor_are_never_collapsed_with_each_other(self):
        """Conservative default: lacking anchor information is never treated as proof of a SHARED
        anchor -- matches the pre-Finding-2 per-proposition dedup behavior exactly."""
        units = [
            _unit("u1", 1, "Participants showed elevated neuroticism.", proposition_ids=["p1", "p2"])
        ]  # no proposition_anchor
        client = _FakeModelClient({"p1": "neuroticism", "p2": "neuroticism"})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(result), 2)

    def test_proposition_level_grounding_remains_intact_after_dedup(self):
        anchor = (1, 999, "e1")
        units = [
            _unit(
                "u1",
                1,
                "Participants showed elevated neuroticism.",
                proposition_ids=["p1", "p2"],
                proposition_anchor={"p1": anchor, "p2": anchor},
            )
        ]
        # p2's own nomination is NOT literally in the passage -- grounding still rejects it even
        # though p1's own nomination (same anchor) is valid; the survivor is p1 alone.
        client = _FakeModelClient({"p1": "neuroticism", "p2": "the hippocampus"})
        result = sm.nominate_with_model(self._role_spec(), units, client)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["supporting_proposition_ids"], ["p1"])


class ReformulatedNominationRepresentabilityTests(unittest.TestCase):
    """Phase 9 Part G: proves the PLUMBING (grounding, schema shape, `map_requirement`'s own
    accept/decline handling) can represent every ACCEPT/DECLINE example the reformulated
    `qwen.nomination_prompt` asks a model to distinguish -- clause-shaped behaviors, lowercase
    common-noun entities, bare proper nouns, and the matching generic-assertion declines. These
    are hand-scripted fake clients; the engine cannot prove the model semantically obeys the
    instruction, and NOTHING here is a claim about live Qwen's actual behavior under the new
    prompt -- only that the architecture can correctly carry either outcome through to a
    RoleBinding (accept) or `missing` (decline) once a client returns it."""

    def _role_spec(self, category):
        return se.new_role_spec("x", category, "model_nomination_only")

    def _accepts(self, category, passage, exact_text):
        units = [_unit("u1", 1, passage)]
        client = _FakeModelClient({"u1-p": exact_text})
        result = sm.map_requirement(
            se.new_requirement(
                "t#req",
                "atomic",
                {"x": self._role_spec(category)},
                se.new_role_completion(required_roles=["x"]),
                "exists",
            ),
            units,
            model_client=client,
        )
        self.assertEqual(result["state"], "filled", f"expected ACCEPT to fill: {exact_text!r}")
        self.assertEqual(result["instances"][0]["role_bindings"]["x"]["exact_text"], exact_text)

    def _declines(self, category, passage):
        """A well-behaved nominator returns [] for a generic-assertion-only excerpt -- simulated
        directly (never coerced from the passage), since this is a plumbing test of what happens
        when a client declines, not a test of whether Qwen WOULD decline."""
        units = [_unit("u1", 1, passage)]
        client = _FakeModelClient({})  # scripted empty -- returns no nominations for any proposition
        result = sm.map_requirement(
            se.new_requirement(
                "t#req",
                "atomic",
                {"x": self._role_spec(category)},
                se.new_role_completion(required_roles=["x"]),
                "exists",
            ),
            units,
            model_client=client,
        )
        self.assertEqual(result["state"], "missing", f"expected DECLINE to leave the role missing: {passage!r}")

    # -- ACCEPT: the identifying span survives end-to-end -----------------------------------------

    def test_accept_population_adolescents_in_japan(self):
        self._accepts(
            "a named culture or population", "The sample consisted of adolescents in Japan.", "adolescents in Japan"
        )

    def test_accept_intervention_mindfulness_training(self):
        self._accepts(
            "a named intervention",
            "Participants completed mindfulness training over eight weeks.",
            "mindfulness training",
        )

    def test_accept_behavior_clause_shaped_participants_donated_less_money(self):
        """Proves a CLAUSE (not a bare noun phrase) is representable -- the reformulated prompt
        explicitly does not require noun-phrase shape."""
        self._accepts(
            "an observed behavior or behavioral measure",
            "In the study, participants donated less money to the charity.",
            "participants donated less money",
        )

    def test_accept_measurement_named_modality(self):
        self._accepts(
            "the method or modality used to measure neural activity",
            "Functional MRI was used to measure activity during the task.",
            "Functional MRI",
        )

    def test_accept_trait_anxiety(self):
        self._accepts(
            "a named individual-difference trait or construct",
            "We measured trait anxiety in all participants.",
            "trait anxiety",
        )

    def test_accept_lowercase_common_noun_amygdala(self):
        """Direct regression for the Phase 8 forensic finding and the Phase 9 prompt's explicit
        'does not need to be a proper noun or capitalized' instruction -- a genuine scientific
        term that is NOT capitalized must still be representable as an accepted referent."""
        self._accepts(
            "a specific named brain area", "Activity in the amygdala was elevated during the task.", "amygdala"
        )

    # -- DECLINE: a generic existence/occurrence assertion leaves the role missing ------------------

    def test_decline_population_generic(self):
        self._declines("a named culture or population", "A population was studied across several sites.")

    def test_decline_intervention_generic(self):
        self._declines("a named intervention", "An intervention reduced symptoms significantly.")

    def test_decline_behavior_generic(self):
        self._declines("an observed behavior or behavioral measure", "A behavioral manifestation occurred.")

    def test_decline_measurement_generic(self):
        self._declines("the method or modality used to measure neural activity", "Neural activity was measured.")

    def test_decline_trait_generic(self):
        self._declines(
            "a named individual-difference trait or construct", "Individual differences predicted the outcome."
        )


class ParentEligibilityForkingTests(unittest.TestCase):
    """Phase 16's full deterministic matrix (plan §13 / brief §M) for `map_paired_requirement`,
    now the SOLE parent-context instance-generation path for every quantifier (`exists` and
    `for_each_discovered_instance` alike -- `map_any_requirement` no longer branches on
    quantifier for parent-context requirements)."""

    def _parent_req(self, instances):
        specs = {
            "region": se.new_role_spec("region", "a specific NAMED brain area", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["region", "relation"])
        req = se.new_requirement("c4#req", "atomic", specs, completion, "exists")
        req["instances"] = instances
        return se.recompute_requirement(req)

    def _complete_instance(self, key, region_prop, region_text, *, relation_prop=None):
        relation_prop = relation_prop or region_prop
        inst = se.new_instance(key)
        inst["role_bindings"]["region"] = se.new_role_binding(
            "region",
            state="filled",
            proposition_id=region_prop,
            exact_text=region_text,
            provenance={
                "candidate_source": "model_mapping",
                "detail": "",
                "model": "stub",
                "supporting_proposition_ids": [region_prop],
            },
        )
        inst["role_bindings"]["relation"] = se.new_role_binding(
            "relation",
            state="filled",
            proposition_id=relation_prop,
            exact_text="relation evidence",
            provenance={
                "candidate_source": "deterministic_mapping",
                "detail": "achieved_outcome_predicate",
                "model": None,
            },
        )
        return inst

    def _incomplete_instance(self, key, region_prop, region_text):
        inst = se.new_instance(key)
        inst["role_bindings"]["region"] = se.new_role_binding(
            "region",
            state="filled",
            proposition_id=region_prop,
            exact_text=region_text,
            provenance={"candidate_source": "model_mapping", "detail": "", "model": "stub"},
        )
        inst["role_bindings"]["relation"] = se.new_role_binding(
            "relation",
            state="filled",
            proposition_id="relation-other-proposition",
            exact_text="relation evidence",
            provenance={
                "candidate_source": "deterministic_mapping",
                "detail": "achieved_outcome_predicate",
                "model": None,
            },
        )
        return inst

    def _child_req(self):
        specs = {
            "region": se.new_role_spec("region", "a specific NAMED brain area", "model_nomination_only"),
            "behavior": se.new_role_spec("behavior", "an observed behavior", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["region", "behavior"])
        return se.new_requirement("c5#req", "relational", specs, completion, "exists", parent_context_roles=["region"])

    def _no_match_units(self):
        return [_unit("U1", 1, "We administered a plain survey to participants in a quiet room.")]

    def _matching_units(self):
        # Verified directly against attr.has_result_predicate -- "This produced a clear
        # significant result." does NOT match; this exact phrase (already used elsewhere in this
        # file) does.
        return [_unit("U1", 1, "This finding was found to be significant.")]

    def _region_texts(self, result):
        return {inst["role_bindings"]["region"]["exact_text"] for inst in result["instances"]}

    # 1. one complete parent instance -> existing behavior preserved.
    def test_one_complete_parent_instance_propagates(self):
        parent = self._parent_req([self._complete_instance("amygdala", "p11", "amygdala")])
        result = sm.map_paired_requirement(self._child_req(), parent, self._matching_units())
        self.assertEqual(len(result["instances"]), 1)
        self.assertEqual(self._region_texts(result), {"amygdala"})
        binding = result["instances"][0]["role_bindings"]["region"]
        self.assertEqual(binding["provenance"]["candidate_source"], "parent_context")

    # 3/4/13. incomplete+complete, reversed, and the real Phase-15 adversarial shape.
    def test_incomplete_then_complete_only_complete_propagates(self):
        parent = self._parent_req(
            [self._incomplete_instance("rtpj", "p27", "RTPJ"), self._complete_instance("amygdala", "p11", "amygdala")]
        )
        self.assertFalse(parent["instances"][0]["complete"])
        self.assertTrue(parent["instances"][1]["complete"])
        result = sm.map_paired_requirement(self._child_req(), parent, self._matching_units())
        self.assertEqual(self._region_texts(result), {"amygdala"})

    def test_reversed_parent_order_produces_identical_semantic_result(self):
        forward = self._parent_req(
            [self._incomplete_instance("rtpj", "p27", "RTPJ"), self._complete_instance("amygdala", "p11", "amygdala")]
        )
        backward = self._parent_req(
            [self._complete_instance("amygdala", "p11", "amygdala"), self._incomplete_instance("rtpj", "p27", "RTPJ")]
        )
        result_forward = sm.map_paired_requirement(self._child_req(), forward, self._matching_units())
        result_backward = sm.map_paired_requirement(self._child_req(), backward, self._matching_units())
        self.assertEqual(self._region_texts(result_forward), self._region_texts(result_backward))
        self.assertEqual(result_forward["state"], result_backward["state"])

    # 5. two complete, distinct parent instances -> both propagate.
    def test_two_complete_distinct_parents_both_propagate(self):
        parent = self._parent_req(
            [self._complete_instance("amygdala", "p11", "amygdala"), self._complete_instance("rtpj", "p27", "RTPJ")]
        )
        result = sm.map_paired_requirement(self._child_req(), parent, self._matching_units())
        self.assertEqual(len(result["instances"]), 2)
        self.assertEqual(self._region_texts(result), {"amygdala", "RTPJ"})

    # 6. two complete, same exact_text, DIFFERENT anchors -> never fuzzy-collapsed.
    def test_two_complete_same_text_different_anchors_both_preserved(self):
        parent = self._parent_req(
            [
                self._complete_instance("first", "p11", "amygdala"),
                self._complete_instance("second", "p99", "amygdala", relation_prop="p99"),
            ]
        )
        result = sm.map_paired_requirement(self._child_req(), parent, self._matching_units())
        self.assertEqual(len(result["instances"]), 2)
        prop_ids = {inst["role_bindings"]["region"]["proposition_id"] for inst in result["instances"]}
        self.assertEqual(prop_ids, {"p11", "p99"})

    # 7. complete model-dependent parent -> provenance preserved through the hop.
    def test_model_dependent_complete_parent_preserves_provenance_through_propagation(self):
        from experiments.ask_cli_revised import sufficiency_diagnostic as sd

        parent = self._parent_req([self._complete_instance("amygdala", "p11", "amygdala")])
        parent = sd._stamp_model_dependency_origins(parent, "c4")
        result = sm.map_paired_requirement(self._child_req(), parent, self._matching_units())
        binding = result["instances"][0]["role_bindings"]["region"]
        self.assertTrue(binding["provenance"]["upstream_model_dependent"])
        self.assertEqual(binding["provenance"]["source_lineage"], ["model_mapping", "parent_context"])
        self.assertEqual(len(binding["provenance"]["model_dependency_origins"]), 1)
        origin = binding["provenance"]["model_dependency_origins"][0]
        self.assertEqual(origin["child_id"], "c4")
        self.assertEqual(origin["instance_key"], "amygdala")

    # 8. two-hop propagation preserves origin and multiplicity.
    def test_two_hop_propagation_preserves_origin_and_multiplicity(self):
        from experiments.ask_cli_revised import sufficiency_diagnostic as sd

        grandparent = self._parent_req([self._complete_instance("amygdala", "p11", "amygdala")])
        grandparent = sd._stamp_model_dependency_origins(grandparent, "c4")

        parent_specs = {
            "region": se.new_role_spec("region", "a specific NAMED brain area", "model_nomination_only"),
            "behavior": se.new_role_spec("behavior", "an observed behavior", "achieved_outcome_predicate"),
        }
        parent_completion = se.new_role_completion(required_roles=["region", "behavior"])
        parent_req = se.new_requirement(
            "c5#req", "relational", parent_specs, parent_completion, "exists", parent_context_roles=["region"]
        )
        mapped_parent = sm.map_paired_requirement(parent_req, grandparent, self._matching_units())
        mapped_parent = sd._stamp_model_dependency_origins(mapped_parent, "c5")
        self.assertEqual(mapped_parent["state"], "filled")

        grandchild_specs = {
            "region": se.new_role_spec("region", "a specific NAMED brain area", "model_nomination_only"),
            "attitude": se.new_role_spec("attitude", "a named attitude", "model_nomination_only"),
        }
        grandchild_completion = se.new_role_completion(required_roles=["region", "attitude"])
        grandchild_req = se.new_requirement(
            "c6#req", "relational", grandchild_specs, grandchild_completion, "exists", parent_context_roles=["region"]
        )
        result = sm.map_paired_requirement(grandchild_req, mapped_parent, self._no_match_units())
        self.assertEqual(len(result["instances"]), 1)
        binding = result["instances"][0]["role_bindings"]["region"]
        self.assertTrue(binding["provenance"]["upstream_model_dependent"])
        self.assertEqual(binding["provenance"]["source_lineage"], ["model_mapping", "parent_context", "parent_context"])
        self.assertEqual(len(binding["provenance"]["model_dependency_origins"]), 1)
        self.assertEqual(binding["provenance"]["model_dependency_origins"][0]["child_id"], "c4")

    # 16/17. own-evidence-first: never duplicated once per eligible parent; falls back cleanly.
    def test_two_eligible_parents_with_child_owned_evidence_no_duplicate_forks(self):
        parent = self._parent_req(
            [self._complete_instance("amygdala", "p11", "amygdala"), self._complete_instance("rtpj", "p27", "RTPJ")]
        )
        units = [_unit("U9", 9, "The insula was independently named in this own passage, producing a result.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "insula"})
        result = sm.map_paired_requirement(self._child_req(), parent, units, model_client=client)
        # own evidence wins outright -- exactly one instance, never one per eligible parent.
        self.assertEqual(len(result["instances"]), 1)
        self.assertEqual(result["instances"][0]["role_bindings"]["region"]["exact_text"], "insula")
        self.assertEqual(
            result["instances"][0]["role_bindings"]["region"]["provenance"]["candidate_source"], "model_mapping"
        )

    def test_two_eligible_parents_zero_child_owned_evidence_produces_two_fallback_forks(self):
        parent = self._parent_req(
            [self._complete_instance("amygdala", "p11", "amygdala"), self._complete_instance("rtpj", "p27", "RTPJ")]
        )
        # no model_client at all -- own evidence for "region" (model_nomination_only) is always empty.
        result = sm.map_paired_requirement(self._child_req(), parent, self._matching_units())
        self.assertEqual(len(result["instances"]), 2)
        self.assertEqual(self._region_texts(result), {"amygdala", "RTPJ"})

    # Zero eligible parents -> parent context unavailable (no change from today; named explicitly).
    def test_zero_eligible_parents_still_tests_the_childs_other_role_against_its_own_evidence(self):
        """A real regression caught while re-verifying Phase 15 against this fix: for a NON-
        for_each shape, zero eligible parents must NOT mean zero instances -- that would silently
        skip testing this requirement's OTHER role(s) against the child's own evidence too. The
        historical single-instance-fallback mapper always built exactly one base instance; this
        preserves that exactly (one instance, parent role missing, OTHER role still evaluated)."""
        parent = self._parent_req([self._incomplete_instance("rtpj", "p27", "RTPJ")])
        result = sm.map_paired_requirement(self._child_req(), parent, self._matching_units())
        self.assertEqual(len(result["instances"]), 1)
        inst = result["instances"][0]
        self.assertEqual(inst["role_bindings"]["region"]["state"], "missing")
        self.assertEqual(inst["role_bindings"]["behavior"]["state"], "filled")  # still tried, still found
        self.assertEqual(result["state"], "partially_filled")  # not "filled" -- region is missing

    def test_zero_eligible_parents_and_zero_own_evidence_anywhere_is_one_missing_instance(self):
        parent = self._parent_req([self._incomplete_instance("rtpj", "p27", "RTPJ")])
        result = sm.map_paired_requirement(self._child_req(), parent, self._no_match_units())
        self.assertEqual(len(result["instances"]), 1)
        self.assertEqual(result["state"], "missing")

    def test_real_phase15_recorded_nomination_end_to_end_c6_inherits_amygdala_only(self):
        """The real recorded Phase-15 live nomination output (PHASE15_C4_SEMANTIC_CONSUMPTION_
        RESULTS.md's own §J raw output, hardcoded here as a frozen historical literal -- no live
        call, no dependency on any `.local/` artifact), run through the REAL pipeline end to end:
        `nominate_with_model` -> c4's own forking (no parent) -> c6's propagation. Before Phase 16,
        c6 inherited the RTPJ (c4's `instances[0]`, purely because the model listed it first in
        its raw JSON); this locks in the corrected result: amygdala only, matching the module
        docstring's §7 worked example exactly."""
        real_raw_nominations = [
            {"proposition_id": "p27", "exact_text": "a cortical region in the right temporo-parietal junction (RTPJ)"},
            {"proposition_id": "p11", "exact_text": "the specific amygdala"},
            {"proposition_id": "p2", "exact_text": "the specific amygdala"},
        ]

        class _RecordedPhase15Client:
            model_name = "recorded-phase15-literal"

            def nominate_sufficiency_role(self, *, category_description, candidates):
                offered = {c["proposition_id"] for c in candidates}
                return [n for n in real_raw_nominations if n["proposition_id"] in offered]

        c4_specs = {
            "region": se.new_role_spec("region", "a specific NAMED brain area", "model_nomination_only"),
            "relation": se.new_role_spec(
                "relation",
                "evidence that the named region bears on the bias",
                "achieved_outcome_predicate",
                disqualifying_guards=["hedged"],
            ),
        }
        c4_completion = se.new_role_completion(required_roles=["region", "relation"])
        c4_req = se.new_requirement("c4#suff:specific-region", "atomic", c4_specs, c4_completion, "exists")
        units = [
            _unit(
                "U_amygdala",
                67,
                "Across these levels of organization, the specific amygdala response to facial "
                "anomalies correlated with stronger just-world beliefs.",
                proposition_ids=["p11", "p2"],
                # same physical anchor for both -- matches the real Phase-15 data exactly (p11/p2
                # are the SAME passage, paper 67/chunk 34974/span e7), which is what makes
                # nominate_with_model's own anchor-based dedup collapse them to one nomination.
                proposition_anchor={"p11": (67, 34974, "e7"), "p2": (67, 34974, "e7")},
            ),
            _unit(
                "U_rtpj",
                74,
                "fMRI studies have demonstrated a critical role for a cortical region in the right "
                "temporo-parietal junction (RTPJ) in theory of mind.",
                proposition_ids=["p27"],
            ),
        ]
        c4_mapped = sm.map_requirement(c4_req, units, model_client=_RecordedPhase15Client())
        self.assertEqual(len(c4_mapped["instances"]), 2)
        self.assertEqual(c4_mapped["state"], "filled")

        c6_mapped = sm.map_paired_requirement(self._child_req(), c4_mapped, self._no_match_units())
        self.assertEqual(
            {inst["role_bindings"]["region"]["exact_text"] for inst in c6_mapped["instances"]},
            {"the specific amygdala"},
        )

        # Adversarial permutation, same real fixture: reverse c4's own instance list (simulating
        # the model having listed amygdala before RTPJ) -- the corrected result must be identical.
        reversed_c4 = {**c4_mapped, "instances": list(reversed(c4_mapped["instances"]))}
        reversed_c6 = sm.map_paired_requirement(self._child_req(), reversed_c4, self._no_match_units())
        self.assertEqual(
            {inst["role_bindings"]["region"]["exact_text"] for inst in reversed_c6["instances"]},
            {"the specific amygdala"},
        )

    def test_for_each_discovered_instance_with_zero_eligible_parents_is_still_zero_instances(self):
        """The ONE shape where zero eligible parents genuinely means zero instances (unchanged
        from before this fix) -- for_each's own semantics IS "one per discovered parent". Mirrors
        the real c8 shape: trait filled, the OTHER required role (relation) missing -> the parent
        instance is genuinely incomplete, not merely role-unfilled."""
        parent_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "relation": se.new_role_spec("relation", "relation", "achieved_outcome_predicate"),
        }
        parent_completion = se.new_role_completion(required_roles=["trait", "relation"])
        parent_req = se.new_requirement("c8#req", "atomic", parent_specs, parent_completion, "exists")
        incomplete = se.new_instance("i1")
        incomplete["role_bindings"]["trait"] = se.new_role_binding(
            "trait",
            state="filled",
            proposition_id="p1",
            exact_text="empathy",
            provenance={"candidate_source": "model_mapping", "detail": "", "model": "stub"},
        )
        incomplete["role_bindings"]["relation"] = se.new_role_binding("relation", state="missing", reason="not_found")
        parent_req["instances"] = [incomplete]
        parent_req = se.recompute_requirement(parent_req)
        self.assertFalse(parent_req["instances"][0]["complete"])

        child_specs = {
            "trait": se.new_role_spec("trait", "a named trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "a named scale", "named_instrument_lexicon"),
        }
        child_completion = se.new_role_completion(required_roles=["trait", "scale"])
        child_req = se.new_requirement(
            "c9#req",
            "relational",
            child_specs,
            child_completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )
        result = sm.map_paired_requirement(child_req, parent_req, self._matching_units())
        self.assertEqual(result["instances"], [])
        self.assertEqual(result["state"], "missing")


# ---------------------------------------------------------------------------------------------
# Phase 19: robust model-nomination scoping + nomination-receipt integration. The legacy
# (context-free) path above this point is left completely untouched -- every test below opts in
# explicitly via a `nomination_context`, never changing default behavior for an existing caller.
# ---------------------------------------------------------------------------------------------

from experiments.ask_cli_revised import sufficiency_model_scope as mscope  # noqa: E402


class CandidateRowsForRoleTests(unittest.TestCase):
    """`_candidate_rows_for_role` is a pure extraction from `nominate_with_model`'s own inline
    logic (audit §4/§10) -- it must build EXACTLY the rows the model is shown, so a fingerprint
    computed from it is trustworthy."""

    def _role_spec(self, **kwargs):
        return se.new_role_spec("r", "a role", "model_nomination_only", **kwargs)

    def test_one_row_per_admissible_proposition_id(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.", proposition_ids=["p1", "p2"])]
        rows = sm._candidate_rows_for_role(self._role_spec(), units)
        self.assertEqual({r["proposition_id"] for r in rows}, {"p1", "p2"})
        self.assertTrue(all(r["passage"] == units[0]["passage"] for r in rows))

    def test_inadmissible_unit_contributes_no_rows(self):
        units = [_unit("u1", 1, "might involve the amygdala")]
        role_spec = self._role_spec(disqualifying_guards=["hedged"])
        self.assertEqual(sm._candidate_rows_for_role(role_spec, units), [])

    def test_matches_what_nominate_with_model_actually_offers(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.", proposition_ids=["p1", "p2"])]
        client = _FakeModelClient()
        role_spec = self._role_spec()
        sm.nominate_with_model(role_spec, units, client)
        offered_ids = {c["proposition_id"] for c in client.calls[0]["candidates"]}
        row_ids = {r["proposition_id"] for r in sm._candidate_rows_for_role(role_spec, units)}
        self.assertEqual(offered_ids, row_ids)


class BindRoleCandidatesScopingTests(unittest.TestCase):
    """`_bind_role_candidates` is the one integration checkpoint (audit §19) -- scope threading,
    authorization, memoization, and failure fallback all land here, never scattered elsewhere."""

    def _role_spec(self, **kwargs):
        return se.new_role_spec(
            "named_brain_region_or_network", "a specific named brain area", "model_nomination_only", **kwargs
        )

    def test_with_no_nomination_context_behavior_is_byte_identical_to_pre_phase_19(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        no_scope = sm._bind_role_candidates(self._role_spec(), units, model_client=client)
        client2 = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        with_unused_scope_args = sm._bind_role_candidates(
            self._role_spec(), units, model_client=client2, child_id="c4", requirement_id="c4#req"
        )
        self.assertEqual(len(no_scope), 1)
        self.assertEqual(no_scope[0]["exact_text"], with_unused_scope_args[0]["exact_text"])
        self.assertNotIn("nomination_receipt_status", no_scope[0]["provenance"])
        self.assertNotIn("nomination_receipt_status", with_unused_scope_args[0]["provenance"])

    def test_with_nomination_context_but_no_child_id_raises(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        with self.assertRaises(ValueError):
            sm._bind_role_candidates(self._role_spec(), units, model_client=client, nomination_context=ctx)

    def test_fresh_authorized_call_stamps_receipt_status_on_provenance(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        result = sm._bind_role_candidates(
            self._role_spec(),
            units,
            model_client=client,
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        self.assertEqual(result[0]["provenance"]["nomination_receipt_status"], "fresh")
        self.assertEqual(result[0]["provenance"]["candidate_source"], "model_mapping")

    def test_unauthorized_scope_with_no_prior_receipt_degrades_to_no_candidates(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        other_scope = mscope.new_model_nomination_scope("c99", "other#req", "other_role")
        ctx = mscope.new_nomination_context(mscope.exact_scope_set_policy([other_scope]))
        result = sm._bind_role_candidates(
            self._role_spec(),
            units,
            model_client=client,
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        self.assertEqual(result, [])
        self.assertEqual(client.calls, [], "an unauthorized scope must never reach the model")

    def test_repeated_call_under_the_same_scope_within_one_context_memoizes(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        client = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sm._bind_role_candidates(
            self._role_spec(),
            units,
            model_client=client,
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        result2 = sm._bind_role_candidates(
            self._role_spec(),
            units,
            model_client=client,
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        self.assertEqual(len(client.calls), 1, "the same scope resolved twice must cost exactly one model call")
        self.assertEqual(result2[0]["provenance"]["nomination_receipt_status"], "memoized_in_pass")

    def test_no_descriptive_string_comparison_used_for_authorization(self):
        """Two roles with the IDENTICAL category_description but different (child_id,
        requirement_id, role) must be authorized independently -- proving authorization never
        reads `category_description` at all (audit §4/§6/test #7)."""
        same_description = "a specific named brain area"
        role_spec_a = se.new_role_spec("named_brain_region_or_network", same_description, "model_nomination_only")
        role_spec_b = se.new_role_spec("named_brain_region_or_network", same_description, "model_nomination_only")
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        target_scope = mscope.new_model_nomination_scope("c4", "c4#req", "named_brain_region_or_network")
        ctx = mscope.new_nomination_context(mscope.exact_scope_set_policy([target_scope]))

        client_a = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        result_a = sm._bind_role_candidates(
            role_spec_a,
            units,
            model_client=client_a,
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        self.assertEqual(result_a[0]["exact_text"], "amygdala", "the authorized (c4) scope must actually bind")
        client_b = _FakeModelClient({units[0]["proposition_ids"][0]: "amygdala"})
        result_b = sm._bind_role_candidates(
            role_spec_b,
            units,
            model_client=client_b,
            child_id="c5",
            requirement_id="c5#req",
            nomination_context=ctx,
        )
        self.assertEqual(len(client_a.calls), 1, "the authorized (c4) scope must call the model")
        self.assertEqual(
            len(client_b.calls),
            0,
            "an unauthorized (c5) scope must NOT call the model despite "
            "sharing the identical category_description text",
        )
        self.assertEqual(result_b, [])

    def test_mechanical_failure_with_valid_prior_receipt_falls_back(self):
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]

        class _RaisingClient:
            model_name = "raising-fake"

            def nominate_sufficiency_role(self, *, category_description, candidates):
                raise RuntimeError("transport failed")

        scope = mscope.new_model_nomination_scope("c4", "c4#req", "named_brain_region_or_network")
        prior_accepted = [
            {
                "proposition_id": units[0]["proposition_ids"][0],
                "exact_text": "amygdala",
                "supporting_proposition_ids": [units[0]["proposition_ids"][0]],
            }
        ]
        prior_receipt = mscope.new_nomination_receipt(
            scope,
            model_name="old-model",
            request_fingerprint="irrelevant",
            candidates_offered=[],
            accepted=prior_accepted,
            status="fresh",
        )
        ctx = mscope.new_nomination_context(
            mscope.all_eligible_policy(), prior_receipts={mscope.new_model_nomination_key(scope): prior_receipt}
        )
        result = sm._bind_role_candidates(
            self._role_spec(),
            units,
            model_client=_RaisingClient(),
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        self.assertEqual(result[0]["exact_text"], "amygdala")
        self.assertEqual(result[0]["provenance"]["nomination_receipt_status"], "fresh_failed_fallback_to_prior")

    def test_mechanical_failure_with_stale_prior_receipt_degrades_to_missing(self):
        """A prior accepted proposition_id that no longer exists in the current candidate pool
        must NOT be replayed (audit §L: fail that receipt CLOSED, never retain stale evidence)."""
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]

        class _RaisingClient:
            model_name = "raising-fake"

            def nominate_sufficiency_role(self, *, category_description, candidates):
                raise RuntimeError("transport failed")

        scope = mscope.new_model_nomination_scope("c4", "c4#req", "named_brain_region_or_network")
        stale_accepted = [
            {
                "proposition_id": "p-no-longer-present",
                "exact_text": "hippocampus",
                "supporting_proposition_ids": ["p-no-longer-present"],
            }
        ]
        prior_receipt = mscope.new_nomination_receipt(
            scope,
            model_name="old-model",
            request_fingerprint="irrelevant",
            candidates_offered=[],
            accepted=stale_accepted,
            status="fresh",
        )
        ctx = mscope.new_nomination_context(
            mscope.all_eligible_policy(), prior_receipts={mscope.new_model_nomination_key(scope): prior_receipt}
        )
        result = sm._bind_role_candidates(
            self._role_spec(),
            units,
            model_client=_RaisingClient(),
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        self.assertEqual(result, [])

    def test_prior_receipt_with_exact_text_no_longer_grounded_is_rejected(self):
        """Test #20: the proposition_id still exists, but the accepted `exact_text` is no longer
        a literal substring of its (possibly re-extracted) passage -- the receipt must still be
        rejected wholesale, not just the proposition-existence check from the test above."""
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        pid = units[0]["proposition_ids"][0]
        scope = mscope.new_model_nomination_scope("c4", "c4#req", "named_brain_region_or_network")
        ungrounded_accepted = [
            {
                "proposition_id": pid,
                "exact_text": "hippocampus",  # never in this passage
                "supporting_proposition_ids": [pid],
            }
        ]
        self.assertFalse(
            sm._prior_receipt_is_admissible(
                mscope.new_nomination_receipt(
                    scope,
                    model_name="m",
                    request_fingerprint="x",
                    candidates_offered=[],
                    accepted=ungrounded_accepted,
                    status="fresh",
                ),
                self._role_spec(),
                units,
            )
        )

    def test_prior_receipt_with_now_inadmissible_guard_is_rejected(self):
        """A proposition_id still exists and the text still matches, but the unit is no longer
        admissible per this role's own disqualifying guards (e.g. a guard flag changed) -- the
        receipt is still rejected (admissibility, not just literal grounding, is checked)."""
        units = [_unit("u1", 1, "might involve the amygdala")]  # hedged
        pid = units[0]["proposition_ids"][0]
        role_spec = self._role_spec(disqualifying_guards=["hedged"])
        scope = mscope.new_model_nomination_scope("c4", "c4#req", "named_brain_region_or_network")
        accepted = [{"proposition_id": pid, "exact_text": "amygdala", "supporting_proposition_ids": [pid]}]
        self.assertFalse(
            sm._prior_receipt_is_admissible(
                mscope.new_nomination_receipt(
                    scope,
                    model_name="m",
                    request_fingerprint="x",
                    candidates_offered=[],
                    accepted=accepted,
                    status="fresh",
                ),
                role_spec,
                units,
            )
        )

    def test_authorized_target_scope_gets_a_fresh_call_even_when_candidates_have_broadened(self):
        """Test #21: a target/authorized scope's fresh call is never blocked by candidates having
        broadened since a prior pass -- there is no cross-pass fingerprint comparison at all, by
        design (audit §M: this is exactly what "recovery adds new evidence" requires)."""
        narrower_units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        broader_units = narrower_units + [_unit("u2", 2, "The hippocampus also showed increased activity.")]
        scope = mscope.new_model_nomination_scope("c4", "c4#req", "named_brain_region_or_network")
        prior_receipt = mscope.new_nomination_receipt(
            scope,
            model_name="old",
            request_fingerprint="whatever-the-narrower-fingerprint-was",
            candidates_offered=[],
            accepted=[
                {
                    "proposition_id": narrower_units[0]["proposition_ids"][0],
                    "exact_text": "amygdala",
                    "supporting_proposition_ids": [narrower_units[0]["proposition_ids"][0]],
                }
            ],
            status="fresh",
        )
        ctx = mscope.new_nomination_context(
            mscope.exact_scope_set_policy([scope]),
            prior_receipts={mscope.new_model_nomination_key(scope): prior_receipt},
        )
        client = _FakeModelClient(
            {
                narrower_units[0]["proposition_ids"][0]: "amygdala",
                broader_units[1]["proposition_ids"][0]: "hippocampus",
            }
        )
        result = sm._bind_role_candidates(
            self._role_spec(),
            broader_units,
            model_client=client,
            child_id="c4",
            requirement_id="c4#req",
            nomination_context=ctx,
        )
        self.assertEqual(
            len(client.calls),
            1,
            "the authorized scope must make a fresh call against the CURRENT, "
            "broadened candidate pool rather than being blocked by the prior "
            "pass's different fingerprint",
        )
        self.assertEqual({r["exact_text"] for r in result}, {"amygdala", "hippocampus"})

    def test_unauthorized_scope_ignores_newly_broadened_candidates_and_stays_held_fixed(self):
        """Test #22: a held-fixed (non-target) scope's broadened current candidate pool is never
        consulted -- the prior decision alone is replayed, exactly as "held fixed" requires."""
        narrower_units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        broader_units = narrower_units + [_unit("u2", 2, "The hippocampus also showed increased activity.")]
        scope = mscope.new_model_nomination_scope("c5", "c5#req", "named_brain_region_or_network")
        other_target = mscope.new_model_nomination_scope("c4", "c4#req", "named_brain_region_or_network")
        prior_accepted = [
            {
                "proposition_id": narrower_units[0]["proposition_ids"][0],
                "exact_text": "amygdala",
                "supporting_proposition_ids": [narrower_units[0]["proposition_ids"][0]],
            }
        ]
        prior_receipt = mscope.new_nomination_receipt(
            scope,
            model_name="old",
            request_fingerprint="irrelevant",
            candidates_offered=[],
            accepted=prior_accepted,
            status="fresh",
        )
        ctx = mscope.new_nomination_context(
            mscope.exact_scope_set_policy([other_target]),
            prior_receipts={mscope.new_model_nomination_key(scope): prior_receipt},
        )
        client = _FakeModelClient(
            {
                narrower_units[0]["proposition_ids"][0]: "amygdala",
                broader_units[1]["proposition_ids"][0]: "hippocampus",
            }
        )
        result = sm._bind_role_candidates(
            self._role_spec(),
            broader_units,
            model_client=client,
            child_id="c5",
            requirement_id="c5#req",
            nomination_context=ctx,
        )
        self.assertEqual(
            client.calls, [], "a held-fixed scope must never call the model regardless of broadened candidates"
        )
        self.assertEqual(
            {r["exact_text"] for r in result},
            {"amygdala"},
            "only the PRIOR decision is replayed -- "
            "the newly-added hippocampus unit is "
            "never considered for a held-fixed scope",
        )


class MapRequirementPhase19ForkMemoizationTests(unittest.TestCase):
    """The audit's real finding (§3/§8/§J): a later role reached once per pre-existing fork must
    cost exactly one physical model call per mapping pass when every invocation is the same
    request -- proven here through the REAL `map_requirement` fork mechanics, not a bare
    `resolve_nomination` unit test."""

    def test_a_later_role_forked_by_an_earlier_one_calls_the_model_exactly_once(self):
        specs = {
            "culture_or_population": se.new_role_spec(
                "culture_or_population", "a named culture", "model_nomination_only"
            ),
            "operationalization_or_measure": se.new_role_spec(
                "operationalization_or_measure", "how it was measured", "model_nomination_only"
            ),
        }
        completion = se.new_role_completion(required_roles=["culture_or_population", "operationalization_or_measure"])
        req = se.new_requirement("c11#req", "relational", specs, completion, "exists")
        units = [_unit("u1", 1, "Hadza and U.S. participants were assessed using the IRI questionnaire.")]
        pid = units[0]["proposition_ids"][0]

        # Role 1 forks into 2 instances from one passage (two distinct cultures named).
        first_role_client = _FakeModelClient({pid: ["Hadza", "U.S."]})

        class _CombinedClient:
            model_name = "combined-fake"

            def __init__(self):
                self.calls = []

            def nominate_sufficiency_role(self, *, category_description, candidates):
                self.calls.append(category_description)
                if category_description == "a named culture":
                    return first_role_client.nominate_sufficiency_role(
                        category_description=category_description, candidates=candidates
                    )
                # Role 2: the SAME units_here/role_spec every time it's reached -- byte-identical
                # requests across both forks of role 1.
                return [{"proposition_id": pid, "exact_text": "IRI questionnaire"}]

        client = _CombinedClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        result = sm.map_requirement(req, units, model_client=client, child_id="c11", nomination_context=ctx)

        role2_calls = [c for c in client.calls if c == "how it was measured"]
        self.assertEqual(len(result["instances"]), 2, "role 1 must still fork into 2 instances")
        self.assertEqual(
            len(role2_calls),
            1,
            "role 2 is reached once per pre-existing fork (2x) but must cost exactly ONE physical "
            "model call this pass -- the confirmed audit §3/§8 redundancy, now memoized",
        )
        for instance in result["instances"]:
            self.assertEqual(
                instance["role_bindings"]["operationalization_or_measure"]["exact_text"], "IRI questionnaire"
            )

    def test_result_semantics_match_what_the_old_repeated_call_pattern_would_have_produced(self):
        """Same scenario, but WITHOUT a nomination_context (legacy path, repeated calls) --
        confirms memoization changes nothing observable about the final mapped result."""
        specs = {
            "culture_or_population": se.new_role_spec(
                "culture_or_population", "a named culture", "model_nomination_only"
            ),
            "operationalization_or_measure": se.new_role_spec(
                "operationalization_or_measure", "how it was measured", "model_nomination_only"
            ),
        }
        completion = se.new_role_completion(required_roles=["culture_or_population", "operationalization_or_measure"])
        req = se.new_requirement("c11#req", "relational", specs, completion, "exists")
        units = [_unit("u1", 1, "Hadza and U.S. participants were assessed using the IRI questionnaire.")]
        pid = units[0]["proposition_ids"][0]

        class _DeterministicClient:
            model_name = "deterministic-fake"

            def nominate_sufficiency_role(self, *, category_description, candidates):
                if category_description == "a named culture":
                    return [
                        {"proposition_id": pid, "exact_text": "Hadza"},
                        {"proposition_id": pid, "exact_text": "U.S."},
                    ]
                return [{"proposition_id": pid, "exact_text": "IRI questionnaire"}]

        legacy_result = sm.map_requirement(req, units, model_client=_DeterministicClient(), child_id="c11")
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        memoized_result = sm.map_requirement(
            req, units, model_client=_DeterministicClient(), child_id="c11", nomination_context=ctx
        )

        def _strip(result):
            return [
                {
                    role: {"exact_text": b.get("exact_text"), "state": b.get("state")}
                    for role, b in inst["role_bindings"].items()
                }
                for inst in sorted(result["instances"], key=lambda i: i["instance_key"] or "")
            ]

        self.assertEqual(_strip(legacy_result), _strip(memoized_result))


class MapRequirementPhase19bMultiInstancePartitionTests(unittest.TestCase):
    """The Phase-21-preflight finding, reproduced synthetically (never by excluding the real c12
    case, which lives in `test_sufficiency_phase19b_real_v9_replay.py`): a `multi_instance=True`,
    no-parent-context requirement with ≥2 real candidate units offers a DIFFERENT, disjoint
    candidate pool to the SAME `(child_id, requirement_id, role)` authorization scope once per
    unit (`build_multi_instances`). Before Phase 19b this raised `RequestFingerprintMismatch`
    before even reaching the second unit; `request_context` (the per-unit `root_key`) now gives
    each its own receipt slot."""

    def test_single_model_role_two_units_shape_matches_real_c8(self):
        """c8's own shape: ONE model_nomination_only role, `open_list`, no parent context --
        currently dormant in real v9 evidence (only 1 real unit today) but structurally identical
        to c12's crash-prone shape the moment a second unit exists."""
        specs = {
            "individual_difference_trait_or_construct": se.new_role_spec(
                "individual_difference_trait_or_construct", "a named trait or construct", "model_nomination_only"
            )
        }
        completion = se.new_role_completion(required_roles=["individual_difference_trait_or_construct"])
        req = se.new_requirement("c8#req", "atomic", specs, completion, "open_list", multi_instance=True)
        units = [
            _unit("U1", 1, "Participants completed the empathy quotient scale."),
            _unit("U2", 2, "The researchers also measured disgust sensitivity in this sample."),
        ]
        client = _FakeModelClient(
            {units[0]["proposition_ids"][0]: "empathy", units[1]["proposition_ids"][0]: "disgust sensitivity"}
        )
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())

        # Before Phase 19b: RequestFingerprintMismatch here. Now: completes cleanly.
        result = sm.map_requirement(req, units, model_client=client, child_id="c8", nomination_context=ctx)

        self.assertEqual(len(result["instances"]), 2)
        texts = {
            i["role_bindings"]["individual_difference_trait_or_construct"]["exact_text"] for i in result["instances"]
        }
        self.assertEqual(texts, {"empathy", "disgust sensitivity"})
        keys = [
            k for k in ctx["in_pass_receipts"] if k[0] == ("c8", "c8#req", "individual_difference_trait_or_construct")
        ]
        self.assertEqual({k[1] for k in keys}, {"U1", "U2"})
        self.assertEqual(len(client.calls), 2)  # one physical call per unit, never zero, never more

    def test_two_model_roles_two_units_shape_matches_real_c11_and_c12(self):
        """c11/c12's own shape: TWO model_nomination_only roles on one multi_instance requirement
        with no parent context -- real q_aib c12 is the confirmed-crashing case this fix targets."""
        specs = {
            "intervention": se.new_role_spec("intervention", "a named intervention", "model_nomination_only"),
            "target_manifestation": se.new_role_spec(
                "target_manifestation", "what it targeted", "model_nomination_only"
            ),
        }
        completion = se.new_role_completion(required_roles=["intervention", "target_manifestation"])
        req = se.new_requirement("c12#req", "relational", specs, completion, "exists", multi_instance=True)
        units = [
            _unit("U1", 1, "A mindfulness training reduced implicit bias scores."),
            _unit("U5", 2, "Perspective-taking exercises reduced explicit prejudice."),
        ]
        pid1, pid5 = units[0]["proposition_ids"][0], units[1]["proposition_ids"][0]

        class _TwoUnitClient:
            model_name = "fake-c12-shape"

            def __init__(self):
                self.calls: list[dict] = []

            def nominate_sufficiency_role(self, *, category_description, candidates):
                self.calls.append({"category_description": category_description, "candidates": candidates})
                (candidate,) = candidates  # exactly one admissible candidate per unit-scoped call
                scripted = {
                    (pid1, "a named intervention"): "mindfulness training",
                    (pid1, "what it targeted"): "implicit bias",
                    (pid5, "a named intervention"): "perspective-taking exercises",
                    (pid5, "what it targeted"): "explicit prejudice",
                }
                text = scripted[(candidate["proposition_id"], category_description)]
                return [{"proposition_id": candidate["proposition_id"], "exact_text": text}]

        client = _TwoUnitClient()
        ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        result = sm.map_requirement(req, units, model_client=client, child_id="c12", nomination_context=ctx)

        self.assertEqual(len(result["instances"]), 2)
        self.assertEqual(len(client.calls), 4)  # 2 roles x 2 units, never collapsed, never crashed
        u1_keys = [k for k in ctx["in_pass_receipts"] if k[0][0] == "c12" and k[1] == "U1"]
        u5_keys = [k for k in ctx["in_pass_receipts"] if k[0][0] == "c12" and k[1] == "U5"]
        self.assertEqual(len(u1_keys), 2)
        self.assertEqual(len(u5_keys), 2)
        # receipt A (U1's intervention) must never equal receipt B (U5's intervention)
        intervention_u1 = ctx["in_pass_receipts"][(("c12", "c12#req", "intervention"), "U1")]
        intervention_u5 = ctx["in_pass_receipts"][(("c12", "c12#req", "intervention"), "U5")]
        self.assertNotEqual(intervention_u1["accepted"], intervention_u5["accepted"])

    def test_u2_held_fixed_rebuild_of_the_synthetic_two_unit_shape_makes_zero_fresh_calls(self):
        specs = {
            "individual_difference_trait_or_construct": se.new_role_spec(
                "individual_difference_trait_or_construct", "a named trait or construct", "model_nomination_only"
            )
        }
        completion = se.new_role_completion(required_roles=["individual_difference_trait_or_construct"])
        req = se.new_requirement("c8#req", "atomic", specs, completion, "open_list", multi_instance=True)
        units = [
            _unit("U1", 1, "Participants completed the empathy quotient scale."),
            _unit("U2", 2, "The researchers also measured disgust sensitivity in this sample."),
        ]
        client = _FakeModelClient(
            {units[0]["proposition_ids"][0]: "empathy", units[1]["proposition_ids"][0]: "disgust sensitivity"}
        )
        u1_ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
        sm.map_requirement(req, units, model_client=client, child_id="c8", nomination_context=u1_ctx)
        self.assertEqual(len(client.calls), 2)

        u1_snapshot = dict(u1_ctx["in_pass_receipts"])
        u2_ctx = mscope.new_nomination_context(mscope.exact_scope_set_policy(set()), prior_receipts=u1_snapshot)
        result = sm.map_requirement(req, units, model_client=client, child_id="c8", nomination_context=u2_ctx)

        self.assertEqual(len(client.calls), 2, "U2 must make zero additional physical calls")
        texts = {
            i["role_bindings"]["individual_difference_trait_or_construct"]["exact_text"] for i in result["instances"]
        }
        self.assertEqual(texts, {"empathy", "disgust sensitivity"})  # both held-fixed bindings replayed correctly


class MapAnyRequirementPhase19ChildIdThreadingTests(unittest.TestCase):
    """Proves child_id reaches the real scope even when requirement ids do NOT follow the
    "childid#..." naming convention -- i.e. child_id is genuinely threaded, never parsed back out
    of the requirement id string (audit §4, test #6)."""

    def test_child_id_threaded_even_when_requirement_id_does_not_start_with_it(self):
        specs = {"region": se.new_role_spec("region", "a region", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["region"])
        # Deliberately misleading id -- looks like it belongs to "zzz", not "c4".
        req = se.new_requirement("zzz#totally-unrelated-id", "atomic", specs, completion, "exists")
        units = [_unit("u1", 1, "The amygdala showed increased activity.")]
        pid = units[0]["proposition_ids"][0]
        client = _FakeModelClient({pid: "amygdala"})

        target_scope = mscope.new_model_nomination_scope("c4", "zzz#totally-unrelated-id", "region")
        ctx = mscope.new_nomination_context(mscope.exact_scope_set_policy([target_scope]))

        result = sm.map_any_requirement(req, units, model_client=client, child_id="c4", nomination_context=ctx)
        self.assertEqual(result["instances"][0]["role_bindings"]["region"]["exact_text"], "amygdala")
        self.assertEqual(len(client.calls), 1)


class MapPairedRequirementPhase19Tests(unittest.TestCase):
    """Descendant propagation stays architecturally untouched (audit §13/§Q): a fresh parent
    scope updates a paired child with zero extra model calls, and an INDEPENDENT descendant
    model-assisted role is never authorized merely because its parent was the recovery target."""

    def test_independent_descendant_role_is_held_fixed_unless_its_own_scope_is_named(self):
        parent_specs = {"region": se.new_role_spec("region", "a region", "model_nomination_only")}
        parent_completion = se.new_role_completion(required_roles=["region"])
        parent_req = se.new_requirement("c4#req", "atomic", parent_specs, parent_completion, "exists")
        parent_units = [_unit("pu1", 1, "The amygdala showed increased activity.")]
        parent_client = _FakeModelClient({parent_units[0]["proposition_ids"][0]: "amygdala"})
        parent_target = mscope.new_model_nomination_scope("c4", "c4#req", "region")
        parent_ctx = mscope.new_nomination_context(mscope.exact_scope_set_policy([parent_target]))
        mapped_parent = sm.map_requirement(
            parent_req, parent_units, model_client=parent_client, child_id="c4", nomination_context=parent_ctx
        )

        child_specs = {
            "region": se.new_role_spec("region", "a region", "model_nomination_only"),
            "own_independent_role": se.new_role_spec(
                "own_independent_role", "an unrelated independent finding", "model_nomination_only"
            ),
        }
        child_completion = se.new_role_completion(required_roles=["region", "own_independent_role"])
        child_req = se.new_requirement(
            "c5#req", "relational", child_specs, child_completion, "exists", parent_context_roles=["region"]
        )
        child_units = [_unit("cu1", 1, "A behavioral effect was independently observed.")]

        class _ShouldNeverBeCalledClient:
            model_name = "should-not-be-called"

            def nominate_sufficiency_role(self, *, category_description, candidates):
                raise AssertionError("an unauthorized, unrelated descendant scope must never call the model")

        # Same policy object (parent-only authorization) reused for the child's own mapping pass.
        result = sm.map_paired_requirement(
            child_req,
            mapped_parent,
            child_units,
            model_client=_ShouldNeverBeCalledClient(),
            child_id="c5",
            nomination_context=parent_ctx,
        )
        self.assertEqual(result["instances"][0]["role_bindings"]["region"]["exact_text"], "amygdala")
        self.assertEqual(
            result["instances"][0]["role_bindings"]["region"]["provenance"]["candidate_source"], "parent_context"
        )
        self.assertEqual(result["instances"][0]["role_bindings"]["own_independent_role"]["state"], "missing")


if __name__ == "__main__":
    unittest.main()
