"""End-to-end SEQUENCING test on the real library with a scripted fake model: plumbing and invariants, not scientific content."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import budget, pipeline, realenv, report
from experiments.ask_cli_revised.contract_directed import model_stages as ms
from experiments.ask_cli_revised.contract_directed.fakes import FakeClient

RAW = "Raw answer text citing [P1] exactly as generated."


def responder(kind, prompt, schema):
    if kind == "free":
        return RAW
    props = schema["properties"]
    if "abstract_quote" in props:  # triage
        return {
            "contribution_type": "original_empirical",
            "relation_to_child": "possibly_addresses",
            "abstract_quote": "",
            "reason": "fake",
        }
    if (
        "propositions" in props
    ):  # localization: establish the first unit that looks like a measure, a culture or a result
        enum = props["propositions"]["items"]["properties"]["establishing"]["items"]["enum"]
        for line in prompt.splitlines():
            m = re.match(r"\[(s\d+)\] .*?(?:scale|questionnaire|Hadza|correlated|found)", line, re.IGNORECASE)
            if m and m.group(1) in enum:
                return {
                    "propositions": [
                        {
                            "establishing": [m.group(1)],
                            "qualifying": [],
                            "referents": [],
                            "provenance_class": "this_study_reports",
                            "attribution_basis_phrase": "",
                            "relation_polarity": "association",
                            "unresolved": [],
                        }
                    ],
                    "none_established": False,
                }
        return {"propositions": [], "none_established": True}
    units = props["units"]["properties"]  # eligibility: fill every slot with the first span
    out = {}
    for uid, spec in units.items():
        slots = {}
        for name in spec["properties"]["slots"]["properties"]:
            slots[name] = {"span_ids": ["p1"], **({"value": "association"} if name == "polarity" else {})}
        out[uid] = {"slots": slots, "reason": "fake"}
    return {"units": out}


@unittest.skipUnless(realenv.available(), "real disposable library / frozen data not present")
class PipelineSequencingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caps = budget.Caps(
            triage_papers=3,
            inspected_papers=2,
            neighborhoods=6,
            recovery_neighborhoods=2,
            bridge_neighborhoods=1,
            eligibility_packets=6,
        )
        cls.tmp = tempfile.TemporaryDirectory()
        cls.run_dir = Path(cls.tmp.name)
        client = FakeClient(responder)
        ledger = ms.Ledger(max_calls=400, wall_seconds=600)
        env = ms.Env(client=client, ledger=ledger)
        cls.pipe = pipeline.Run(
            run_dir=cls.run_dir,
            library=realenv.library(),
            retriever=realenv.retriever(),
            substrate=realenv.substrate(),
            caps=cls.caps,
            env=env,
        )
        cls.children = ["c9", "c11"]
        cls.status = pipeline.run_children(cls.pipe, cls.children)
        cls.client, cls.ledger = client, ledger

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def lines(self, name):
        path = self.run_dir / name
        return (
            [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if path.exists()
            else []
        )

    def test_the_run_completes_and_writes_every_stage_receipt(self):
        self.assertIsNone(self.status["halted"], self.status)
        for name in (
            "01_nominations.jsonl",
            "02_triage.jsonl",
            "04_anchors.jsonl",
            "05_neighborhoods.jsonl",
            "06_localization.jsonl",
            "09_coverage.json",
            "13_assignment_matrix.json",
            "14_ledger.json",
            "11_bridge.jsonl",
        ):
            self.assertTrue((self.run_dir / name).is_file(), name)
        for child in self.children:
            self.assertTrue((self.run_dir / "12_answers" / f"{child}_raw_answer.txt").is_file())

    def test_the_raw_answer_is_preserved_exactly_as_generated(self):
        for child in self.children:
            self.assertEqual((self.run_dir / "12_answers" / f"{child}_raw_answer.txt").read_text(encoding="utf-8"), RAW)

    def test_worst_case_budget_is_never_exceeded(self):
        worst = budget.worst_case(len(self.children), self.caps)["worst_case_total_calls"]
        self.assertLessEqual(self.ledger.calls, worst)
        self.assertLessEqual(self.ledger.stages["triage"]["calls"], len(self.children) * self.caps.triage_papers)
        self.assertLessEqual(
            self.ledger.stages["eligibility"]["calls"], self.caps.eligibility_packets * len(self.children)
        )

    def test_every_packet_is_judged_against_every_child_regardless_of_route(self):
        judged = self.lines("08_eligibility.jsonl")
        by_packet: dict[str, set] = {}
        for rec in judged:
            if rec.get("child_id"):
                by_packet.setdefault(rec["packet_id"], set()).add(rec["child_id"])
        self.assertTrue(by_packet, "the fake model should have produced at least one packet")
        for packet_id, kids in by_packet.items():
            self.assertEqual(kids, set(self.children), packet_id)
        self.assertTrue(any(r.get("route_relation") == "cross_child" for r in judged) or len(self.children) == 1)

    def test_no_prompt_ever_contains_the_parent_question_or_a_siblings_wording(self):
        question = realenv.substrate().contract["original_question"]
        run_children = [c for c in realenv.substrate().children if c.child_id in self.children]
        # a child's own APPROVED carried scope (c11 carries c10's wording) is part of its contract, exactly as in the baseline
        allowed_carried = {c.scope_carrier_wording for c in run_children if c.scope_carrier_wording}
        sibling_only = {
            c.wording for c in realenv.substrate().children if c.child_id not in self.children
        } - allowed_carried
        for call in self.client.calls:
            self.assertNotIn(question, call["prompt"])
            for wording in sibling_only:
                self.assertNotIn(wording, call["prompt"])

    def test_answers_are_thinking_off_free_prose_with_the_baseline_options(self):
        free = [c for c in self.client.calls if c["kind"] == "free"]
        self.assertEqual(len(free), len(self.children))
        for call in free:
            self.assertFalse(call["think"])
            self.assertEqual(call["options"], ms.topo.SUPERVISOR_BASE_OPTIONS)

    def test_diagnostics_are_recorded_and_never_gate(self):
        for child in self.children:
            record = json.loads((self.run_dir / "12_answers" / f"{child}_record.json").read_text(encoding="utf-8"))
            self.assertFalse(record["diagnostics"]["gating"])
            self.assertFalse(record["diagnostics"]["prompt_leakage"]["contains_parent_question"])

    def test_coverage_rows_carry_not_certified_completeness_and_a_search_receipt(self):
        rows = json.loads((self.run_dir / "09_coverage.json").read_text(encoding="utf-8"))
        for child in self.children:
            for row in rows[child]:
                self.assertEqual(row["completeness"], "not_certified")
            content = [r for r in rows[child] if r["row_type"] == "content"]
            self.assertTrue(all("search" in r for r in content))

    def test_recovery_records_keep_the_original_route_and_the_reason(self):
        for rec in self.lines("10_recovery.jsonl"):
            self.assertTrue(rec["trigger_reason"])
            self.assertTrue(rec["recovers"])
            self.assertLessEqual(
                len([r for r in self.lines("10_recovery.jsonl") if r["child_id"] == rec["child_id"]]),
                self.caps.recovery_neighborhoods,
            )

    def test_the_bridge_is_recorded_as_conditional_and_not_executed_offline(self):
        for rec in self.lines("11_bridge.jsonl"):
            self.assertIn("triggered", rec["trigger"])
            self.assertFalse(rec["executed"])

    def test_the_report_layer_runs_over_the_receipts_and_labels_attribution_descriptive(self):
        summary = report.write_all(self.run_dir, realenv.substrate(), self.children)
        self.assertIn("15_expectation_results.json", summary["files"])
        results = json.loads((self.run_dir / "15_expectation_results.json").read_text(encoding="utf-8"))
        ids = {r["id"] for r in results}
        self.assertIn("I.pieces_verbatim", ids)
        self.assertIn("N1.unattributed_never_closes", ids)
        for r in results:
            self.assertIn(r["status"], {"pass", "fail", "review", "not_evaluable"})
        attribution = json.loads((self.run_dir / "16_route_attribution.json").read_text(encoding="utf-8"))
        self.assertIn("does not show how a route-exclusive run would have performed", attribution["caveat"])
        sheet = (self.run_dir / "17_review_sheet.md").read_text(encoding="utf-8")
        self.assertIn("no composite score", sheet)
        for child in self.children:
            self.assertIn(child, (self.run_dir / f"trace_{child}.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
