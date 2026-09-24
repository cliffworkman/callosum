"""Mechanical checks on a completed run: contract, ledger, conformance, NO ANSWER accounting, plan legality, labels."""

import json
import unittest
from pathlib import Path

from experiments.ask_cli_revised import e2e_checks as checks
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.supervisor_eval import cases
from experiments.ask_cli_revised.test_e2e_run import INITIAL, NEW, Harness, ScriptedClient, c_supports, p_all, r_maps


def read(run_dir, name):
    return json.loads((Path(run_dir) / name).read_text(encoding="utf-8"))


def write(run_dir, name, payload):
    (Path(run_dir) / name).write_text(json.dumps(payload), encoding="utf-8")


def t0_run():
    harness = Harness(
        topo.WAVE1["T0"], initial=INITIAL, recovery=NEW, clients={"shared": ScriptedClient(r=r_maps("s3-o1"))}
    )
    harness.run()
    return harness


class CallClassificationTests(unittest.TestCase):
    def test_a_usable_call_is_usable(self):
        self.assertEqual(checks.classify_call({"validation_ok": True}), ("usable", "usable"))

    def test_a_capped_or_malformed_answer_from_a_reachable_model_is_a_model_mechanical_failure(self):
        capped = {"validation_ok": False, "status": "ok", "failure_reason": "truncated_at_output_cap"}
        self.assertEqual(checks.classify_call(capped), ("model", "truncated_at_output_cap"))
        bad = {"validation_ok": False, "status": "ok", "failure_reason": "schema_invalid"}
        self.assertEqual(checks.classify_call(bad), ("model", "schema_invalid"))
        unlabelled = {"validation_ok": False, "provider_ok": True, "failure_reason": None}
        self.assertEqual(checks.classify_call(unlabelled), ("model", "invalid_output"))

    def test_a_provider_or_transport_failure_is_an_infrastructure_failure_not_a_model_verdict(self):
        self.assertEqual(
            checks.classify_call({"validation_ok": False, "failure_reason": "provider_error: connection reset"})[0],
            "infrastructure",
        )
        for status in ("http_error", "runtime_error", "transport_error"):
            self.assertEqual(checks.classify_call({"validation_ok": False, "status": status})[0], "infrastructure")

    def test_a_wall_timeout_and_a_refused_oversized_prompt_are_their_own_buckets(self):
        self.assertEqual(checks.classify_call({"validation_ok": False, "status": "timeout"})[0], "timeout")
        self.assertEqual(
            checks.classify_call({"validation_ok": False, "status": "not_sent", "failure_reason": "prompt_too_large"})[
                0
            ],
            "prompt_too_large",
        )


class NoAnswerAccountingTests(unittest.TestCase):
    def rows(self, task, n_ok, n_bad, *, model="m", reason="truncated_at_output_cap"):
        ok = [{"task": task, "model": model, "validation_ok": True} for _ in range(n_ok)]
        bad = [
            {"task": task, "model": model, "validation_ok": False, "status": "ok", "failure_reason": reason}
            for _ in range(n_bad)
        ]
        return ok + bad

    def test_the_gate_rate_is_measured_and_reported_not_thresholded(self):
        table = checks.no_answer_table(
            self.rows("context_gate", 9, 1) + self.rows("form_claim", 5, 0), worker_model="w"
        )
        gate = table["gate"]
        self.assertEqual((gate["calls"], gate["no_answer"]), (10, 1))
        self.assertAlmostEqual(gate["rate"], 0.1)
        self.assertNotIn("threshold", gate)
        self.assertEqual(table["by_task"]["context_gate"]["m"]["model"], 1)

    def test_no_gate_calls_gives_a_null_rate_not_zero(self):
        self.assertIsNone(checks.no_answer_table([], worker_model="w")["gate"]["rate"])

    def test_infrastructure_failures_are_counted_apart_from_model_failures(self):
        rows = self.rows("claim_responsiveness", 3, 0)
        rows.append({"task": "claim_responsiveness", "model": "m", "validation_ok": False, "status": "http_error"})
        rows.append({"task": "claim_responsiveness", "model": "m", "validation_ok": False, "status": "ok",
                     "failure_reason": "capped_at_allowance"})  # fmt: skip
        table = checks.no_answer_table(rows, worker_model="w")
        counts = table["by_task"]["claim_responsiveness"]["m"]
        self.assertEqual((counts["infrastructure"], counts["model"], counts["usable"]), (1, 1, 3))
        self.assertEqual(table["infrastructure_failures"], 1)

    def test_a_worker_call_without_a_recorded_model_is_attributed_to_the_bound_worker(self):
        rows = [{"task": "select_evidence", "validation_ok": True}]
        table = checks.no_answer_table(rows, worker_model="callosum-managed-local")
        self.assertIn("callosum-managed-local", table["by_task"]["select_evidence"])


