"""Mechanical checks on a hierarchical run directory, and a whole guarded ``run_topology`` over the hierarchy (all faked).

The checks read only what a run wrote: the sealed ledger, the answer, and every prompt the models were actually sent.
They verify carriage and structure; they never judge whether a model's responsiveness answers were right.
"""

import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from experiments.ask_cli_revised import e2e
from experiments.ask_cli_revised import e2e_checks as checks
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.hierarchy_test_support import (
    HierHarness,
    ScriptedClient,
    needs_artifacts,
    r_by_claim,
    rec,
)
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.test_e2e_run import INITIAL as FLAT_INITIAL
from experiments.ask_cli_revised.test_e2e_run import GuardedRunEndToEndTests, Harness, r_maps

CLAIM_C5 = "Amygdala activity was associated with the bias in one sample."
INITIAL = [rec("c5", CLAIM_C5, chunk=11), rec("c4", "No association was found in any region.", chunk=12)]


def read(run_dir, name):
    return json.loads((Path(run_dir) / name).read_text(encoding="utf-8"))


def write(run_dir, name, payload):
    (Path(run_dir) / name).write_text(json.dumps(payload), encoding="utf-8")


def call_rows(run_dir):
    path = Path(run_dir) / "qwen_calls.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_calls(run_dir, rows):
    (Path(run_dir) / "qwen_calls.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


@needs_artifacts
class HierarchicalReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.subs = {s["subquestion_id"]: s for s in hc.hierarchy_subquestions(cls.contract)}

    def run_dir(self):
        h = HierHarness(
            topo.WAVE1["T0"],
            self.contract,
            initial=INITIAL,
            recovery=[],
            clients={"shared": ScriptedClient(r=r_by_claim({CLAIM_C5: ["c5"]}))},
        )
        self.addCleanup(h.close)
        h.run()
        return h.trace.dir

    def report(self, run_dir):
        return checks.mechanical_report(run_dir, profile=topo.WAVE1["T0"], question_key=hc.HIER_QUESTION_KEY)

    def test_a_faithful_hierarchical_run_passes_every_check_including_the_new_ones(self):
        report = self.report(self.run_dir())
        self.assertTrue(all(c["ok"] for c in report["checks"].values()), report["checks"])
        for name in ("hierarchy_readiness", "hierarchy_carriage", "rollup_no_derived_verdict"):
            self.assertIn(name, report["checks"])
        self.assertFalse(report["frozen_labels"]["applicable"])  # the flat AIB labels are keyed on the flat item ids
        self.assertEqual(report["checks"]["contract_preserved"]["hierarchy"]["basis"], "structural")

    def test_the_flat_report_has_none_of_the_hierarchy_checks_and_is_otherwise_unchanged(self):
        h = Harness(
            topo.WAVE1["T0"], initial=FLAT_INITIAL, recovery=[], clients={"shared": ScriptedClient(r=r_maps("s3-o1"))}
        )
        self.addCleanup(h.close)
        h.run()
        report = checks.mechanical_report(h.trace.dir, profile=topo.WAVE1["T0"], question_key="lld")
        self.assertFalse(any(name.startswith("hierarchy") or name.startswith("rollup") for name in report["checks"]))
        self.assertEqual(
            sorted(report["checks"]),
            sorted(
                [
                    "contract_preserved",
                    "ledger_valid",
                    "final_conformant",
                    "unsupported_final_claims",
                    "scope_statement",
                    "plan_legal",
                    "coverage_from_authority",
                    "corpus_absence",
                ]
            ),
        )

    def test_an_altered_sealed_contract_fails_contract_preserved(self):
        run = self.run_dir()
        ledger = read(run, "11_verified_ledger.json")
        ledger["request_contract"]["hierarchy"]["children"][0]["wording"] += " (edited)"
        write(run, "11_verified_ledger.json", ledger)
        report = self.report(run)
        self.assertFalse(report["checks"]["contract_preserved"]["ok"])
        self.assertIn("c1", " ".join(report["checks"]["contract_preserved"]["hierarchy"]["problems"]))

    def test_a_ledger_whose_items_are_not_the_children_fails_contract_preserved(self):
        run = self.run_dir()
        ledger = read(run, "11_verified_ledger.json")
        ledger["obligation_states"] = ledger["obligation_states"][:-1]
        write(run, "11_verified_ledger.json", ledger)
        self.assertFalse(self.report(run)["checks"]["contract_preserved"]["ok"])

    def test_a_recorded_readiness_that_is_not_all_executable_fails(self):
        run = self.run_dir()
        ledger = read(run, "11_verified_ledger.json")
        ledger["request_contract"]["hierarchy"]["readiness"]["all_executable"] = False
        write(run, "11_verified_ledger.json", ledger)
        self.assertFalse(self.report(run)["checks"]["hierarchy_readiness"]["ok"])

    def test_carriage_fails_when_a_supervisor_prompt_lost_an_item_line(self):
        run = self.run_dir()
        rows = call_rows(run)
        target = next(r for r in rows if r["task"] == "claim_responsiveness")
        display = self.subs["c12"]["obligations"][0]["model_display"]
        target["prompt_text"] = target["prompt_text"].replace(f"- c12: {display}", "- c12: (removed)")
        write_calls(run, rows)
        carriage = self.report(run)["checks"]["hierarchy_carriage"]
        self.assertFalse(carriage["ok"])
        self.assertIn(
            {"call": rows.index(target), "task": "claim_responsiveness", "child": "c12", "missing": "item line"},
            carriage["violations"],
        )

    def worker_rows(self, *, drop_scope=False, drop_item_line=False):
        c11 = self.subs["c11"]
        text = c11["text"]
        if drop_scope:
            text = text.replace(
                hc.SCOPE_HEAD + "is there any cross-cultural evidence for the anomalous is bad bias?\n\n", ""
            )
        item = "" if drop_item_line else f"- c11: {c11['obligations'][0]['model_display']}"
        return [
            {"task": "context_gate", "prompt_text": f"Question:\n{text}\n\nCurrent text:\nX", "validation_ok": True},
            {
                "task": "form_claim",
                "prompt_text": f"Question:\n{text}\n\nSurrounding context:\nY",
                "validation_ok": True,
            },
            {
                "task": "select_evidence",
                "prompt_text": f"Question:\n{text}\n\nRequested information:\n{item}\n\nCandidate excerpts:\nZ",
                "validation_ok": True,
            },
            {
                "task": "recovery_query",
                "prompt_text": f"Scholarly question:\n{text}\n\nMissing information:\n{c11['obligations'][0]['model_display']}",
                "validation_ok": True,
            },
        ]

    def test_carriage_accepts_worker_prompts_that_carry_c11s_scope_and_item_line(self):
        run = self.run_dir()
        write_calls(run, call_rows(run) + self.worker_rows())
        self.assertTrue(self.report(run)["checks"]["hierarchy_carriage"]["ok"])

    def test_carriage_fails_when_a_worker_prompt_for_c11_lost_the_scope(self):
        run = self.run_dir()
        write_calls(run, call_rows(run) + self.worker_rows(drop_scope=True))
        carriage = self.report(run)["checks"]["hierarchy_carriage"]
        self.assertFalse(carriage["ok"])
        self.assertTrue(all(v["missing"] == "a child's exact retrieval text" for v in carriage["violations"]))

    def test_carriage_fails_when_select_evidence_lost_the_item_line(self):
        run = self.run_dir()
        write_calls(run, call_rows(run) + self.worker_rows(drop_item_line=True))
        carriage = self.report(run)["checks"]["hierarchy_carriage"]
        self.assertFalse(carriage["ok"])
        self.assertEqual([v["task"] for v in carriage["violations"]], ["select_evidence"])

    def test_the_rollup_check_fails_if_an_obligation_is_ever_called_fulfilled(self):
        run = self.run_dir()
        ledger = read(run, "11_verified_ledger.json")
        ledger["hierarchy"]["obligations"][0]["obligation_fulfilment"] = "fulfilled"
        write(run, "11_verified_ledger.json", ledger)
        check = self.report(run)["checks"]["rollup_no_derived_verdict"]
        self.assertFalse(check["ok"])

    def test_the_rollup_check_fails_if_a_parent_gains_an_answered_verdict(self):
        run = self.run_dir()
        ledger = read(run, "11_verified_ledger.json")
        ledger["hierarchy"]["parents"][0]["answered"] = True
        write(run, "11_verified_ledger.json", ledger)
        self.assertFalse(self.report(run)["checks"]["rollup_no_derived_verdict"]["ok"])

    def test_the_rollup_check_fails_if_the_rendered_reconciliation_states_a_verdict(self):
        run = self.run_dir()
        answer = (Path(run) / "14_final_answer.md").read_text(encoding="utf-8")
        answer = answer.replace(
            "Individual obligation fulfilment: NOT assessed by this run.", "Every obligation is fulfilled."
        )
        (Path(run) / "14_final_answer.md").write_text(answer, encoding="utf-8")
        self.assertFalse(self.report(run)["checks"]["rollup_no_derived_verdict"]["ok"])


@needs_artifacts
class GuardedHierarchicalRunTests(unittest.TestCase):
    """run_topology around a fully faked runtime, over the hierarchy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        self.shared = ScriptedClient(r=r_by_claim({CLAIM_C5: ["c5"]}))

        def build(db, **kwargs):
            return SimpleNamespace(
                engine=SimpleNamespace(connect=lambda: contextlib.nullcontext(MagicMock())),
                qwen_config="QWEN-CONFIG",
                close=lambda: None,
            )

        self.build = build

    def go(self, **kwargs):
        def initial_pass(conn, *, rt, qwen, subquestions, sink, trace):
            from experiments.ask_cli_revised.test_e2e_run import add

            for record in INITIAL:
                add(sink, dict(record, provenance=dict(record["provenance"])))

        def recover_round(conn, *, rt, qwen, subquestions, gaps, plan, sink, trace):
            return []

        with patch.object(e2e, "_initial_pass", initial_pass), patch.object(e2e, "_recover_round", recover_round):
            return e2e.run_topology(
                "T0",
                "aib",
                db_path=Path(self.tmp.name) / "library.sqlite",
                library_frozen=Path(self.tmp.name) / "library.frozen.json",
                out_dir=Path(self.tmp.name) / "out",
                git_root=Path(self.tmp.name),
                scored=True,
                hierarchy=True,
                hierarchy_loader=lambda question: self.contract,
                authorization_checker=lambda path, question: None,
                git_state_fn=lambda root: {"sha": "abc123", "branch": "experiment/ask-e2e", "dirty_paths": []},
                verify_library=lambda db, frozen: {"sha256": "same"},
                verify_contracts=lambda: None,
                runtime_factory=self.build,
                client_factory=lambda url: self.shared,
                managed_chat=lambda config: self.shared,
                **kwargs,
            )

    def test_a_clean_hierarchical_run_writes_a_manifest_that_records_the_hierarchy_and_passes_its_checks(self):
        manifest = self.go()
        out = Path(self.tmp.name) / "out"
        self.assertEqual(manifest["question_key"], hc.HIER_QUESTION_KEY)
        self.assertEqual(manifest["request_kind"], hc.HIER_VERSION)
        self.assertEqual(manifest["model_facing_sha256"], hc.model_facing_sha256(self.contract))
        self.assertEqual(manifest["hierarchy"]["readiness"], {"researcher_approved": 6, "runnable_by_construction": 5})
        self.assertEqual(
            [c["child_id"] for c in manifest["hierarchy"]["children"]],
            ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"],
        )
        self.assertEqual(manifest["hierarchy"]["labels"], hc.LABELS)
        self.assertTrue(all(manifest["mechanical_checks"].values()), manifest["mechanical_checks"])
        self.assertEqual(manifest["technical_validity"], {"valid": True, "issues": []})
        self.assertEqual(read(out, "00_question.json")["question_key"], hc.HIER_QUESTION_KEY)
        self.assertEqual(read(out, "01_request_contract.json")["version"], hc.HIER_VERSION)
        self.assertIn(
            "## Parent reconciliation (structural; no verdict)",
            (out / "14_final_answer.md").read_text(encoding="utf-8"),
        )

    def test_the_flat_manifest_gains_no_hierarchy_keys(self):
        flat = GuardedRunEndToEndTests("test_cleanup_unloads_only_what_the_run_loaded_and_closes_the_runtime")
        flat.setUp()
        self.addCleanup(flat.doCleanups)
        manifest = flat.go()
        self.assertEqual(manifest["question_key"], "lld")
        for key in ("hierarchy", "request_kind"):
            self.assertNotIn(key, manifest)


if __name__ == "__main__":
    unittest.main()
