"""A hierarchical request on the reviewed route: one pipeline, and a record of what actually ran.

Real ``e2e.execute`` / ``e2e.run_topology`` over the frozen q_aib hierarchy and frozen scientific contract, with
scripted clients (no live model, no network). The review records here are test stand-ins, not approvals.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from experiments.ask_cli_revised import e2e, sufficiency_freeze
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised import reviewed_ask_inputs as ri
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import test_hierarchy_e2e as fixtures
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised._layerc_common import ProjectionIntegrityError
from experiments.ask_cli_revised.hierarchy_test_support import (
    CHILD_IDS,
    ArtifactCopy,
    HierHarness,
    c_supports_children,
    needs_artifacts,
    p_preserve,
    r_by_claim,
)
from experiments.ask_cli_revised.overview_test_support import Entail, OverviewClient
from experiments.ask_cli_revised.overview_test_support import record as overview_record
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.test_e2e_run import ScriptedClient, rec
from experiments.ask_cli_revised.test_hierarchy_child_overview_e2e import C1_CLAIM, C1_PASSAGE

STATEMENT = "The insular cortex showed greater activation for anomalous faces."


def reviewed_files(contract, science, parents, folder: Path, *, tamper=False):
    reporting = rc.from_hierarchy(contract, science, requested_construct_terms=[])
    review = {
        "schema": "reviewed-ask-inputs-v1",
        "status": "reviewed",
        "reviewed_by": "OFFLINE TEST AUTHOR; not a production approval",
        "reviewed_at": "2026-10-12",
        "inputs": ri.input_refs(contract, science, reporting, parents),
    }
    if tamper:
        reporting["nodes"][0]["literal_text"] += " (edited after review)"
    paths = folder / "reporting.json", folder / "review.json"
    paths[0].write_text(json.dumps(reporting), encoding="utf-8")
    paths[1].write_text(json.dumps(review), encoding="utf-8")
    return reporting, review, paths


@needs_artifacts
class ReportingFromHierarchyTests(unittest.TestCase):
    def test_one_node_per_approved_child_with_its_wording_parent_and_ownership(self):
        contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        science, parents = e2e._default_sufficiency_loader(contract)
        reporting = rc.from_hierarchy(contract, science, requested_construct_terms=[])
        nodes = {n["node_id"]: n for n in reporting["nodes"]}
        self.assertEqual(set(nodes), set(CHILD_IDS))
        wording = {
            sq["obligations"][0]["field_id"]: sq["obligations"][0]["note"] for sq in hc.hierarchy_subquestions(contract)
        }
        for cid, node in nodes.items():
            self.assertEqual(node["literal_text"], wording[cid])
            self.assertEqual(node["owning_child_ids"], [cid])
            self.assertEqual(node["parent_id"], None if parents.get(cid, "R") == "R" else parents[cid])
        self.assertEqual(reporting["scientific_only_child_ids"], [])
        rc.validate(reporting, contract, science)  # the reviewed route's own structural check accepts it


@needs_artifacts
class HierarchicalRequestOnTheReviewedRouteTests(unittest.TestCase):
    def setUp(self):
        self.artifacts = ArtifactCopy()
        self.addCleanup(self.artifacts.close)
        self.contract = self.artifacts.load()
        self.science, self.parents = e2e._default_sufficiency_loader(self.contract)

    def _run(self, *, reviewed: bool):
        inputs = None
        if reviewed:
            reporting = rc.from_hierarchy(self.contract, self.science, requested_construct_terms=[])
            review = {
                "schema": "reviewed-ask-inputs-v1",
                "status": "reviewed",
                "reviewed_by": "OFFLINE TEST AUTHOR; not a production approval",
                "reviewed_at": "2026-10-12",
                "inputs": ri.input_refs(self.contract, self.science, reporting, self.parents),
            }
            inputs = ri.bind_reviewed_inputs(self.contract, self.science, reporting, self.parents, review)
        answer = {"overview": [{"unit_ids": ["U1"], "bears_on": ["c1"], "text": STATEMENT}]}
        harness = HierHarness(
            topo.CHILD_OVERVIEW_PROFILES["T5C"],
            self.contract,
            initial=[overview_record(C1_CLAIM, C1_PASSAGE, sid="c1")],
            clients={
                "isolated": OverviewClient(
                    r=r_by_claim({C1_CLAIM: ["c1"]}),
                    c=c_supports_children({"c1": "p1"}),
                    p=p_preserve,
                    s=lambda prompt, schema: answer,
                )
            },
        )
        self.addCleanup(harness.close)
        with patch.object(e2e, "_paper_labels", lambda rt, ids: {}):
            result = harness.run(
                entail=Entail(),
                sufficiency_contract=self.science,
                sufficiency_parent_of=self.parents,
                parent_narrative_enabled=True,
                _reviewed_inputs=inputs,
            )
        return harness, result

    def test_the_reviewed_scientific_components_and_the_child_syntheses_both_execute(self):
        harness, result = self._run(reviewed=True)
        path = result["execution_path"]
        components = path["components"]
        self.assertEqual(path["route"], "reviewed")
        self.assertEqual(path["request_kind"], hc.HIER_VERSION)
        self.assertEqual(path["effective_semantics_versions"], [se.SUFFICIENCY_SEMANTICS_V8])
        self.assertTrue(components["layer_c_v2"]["executed"])
        self.assertEqual(components["layer_c_v2"]["evidence"]["profile"], "fresh-v8-layerc-v2-plan-v5")
        self.assertEqual(components["answer_plan_v5"]["evidence"]["nodes"], len(CHILD_IDS))
        self.assertTrue(components["child_synthesis"]["executed"])
        self.assertEqual(components["child_synthesis"]["evidence"]["children"], len(CHILD_IDS))
        self.assertTrue(components["narrative_parent_overview"]["executed"])
        self.assertFalse(components["legacy_parent_claim_realization"]["executed"])
        self.assertIn("parent_synthesis_v2", components["legacy_parent_claim_realization"]["skipped_reason"])
        self.assertFalse(components["model_nomination"]["executed"])
        out = harness.trace.dir
        self.assertEqual(json.loads((out / "21_execution_path.json").read_text(encoding="utf-8")), path)
        # the selected answer is the plan-v5 render, and the child syntheses and hierarchical document exist beside it
        selected = json.loads((out / "15_v2_output.json").read_text(encoding="utf-8"))["render"]["layer1"]
        self.assertEqual((out / "14_final_answer.md").read_text(encoding="utf-8").rstrip("\n"), selected.rstrip("\n"))
        self.assertIn(STATEMENT.rstrip("."), (out / "14_final_answer.c1.md").read_text(encoding="utf-8"))
        self.assertIn(STATEMENT.rstrip("."), (out / "19_hierarchical_answer.md").read_text(encoding="utf-8"))

    def test_an_empty_selected_answer_is_reported_with_what_withheld_each_part_not_masked(self):
        _, result = self._run(reviewed=True)
        selected = result["execution_path"]["selected_answer"]
        self.assertEqual(selected["nodes_with_statements"] + selected["nodes_without_statements"], len(CHILD_IDS))
        for row in selected["withheld_or_empty_attribution"]:
            if not row["statements"]:
                self.assertTrue(row["limitations"], row)  # every empty part names the limitation kinds behind it

    def test_without_reviewed_inputs_the_route_and_its_skips_are_stated(self):
        _, result = self._run(reviewed=False)
        path = result["execution_path"]
        self.assertEqual(path["route"], "hierarchical")
        self.assertEqual(path["effective_semantics_versions"], [se.SUFFICIENCY_SEMANTICS_VERSION])
        self.assertFalse(path["components"]["layer_c_v2"]["executed"])
        self.assertIn("reviewed", path["components"]["layer_c_v2"]["skipped_reason"])
        self.assertTrue(path["components"]["child_synthesis"]["executed"])


@needs_artifacts
class RunTopologyReviewedHierarchyTests(unittest.TestCase):
    """run_topology with model nomination and a recovery round, on the reviewed route."""

    def setUp(self):
        self.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        self.science = sufficiency_freeze.load_verified()
        self.parents = hc.parent_of(self.contract)
        self.profile = replace(topo.WAVE1["T0"], W=replace(topo.WAVE1["T0"].W, think=False))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _go(self, **flags):
        claim_b = fixtures.TargetedPostRecoveryRemapIntegrationTests.CLAIM_C5B
        shared = ScriptedClient(
            r=r_by_claim(
                {fixtures.CLAIM_C5: ["c5"], fixtures.CLAIM_C4: ["c4"], fixtures.CLAIM_C12: ["c12"], claim_b: ["c5"]}
            )
        )
        harness = HierHarness(
            self.profile,
            self.contract,
            initial=fixtures.INITIAL,
            recovery=[rec("c5", claim_b, chunk=21, origin="recovery")],
            clients={"shared": shared},
        )
        self.addCleanup(harness.close)
        harness.rt.close = lambda: None
        fake = fixtures._DeclineUnderTwoCandidatesClient()
        patches = [
            patch.object(e2e, "_initial_pass", harness._initial_pass),
            patch.object(e2e, "_recover_round", harness._recover_round),
            patch.object(topo, "resolve_profile", side_effect=lambda n: self.profile if n == "T0" else topo.WAVE1[n]),
            patch.object(
                e2e,
                "_sufficiency_u1_context",
                side_effect=lambda profile, bound: (fake, mscope.new_nomination_context(mscope.all_eligible_policy())),
            ),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return e2e.run_topology(
                "T0",
                "aib",
                db_path=self.root / "l.sqlite",
                library_frozen=self.root / "l.json",
                out_dir=self.root / "out",
                git_root=self.root,
                scored=False,
                hierarchy=True,
                hierarchy_loader=lambda question: harness.contract,
                authorization_checker=lambda auth, question: None,
                git_state_fn=lambda r: {"sha": "x", "branch": "b", "dirty_paths": []},
                verify_library=lambda db, frozen: {"sha256": "same"},
                verify_contracts=lambda: None,
                runtime_factory=lambda *a, **kw: harness.rt,
                client_factory=lambda url: shared,
                managed_chat=lambda config: shared,
                sufficiency_model_assist=True,
                sufficiency_recovery_gate=True,
                **flags,
            )

    def test_model_nomination_and_recovery_run_under_the_reviewed_semantics(self):
        _, _, (reporting, review) = reviewed_files(self.contract, self.science, self.parents, self.root)
        manifest = self._go(reviewed_reporting=reporting, reviewed_review=review)
        path = manifest["execution_path"]
        self.assertEqual(path["route"], "reviewed")
        self.assertEqual(path["effective_semantics_versions"], [se.SUFFICIENCY_SEMANTICS_V8])
        nomination = path["components"]["model_nomination"]
        self.assertTrue(nomination["executed"])
        self.assertGreater(nomination["evidence"]["initial"]["requests"], 0)
        self.assertTrue(path["components"]["recovery_round"]["executed"])
        self.assertTrue(path["components"]["layer_c_v2"]["executed"])
        self.assertTrue((self.root / "out" / "15_v2_output.json").is_file())
        self.assertEqual([s["stage"] for s in path["stage_models"]][:1], ["W1"])
        # the run's own mechanical checks still pass on this route
        self.assertEqual(manifest["technical_validity"], {"valid": True, "issues": []})

    def test_a_review_that_does_not_match_what_will_run_refuses_before_anything_is_written(self):
        _, _, (reporting, review) = reviewed_files(self.contract, self.science, self.parents, self.root, tamper=True)
        with self.assertRaises(ProjectionIntegrityError):
            self._go(reviewed_reporting=reporting, reviewed_review=review)
        self.assertFalse((self.root / "out").exists())

    def test_half_a_reviewed_input_pair_is_refused(self):
        with self.assertRaises(ValueError):
            self._go(reviewed_reporting=self.root / "reporting.json")

    def test_the_same_fixture_without_reviewed_inputs_stays_on_the_hierarchical_route(self):
        manifest = self._go()
        path = manifest["execution_path"]
        self.assertEqual(path["route"], "hierarchical")
        self.assertEqual(path["effective_semantics_versions"], [se.SUFFICIENCY_SEMANTICS_VERSION])
        self.assertFalse(path["components"]["layer_c_v2"]["executed"])
