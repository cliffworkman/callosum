"""Phase 26: the deterministic parent-synthesis renderer and construction record. No model client."""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import parent_synthesis_render as psr
from experiments.ask_cli_revised import parent_synthesis_test_support as pst
from experiments.ask_cli_revised import sufficiency_engine as se


def _one_role_value_claim():
    sealed = pst.sealed_with(("p1", 1, "the amygdala", ["x"]))
    specs = {"region": pst.spec("region", "a named brain region")}
    completion = se.new_role_completion(required_roles=["region"])
    req = pst.requirement(
        "x#req", specs, completion, "exists", [pst.instance({"region": pst.filled("region", "p1", "the amygdala")})]
    )
    return psl.build_claim_ledger(pst.map_with("x", req), sealed), sealed


class RenderAnswerShapeTests(unittest.TestCase):
    def test_sections_appear_in_order(self):
        claims, _sealed = _one_role_value_claim()
        text = psr.render_answer(claims, [])
        for heading in (
            "# Overview",
            "## Qualified / heterogeneous findings",
            "## Supporting findings",
            "## Unresolved parts",
        ):
            self.assertIn(heading, text)
        self.assertLess(text.index("# Overview"), text.index("## Qualified / heterogeneous findings"))
        self.assertLess(text.index("## Qualified / heterogeneous findings"), text.index("## Supporting findings"))
        self.assertLess(text.index("## Supporting findings"), text.index("## Unresolved parts"))

    def test_a_role_value_claim_renders_literally(self):
        claims, _sealed = _one_role_value_claim()
        text = psr.render_answer(claims, [])
        self.assertIn("a named brain region: the amygdala", text)

    def test_relational_claim_renders_every_role_without_inventing_a_sentence(self):
        sealed = pst.sealed_with(("p1", 1, "amygdala and avoidance", ["x"]))
        specs = {"region": pst.spec("region", "a named region"), "behavior": pst.spec("behavior", "a named behavior")}
        completion = se.new_role_completion(required_roles=["region", "behavior"])
        inst = pst.instance(
            {
                "region": pst.filled("region", "p1", "the amygdala", source="model_mapping"),
                "behavior": pst.filled("behavior", "p1", "avoidance"),
            }
        )
        req = pst.requirement("x#req", specs, completion, "exists", [inst], kind="relational")
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        text = psr.render_answer(claims, [])
        self.assertIn("region: the amygdala", text)
        self.assertIn("behavior: avoidance", text)

    def test_category_list_claim_joins_members_under_one_shared_category(self):
        sealed = pst.sealed_with(("p1", 1, "region a", ["x"]), ("p2", 2, "region b", ["x"]))
        specs = {"region": pst.spec("region", "a named region")}
        completion = se.new_role_completion(required_roles=["region"])
        instances = [
            pst.instance({"region": pst.filled("region", "p1", "region a", source="model_mapping")}),
            pst.instance({"region": pst.filled("region", "p2", "region b", source="model_mapping")}),
        ]
        req = pst.requirement("x#req", specs, completion, "exists", instances)
        claims = psl.build_claim_ledger(pst.map_with("x", req), sealed)
        text = psr.render_answer(claims, [])
        line = next(ln for ln in text.splitlines() if "a named region" in ln and "region a" in ln)
        self.assertIn("region b", line)

    def test_heterogeneous_direction_claim_appears_under_qualified_never_in_overview(self):
        sealed = pst.sealed_with(
            ("p1", 1, "Intervention X showed decreased bias scores in the treatment group.", ["x"]),
            ("p2", 2, "No significant effect of Intervention X on bias scores was observed.", ["x"]),
        )
        specs = {"a": pst.spec("a", "category a")}
        completion = se.new_role_completion(required_roles=["a"])
        inst1 = pst.instance({"a": pst.filled("a", "p1", "decreased bias scores")}, instance_key="i1")
        inst2 = pst.instance({"a": pst.filled("a", "p2", "no significant effect")}, instance_key="i2")
        req = pst.requirement(
            "x#req",
            specs,
            completion,
            "for_each_discovered_instance",
            [inst1, inst2],
            multi_instance=True,
            effectiveness=se.new_effectiveness_assessment(),
        )
        from experiments.ask_cli_revised import sufficiency_diagnostic as sd

        smf = pst.map_with("x", req)
        sd.compute_direction_and_effectiveness(sealed, smf, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION)
        claims = psl.build_claim_ledger(smf, sealed)
        text = psr.render_answer(claims, [])
        overview_section = text.split("## Qualified")[0]
        self.assertNotIn("effectiveness", overview_section.lower())
        qualified_section = text.split("## Qualified")[1].split("## Supporting")[0]
        self.assertIn("heterogen", qualified_section.lower())

    def test_consensus_direction_claim_appears_in_overview_not_qualified(self):
        sealed, smf = pst.real_c12_fixture()
        claims = psl.build_claim_ledger(smf, sealed)
        text = psr.render_answer(claims, [])
        overview_section = text.split("## Qualified")[0]
        self.assertIn("supported", overview_section.lower())

    def test_gap_report_renders_under_unresolved_parts_by_reason(self):
        gaps = [
            {
                "target_id": "x::1",
                "search_child_id": "x",
                "requirement_id": "x#req",
                "target_roles": ["a"],
                "reason": "missing",
                "goal_mode": "single_role",
                "category_descriptions": ["category a"],
            }
        ]
        text = psr.render_answer([], gaps)
        unresolved = text.split("## Unresolved parts")[1]
        self.assertIn("category a", unresolved)
        self.assertIn("missing", unresolved)

    def test_no_claims_or_gaps_is_still_a_readable_answer(self):
        text = psr.render_answer([], [])
        self.assertIsInstance(text, str)
        self.assertIn("# Overview", text)

    def test_the_c12_wrong_value_renders_unflagged_and_unfixed(self):
        """The deterministic renderer must not "fix" or suppress the known-wrong upstream value."""
        sealed, smf = pst.real_c12_fixture()
        claims = psl.build_claim_ledger(smf, sealed)
        text = psr.render_answer(claims, [])
        self.assertIn(pst.C12_WRONG_TARGET_MANIFESTATION_TEXT, text)


