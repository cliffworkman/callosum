"""Layer B tests: extraction, supersession provenance, and a golden-output test that authors
q_aib's own contract end-to-end against the REAL preserved hierarchy contract -- no model, no
network, no E2E. Follows `test_overview_replay_real.py`'s own env-var-gated-skip idiom.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_authoring as sa
from experiments.ask_cli_revised import sufficiency_engine as se

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "q-aib-hierarchical-t5c-live-20260930"
    / "run"
    / "01_request_contract.json"
)
_PATH = Path(os.environ.get("QAIB_REQUEST_CONTRACT", str(_DEFAULT_PATH)))
needs_real_contract = unittest.skipUnless(
    _PATH.is_file(), f"the preserved q_aib request contract is not present at {_PATH}"
)


def _load_children_by_id() -> dict:
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    return {c["child_id"]: c for c in data["hierarchy"]["children"]}


class ExtractionTests(unittest.TestCase):
    def test_extract_recorded_requirements_reads_qualifications_and_requirements(self):
        child = {
            "qualifications": [
                {"id": "c4#constraint:evidence-establishes", "text": "the request asks what the evidence establishes"}
            ],
            "requirements": [
                {
                    "id": "RC-9#scope:measures-of-behavior",
                    "text": "measures of behavior",
                    "class": "human_review_meaning",
                }
            ],
            "structural_requirements": [{"id": "RC-5#pair", "state": "members_present"}],
            "scope_carrier": {
                "from": "c10",
                "wording": "is there any cross-cultural evidence for the anomalous is bad bias?",
            },
        }
        fragments = sa.extract_recorded_requirements(child)
        ids = {f["id"] for f in fragments}
        self.assertIn("c4#constraint:evidence-establishes", ids)
        self.assertIn("RC-9#scope:measures-of-behavior", ids)
        self.assertIn("RC-5#pair", ids)
        self.assertIn("scope_carrier:c10", ids)

    def test_extract_recorded_requirements_on_an_empty_child_returns_nothing(self):
        self.assertEqual(sa.extract_recorded_requirements({}), [])


class SupersessionProvenanceTests(unittest.TestCase):
    def test_author_supersession_attaches_dated_attributed_record(self):
        specs = {"a": se.new_role_spec("a", "a", "model_nomination_only")}
        completion = se.new_role_completion(required_roles=["a"])
        req = se.new_requirement("x#req", "atomic", specs, completion, "exists")
        superseded = sa.author_supersession(req, authorized_by="Cliff", date="2026-09-30", rationale="test")
        self.assertEqual(superseded["_authored"]["authorized_by"], "Cliff")
        self.assertEqual(superseded["_authored"]["date"], "2026-09-30")
        # the underlying requirement is otherwise untouched
        self.assertEqual(superseded["id"], req["id"])

    def test_d1_supersession_scope_is_sufficiency_assessment_only(self):
        self.assertEqual(sa.D1_SUFFICIENCY_SUPERSESSION["supersedes"], "D-1")
        self.assertIn("Sufficiency assessment only", sa.D1_SUFFICIENCY_SUPERSESSION["scope"])

    def test_d1_supersession_never_mutates_hierarchy_contracts_own_record(self):
        before = dict(hc.D1_RECORD)
        sa.assert_hierarchy_contract_untouched(hc)
        self.assertEqual(hc.D1_RECORD, before)

    def test_c3_supersession_is_scoped_to_sufficiency_not_the_hierarchy_pin(self):
        self.assertEqual(sa.C3_SEMANTIC_SUPERSESSION["child_id"], "c3")
        self.assertIn("hierarchy contract's own c3 record", sa.C3_SEMANTIC_SUPERSESSION["note"])


@needs_real_contract
class GoldenOutputContractTests(unittest.TestCase):
    """Authors q_aib's contract end-to-end against the REAL preserved hierarchy contract and
    checks it matches the approved design (§9 of the plan) exactly."""

    @classmethod
    def setUpClass(cls):
        cls.children = _load_children_by_id()
        cls.contract = sa.build_qaib_contract(cls.children)

    def test_all_eleven_children_present(self):
        expected = {"c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"}
        self.assertEqual(set(self.contract), expected)

    def test_c1_role_completion_matches_design(self):
        req = self.contract["c1"]["requirements"][0]
        self.assertEqual(req["role_completion"]["required_roles"], ["neural_manifestation_evidence"])
        self.assertEqual(
            req["role_completion"]["alternative_role_groups"],
            [["neural_measure_or_modality", "brain_region_or_network"]],
        )
        self.assertEqual(req["instance_quantifier"], "exists")
        self.assertIsNone(req["direction"])
        self.assertIn(self.children["c1"]["wording"], req["source_wording_span"])

    def test_c2_requires_both_identification_and_manifestation(self):
        req = self.contract["c2"]["requirements"][0]
        self.assertEqual(
            set(req["role_completion"]["required_roles"]),
            {"behavior_or_behavioral_measure", "behavioral_manifestation_evidence"},
        )

    def test_c3_has_two_requirements_atomic_and_cardinality(self):
        reqs = self.contract["c3"]["requirements"]
        self.assertEqual(len(reqs), 2)
        kinds = {r["kind"] for r in reqs}
        self.assertEqual(kinds, {"atomic", "cardinality"})
        cardinality = next(r for r in reqs if r["kind"] == "cardinality")
        self.assertEqual(cardinality["instance_quantifier"], "all_requested_categories")
        terms = cardinality["role_specs"]["category_evidence"]["requested_category_terms"]
        self.assertEqual(set(terms), {"implicit", "explicit"})
        self.assertIn("_authored", cardinality)

    def test_c4_requires_named_region_and_relevance_and_allows_empty_result(self):
        req = self.contract["c4"]["requirements"][0]
        self.assertEqual(
            set(req["role_completion"]["required_roles"]),
            {"named_brain_region_or_network", "region_bears_on_bias_evidence"},
        )
        self.assertTrue(req["empty_result_semantically_allowed"])

    def test_c5_and_c6_keep_direction_c1_and_c2_do_not(self):
        c5_req = self.contract["c5"]["requirements"][0]
        c6_relational = next(r for r in self.contract["c6"]["requirements"] if r["kind"] == "relational")
        self.assertIsNotNone(c5_req["direction"])
        self.assertIsNotNone(c6_relational["direction"])
        for cid in ("c1", "c2"):
            for req in self.contract[cid]["requirements"]:
                self.assertIsNone(req["direction"])

    def test_c9_is_relational_paired_not_cardinality(self):
        req = self.contract["c9"]["requirements"][0]
        self.assertEqual(req["kind"], "relational")
        self.assertEqual(req["instance_quantifier"], "for_each_discovered_instance")
        self.assertEqual(req["parent_context_roles"], ["individual_difference_trait_or_construct"])

    def test_c11_is_for_each_discovered_instance_not_a_bare_exists(self):
        req = self.contract["c11"]["requirements"][0]
        self.assertEqual(req["instance_quantifier"], "for_each_discovered_instance")
        self.assertNotEqual(req["instance_quantifier"], "exists")

    def test_c12_uses_effectiveness_assessment_not_a_signed_direction(self):
        req = self.contract["c12"]["requirements"][0]
        self.assertIsNone(req["direction"])
        self.assertIsNotNone(req["effectiveness"])
        self.assertEqual(
            set(req["role_completion"]["required_roles"]),
            {"intervention", "target_manifestation", "observed_effect_or_outcome"},
        )

    def test_c8_is_open_list_multi_instance(self):
        req = self.contract["c8"]["requirements"][0]
        self.assertEqual(req["instance_quantifier"], "open_list")
        self.assertTrue(req["multi_instance"])

    def test_no_hidden_benchmark_vocabulary_in_any_role_description(self):
        """A cheap, additional local check alongside the dedicated leakage suite (whole-word
        matched -- a bare substring check on a short acronym like "IRI" false-positives on
        ordinary English): none of the contract's own role descriptions/source spans accidentally
        echo an obviously benchmark-specific instrument acronym absent from the approved wording."""
        import re

        forbidden = ("iat", "ebq", "iri", "dg", "ug", "hadza")
        for contract in self.contract.values():
            for req in contract["requirements"]:
                for spec in req["role_specs"].values():
                    text = f"{spec['category_description']} {spec['source_wording_span']}"
                    for term in forbidden:
                        self.assertIsNone(re.search(rf"\b{term}\b", text, re.IGNORECASE))


@needs_real_contract
class FreezeTests(unittest.TestCase):
    def test_freeze_is_a_pure_dict_never_written_to_disk_here(self):
        children = _load_children_by_id()
        contract = sa.build_qaib_contract(children)
        frozen = sa.freeze(contract)
        self.assertEqual(frozen["question_key"], sa.QUESTION_KEY)
        self.assertIn("UNREVIEWED_CANDIDATE", frozen["status"])
        self.assertEqual(set(frozen["per_child"]), set(contract))
        self.assertIn("D1", frozen["supersessions"])
        self.assertIn("C3", frozen["supersessions"])

    def test_freeze_hash_stable_across_repeated_calls(self):
        children = _load_children_by_id()
        contract1 = sa.build_qaib_contract(children)
        contract2 = sa.build_qaib_contract(children)
        self.assertEqual(sa.freeze(contract1)["combined_hash"], sa.freeze(contract2)["combined_hash"])


if __name__ == "__main__":
    unittest.main()
