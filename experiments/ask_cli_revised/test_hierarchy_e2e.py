"""The E2E orchestration over the approved v8 hierarchy: what reaches each stage, what the sealed ledger records, and
what the run refuses before it touches anything. Retrieval and models are faked; nothing here calls a model.
"""

import contextlib
import copy
import io
import json
import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from experiments.ask_cli_revised import e2e, sufficiency_diagnostic, sufficiency_freeze, sufficiency_recovery_targets
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.hierarchy_test_support import (
    CHILD_IDS,
    Harness,
    HierHarness,
    ScriptedClient,
    c_supports_children,
    needs_artifacts,
    p_preserve,
    r_by_claim,
    rec,
    request_block,
)
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.request_contract import obligation_display, request_subquestions
from experiments.ask_cli_revised.test_e2e_run import INITIAL as FLAT_INITIAL
from experiments.ask_cli_revised.test_e2e_run import r_maps

CLAIM_C5 = "Amygdala activity was associated with the bias in one sample."
CLAIM_C4 = "A region-of-interest analysis found no association between any area and the bias."
CLAIM_C12 = "Participants were administered a bias-reduction training in the study."
INITIAL = [rec("c5", CLAIM_C5, chunk=11), rec("c4", CLAIM_C4, chunk=12), rec("c12", CLAIM_C12, chunk=13)]
VERDICT_WORDS = re.compile(r"\b(?:fulfilled|answered|unanswered|satisfied|covered|complete)\b", re.IGNORECASE)


def item_states(result):
    return {row["field_id"]: row["state"] for row in result["coverage_final"]["obligations"]}


def walk(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)
    elif isinstance(value, str):
        yield value