class RealRunChecksTests(unittest.TestCase):
    def setUp(self):
        self.h = t0_run()
        self.addCleanup(self.h.close)
        self.dir = self.h.trace.dir

    def report(self):
        return checks.mechanical_report(self.dir, profile=topo.WAVE1["T0"], question_key="lld")

    def test_a_clean_run_passes_every_mechanical_check(self):
        report = self.report()
        failed = [name for name, check in report["checks"].items() if not check["ok"]]
        self.assertEqual(failed, [])
        self.assertTrue(report["technical_validity"]["valid"])
        self.assertEqual(report["checks"]["unsupported_final_claims"]["count"], 0)

    def test_the_report_carries_recovery_accounting_by_action(self):
        report = self.report()
        self.assertEqual(report["recovery"]["rows"], len(read(self.dir, "13_gap_recovery.json")))

    def test_an_appended_final_claim_breaks_conformance(self):
        answer = self.dir / "14_final_answer.md"
        answer.write_text(answer.read_text(encoding="utf-8") + "\nInvented finding [p1].\n", encoding="utf-8")
        report = self.report()
        self.assertFalse(report["checks"]["final_conformant"]["ok"])

    def test_a_corpus_absence_claim_in_the_final_text_is_flagged_for_review(self):
        answer = self.dir / "14_final_answer.md"
        answer.write_text(
            answer.read_text(encoding="utf-8") + "\nThe library contains no such evidence.\n", encoding="utf-8"
        )
        report = self.report()
        self.assertFalse(report["checks"]["corpus_absence"]["ok"])
        self.assertTrue(report["checks"]["corpus_absence"]["hits"])

    def test_an_illegal_planned_action_or_a_mark_covered_on_a_missing_claim_fails_plan_legality(self):
        plan = read(self.dir, "13_recovery_plan.json")
        plan["plan"]["s1-o1"] = "REWRITE_THE_QUESTION"
        write(self.dir, "13_recovery_plan.json", plan)
        self.assertFalse(self.report()["checks"]["plan_legal"]["ok"])
        plan["plan"]["s1-o1"] = "MARK_COVERED:p99"
        write(self.dir, "13_recovery_plan.json", plan)
        self.assertFalse(self.report()["checks"]["plan_legal"]["ok"])

    def test_coverage_that_the_mappings_do_not_support_fails_the_authority_check_for_a_det_arm(self):
        coverage = read(self.dir, "12_coverage_audit.json")
        row = next(r for r in coverage["obligations"] if r["field_id"] == "s1-o1")
        row["state"] = "judged_responsive"
        row["proposition_ids"] = ["p1"]
        write(self.dir, "12_coverage_audit.json", coverage)
        self.assertFalse(self.report()["checks"]["coverage_from_authority"]["ok"])

    def test_a_changed_contract_fails_the_contract_check(self):
        ledger = read(self.dir, "11_verified_ledger.json")
        ledger["request_contract"]["question_hash"] = "0" * 64
        write(self.dir, "11_verified_ledger.json", ledger)
        self.assertFalse(self.report()["checks"]["contract_preserved"]["ok"])

    def test_infrastructure_failures_make_the_run_technically_invalid_but_are_reported_not_hidden(self):
        with (self.dir / "qwen_calls.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"task": "form_claim", "validation_ok": False, "status": "transport_error"}) + "\n")
        report = self.report()
        self.assertFalse(report["technical_validity"]["valid"])
        self.assertEqual(report["no_answer"]["infrastructure_failures"], 1)


class ModelCoverageChecksTests(unittest.TestCase):
    def test_an_inconsistent_coverage_answer_is_counted_as_a_mechanical_failure(self):
        def inconsistent(prompt, schema):
            coverage = {
                ob: {"status": "unresolved", "supporting_proposition_ids": ["p1"]}
                for ob in schema["properties"]["coverage"]["properties"]
            }
            return {"rationale": "x", "coverage": coverage}

        isolated = ScriptedClient(c=inconsistent, p=p_all("PRESERVE_UNRESOLVED"))
        h = Harness(
            topo.WAVE1["T5"], initial=INITIAL, recovery=NEW, clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        self.addCleanup(h.close)
        h.run()
        report = checks.mechanical_report(h.trace.dir, profile=topo.WAVE1["T5"], question_key="lld")
        self.assertEqual(report["no_answer"]["inconsistent_coverage_answers"], 1)

    def test_a_model_coverage_arm_is_not_held_to_the_det_mapping_consistency_check(self):
        isolated = ScriptedClient(c=c_supports({"s3-o1": "p1"}), p=p_all("PRESERVE_UNRESOLVED"))
        h = Harness(
            topo.WAVE1["T5"], initial=INITIAL, recovery=NEW, clients={"shared": ScriptedClient(), "isolated": isolated}
        )
        self.addCleanup(h.close)
        h.run()
        report = checks.mechanical_report(h.trace.dir, profile=topo.WAVE1["T5"], question_key="lld")
        self.assertTrue(report["checks"]["coverage_from_authority"]["ok"])
        self.assertEqual(report["checks"]["coverage_from_authority"]["basis"], "model_authority")


class FrozenLabelTests(unittest.TestCase):
    P3 = cases._claim("p3")  # the frozen clear positive for s1-o1

    def ledger(self, claim, attached):
        return {
            "verified_propositions": [
                {"proposition_id": "p1", "proposition_text": claim, "responsive_obligation_ids": list(attached)}
            ]
        }

    def test_a_claim_matching_a_frozen_label_inherits_its_expected_judgment(self):
        result = checks.frozen_label_reuse(self.ledger(self.P3, ["s1-o1"]), "aib")
        self.assertEqual(result["matched"][0]["frozen_id"], "A1")
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["missing_required"], [])

    def test_a_forbidden_attachment_is_a_violation_and_a_missing_required_one_is_reported(self):
        wrong = checks.frozen_label_reuse(self.ledger(self.P3, ["s4-o1"]), "aib")
        self.assertEqual(wrong["violations"][0]["obligation_id"], "s4-o1")
        self.assertEqual(wrong["missing_required"][0]["obligation_id"], "s1-o1")

    def test_matching_ignores_case_spacing_and_a_trailing_period(self):
        variant = "  " + self.P3.upper().replace(" ", "  ") + "."
        self.assertEqual(len(checks.frozen_label_reuse(self.ledger(variant, ["s1-o1"]), "aib")["matched"]), 1)

    def test_frozen_labels_apply_only_to_the_aib_question(self):
        result = checks.frozen_label_reuse(self.ledger(self.P3, ["s1-o1"]), "lld")
        self.assertEqual(result["matched"], [])
        self.assertFalse(result["applicable"])

    def test_a_claim_with_no_frozen_label_is_left_for_adjudication(self):
        result = checks.frozen_label_reuse(self.ledger("An unrelated result.", ["s1-o1"]), "aib")
        self.assertEqual(result["unlabelled_responsive"], ["p1"])


class AdjudicationSheetTests(unittest.TestCase):
    def sealed(self, claims):
        return {
            "request_contract": {"original_question": "q"},
            "obligation_states": [
                {"field_id": "s1-o1", "source_unit_id": "u1", "note": "item one", "display": "item one"},
                {"field_id": "s2-o1", "source_unit_id": "u2", "note": "item two", "display": "item two"},
            ],
            "verified_propositions": [
                {
                    "proposition_id": f"p{i}",
                    "proposition_text": text,
                    "quote": f"quote for {text}",
                    "paper_id": 7,
                    "responsive_obligation_ids": list(obs),
                }
                for i, (text, obs) in enumerate(claims, start=1)
            ],
        }

    def test_the_sheet_strips_arm_labels_uses_opaque_ids_and_keeps_the_key_separate(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            runs = {
                "T1": self.sealed([("Claim A.", ["s1-o1"])]),
                "T2": self.sealed([("Claim A.", ["s1-o1"]), ("Claim B.", ["s2-o1"])]),
            }
            sheet_path, key_path = checks.build_adjudication_sheet(runs, "builtenv", Path(tmp), salt="fixed")
            sheet = sheet_path.read_text(encoding="utf-8")
            key = json.loads(key_path.read_text(encoding="utf-8"))
            for arm in ("T1", "T2"):
                self.assertNotIn(arm, sheet)
            self.assertEqual(len(key["items"]), 2)  # "Claim A." judged by both arms appears once
            merged = next(i for i in key["items"].values() if i["claim"] == "Claim A.")
            self.assertEqual(sorted(a["arm"] for a in merged["attachments"]), ["T1", "T2"])
            self.assertIn("Claim B.", sheet)
            self.assertIn("quote for Claim B.", sheet)

    def test_on_aib_a_claim_with_a_frozen_label_is_not_sent_for_adjudication(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            runs = {"T1": self.sealed([(FrozenLabelTests.P3, ["s1-o1"]), ("A new result.", ["s2-o1"])])}
            sheet_path, key_path = checks.build_adjudication_sheet(runs, "aib", Path(tmp), salt="fixed")
            key = json.loads(key_path.read_text(encoding="utf-8"))
            self.assertEqual([i["claim"] for i in key["items"].values()], ["A new result."])

    def test_only_judged_responsive_attachments_are_adjudicated(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            runs = {"T1": self.sealed([("Not attached.", [])])}
            _, key_path = checks.build_adjudication_sheet(runs, "builtenv", Path(tmp), salt="fixed")
            self.assertEqual(json.loads(key_path.read_text(encoding="utf-8"))["items"], {})


if __name__ == "__main__":
    unittest.main()
