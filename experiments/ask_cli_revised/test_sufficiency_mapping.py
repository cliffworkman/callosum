"""Tests for the deterministic-first mapping dispatch (by declared strategy, never role-name
inspection), per-role admissibility, and the explicitly-unbound model-nomination scaffold.
No model, no network, no E2E.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm


def _unit(unit_id, paper_id, passage, proposition_ids=None):
    flags = oe.passage_flags(passage)
    return {
        "unit_id": unit_id,
        "paper_id": paper_id,
        "passage": passage,
        "proposition_ids": proposition_ids or [f"{unit_id}-p"],
        "flags": flags,
        "attached_children": [],
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
        spec = se.new_role_spec("d", "d", "direction_or_sign_pattern")
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
        specs = {
            "region": se.new_role_spec("region", "region", "model_nomination_only"),
            "behavior": se.new_role_spec("behavior", "behavior", "achieved_outcome_predicate"),
        }
        completion = se.new_role_completion(required_roles=["region", "behavior"])
        req = se.new_requirement("r#req", "relational", specs, completion, "exists", parent_context_roles=["region"])
        parent_binding = se.new_role_binding(
            "region",
            state="filled",
            proposition_id="parent-p1",
            exact_text="amygdala",
            provenance={"candidate_source": "parent_context", "detail": "", "model": None},
        )
        # even with the region pre-seeded from a parent, no behavior evidence in this child's own
        # candidate units means the requirement stays incomplete.
        units = [_unit("U1", 1, "We administered the task to all participants.")]
        result = sm.map_requirement(req, units, parent_context_bindings={"region": parent_binding})
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


class PairedMappingTests(unittest.TestCase):
    def _parent_requirement_with_one_discovered_trait(self):
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
        instance["role_bindings"]["relation"] = se.new_role_binding("relation", state="missing", reason="not_found")
        parent["instances"] = [instance]
        return se.recompute_requirement(parent)

    def test_pairing_scoped_to_parents_currently_discovered_instances(self):
        parent = self._parent_requirement_with_one_discovered_trait()
        specs = {
            "trait": se.new_role_spec("trait", "trait", "model_nomination_only"),
            "scale": se.new_role_spec("scale", "named scale", "named_instrument_lexicon"),
        }
        completion = se.new_role_completion(required_roles=["trait", "scale"])
        req = se.new_requirement(
            "child#req",
            "relational",
            specs,
            completion,
            "for_each_discovered_instance",
            multi_instance=True,
            parent_context_roles=["trait"],
        )
        units = [_unit("U9", 2, "The Empathy Scale was used to assess trait empathy in participants.")]
        result = sm.map_paired_requirement(req, parent, units)
        self.assertEqual(len(result["instances"]), 1)
        self.assertEqual(result["state"], "filled")

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
    def test_map_direction_returns_none_when_not_declared(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("d#req", "relational", specs, completion, "exists")
        self.assertIsNone(sm.map_direction(req, []))

    def test_map_direction_honest_when_relationship_established_but_no_sign_reported(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement(
            "d#req", "relational", specs, completion, "exists", direction=se.new_direction_assessment()
        )
        units = [_unit("U1", 1, "A relationship was observed between the two measures.")]
        result = sm.map_direction(req, units)
        self.assertFalse(result["reported"])

    def test_map_effectiveness_null_result_is_reported_and_not_supported(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement(
            "e#req", "relational", specs, completion, "exists", effectiveness=se.new_effectiveness_assessment()
        )
        units = [_unit("U1", 1, "No significant effect on bias scores was observed for this intervention.")]
        result = sm.map_effectiveness(req, units)
        self.assertTrue(result["outcome_reported"])
        self.assertEqual(result["conclusion"], "not_supported")

    def test_map_effectiveness_attempt_only_language_leaves_outcome_unreported(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement(
            "e#req", "relational", specs, completion, "exists", effectiveness=se.new_effectiveness_assessment()
        )
        units = [_unit("U1", 1, "This intervention might potentially help reduce the bias in future work.")]
        result = sm.map_effectiveness(req, units)
        self.assertFalse(result["outcome_reported"])


class ModelNominationScaffoldTests(unittest.TestCase):
    def test_nominate_with_model_is_unbound(self):
        spec = se.new_role_spec("x", "x", "model_nomination_only")
        with self.assertRaises(NotImplementedError):
            sm.nominate_with_model(spec, [], model_client=None)

    def test_prompt_template_uses_category_description_only(self):
        rendered = sm.MODEL_NOMINATION_PROMPT_TEMPLATE.format(category_description="a named brain region")
        self.assertIn("a named brain region", rendered)
        self.assertNotIn("{", rendered)


if __name__ == "__main__":
    unittest.main()