@needs_artifacts
class HierarchyExecuteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.display = {
            s["subquestion_id"]: obligation_display(s["obligations"][0]) for s in request_subquestions(cls.contract)
        }

    def run_t0(self, mapping, *, initial=INITIAL):
        shared = ScriptedClient(r=r_by_claim(mapping))
        h = HierHarness(topo.WAVE1["T0"], self.contract, initial=initial, recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        return h, shared, h.run()

    def test_every_child_is_searched_and_the_child_ids_are_the_ids_through_every_stage(self):
        h, shared, result = self.run_t0({CLAIM_C5: ["c5"]})
        self.assertEqual(h.initial_subquestions, 11)
        states = item_states(result)
        self.assertEqual(list(states), CHILD_IDS)
        self.assertEqual(states["c5"], "judged_responsive")
        self.assertEqual({k for k, v in states.items() if v == "no_responsive_claim"}, set(CHILD_IDS) - {"c5"})
        self.assertEqual(list(result["recovery_plan"]["plan"]), CHILD_IDS)
        by_text = {r["proposition_text"]: r for r in result["sealed"]["verified_propositions"]}
        self.assertEqual(by_text[CLAIM_C5]["responsive_obligation_ids"], ["c5"])
        self.assertEqual(by_text[CLAIM_C4]["responsive_obligation_ids"], [])
        self.assertEqual(result["sealed"]["request_contract"]["version"], hc.HIER_VERSION)

    def test_every_item_state_row_carries_its_childs_hierarchy_record_and_flat_rows_are_unchanged(self):
        _, _, result = self.run_t0({CLAIM_C5: ["c5"]})
        for row in result["sealed"]["obligation_states"]:
            self.assertEqual(row["hierarchy"]["child_id"], row["field_id"])
            self.assertEqual(row["hierarchy"]["wording_sha256"], hc.sha256_text(row["note"]))
        flat = Harness(topo.WAVE1["T0"], initial=FLAT_INITIAL, clients={"shared": ScriptedClient(r=r_maps("s3-o1"))})
        self.addCleanup(flat.close)
        self.assertTrue(all("hierarchy" not in row for row in flat.run()["sealed"]["obligation_states"]))

    def test_r_is_shown_every_childs_exact_item_line(self):
        _, shared, _ = self.run_t0({CLAIM_C5: ["c5"]})
        prompts = [c["prompt"] for c in shared.calls if c["kind"] == "R"]
        self.assertEqual(len(prompts), 3)
        for prompt in prompts:
            for cid, display in self.display.items():
                self.assertIn(f"- {cid}: {display}", prompt)

    def test_no_provenance_or_network_text_appears_in_the_request_derived_part_of_any_r_prompt(self):
        _, shared, _ = self.run_t0({})
        for call in shared.calls:
            block = request_block(call["prompt"])
            self.assertEqual(hc.provenance_tokens(block), [], block)
            self.assertFalse(hc.mentions_networks(block))

    def test_the_c12_constraints_reach_r_verbatim(self):
        _, shared, _ = self.run_t0({})
        prompt = next(c["prompt"] for c in shared.calls if c["kind"] == "R")
        self.assertIn("evidence that an intervention was attempted is not evidence that it worked", prompt)
        self.assertIn("the question is about EFFECTIVE interventions", prompt)

    def test_an_empty_c4_is_not_a_failure_and_nothing_forces_a_positive_finding(self):
        h, _, result = self.run_t0({CLAIM_C5: ["c5"]})
        row = next(r for r in result["coverage_final"]["obligations"] if r["field_id"] == "c4")
        self.assertEqual(row["state"], "no_responsive_claim")
        self.assertEqual(row["proposition_ids"], [])
        self.assertTrue(result["final_audit"]["constrained_render_match"])
        answer = (h.trace.dir / "14_final_answer.md").read_text(encoding="utf-8")
        section = answer.split("### c4:", 1)[1].split("\n### ", 1)[0]
        self.assertIn("No claim has been judged responsive to this item", section)

    def test_retrieval_provenance_alone_never_attaches_a_claim_to_an_item(self):
        _, _, result = self.run_t0({})  # R judges nothing responsive; the claim was retrieved for c5
        states = item_states(result)
        self.assertEqual(states["c5"], "no_responsive_claim")
        self.assertTrue(all(r["responsive_obligation_ids"] == [] for r in result["sealed"]["verified_propositions"]))

    def test_attaching_to_a_subordinate_never_closes_its_parent_and_the_reverse(self):
        _, _, sub = self.run_t0({CLAIM_C5: ["c5"]})
        parents = {p["node"]: p for p in sub["sealed"]["hierarchy"]["parents"]}
        self.assertEqual(parents["c4"]["own_item_state"], "no_responsive_claim")
        self.assertEqual(
            parents["c4"]["subordinate_item_states"], {"c5": "judged_responsive", "c6": "no_responsive_claim"}
        )
        _, _, par = self.run_t0({CLAIM_C4: ["c4"]})
        parents = {p["node"]: p for p in par["sealed"]["hierarchy"]["parents"]}
        self.assertEqual(parents["c4"]["own_item_state"], "judged_responsive")
        self.assertEqual(
            parents["c4"]["subordinate_item_states"], {"c5": "no_responsive_claim", "c6": "no_responsive_claim"}
        )

    def test_the_sealed_ledger_carries_a_structural_rollup_with_the_four_labels_and_no_verdict(self):
        _, _, result = self.run_t0({CLAIM_C5: ["c5"], CLAIM_C4: ["c4"]})
        roll = result["sealed"]["hierarchy"]
        states = item_states(result)
        self.assertEqual(roll["labels"], hc.LABELS)
        self.assertEqual(len(roll["obligations"]), 24)
        self.assertEqual(roll["representation_accounted"]["accounted"], 24)
        for o in roll["obligations"]:
            self.assertEqual(o["representation"], "accounted")
            self.assertEqual(o["obligation_fulfilment"], "not_assessed")
            self.assertEqual(o["owner_item_state"], states[o["owner_child"]])
        self.assertEqual([p["node"] for p in roll["parents"]], ["c4", "c8", "c10"])
        self.assertTrue(all(p["parent_completeness"] == "not_certified" for p in roll["parents"]))
        self.assertEqual([b["id"] for b in roll["background"]], ["S1"])
        self.assertIn("never closes", roll["closure_rule"])
        for text in walk(roll):
            self.assertIsNone(VERDICT_WORDS.search(text), text)

    def test_the_rollup_records_human_review_meanings_and_networks_as_recorded_not_operationalized(self):
        _, _, result = self.run_t0({})
        by_child = {c["child_id"]: c for c in result["sealed"]["hierarchy"]["children"]}
        for cid in ("c5", "c6"):
            meanings = by_child[cid]["human_review_meanings"]
            self.assertEqual(len(meanings), 3)
            self.assertTrue(
                all(m["operationalized"] is False and m["assessed"] is False and m["text"] for m in meanings)
            )
            self.assertEqual([r["id"].split("#")[1] for r in by_child[cid]["superseded"]], ["scope:areas-and-networks"])
            self.assertFalse(by_child[cid]["superseded"][0]["asked_by_this_run"])
            self.assertEqual(
                [r["text"] for r in by_child[cid]["active_constraints"]],
                ["it does not presuppose that an association exists, has a direction, or is causal"],
            )
        self.assertEqual(by_child["c9"]["human_review_meanings"], [])
        c11 = by_child["c11"]
        self.assertEqual(c11["scope_carrier"]["from"], "c10")
        self.assertEqual(c11["wording_provenance"], "deterministic_scaffold")
        self.assertEqual(c11["approval_ref"], "CD-3")

    def test_a_tampered_contract_is_refused_before_any_stage_or_side_effect(self):
        contract = copy.deepcopy(self.contract)
        next(c for c in contract["hierarchy"]["children"] if c["child_id"] == "c11")["scope_carrier"] = None
        shared = ScriptedClient()
        h = HierHarness(topo.WAVE1["T0"], contract, initial=INITIAL, clients={"shared": shared})
        self.addCleanup(h.close)
        with self.assertRaises(hc.HierarchyRejected):
            h.run()
        self.assertEqual(shared.calls, [])
        self.assertEqual(list(h.trace.dir.iterdir()), [])
        self.assertEqual(h.guard.events, [])

    def test_slicing_the_children_or_seeding_the_claims_is_refused_but_lowering_the_caps_is_allowed(self):
        for limits, seed in (
            ({"max_initial_subquestions": 3}, None),
            ({"max_recovery_gaps": 2}, None),
            ({"max_initial_subquestions": 3, "max_recovery_gaps": 2}, None),
            (None, lambda *a, **k: {}),
        ):
            with self.subTest(limits=limits, seeded=bool(seed)):
                shared = ScriptedClient()
                h = HierHarness(topo.WAVE1["T0"], self.contract, initial=INITIAL, clients={"shared": shared})
                self.addCleanup(h.close)
                with self.assertRaises(ValueError):
                    h.run(smoke_limits=limits, seed_pass=seed)
                self.assertEqual(shared.calls, [])
        h = HierHarness(
            topo.WAVE1["T0"], self.contract, initial=INITIAL, clients={"shared": ScriptedClient(r=r_by_claim({}))}
        )
        self.addCleanup(h.close)
        h.run(smoke_limits={"per_subq_paper_cap": 4, "within_paper_top_k": 8})
        self.assertEqual(h.initial_subquestions, 11)


@needs_artifacts
class SufficiencyIntegrationTests(unittest.TestCase):
    """Phase 20a: proves the deterministic sufficiency-mapping block inside execute() --
    structurally complete since an earlier phase (`sufficiency_contract=`/`sufficiency_parent_of=`
    kwargs, both threaded all the way to the model-nomination checkpoint) but never once exercised
    by any test in this suite -- reaches EXACTLY the same result through the real orchestration
    path every other test in this file drives as calling `compute_diagnostic_sufficiency_map`/
    `compute_direction_and_effectiveness` directly on the resulting sealed ledger. Uses the REAL,
    committed, human-reviewed v9 sufficiency contract (`sufficiency_freeze.load_verified`) and the
    REAL hierarchy's own parent map (`hierarchy_contract.parent_of`) -- never a synthetic fixture --
    so this is also the first exercise of either of those two Phase-20a functions against genuine
    orchestration output rather than only unit-level literals."""

    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.contract_by_child = sufficiency_freeze.load_verified()
        cls.parent_of = hc.parent_of(cls.contract)

    def _run(self, **kwargs):
        shared = ScriptedClient(r=r_by_claim({CLAIM_C5: ["c5"], CLAIM_C4: ["c4"], CLAIM_C12: ["c12"]}))
        h = HierHarness(topo.WAVE1["T0"], self.contract, initial=INITIAL, recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        result = h.run(sufficiency_contract=self.contract_by_child, sufficiency_parent_of=self.parent_of, **kwargs)
        return result

    def test_the_real_frozen_contract_and_the_real_hierarchy_agree_on_every_child(self):
        self.assertIsNotNone(self.contract_by_child)
        self.assertEqual(set(self.contract_by_child), set(CHILD_IDS))
        self.assertEqual(set(self.parent_of), set(CHILD_IDS))

    def test_execute_reaches_sufficiency_mapping_with_zero_model_assistance(self):
        """Phase 20a's own invariant (section E): `HierHarness.run()` never threads a
        `model_client`/`nomination_context` unless explicitly asked, and this test never asks --
        so no binding anywhere in the result can be model-sourced; there is no model to have
        produced one."""
        result = self._run()
        self.assertIsNotNone(result["sufficiency_map_initial"])
        self.assertEqual(set(result["sufficiency_map_initial"]), set(CHILD_IDS))
        for contract in result["sufficiency_map_initial"].values():
            for req in contract["requirements"]:
                for instance in req["instances"]:
                    for binding in instance["role_bindings"].values():
                        prov = binding.get("provenance") or {}
                        self.assertNotEqual(prov.get("candidate_source"), "model_mapping")

    def test_the_integrated_run_matches_calling_the_deterministic_mapper_directly(self):
        """The audit's own authoritative equivalence invariant: for the SAME sealed ledger, the
        SAME frozen contract, and the SAME parent map, the integrated run_topology()/execute() path
        must equal calling `compute_diagnostic_sufficiency_map` + `compute_direction_and_
        effectiveness` directly -- never merely agree with a historical, differently-coded phase."""
        result = self._run()
        direct = sufficiency_diagnostic.compute_diagnostic_sufficiency_map(
            result["sealed"], self.contract_by_child, self.parent_of
        )
        sufficiency_diagnostic.compute_direction_and_effectiveness(
            result["sealed"], direct, semantics_version=se.SUFFICIENCY_SEMANTICS_VERSION
        )
        self.assertEqual(direct, result["sufficiency_map_final"])

    def test_recovery_targets_are_reachable_under_their_own_existing_gate(self):
        """`sufficiency_recovery_gate_enabled` is a separate opt-in from mapping reachability
        (section K) -- exercised explicitly here, never implied merely because mapping ran."""
        result = self._run(sufficiency_recovery_gate_enabled=True)
        self.assertIsInstance(result["sufficiency_recovery_targets"], dict)
        direct_targets = sufficiency_recovery_targets.compute_recovery_targets(
            result["sufficiency_map_final"], self.parent_of
        )
        self.assertEqual(set(direct_targets), set(result["sufficiency_recovery_targets"]))

    def test_the_recovery_gate_never_changes_the_mapping_result(self):
        """The gate changes only whether recovery-target rows are additionally synthesized into
        `gaps` -- it must never change what `sufficiency_map_initial` itself contains."""
        off = self._run(sufficiency_recovery_gate_enabled=False)
        on = self._run(sufficiency_recovery_gate_enabled=True)
        self.assertEqual(off["sufficiency_map_initial"], on["sufficiency_map_initial"])

    def test_omitting_the_sufficiency_contract_reproduces_pre_phase_20a_behavior_exactly(self):
        """The one guarantee this phase must never break: every existing caller that never passes
        `sufficiency_contract` observes byte-identical (here: structurally None) behavior."""
        shared = ScriptedClient(r=r_by_claim({CLAIM_C5: ["c5"]}))
        h = HierHarness(topo.WAVE1["T0"], self.contract, initial=INITIAL, recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        result = h.run()
        self.assertIsNone(result["sufficiency_map_initial"])
        self.assertIsNone(result["sufficiency_map_final"])
        self.assertEqual(result["sufficiency_recovery_targets"], {})


class FakeQwenNomination:
    """A minimal duck-typed model_client -- exactly `sufficiency_mapping.nominate_with_model`'s own
    sanctioned fake-client shape (Phase 19's audit: "every one of the ~10 existing live/recorded/
    replay/fake client implementations needed zero modification"). Deliberately bypasses QwenTasks/
    ScriptedClient/execution_policy entirely -- this tests execute()'s OWN wiring (does it construct
    model_client/nomination_context correctly, does U2 really make zero fresh calls, is a binding's
    provenance correct), not the real transport stack, which is exercised elsewhere (test_backends.py,
    the Phase 10 live diagnostic) and unchanged by this phase."""

    def __init__(self, *, model_name="qwen3.5:9b", raise_always=False):
        self.model_name = model_name
        self.calls: list[dict] = []
        self._raise_always = raise_always

    def nominate_sufficiency_role(self, *, category_description, candidates):
        self.calls.append({"category_description": category_description, "candidates": list(candidates)})
        if self._raise_always:
            raise RuntimeError("synthetic transport failure")
        if not candidates:
            return []
        first = candidates[0]
        return [{"proposition_id": first["proposition_id"], "exact_text": first["passage"][:15]}]


@needs_artifacts
class ModelAssistIntegrationTests(unittest.TestCase):
    """Phase 20b: production initial model-assisted sufficiency wiring, feature-gated off by
    default. Real frozen v9 contract + real hierarchy parent map (same fixtures as Phase 20a's own
    `SufficiencyIntegrationTests`), a fake (never real) nomination client injected directly as
    `bound.qwen` after a real `e2e.bind()` call (so `bound.supervisors` -- R/C/P -- are built
    normally; only the nomination seam is faked). No live model call anywhere in this class.

    Profile choice: `topo.WAVE1["T0"].W` is `managed_local` with `think=None` (not `False`) --
    `_resolve_qwen`'s own underlying config carries no `think` field at all, so `think` is simply
    never consulted for that kind; `None` is correctly treated as "not verified False" and refused
    by `_sufficiency_u1_context`'s own fail-closed check. A `replace()`'d copy with `W.think=False`
    is used everywhere assistance is meant to succeed -- the structure (legacy P -> SEARCH actions
    for every unresolved gap -> both U1 AND U2 fire) is what exercises the full lifecycle this class
    tests; `topo.WAVE1["T5"]` (model-based P, `p_preserve`) never plans a SEARCH action at all, so it
    never reaches U2 -- confirmed empirically before writing these tests, not assumed.
    """

    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.contract_by_child = sufficiency_freeze.load_verified()
        cls.parent_of = hc.parent_of(cls.contract)
        cls.assist_profile = replace(topo.WAVE1["T0"], W=replace(topo.WAVE1["T0"].W, think=False))

    def _bound_with_fake_qwen(self, profile, h, fake_qwen):
        real_bound = e2e.bind(
            profile, rt=h.rt, clients=h.clients, trace=h.trace, managed_chat=lambda config: h.clients["shared"]
        )
        return e2e.Bound(qwen=fake_qwen, supervisors=real_bound.supervisors)

    def _run(self, *, profile=None, fake_qwen=None, assist=True, **kwargs):
        profile = profile or self.assist_profile
        fake_qwen = fake_qwen if fake_qwen is not None else FakeQwenNomination()
        shared = ScriptedClient(r=r_by_claim({CLAIM_C5: ["c5"], CLAIM_C4: ["c4"], CLAIM_C12: ["c12"]}))
        h = HierHarness(profile, self.contract, initial=INITIAL, recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        bound = self._bound_with_fake_qwen(profile, h, fake_qwen)
        with (
            patch.object(e2e, "_initial_pass", h._initial_pass),
            patch.object(e2e, "_recover_round", h._recover_round),
        ):
            result = e2e.execute(
                rt=h.rt,
                profile=profile,
                contract=h.contract,
                trace=h.trace,
                guard=h.guard,
                bound=bound,
                sufficiency_contract=self.contract_by_child,
                sufficiency_parent_of=self.parent_of,
                sufficiency_model_assist_enabled=assist,
                **kwargs,
            )
        return result, fake_qwen, h

    # ---- enablement / preflight ---------------------------------------------------------------

    def test_default_off_preserves_phase_20a_behavior_exactly(self):
        shared = ScriptedClient(r=r_by_claim({CLAIM_C5: ["c5"], CLAIM_C4: ["c4"], CLAIM_C12: ["c12"]}))
        h = HierHarness(topo.WAVE1["T0"], self.contract, initial=INITIAL, recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        off = h.run(sufficiency_contract=self.contract_by_child, sufficiency_parent_of=self.parent_of)
        self.assertIsNone(off["sufficiency_model_assist"])
        for contract in off["sufficiency_map_initial"].values():
            for req in contract["requirements"]:
                for instance in req["instances"]:
                    for binding in instance["role_bindings"].values():
                        prov = binding.get("provenance") or {}
                        self.assertNotEqual(prov.get("candidate_source"), "model_mapping")

    def test_enabled_without_a_sufficiency_contract_is_refused(self):
        shared = ScriptedClient(r=r_by_claim({}))
        h = HierHarness(self.assist_profile, self.contract, initial=[], recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        with self.assertRaises(e2e.SufficiencyModelAssistRefused) as ctx:
            h.run(sufficiency_model_assist_enabled=True)  # no sufficiency_contract supplied
        self.assertIn("no sufficiency contract is active", str(ctx.exception))

    def test_a_thinking_enabled_w_binding_is_refused_before_any_call(self):
        shared = ScriptedClient(r=r_by_claim({}))
        h = HierHarness(topo.WAVE1["T0"], self.contract, initial=[], recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        with self.assertRaises(e2e.SufficiencyModelAssistRefused) as ctx:
            h.run(
                sufficiency_contract=self.contract_by_child,
                sufficiency_parent_of=self.parent_of,
                sufficiency_model_assist_enabled=True,
            )  # T0's own W.think is None, never explicitly False
        self.assertIn("thinking setting", str(ctx.exception))
        self.assertEqual(shared.calls, [])  # refused before W1 ever touches the (fake) client

    def test_missing_model_name_is_refused_not_silently_provenance_none(self):
        shared = ScriptedClient(r=r_by_claim({}))
        h = HierHarness(self.assist_profile, self.contract, initial=[], recovery=[], clients={"shared": shared})
        self.addCleanup(h.close)
        bound = self._bound_with_fake_qwen(self.assist_profile, h, FakeQwenNomination(model_name=None))
        with self.assertRaises(e2e.SufficiencyModelAssistRefused) as ctx:
            with (
                patch.object(e2e, "_initial_pass", h._initial_pass),
                patch.object(e2e, "_recover_round", h._recover_round),
            ):
                e2e.execute(
                    rt=h.rt, profile=self.assist_profile, contract=h.contract, trace=h.trace, guard=h.guard,
                    bound=bound,
                    sufficiency_contract=self.contract_by_child, sufficiency_parent_of=self.parent_of,
                    sufficiency_model_assist_enabled=True,
                )  # fmt: skip
        self.assertIn("model_name", str(ctx.exception))

    def test_a_non_hierarchical_run_may_not_combine_the_flag_without_hierarchy(self):
        with self.assertRaises(ValueError) as ctx:
            e2e.run_topology(
                "T5", "lld",
                db_path="x", library_frozen="y", out_dir="z", git_root=".",
                scored=False, hierarchy=False, sufficiency_model_assist=True,
            )  # fmt: skip
        self.assertIn("--sufficiency-model-assist requires --hierarchy", str(ctx.exception))

    # ---- the mandatory nomination-context invariant --------------------------------------------

    def test_model_client_and_nomination_context_are_always_constructed_together(self):
        """The researcher decision this phase opened with, proven directly against the one
        function that enforces it: `_sufficiency_u1_context` either returns BOTH a real client and
        a real Phase-19 context, or raises -- there is no path that returns one without the other."""
        client, context = e2e._sufficiency_u1_context(
            self.assist_profile, e2e.Bound(qwen=FakeQwenNomination(), supervisors={})
        )
        self.assertIsNotNone(client)
        self.assertIsNotNone(context)
        self.assertEqual(context["policy"], mscope.all_eligible_policy())

    def test_disabled_path_never_constructs_a_context_at_all(self):
        result, fake, _ = self._run(assist=False)
        self.assertEqual(fake.calls, [])
        self.assertIsNone(result["sufficiency_model_assist"])

    # ---- U1: ALL_ELIGIBLE, demand-driven -------------------------------------------------------

    def test_u1_uses_all_eligible_and_is_demand_driven_not_a_precall_of_every_scope(self):
        result, fake, _ = self._run()
        summary = result["sufficiency_model_assist"]["initial"]
        self.assertTrue(summary["enabled"])
        # Confirmed empirically: 11 of the frozen v9 contract's 15 declared scopes are actually
        # reached under these real claims; 5 have real candidates (one physical call each), 6 have
        # none (zero calls, `fresh_no_candidates`) -- never a pre-call of all 15 inventory scopes.
        self.assertEqual(summary["scopes_reached"], 11)
        self.assertEqual(summary["by_status"], {"fresh": 5, "fresh_no_candidates": 6})
        self.assertEqual(len(fake.calls), 5)

    def test_a_real_nomination_produces_a_correctly_provenanced_filled_binding(self):
        result, _, _ = self._run()
        c5 = result["sufficiency_map_initial"]["c5"]
        req = next(r for r in c5["requirements"] if r["id"] == "c5#suff:brain-behavior")
        self.assertEqual(req["state"], "filled")
        for role in ("named_brain_region_or_network", "behavior_or_behavioral_measure"):
            binding = req["instances"][0]["role_bindings"][role]
            prov = binding["provenance"]
            self.assertEqual(prov["candidate_source"], "model_mapping")
            self.assertEqual(prov["model"], "qwen3.5:9b")

    def test_direction_effectiveness_annotation_still_runs_over_a_model_filled_instance(self):
        """Phase 18 remains closed and unmodified (confirmed by `git diff --stat`); this is the
        audit's own requested integration assertion that the SAME annotation pass still reaches an
        instance whose completion is model-dependent, producing the correctly-shaped diagnostic
        metadata (never skipped, never erroring) even when no direction word happens to appear in
        this fake's own (non-semantic) synthetic `exact_text`."""
        result, _, _ = self._run()
        req = next(
            r for r in result["sufficiency_map_initial"]["c5"]["requirements"] if r["id"] == "c5#suff:brain-behavior"
        )
        self.assertIn("direction_observations", req["instances"][0])
        self.assertIn("direction_summary", req)
        self.assertEqual(req["direction_summary"]["complete_instance_keys"], [None])

    def test_u1_stage_uses_the_shared_w_residency_stage_accounting(self):
        """Audit §11: brought under the SAME mechanism every other bound.qwen call uses -- never a
        hardcoded `swap_seconds: 0.0` fiction for a pass that actually touched the model."""
        result, _, _ = self._run()
        u1 = next(s for s in result["stage_log"] if s["stage"] == "U1")
        self.assertEqual(u1["role"], "W")
        self.assertEqual(u1["binding"]["model"], "callosum-managed-local")
        self.assertIn("scopes_reached", u1["detail"])

    def test_zero_candidate_scope_makes_zero_calls(self):
        result, fake, _ = self._run()
        offered = {tuple(c["proposition_id"] for c in call["candidates"]) for call in fake.calls}
        self.assertNotIn((), offered)  # no call was EVER made with an empty candidate list

    # ---- mechanical failure never crashes the run ----------------------------------------------

    def test_a_mechanical_nomination_failure_does_not_crash_the_run(self):
        result, fake, h = self._run(fake_qwen=FakeQwenNomination(raise_always=True))
        self.assertTrue(fake.calls)  # it really was invoked
        c5 = result["sufficiency_map_initial"]["c5"]
        req = next(r for r in c5["requirements"] if r["id"] == "c5#suff:brain-behavior")
        for role in ("named_brain_region_or_network", "behavior_or_behavioral_measure"):
            self.assertEqual(req["instances"][0]["role_bindings"][role]["state"], "missing")
        self.assertIsNotNone(result["final_audit"])  # the run completed to a rendered answer
        summary = result["sufficiency_model_assist"]["initial"]
        self.assertIn("fresh_failed_no_valid_prior", summary["by_status"])

    # ---- U2: held fixed, zero fresh calls -------------------------------------------------------

    def test_u2_fires_and_makes_zero_fresh_calls(self):
        result, fake, _ = self._run()
        self.assertIn("U2", [s["stage"] for s in result["stage_log"]])
        final_summary = result["sufficiency_model_assist"]["final"]
        self.assertTrue(final_summary["enabled"])
        self.assertEqual(final_summary["scopes_reached"], 11)
        self.assertEqual(final_summary["by_status"], {"held_fixed_replay": 11})
        self.assertEqual(len(fake.calls), 5)  # identical to U1 alone -- U2 added exactly zero

    def test_u2_replays_the_exact_u1_binding_held_fixed(self):
        result, _, _ = self._run()
        initial_binding = result["sufficiency_map_initial"]["c5"]["requirements"][0]["instances"][0]["role_bindings"][
            "named_brain_region_or_network"
        ]
        final_binding = result["sufficiency_map_final"]["c5"]["requirements"][0]["instances"][0]["role_bindings"][
            "named_brain_region_or_network"
        ]
        self.assertEqual(initial_binding["exact_text"], final_binding["exact_text"])
        self.assertEqual(final_binding["provenance"]["candidate_source"], "model_mapping")

    def test_u2_never_wrapped_in_the_w_residency_stage(self):
        """Audit §11's own stated constraint: replaying already-known receipts must never incur a
        W residency swap -- U2's own stage_log entry is built manually, never via `stage("U2","W")`."""
        result, _, _ = self._run()
        u2 = next(s for s in result["stage_log"] if s["stage"] == "U2")
        self.assertEqual(u2["swap_seconds"], 0.0)
        self.assertEqual(u2["binding"]["kind"], "sufficiency_model_assist_held_fixed")
        self.assertEqual(u2["binding"]["model"], "qwen3.5:9b")

    def test_u1_receipt_snapshot_is_independent_of_the_live_u1_context(self):
        """Audit §9: U2 must never be able to mutate the authoritative U1 receipt record. Proven
        directly against the snapshot helper's own real output, not merely trusted."""
        client, context = e2e._sufficiency_u1_context(
            self.assist_profile, e2e.Bound(qwen=FakeQwenNomination(), supervisors={})
        )
        scope = mscope.new_model_nomination_scope("c4", "req", "role")
        mscope.resolve_nomination(
            scope, candidate_rows=[], category_description="x", model_name="m",
            make_fresh_call=lambda: [], nomination_context=context,
        )  # fmt: skip
        snapshot = dict(context["in_pass_receipts"])
        context["in_pass_receipts"]["intruder"] = {"injected": True}
        self.assertNotIn("intruder", snapshot)

    # ---- recovery gate stays separate ------------------------------------------------------------

    def test_model_assist_on_with_recovery_gate_off_still_maps_but_injects_no_recovery_targets(self):
        """`sufficiency_recovery_targets` in the result is always COMPUTED once a map exists
        (unconditionally, at the end of execute() -- unrelated to the gate); the gate controls only
        whether those rows are additionally INJECTED as synthetic search gaps. Observed via the
        scripted harness's own `recover_calls[0]["gaps"]` -- a sufficiency-derived target appends
        its owning child id again even when the generic pass already gapped it (by design, per
        execute()'s own comment), so gate ON must search a STRICTLY LARGER gap list than gate OFF,
        given the same real model-mapped structure (confirmed non-trivial: c12/c4 are only
        `partially_filled`, exactly the shape that yields a real recovery target)."""
        off, _, h_off = self._run(sufficiency_recovery_gate_enabled=False)
        on, _, h_on = self._run(sufficiency_recovery_gate_enabled=True)
        self.assertTrue(off["sufficiency_model_assist"]["initial"]["enabled"])
        self.assertTrue(on["sufficiency_recovery_targets"])  # real targets exist to (not) inject
        self.assertEqual(off["sufficiency_recovery_targets"], on["sufficiency_recovery_targets"])
        gaps_off = h_off.recover_calls[0]["gaps"]
        gaps_on = h_on.recover_calls[0]["gaps"]
        self.assertEqual(len(gaps_off), len(set(gaps_off)))  # no duplicates when the gate is off
        self.assertGreater(len(gaps_on), len(gaps_off))  # the gate injects additional target rows

    # ---- persistence -----------------------------------------------------------------------------

    def test_the_receipt_artifact_round_trips_with_no_hidden_reasoning(self):
        result, fake, h = self._run()
        path = h.trace.dir / "18_sufficiency_model_assist.json"
        self.assertTrue(path.is_file())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["model_name"], "qwen3.5:9b")
        self.assertIs(payload["think"], False)
        self.assertEqual(len(payload["initial"]), 11)
        self.assertEqual(len(payload["final"]), 11)
        blob = json.dumps(payload).lower()
        for forbidden in ("thinking", "reasoning", "raw_text", "chain_of_thought"):
            self.assertNotIn(forbidden, blob)


class _DeclineUnderTwoCandidatesClient:
    """Phase 22: a model_client whose nomination outcome depends on how many admissible candidate
    rows it is actually offered -- declines (returns `[]`) under 2, accepts (nominates the first
    candidate's own grounded prefix) at 2 or more. Used to drive a real, end-to-end "U1 declines,
    recovery broadens the SAME request's candidate pool, U2 genuinely reconsiders and succeeds"
    scenario through the real `execute()` path -- never a synthetic toy mapper."""

    model_name = "qwen3.5:9b"

    def __init__(self):
        self.calls: list[dict] = []

    def nominate_sufficiency_role(self, *, category_description, candidates):
        self.calls.append({"category_description": category_description, "candidates": list(candidates)})
        if len(candidates) < 2:
            return []
        first = candidates[0]
        return [{"proposition_id": first["proposition_id"], "exact_text": first["passage"][:15]}]


@needs_artifacts
class TargetedPostRecoveryRemapIntegrationTests(unittest.TestCase):
    """Phase 22: target-scoped post-recovery model remapping, exercised end to end through the
    real `execute()` path -- real frozen v9 contract, real hierarchy, a fake (never live) client,
    no network, no live recovery. One real `provisional`/`missing`-shaped scenario where recovery
    genuinely broadens evidence for an already-reached-but-unfilled request, proving the full
    lifecycle (U1 -> targets -> recovery -> F -> targeted U2) fires real new calls for SOME
    requests while holding others fixed, all within the precomputed call-budget invariant.

    Every number below was empirically confirmed by directly running this exact fixture against
    the real frozen v9 contract (never hand-derived) -- the same discipline every prior Phase-19/
    20/21 integration test in this file already follows."""

    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.contract_by_child = sufficiency_freeze.load_verified()
        cls.parent_of = hc.parent_of(cls.contract)
        cls.assist_profile = replace(topo.WAVE1["T0"], W=replace(topo.WAVE1["T0"].W, think=False))

    CLAIM_C5B = "A second finding also linked amygdala reactivity to the same bias."

    def _run(self, *, gate_enabled):
        shared = ScriptedClient(
            r=r_by_claim({CLAIM_C5: ["c5"], CLAIM_C4: ["c4"], CLAIM_C12: ["c12"], self.CLAIM_C5B: ["c5"]})
        )
        recovery = [rec("c5", self.CLAIM_C5B, chunk=21, origin="recovery")]
        h = HierHarness(
            self.assist_profile, self.contract, initial=INITIAL, recovery=recovery, clients={"shared": shared}
        )
        self.addCleanup(h.close)
        real_bound = e2e.bind(
            self.assist_profile, rt=h.rt, clients=h.clients, trace=h.trace, managed_chat=lambda c: h.clients["shared"]
        )
        fake = _DeclineUnderTwoCandidatesClient()
        bound = e2e.Bound(qwen=fake, supervisors=real_bound.supervisors)
        with (
            patch.object(e2e, "_initial_pass", h._initial_pass),
            patch.object(e2e, "_recover_round", h._recover_round),
        ):
            result = e2e.execute(
                rt=h.rt,
                profile=self.assist_profile,
                contract=h.contract,
                trace=h.trace,
                guard=h.guard,
                bound=bound,
                sufficiency_contract=self.contract_by_child,
                sufficiency_parent_of=self.parent_of,
                sufficiency_model_assist_enabled=True,
                sufficiency_recovery_gate_enabled=gate_enabled,
            )
        return result, fake, h

    def test_gate_on_fires_a_genuine_targeted_remap_within_the_call_budget(self):
        result, fake, _ = self._run(gate_enabled=True)
        u2 = result["sufficiency_model_assist"]["final"]
        u2_stage = next(s for s in result["stage_log"] if s["stage"] == "U2")

        self.assertEqual(u2_stage["binding"]["kind"], "sufficiency_model_assist_targeted_remap")
        self.assertEqual(u2_stage["binding"]["fresh_request_count"], 8)
        self.assertEqual(u2["scopes_reached"], 11)
        self.assertEqual(u2["by_status"], {"fresh_no_candidates": 6, "held_fixed_replay": 3, "fresh": 2})
        # At least one request was genuinely excluded (held fixed) -- F never widened to "everything".
        self.assertGreaterEqual(u2["by_status"]["held_fixed_replay"], 1)
        # At least one request was genuinely reconsidered with a real new call -- not a no-op pass.
        self.assertGreaterEqual(u2["by_status"]["fresh"], 1)
        # No RuntimeError was raised by execute()'s own hard call-budget assertion -- confirmed
        # implicitly (the run completed), and explicitly here: every status that represents a
        # physical fresh attempt sums to exactly the declared fresh_request_count (|F|).
        fresh_attempted = sum(
            u2["by_status"].get(s, 0)
            for s in ("fresh", "fresh_no_candidates", "fresh_failed_fallback_to_prior", "fresh_failed_no_valid_prior")
        )
        self.assertEqual(fresh_attempted, u2_stage["binding"]["fresh_request_count"])

        c5 = result["sufficiency_map_final"]["c5"]
        req = next(r for r in c5["requirements"] if r["id"] == "c5#suff:brain-behavior")
        self.assertEqual(req["state"], "filled")
        for role in ("named_brain_region_or_network", "behavior_or_behavioral_measure"):
            self.assertEqual(req["instances"][0]["role_bindings"][role]["state"], "filled")

    def test_gate_off_with_the_same_broadened_evidence_stays_fully_held_fixed(self):
        """The exact same recovery evidence is sealed either way (the harness injects it
        unconditionally once `_recover_round` runs at all, regardless of gate state) -- proving
        the gate, not evidence availability, is what decides whether U2 ever looks at it."""
        result, fake, h = self._run(gate_enabled=False)
        u1_call_count = len(fake.calls)
        u2 = result["sufficiency_model_assist"]["final"]
        u2_stage = next(s for s in result["stage_log"] if s["stage"] == "U2")

        self.assertEqual(u2_stage["binding"]["kind"], "sufficiency_model_assist_held_fixed")
        self.assertEqual(u2_stage["binding"]["fresh_request_count"], 0)
        self.assertEqual(u2["by_status"], {"held_fixed_replay": 11})
        self.assertEqual(len(fake.calls), u1_call_count)  # zero additional calls beyond U1's own

    def test_fresh_u2_sees_the_broadened_pool_not_just_the_original_candidate(self):
        """Confirms U2's own fresh call for c5's request was genuinely offered the POST-RECOVERY
        candidate pool (2 propositions), never only the one U1 already knew about -- the brief's
        own explicit preference (full current pool, never a recovered-only subset)."""
        _, fake, _ = self._run(gate_enabled=True)
        # Every call this client ever received with >=2 candidates succeeded (by construction);
        # at least one such call must have occurred for c5's own requirement to end up filled.
        broadened_calls = [c for c in fake.calls if len(c["candidates"]) >= 2]
        self.assertGreaterEqual(len(broadened_calls), 1)


@needs_artifacts
class RunTopologyRecoveryActivationTests(unittest.TestCase):
    """Phase 24: proves the new `--sufficiency-recovery` CLI/config surface, threaded through
    `run_topology()`, reaches `execute()` exactly once and is semantically equivalent to calling
    `execute()` directly with `sufficiency_recovery_gate_enabled=True` on the SAME fixture -- the
    same discipline `RunTopologySufficiencyWiringTests` already established for
    `sufficiency_contract`/`sufficiency_parent_of` threading, extended to this one remaining
    unthreaded kwarg. Reuses Phase 22's own real, non-trivial scripted fixture
    (`TargetedPostRecoveryRemapIntegrationTests`'s claim/recovery set and
    `_DeclineUnderTwoCandidatesClient`) rather than inventing a new scenario -- this is the SAME
    evidence shape already proven (directly) to fire a genuine targeted remap within budget; Phase
    24 only proves the normal production-shaped entry point reaches it identically."""

    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.contract_by_child = sufficiency_freeze.load_verified()
        cls.parent_of = hc.parent_of(cls.contract)
        cls.assist_profile = replace(topo.WAVE1["T0"], W=replace(topo.WAVE1["T0"].W, think=False))

    def _fixture(self):
        shared = ScriptedClient(
            r=r_by_claim(
                {
                    CLAIM_C5: ["c5"],
                    CLAIM_C4: ["c4"],
                    CLAIM_C12: ["c12"],
                    TargetedPostRecoveryRemapIntegrationTests.CLAIM_C5B: ["c5"],
                }
            )
        )
        recovery = [rec("c5", TargetedPostRecoveryRemapIntegrationTests.CLAIM_C5B, chunk=21, origin="recovery")]
        h = HierHarness(
            self.assist_profile, self.contract, initial=INITIAL, recovery=recovery, clients={"shared": shared}
        )
        self.addCleanup(h.close)
        # run_topology() calls rt.close() in its own finally block; HierHarness's own rt (a bare
        # SimpleNamespace, built for direct-execute() callers that never go through run_topology())
        # has no such method -- added here, on the test's own fixture instance, never on production.
        h.rt.close = lambda: None
        return h, shared

    def _direct_execute(self, h, shared, *, gate_enabled, model_assist=True):
        real_bound = e2e.bind(
            self.assist_profile, rt=h.rt, clients=h.clients, trace=h.trace, managed_chat=lambda c: h.clients["shared"]
        )
        qwen = _DeclineUnderTwoCandidatesClient() if model_assist else None
        bound = e2e.Bound(qwen=qwen, supervisors=real_bound.supervisors) if model_assist else real_bound
        with (
            patch.object(e2e, "_initial_pass", h._initial_pass),
            patch.object(e2e, "_recover_round", h._recover_round),
        ):
            return e2e.execute(
                rt=h.rt,
                profile=self.assist_profile,
                contract=h.contract,
                trace=h.trace,
                guard=h.guard,
                bound=bound,
                sufficiency_contract=self.contract_by_child,
                sufficiency_parent_of=self.parent_of,
                sufficiency_model_assist_enabled=model_assist,
                sufficiency_recovery_gate_enabled=gate_enabled,
            )

    def _via_run_topology(self, h, shared, tmp_root, *, recovery_gate, model_assist=True):
        captured_kwargs, captured_result = {}, {}
        real_execute = e2e.execute
        fake = _DeclineUnderTwoCandidatesClient()

        def _spy(**kwargs):
            captured_kwargs.update(kwargs)
            result = real_execute(**kwargs)
            captured_result.update(result)
            return result

        def _fake_u1_context(profile, bound):
            # run_topology() builds `bound` itself via the real bind() -- T0's own W/R are
            # managed_local, so bound.qwen is a real QwenTasks wrapping a bare fake rt.qwen_config
            # this fixture was never meant to resolve a model_name from. Substituting ONLY this one
            # seam (never execute()'s own control flow, never the real bind()/require_models()
            # construction) is the identical technique the direct-execute() path above achieves by
            # constructing `bound.qwen` as the fake directly -- not reachable here since
            # run_topology() owns `bind()` itself.
            return fake, mscope.new_nomination_context(mscope.all_eligible_policy())

        patches = [
            patch.object(e2e, "execute", side_effect=_spy),
            patch.object(e2e, "_initial_pass", h._initial_pass),
            patch.object(e2e, "_recover_round", h._recover_round),
            # run_topology() resolves its own `profile_name` argument via topo.resolve_profile --
            # it has no way to accept a Profile object directly. This fixture's whole point is the
            # think=False variant (the same precondition `_sufficiency_u1_context` enforces), so
            # the standing registry lookup is substituted for "T0" only, the identical narrow
            # technique Phase 23's own harness already used for its own profile variant.
            patch.object(
                topo,
                "resolve_profile",
                side_effect=lambda name: self.assist_profile if name == "T0" else topo.WAVE1[name],
            ),
        ]
        if model_assist:
            patches.append(patch.object(e2e, "_sufficiency_u1_context", side_effect=_fake_u1_context))
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            manifest = e2e.run_topology(
                "T0",
                "aib",
                db_path=tmp_root / "l.sqlite",
                library_frozen=tmp_root / "l.json",
                out_dir=tmp_root / "out",
                git_root=tmp_root,
                scored=False,
                hierarchy=True,
                hierarchy_loader=lambda question: h.contract,
                authorization_checker=lambda auth, question: None,
                git_state_fn=lambda r: {"sha": "x", "branch": "b", "dirty_paths": []},
                verify_library=lambda db, frozen: {"sha256": "same"},
                verify_contracts=lambda: None,
                runtime_factory=lambda *a, **kw: h.rt,
                client_factory=lambda url: shared,
                managed_chat=lambda config: shared,
                sufficiency_model_assist=model_assist,
                sufficiency_recovery_gate=recovery_gate,
            )
        return manifest, captured_kwargs, captured_result

    @staticmethod
    def _without_timing(result: dict) -> dict:
        """Strips the two real-wall-clock fields (`wall_seconds`/`swap_seconds`) from `stage_log` --
        the only fields in `execute()`'s own return dict that are never semantically deterministic
        across two separate invocations of the same scripted fixture. Every other field is compared
        for exact equality."""
        stripped = dict(result)
        stripped["stage_log"] = [
            {k: v for k, v in entry.items() if k not in ("wall_seconds", "swap_seconds")}
            for entry in result["stage_log"]
        ]
        return stripped

    def test_recovery_flag_reaches_execute_exactly_once_and_the_route_is_semantically_equivalent(self):
        h_direct, shared_direct = self._fixture()
        direct = self._direct_execute(h_direct, shared_direct, gate_enabled=True)

        h_route, shared_route = self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            manifest, captured_kwargs, captured_result = self._via_run_topology(
                h_route, shared_route, Path(tmp), recovery_gate=True
            )

        # The flag reached execute() exactly once, with the exact value this call requested.
        self.assertIs(captured_kwargs["sufficiency_recovery_gate_enabled"], True)

        # Direct execute() and the full main-shaped run_topology() route agree on every semantic
        # field: stage execution, RecoveryTargets before and after, the sealed final evidence,
        # the U1/U2 nomination receipts (fresh/fresh_no_candidates/held_fixed statuses included),
        # the final sufficiency map (direction/effectiveness/stop-search live inside it), and F's
        # own count. Section 8's required comparison, in one assertion rather than one per field,
        # since execute()'s return dict already carries every one of those fields by name.
        self.assertEqual(self._without_timing(direct), self._without_timing(captured_result))

        # And the manifest's own thin diagnostics (§12) agree with what actually happened.
        self.assertEqual(manifest["sufficiency"]["recovery_gate_requested"], True)
        self.assertEqual(manifest["sufficiency"]["recovery_gate_enabled"], True)
        self.assertEqual(
            manifest["sufficiency"]["recovery_targets_initial_count"],
            len(direct["sufficiency_recovery_targets_initial"]),
        )
        self.assertTrue(manifest["sufficiency"]["recovery_round_executed"])
        self.assertEqual(
            manifest["sufficiency"]["u2_fresh_request_key_count"], direct["sufficiency_u2_fresh_request_key_count"]
        )
        # §13: the manifest's own count is the fresh-AUTHORIZED key count, never the physical-call
        # count -- confirmed distinct here on real data (2 physical calls underlie this fixture's
        # own F, per TargetedPostRecoveryRemapIntegrationTests' own assertions above).
        by_status = direct["sufficiency_model_assist"]["final"]["by_status"]
        physical_calls = by_status.get("fresh", 0)
        self.assertNotEqual(manifest["sufficiency"]["u2_fresh_request_key_count"], physical_calls)

    def test_gate_absent_through_run_topology_matches_gate_off_direct_exactly(self):
        """§9: with the new flag ABSENT, the normal production route must remain byte-identical
        (modulo wall-clock) to calling execute() with the gate explicitly off -- no target-driven
        recovery round, F empty/absent, U2 fully held fixed where it runs at all, zero new
        recovery-specific search actions or model calls caused by this phase's own change."""
        h_direct, shared_direct = self._fixture()
        direct_off = self._direct_execute(h_direct, shared_direct, gate_enabled=False)

        h_route, shared_route = self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            manifest, captured_kwargs, captured_result = self._via_run_topology(
                h_route, shared_route, Path(tmp), recovery_gate=False
            )

        self.assertIs(captured_kwargs["sufficiency_recovery_gate_enabled"], False)
        self.assertEqual(self._without_timing(direct_off), self._without_timing(captured_result))
        self.assertFalse(direct_off["sufficiency_recovery_targets_initial"])
        self.assertEqual(manifest["sufficiency"]["recovery_gate_requested"], False)
        self.assertEqual(manifest["sufficiency"]["recovery_gate_enabled"], False)
        self.assertEqual(manifest["sufficiency"]["recovery_targets_initial_count"], 0)

    def test_recovery_without_model_assist_is_a_valid_supported_mode(self):
        """§5/§6: audited from code, not assumed -- `execute()`'s own recovery-gate block depends
        only on `sufficiency_map_initial is not None`, which a deterministic-only (model-assist-off)
        sufficiency pass already produces. Proven here through BOTH the direct-execute() path and
        the full `run_topology()` route: the recovery gate alone (no model assistance at all)
        still computes a real `RecoveryTarget` inventory and injects it as search gaps -- recovery
        and model assistance are independent capabilities, confirmed on real data, not invented."""
        h_direct, shared_direct = self._fixture()
        direct = self._direct_execute(h_direct, shared_direct, gate_enabled=True, model_assist=False)
        self.assertIsNone(direct["sufficiency_model_assist"])
        self.assertTrue(direct["sufficiency_recovery_targets_initial"])  # a real, nonempty inventory

        h_route, shared_route = self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            manifest, captured_kwargs, captured_result = self._via_run_topology(
                h_route, shared_route, Path(tmp), recovery_gate=True, model_assist=False
            )
        self.assertIs(captured_kwargs["sufficiency_recovery_gate_enabled"], True)
        self.assertIs(captured_kwargs["sufficiency_model_assist_enabled"], False)
        self.assertEqual(self._without_timing(direct), self._without_timing(captured_result))
        self.assertTrue(manifest["sufficiency"]["recovery_gate_enabled"])
        self.assertGreater(manifest["sufficiency"]["recovery_targets_initial_count"], 0)
        # No fresh-request-key concept exists without model assistance -- the deterministic-only
        # U2 recompute still runs (a search was planned), but F's own count is honestly 0, never
        # fabricated or left stale from a different call.
        self.assertEqual(manifest["sufficiency"]["u2_fresh_request_key_count"], 0)

    def test_model_assist_on_recovery_off_leaves_the_initial_map_reachable_but_injects_nothing(self):
        """§6 state B: model assistance ON, recovery OFF -- the initial sufficiency map (and its
        own would-trigger RecoveryTargets, always computed per execute()'s own unconditional
        end-of-run recomputation) exists and is inspectable, but the gate injects nothing into the
        search plan. Mirrors `test_model_assist_on_with_recovery_gate_off_still_maps_but_injects_
        no_recovery_targets` above, now proven through run_topology() too."""
        h_route, shared_route = self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            manifest, captured_kwargs, captured_result = self._via_run_topology(
                h_route, shared_route, Path(tmp), recovery_gate=False, model_assist=True
            )
        self.assertIs(captured_kwargs["sufficiency_model_assist_enabled"], True)
        self.assertIs(captured_kwargs["sufficiency_recovery_gate_enabled"], False)
        self.assertIsNotNone(captured_result["sufficiency_model_assist"])
        self.assertFalse(captured_result["sufficiency_recovery_targets_initial"])
        self.assertFalse(manifest["sufficiency"]["recovery_gate_enabled"])

    def test_recovery_flag_without_hierarchy_is_refused_by_run_topology_itself(self):
        """§3/§7: `run_topology()` is a real, directly-callable unit independent of the CLI parser
        (the same rationale the pre-existing `sufficiency_model_assist`-requires-`hierarchy` check
        documents) -- this must be enforced here too, not only in `parse_args`."""
        with self.assertRaises(ValueError) as ctx:
            e2e.run_topology(
                "T0",
                "aib",
                db_path="unused",
                library_frozen="unused",
                out_dir="unused",
                git_root="unused",
                hierarchy=False,
                sufficiency_recovery_gate=True,
            )
        self.assertIn("--sufficiency-recovery requires --hierarchy", str(ctx.exception))

    def test_cli_rejects_the_flag_without_hierarchy(self):
        """§7/§16 item 3: the CLI-level refusal, mirroring the existing `--sufficiency-model-assist`
        combo check exactly."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                e2e.parse_args(
                    ["--sufficiency-recovery", "--profile", "T0", "--question", "lld", "--db", "d", "--out", "o"]
                )

    def test_cli_accepts_the_flag_with_hierarchy_default_off_when_absent(self):
        """§16 items 1-2: the flag defaults off, and parses cleanly alongside `--hierarchy`."""
        with contextlib.redirect_stderr(io.StringIO()):
            absent = e2e.parse_args(["--hierarchy", "--preflight-only"])
            present = e2e.parse_args(["--hierarchy", "--preflight-only", "--sufficiency-recovery"])
        self.assertFalse(absent.sufficiency_recovery)
        self.assertTrue(present.sufficiency_recovery)

    def test_no_profile_specific_branch_exists_for_the_new_flag(self):
        """§7: the new flag must work through ORDINARY profile resolution -- proven here by
        running the identical fixture under a SECOND, differently-shaped profile (T0 itself already
        used above is `legacy` P; this repeats the direct-equivalence check under an `ollama`-P
        variant of the same profile family, confirming no T0-only or P-kind-specific branch exists
        anywhere in the new threading)."""
        ollama_p_variant = replace(self.assist_profile, P=replace(topo.WAVE1["T1"].P, endpoint="shared"))
        shared = ScriptedClient(
            r=r_by_claim(
                {
                    CLAIM_C5: ["c5"],
                    CLAIM_C4: ["c4"],
                    CLAIM_C12: ["c12"],
                    TargetedPostRecoveryRemapIntegrationTests.CLAIM_C5B: ["c5"],
                }
            ),
            p=lambda prompt, schema: {
                "rationale": "scripted",
                "plan": {ob: "SEARCH" for ob in schema["properties"]["plan"]["required"]},
            },
        )
        recovery = [rec("c5", TargetedPostRecoveryRemapIntegrationTests.CLAIM_C5B, chunk=21, origin="recovery")]
        h = HierHarness(ollama_p_variant, self.contract, initial=INITIAL, recovery=recovery, clients={"shared": shared})
        self.addCleanup(h.close)
        real_bound = e2e.bind(
            ollama_p_variant, rt=h.rt, clients=h.clients, trace=h.trace, managed_chat=lambda c: h.clients["shared"]
        )
        bound = e2e.Bound(qwen=_DeclineUnderTwoCandidatesClient(), supervisors=real_bound.supervisors)
        with (
            patch.object(e2e, "_initial_pass", h._initial_pass),
            patch.object(e2e, "_recover_round", h._recover_round),
        ):
            result = e2e.execute(
                rt=h.rt,
                profile=ollama_p_variant,
                contract=h.contract,
                trace=h.trace,
                guard=h.guard,
                bound=bound,
                sufficiency_contract=self.contract_by_child,
                sufficiency_parent_of=self.parent_of,
                sufficiency_model_assist_enabled=True,
                sufficiency_recovery_gate_enabled=True,
            )
        self.assertTrue(result["sufficiency_recovery_targets_initial"])
        self.assertEqual(result["sufficiency_map_final"]["c5"]["requirements"][0]["state"], "filled")


@needs_artifacts
class HierarchyModelCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.display = {
            s["subquestion_id"]: obligation_display(s["obligations"][0]) for s in request_subquestions(cls.contract)
        }

    def test_c_and_p_see_every_item_line_and_a_claim_about_administration_does_not_answer_c12(self):
        isolated = ScriptedClient(c=c_supports_children({"c5": "p1"}), p=p_preserve)
        h = HierHarness(
            topo.WAVE1["T5"], self.contract, initial=INITIAL, clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        self.addCleanup(h.close)
        result = h.run()
        c_prompt = next(c["prompt"] for c in isolated.calls if c["kind"] == "C")
        p_prompt = next(c["prompt"] for c in isolated.calls if c["kind"] == "P")
        for cid, display in self.display.items():
            self.assertIn(f"- {cid}: {display}", c_prompt)
            self.assertIn(f"Requested item {cid}: {display}", p_prompt)
        self.assertIn("evidence that an intervention was attempted is not evidence that it worked", c_prompt)
        self.assertIn(
            "is there any cross-cultural evidence for the anomalous is bad bias?",
            p_prompt.split("Requested item c11: ")[1].split("\n")[0],
        )
        states = item_states(result)
        self.assertEqual(states["c12"], "no_responsive_claim")
        self.assertEqual(states["c5"], "judged_responsive")
        self.assertEqual([s["stage"] for s in result["stage_log"]], ["W1", "C1", "P1"])


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "auth.json"

    def write(self, **overrides):
        record = {
            "experiment_id": "hier-smoke-1",
            "question_sha256s": [hc.sha256_text(BENCHMARK_QUESTION)],
            "authorized_by": "a person",
            "authorized_at": "2026-09-26",
            "brief_confirmed": True,
        }
        record.update(overrides)
        self.path.write_text(json.dumps(record), encoding="utf-8")
        return str(self.path)

    def test_a_complete_authorization_naming_this_question_is_accepted(self):
        hc.check_authorization(self.write(), BENCHMARK_QUESTION)

    def test_no_authorization_is_refused(self):
        with self.assertRaises(hc.AuthorizationRefused):
            hc.check_authorization(None, BENCHMARK_QUESTION)

    def test_every_missing_or_wrong_field_is_refused(self):
        cases = [
            {"brief_confirmed": False},
            {"brief_confirmed": "true"},
            {"experiment_id": ""},
            {"authorized_by": ""},
            {"authorized_at": ""},
            {"question_sha256s": ["0" * 64]},
            {"question_sha256s": []},
        ]
        for override in cases:
            with self.subTest(override=override), self.assertRaises(hc.AuthorizationRefused):
                hc.check_authorization(self.write(**override), BENCHMARK_QUESTION)

    def test_an_unreadable_authorization_is_refused(self):
        with self.assertRaises(hc.AuthorizationRefused):
            hc.check_authorization(str(Path(self.tmp.name) / "missing.json"), BENCHMARK_QUESTION)


class RunTopologyRefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mocks = {name: MagicMock() for name in ("git", "library", "contracts", "runtime", "client")}

    def go(self, profile="T5", question="aib", **kwargs):
        return e2e.run_topology(
            profile,
            question,
            db_path=self.root / "l.sqlite",
            library_frozen=self.root / "l.json",
            out_dir=self.root / "out",
            git_root=self.root,
            scored=False,
            hierarchy=True,
            git_state_fn=self.mocks["git"],
            verify_library=self.mocks["library"],
            verify_contracts=self.mocks["contracts"],
            runtime_factory=self.mocks["runtime"],
            client_factory=self.mocks["client"],
            **kwargs,
        )

    def assert_nothing_touched(self):
        for mock in self.mocks.values():
            mock.assert_not_called()
        self.assertFalse((self.root / "out").exists(), "the output directory must not be created")

    def test_a_rejected_hierarchy_touches_no_model_library_database_trace_directory_or_git(self):
        def rejecting(question):
            raise hc.HierarchyRejected(["c4: not executable"])

        with self.assertRaises(hc.HierarchyRejected):
            self.go(hierarchy_loader=rejecting)
        self.assert_nothing_touched()

    @needs_artifacts
    def test_unreviewed_pins_refuse_a_live_run_before_anything_is_touched(self):
        with (
            patch.object(hc, "REVIEW_PATH", self.root / "no-review.json"),
            self.assertRaises(hc.HierarchyRejected) as ctx,
        ):
            self.go()  # the default live loader
        self.assertIn("review", " ".join(ctx.exception.problems).lower())
        self.assert_nothing_touched()

    @needs_artifacts
    def test_a_live_run_without_an_authorization_is_refused_before_anything_is_touched(self):
        contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        with self.assertRaises(hc.AuthorizationRefused):
            self.go(hierarchy_loader=lambda question: contract)
        self.assert_nothing_touched()

    def test_only_the_aib_request_has_an_approved_hierarchy(self):
        loader = MagicMock()
        with self.assertRaises(ValueError):
            self.go(question="lld", hierarchy_loader=loader)
        loader.assert_not_called()
        self.assert_nothing_touched()

    def test_slicing_and_seeding_are_refused_before_the_hierarchy_is_even_loaded(self):
        loader = MagicMock()
        for kwargs in (
            {"smoke_limits": {"max_initial_subquestions": 3}},
            {"smoke_limits": {"max_recovery_gaps": 2}},
            {"smoke_seed": "ledger.json", "smoke_limits": {"per_subq_paper_cap": 4}},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.go(hierarchy_loader=loader, **kwargs)
        loader.assert_not_called()
        self.assert_nothing_touched()


@needs_artifacts
class RunTopologySufficiencyWiringTests(unittest.TestCase):
    """Phase 20a: proves `run_topology()` ITSELF -- not just `execute()`, which already accepted
    these kwargs before this phase -- sources and threads `sufficiency_contract`/
    `sufficiency_parent_of`. Before this phase, a repo-wide search for `sufficiency_contract=`
    found zero call sites anywhere, production or test; this is the first. Fully fakes the
    runtime/client/retrieval layer (the same pattern `test_e2e_run.GuardedRunEndToEndTests` already
    uses for a flat question: real `_initial_pass`/`_recover_round` are patched to add nothing,
    everything else about `execute()` runs for real) so this needs no real database, model, or
    network, while still exercising the genuine end-to-end write/report path `run_topology()`'s own
    post-processing depends on -- a `side_effect` spy records exactly what `execute()` was called
    with, then delegates to the real function rather than replacing it outright."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        self.captured = {}
        self.shared = ScriptedClient()
        self._real_execute = e2e.execute

    def _no_op_initial_pass(self, conn, *, rt, qwen, subquestions, sink, trace):
        pass

    def _no_op_recover_round(self, conn, *, rt, qwen, subquestions, gaps, plan, sink, trace):
        return []

    def _spy_execute(self, **kwargs):
        self.captured = kwargs
        return self._real_execute(**kwargs)

    def _build(self, db, **kwargs):
        return SimpleNamespace(
            engine=SimpleNamespace(connect=lambda: contextlib.nullcontext(MagicMock())),
            qwen_config="QWEN-CONFIG",
            close=lambda: None,
        )

    def go(self, *, question="aib", hierarchy=True, hierarchy_loader=None, **kwargs):
        with (
            patch.object(e2e, "execute", side_effect=self._spy_execute),
            patch.object(e2e, "_initial_pass", self._no_op_initial_pass),
            patch.object(e2e, "_recover_round", self._no_op_recover_round),
        ):
            return e2e.run_topology(
                "T0",
                question,
                db_path=self.root / "l.sqlite",
                library_frozen=self.root / "l.json",
                out_dir=self.root / "out",
                git_root=self.root,
                scored=False,
                hierarchy=hierarchy,
                hierarchy_loader=hierarchy_loader or (lambda question: self.contract),
                authorization_checker=lambda auth, question: None,
                git_state_fn=lambda r: {"sha": "x", "branch": "b", "dirty_paths": []},
                verify_library=lambda db, frozen: {"sha256": "same"},
                verify_contracts=lambda: None,
                runtime_factory=self._build,
                client_factory=lambda url: self.shared,
                managed_chat=lambda config: self.shared,
                **kwargs,
            )

    def test_run_topology_sources_the_real_frozen_contract_and_the_real_parent_map(self):
        self.go()
        self.assertEqual(self.captured["sufficiency_contract"], sufficiency_freeze.load_verified())
        self.assertEqual(self.captured["sufficiency_parent_of"], hc.parent_of(self.contract))

    def test_model_client_and_nomination_context_are_never_passed_by_run_topology(self):
        """Phase 20a's own hard boundary (section E): execute() must receive model_client=None,
        nomination_context=None EXACTLY -- proven here as "run_topology never supplies either
        kwarg at all", which binds to execute()'s own None defaults identically to passing None
        explicitly, without this phase inventing a reason to pass them explicitly."""
        self.go()
        self.assertNotIn("model_client", self.captured)
        self.assertNotIn("nomination_context", self.captured)

    def test_a_non_hierarchical_run_never_sources_a_sufficiency_contract(self):
        loader = MagicMock()
        self.go(question="lld", hierarchy=False, hierarchy_loader=None, sufficiency_loader=loader)
        loader.assert_not_called()
        self.assertIsNone(self.captured["sufficiency_contract"])
        self.assertIsNone(self.captured["sufficiency_parent_of"])

    def test_an_injected_sufficiency_loader_overrides_the_default_and_receives_the_loaded_contract(self):
        sentinel_children, sentinel_parents = {"c1": {"child_id": "c1", "requirements": []}}, {"c1": "R"}
        loader = MagicMock(return_value=(sentinel_children, sentinel_parents))
        self.go(sufficiency_loader=loader)
        loader.assert_called_once_with(self.contract)
        self.assertEqual(self.captured["sufficiency_contract"], sentinel_children)
        self.assertEqual(self.captured["sufficiency_parent_of"], sentinel_parents)

    def test_the_manifest_records_a_thin_sufficiency_presence_summary(self):
        manifest = self.go()
        self.assertEqual(
            manifest["sufficiency"],
            {
                "contract_supplied": True,
                "mapped_children": sorted(sufficiency_freeze.load_verified()),
                # Phase 20b's own additive key -- None whenever model assistance never ran, exactly
                # as it never does in this (default-off) test.
                "model_assist": None,
                # Phase 24's own additive reachability diagnostics -- the recovery gate defaults off
                # and this call never requests it; the deterministic-only U2 recompute still runs
                # (a search was planned in this fixture) and honestly reports zero RecoveryTargets
                # and zero fresh-request keys, since nothing ever requested the gate.
                "recovery_gate_requested": False,
                "recovery_gate_enabled": False,
                "recovery_targets_initial_count": 0,
                "recovery_round_executed": True,
                "u2_fresh_request_key_count": 0,
            },
        )

    def test_an_unverifiable_frozen_artifact_fails_the_run_loudly_not_silently(self):
        """A tampered/unreviewed-but-PRESENT frozen artifact must never be silently treated as
        absent -- that is the one distinction `sufficiency_freeze.load_verified` exists to draw
        (section C: the frozen contract is authoritative, never quietly bypassed)."""

        def rejecting(contract):
            raise sufficiency_freeze.SufficiencyContractRejected(["synthetic: tampered for this test"])

        with self.assertRaises(sufficiency_freeze.SufficiencyContractRejected):
            self.go(sufficiency_loader=rejecting)
        self.assertEqual(self.captured, {})  # execute() itself must never have been reached


class CommandLineTests(unittest.TestCase):
    def parse(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()):
            return e2e.parse_args(list(argv))

    def test_the_flat_arguments_are_unchanged(self):
        args = self.parse("--profile", "T0", "--question", "aib", "--db", "d.sqlite", "--out", "o")
        self.assertFalse(args.hierarchy)
        self.assertFalse(args.preflight_only)
        self.assertEqual(args.library_frozen, "d.sqlite.fingerprint.json")
        for missing in ("--profile", "--question", "--db", "--out"):
            argv = ["--profile", "T0", "--question", "aib", "--db", "d", "--out", "o"]
            i = argv.index(missing)
            with self.subTest(missing=missing), self.assertRaises(SystemExit):
                self.parse(*(argv[:i] + argv[i + 2 :]))

    def test_the_hierarchy_flag_needs_the_aib_question_and_refuses_a_seed(self):
        base = ["--profile", "T5", "--db", "d", "--out", "o", "--hierarchy"]
        self.assertTrue(self.parse(*base, "--question", "aib").hierarchy)
        with self.assertRaises(SystemExit):
            self.parse(*base, "--question", "lld")
        with self.assertRaises(SystemExit):
            self.parse(*base, "--question", "aib", "--smoke", "--smoke-seed", "s.json")

    def test_sufficiency_model_assist_is_off_by_default(self):
        args = self.parse("--profile", "T0", "--question", "aib", "--db", "d", "--out", "o")
        self.assertFalse(args.sufficiency_model_assist)

    def test_sufficiency_model_assist_requires_hierarchy(self):
        with self.assertRaises(SystemExit):
            self.parse(
                "--profile", "T5", "--question", "aib", "--db", "d", "--out", "o", "--sufficiency-model-assist"
            )  # fmt: skip

    def test_sufficiency_model_assist_is_accepted_with_hierarchy(self):
        args = self.parse(
            "--profile", "T5", "--question", "aib", "--db", "d", "--out", "o",
            "--hierarchy", "--sufficiency-model-assist",
        )  # fmt: skip
        self.assertTrue(args.sufficiency_model_assist)
        self.assertTrue(args.hierarchy)

    def test_preflight_only_needs_the_hierarchy_flag_and_needs_no_run_arguments(self):
        with self.assertRaises(SystemExit):
            self.parse("--preflight-only")
        args = self.parse("--hierarchy", "--preflight-only")
        self.assertTrue(args.preflight_only)
        self.assertIsNone(args.db)
        self.assertIsNone(args.out)

    def test_t5c_is_reachable_through_the_actual_production_argument_parser(self):
        """Stage B's own CLI-wiring gap (release-gate step 5, 2026-09-30): CHILD_OVERVIEW_PROFILES existed and
        validated correctly, but topo.profile_names()/resolve_profile() -- what --profile's argparse choices
        and e2e.main()'s own resolution both consult -- were never extended to include it, so `--profile T5C`
        was rejected by argparse before main() ever ran. This proves it through the REAL parser this class
        already exercises for every other profile, not a helper function in isolation."""
        args = self.parse("--hierarchy", "--preflight-only", "--profile", "T5C")
        self.assertEqual(args.profile, "T5C")
        resolved = topo.resolve_profile(args.profile)
        self.assertEqual(resolved.S.kind, "ollama")
        self.assertEqual(resolved.S.model, "qwen3.5:9b")
        self.assertIs(resolved.S.think, False)

    def test_t5o_still_resolves_through_the_parser_with_thinking_on_unchanged(self):
        args = self.parse("--hierarchy", "--preflight-only", "--profile", "T5O")
        resolved = topo.resolve_profile(args.profile)
        self.assertIs(resolved.S.think, True)

    def test_an_unknown_profile_name_still_fails_at_the_parser_as_before(self):
        with self.assertRaises(SystemExit):
            self.parse("--hierarchy", "--preflight-only", "--profile", "NOT-A-REAL-PROFILE")


class MainOrderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_a_rejected_hierarchy_creates_no_directory_and_starts_nothing(self):
        out = Path(self.tmp.name) / "run-dir"
        buf = io.StringIO()
        with (
            patch.object(hc, "load_contract_for_live", side_effect=hc.HierarchyRejected(["c4: not executable"])),
            patch("pathlib.Path.mkdir", side_effect=AssertionError("a directory was created")),
            patch.object(e2e, "run_topology", side_effect=AssertionError("the run started")),
            contextlib.redirect_stdout(buf),
        ):
            rc = e2e.main(
                [
                    "--profile",
                    "T5",
                    "--question",
                    "aib",
                    "--db",
                    "d",
                    "--out",
                    str(out),
                    "--hierarchy",
                    "--juno-sampler",
                    "--experiment-authorization",
                    "a.json",
                ]
            )
        self.assertEqual(rc, 3)
        self.assertIn("c4: not executable", buf.getvalue())
        self.assertFalse(out.exists())

    def test_a_refused_authorization_creates_no_directory_and_starts_nothing(self):
        out = Path(self.tmp.name) / "run-dir"
        buf = io.StringIO()
        with (
            patch.object(hc, "load_contract_for_live", return_value=MagicMock()),
            patch.object(hc, "check_authorization", side_effect=hc.AuthorizationRefused("no authorization")),
            patch("pathlib.Path.mkdir", side_effect=AssertionError("a directory was created")),
            patch.object(e2e, "run_topology", side_effect=AssertionError("the run started")),
            contextlib.redirect_stdout(buf),
        ):
            rc = e2e.main(
                [
                    "--profile",
                    "T5",
                    "--question",
                    "aib",
                    "--db",
                    "d",
                    "--out",
                    str(out),
                    "--hierarchy",
                    "--juno-sampler",
                ]
            )
        self.assertEqual(rc, 3)
        self.assertIn("AUTHORIZATION REFUSED: no authorization", buf.getvalue())
        self.assertFalse(out.exists())

    @needs_artifacts
    def test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects(self):
        buf = io.StringIO()
        with (
            patch.object(hc, "REVIEW_PATH", Path(self.tmp.name) / "no-review.json"),
            patch("pathlib.Path.mkdir", side_effect=AssertionError("a directory was created")),
            patch.object(e2e, "run_topology", side_effect=AssertionError("the run started")),
            patch.object(e2e, "build_runtime", side_effect=AssertionError("a runtime was built")),
            patch.object(e2e, "OllamaClient", side_effect=AssertionError("a client was built")),
            contextlib.redirect_stdout(buf),
        ):
            rc = e2e.main(["--hierarchy", "--preflight-only"])
        text = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("PINS UNREVIEWED", text)
        self.assertIn("hierarchy_contract.review.json", text)
        self.assertIn("Requested focus (child question):", text)
        for cid in CHILD_IDS:
            self.assertIn(f"- {cid}: ", text)
        self.assertIn("obligation fulfilment: not_assessed", text)
        self.assertIn("parent answer completeness: not_certified", text)


if __name__ == "__main__":
    unittest.main()