class SupportingFindingsWithSealedTests(unittest.TestCase):
    def test_sealed_optional_passage_enriches_supporting_findings(self):
        claims, sealed = _one_role_value_claim()
        without = psr.render_answer(claims, [])
        with_sealed = psr.render_answer(claims, [], sealed=sealed)
        self.assertNotIn("Paper 1", without)
        self.assertIn("Paper 1", with_sealed)


class ConstructionRecordTests(unittest.TestCase):
    def test_construction_record_schema_and_hash(self):
        claims, sealed = _one_role_value_claim()
        record = psr.construction_record(claims, [], sealed_hash="sealedhash123", sufficiency_map_hash="maphash456")
        for key in (
            "version",
            "sealed_ledger_hash",
            "sufficiency_map_final_hash",
            "claim_ledger",
            "gap_report",
            "realization_state",
            "fallback_used",
            "parent_synthesis_hash",
        ):
            self.assertIn(key, record)
        self.assertEqual(record["realization_state"], "deterministic_only")
        self.assertTrue(record["fallback_used"])
        self.assertEqual(record["sealed_ledger_hash"], "sealedhash123")
        self.assertEqual(record["sufficiency_map_final_hash"], "maphash456")

    def test_hash_is_stable_and_excludes_itself(self):
        claims, sealed = _one_role_value_claim()
        record = psr.construction_record(claims, [], sealed_hash="h1", sufficiency_map_hash="h2")
        again = psr.construction_record(claims, [], sealed_hash="h1", sufficiency_map_hash="h2")
        self.assertEqual(record["parent_synthesis_hash"], again["parent_synthesis_hash"])

    def test_hash_changes_when_claims_change(self):
        claims, sealed = _one_role_value_claim()
        r1 = psr.construction_record(claims, [], sealed_hash="h1", sufficiency_map_hash="h2")
        r2 = psr.construction_record([], [], sealed_hash="h1", sufficiency_map_hash="h2")
        self.assertNotEqual(r1["parent_synthesis_hash"], r2["parent_synthesis_hash"])

    def test_no_fake_model_metadata(self):
        claims, sealed = _one_role_value_claim()
        record = psr.construction_record(claims, [], sealed_hash="h1", sufficiency_map_hash="h2")
        for forbidden in ("model", "think", "call", "prompt"):
            self.assertNotIn(forbidden, record)


class SufficiencyMapHashTests(unittest.TestCase):
    def test_order_invariant_over_child_insertion(self):
        _claims, _sealed = _one_role_value_claim()
        smf_a = {"x": {"child_id": "x", "requirements": []}, "y": {"child_id": "y", "requirements": []}}
        smf_b = {"y": {"child_id": "y", "requirements": []}, "x": {"child_id": "x", "requirements": []}}
        self.assertEqual(psl.sufficiency_map_hash(smf_a), psl.sufficiency_map_hash(smf_b))

    def test_changes_when_content_changes(self):
        smf_a = {"x": {"child_id": "x", "requirements": []}}
        smf_b = {"x": {"child_id": "x", "requirements": [{"id": "x#req"}]}}
        self.assertNotEqual(psl.sufficiency_map_hash(smf_a), psl.sufficiency_map_hash(smf_b))


if __name__ == "__main__":
    unittest.main()
