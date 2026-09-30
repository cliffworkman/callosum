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
from pathlib import Path
from unittest.mock import MagicMock, patch

from experiments.ask_cli_revised import e2e
from experiments.ask_cli_revised import hierarchy_contract as hc
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
