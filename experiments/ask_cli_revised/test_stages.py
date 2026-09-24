"""R / C / P stages: source-verified claims in, judgments out; NO ANSWER is never a semantic verdict."""

import unittest
from types import SimpleNamespace

from experiments.ask_cli_revised import execution_policy as policy
from experiments.ask_cli_revised import stages
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.calibration.run06.dataset06 import DEPRESSION_QUESTION
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions

QUESTION = DEPRESSION_QUESTION
CONTRACT = build_request_contract(QUESTION)
SUBQUESTIONS = request_subquestions(CONTRACT)
OBLIGATIONS = [sq["obligations"][0] for sq in SUBQUESTIONS]
IDS = [o["field_id"] for o in OBLIGATIONS]


def rec(sid="s3", claim="Amyloid burden was higher in late-life depression.", *, status="verified",
        mapping_state="pending", obligation_ids=(), duplicate=False, paper_id=7, chunk=11, quote="A quote."):  # fmt: skip
    return {
        "subquestion_id": sid,
        "proposition_text": claim,
        "quote": quote,
        "paper_id": paper_id,
        "evidence_anchor_chunk_id": chunk,
        "evidence_span_id": "e1",
        "obligation_ids": list(obligation_ids),
        "mapping_state": mapping_state,
        "verification": {"status": status},
        "provenance": {"origin": "initial", **({"duplicate_of_existing_evidence": True} if duplicate else {})},
    }


class FakeSupervisor:
    """Returns canned StageResults in order and records every prompt it was asked."""

    def __init__(self, *answers, role="R"):
        self.role, self.answers, self.calls, self.records = role, list(answers), [], []

    def call(self, stage, prompt, schema, *, input_text=""):
        self.calls.append({"stage": stage, "prompt": prompt, "schema": schema})
        answer = self.answers.pop(0)
        usable = answer is not None
        record = {
            "model": "fake",
            "stage": stage,
            "usable": usable,
            "outcome": "usable" if usable else "capped_at_allowance",
        }
        self.records.append(record)
        return policy.StageResult(answer=answer, record=record)  # fmt: skip


class ResponsivenessTests(unittest.TestCase):
    def test_only_pending_source_verified_records_are_asked_and_each_is_asked_once(self):
        records = [
            rec(),
            rec(status="weak"),
            rec(duplicate=True),
            rec(mapping_state="mapped", obligation_ids=["s3-o1"]),
        ]
        supervisor = FakeSupervisor({"rationale": "It is about amyloid.", "responsive_obligation_ids": ["s3-o1"]})
        counts = stages.run_responsiveness(supervisor, question=QUESTION, obligations=OBLIGATIONS, records=records)
        self.assertEqual(len(supervisor.calls), 1)
        self.assertEqual(counts, {"asked": 1, "mapped": 1, "no_answer": 0})
        self.assertEqual(records[0]["obligation_ids"], ["s3-o1"])
        self.assertEqual(records[0]["mapping_state"], "mapped")
        self.assertEqual(records[1]["mapping_state"], "pending")  # not source-verified: never asked
        self.assertEqual(records[2]["mapping_state"], "pending")  # duplicate of earlier evidence: never asked

    def test_the_prompt_is_the_frozen_contract_over_all_obligations_with_the_original_request(self):
        supervisor = FakeSupervisor({"rationale": "x", "responsive_obligation_ids": []})
        stages.run_responsiveness(supervisor, question=QUESTION, obligations=OBLIGATIONS, records=[rec()])
        call = supervisor.calls[0]
        self.assertEqual(call["stage"], "claim_responsiveness")
        self.assertIn(QUESTION, call["prompt"])
        self.assertIn("Amyloid burden was higher in late-life depression.", call["prompt"])
        self.assertIn("- s3-o1: amyloid [part of the request sentence:", call["prompt"])
        self.assertEqual(call["schema"]["properties"]["responsive_obligation_ids"]["maxItems"], 8)

    def test_a_valid_empty_selection_is_mapped_to_nothing_which_is_not_no_answer(self):
        records = [rec()]
        stages.run_responsiveness(
            FakeSupervisor({"rationale": "Not about any item.", "responsive_obligation_ids": []}),
            question=QUESTION, obligations=OBLIGATIONS, records=records,
        )  # fmt: skip
        self.assertEqual(records[0]["obligation_ids"], [])
        self.assertEqual(records[0]["mapping_state"], "mapped")  # an answer: "responsive to none"

    def test_no_answer_is_recorded_as_no_answer_never_as_responsive_to_none(self):
        records = [rec()]
        counts = stages.run_responsiveness(
            FakeSupervisor(None), question=QUESTION, obligations=OBLIGATIONS, records=records
        )
        self.assertEqual(records[0]["mapping_state"], "no_answer")
        self.assertEqual(records[0]["obligation_ids"], [])
        self.assertEqual(records[0]["mapping"]["outcome"], "capped_at_allowance")
        self.assertEqual(counts, {"asked": 1, "mapped": 0, "no_answer": 1})

    def test_mapped_ids_follow_obligation_order_and_are_deduplicated(self):
        records = [rec()]
        stages.run_responsiveness(
            FakeSupervisor({"rationale": "x", "responsive_obligation_ids": ["s5-o1", "s3-o1", "s5-o1"]}),
            question=QUESTION, obligations=OBLIGATIONS, records=records,
        )  # fmt: skip
        self.assertEqual(records[0]["obligation_ids"], ["s3-o1", "s5-o1"])


class DetCoverageTests(unittest.TestCase):
    def test_attachments_come_from_the_mapping_and_the_rest_are_unresolved(self):
        records = [rec(mapping_state="mapped", obligation_ids=["s3-o1"]), rec(claim="Other.", sid="s4")]
        result = stages.det_coverage(SUBQUESTIONS, records, authority={"kind": "det", "role": "R"})
        by_ob = {o["field_id"]: o for o in result["obligations"]}
        self.assertEqual(by_ob["s3-o1"]["state"], "judged_responsive")
        self.assertEqual(by_ob["s3-o1"]["proposition_ids"], ["p1"])
        self.assertEqual(by_ob["s4-o1"]["state"], "no_responsive_claim")
        self.assertTrue(result["assessed"])
        self.assertEqual(result["authority"], {"kind": "det", "role": "R"})

    def test_records_whose_mapping_had_no_answer_are_counted_as_mechanical_gaps_for_their_item(self):
        records = [rec(mapping_state="no_answer", sid="s3"), rec(mapping_state="mapped", sid="s4", claim="Y.")]
        by_ob = {o["field_id"]: o for o in stages.det_coverage(SUBQUESTIONS, records, authority={})["obligations"]}
        self.assertEqual(by_ob["s3-o1"]["mechanical_gaps"], 1)
        self.assertEqual(by_ob["s3-o1"]["state"], "no_responsive_claim")  # not asserted absent: the gap is disclosed
        self.assertEqual(by_ob["s4-o1"]["mechanical_gaps"], 0)

    def test_duplicates_and_non_verified_records_never_enter_the_ledger(self):
        records = [rec(duplicate=True, mapping_state="mapped", obligation_ids=["s3-o1"]), rec(status="weak")]
        result = stages.det_coverage(SUBQUESTIONS, records, authority={})
        self.assertTrue(all(o["proposition_ids"] == [] for o in result["obligations"]))


COVERAGE_OK = {
    "rationale": "p1 answers the amyloid item.",
    "coverage": {
        **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
        "s3-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p1"]},
    },
}


class ModelCoverageTests(unittest.TestCase):
    def audit(self, answer, records=None):
        supervisor = FakeSupervisor(answer, role="C")
        result = stages.run_coverage_audit(
            supervisor, question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS,
            records=records if records is not None else [rec()], authority={"kind": "model", "role": "C"},
        )  # fmt: skip
        return result, supervisor

    def test_the_audit_uses_the_frozen_contract_with_quotes_and_provenance(self):
        _, supervisor = self.audit(COVERAGE_OK, [rec(quote="Amyloid PET binding was elevated.")])
        call = supervisor.calls[0]
        self.assertEqual(call["stage"], "coverage_audit")
        self.assertIn('supporting quote: "Amyloid PET binding was elevated."', call["prompt"])
        self.assertIn("retrieved while searching for: s3-o1", call["prompt"])

    def test_judgments_become_the_authoritative_states(self):
        result, _ = self.audit(COVERAGE_OK)
        by_ob = {o["field_id"]: o for o in result["obligations"]}
        self.assertEqual(by_ob["s3-o1"]["state"], "judged_responsive")
        self.assertEqual(by_ob["s3-o1"]["proposition_ids"], ["p1"])
        self.assertEqual(by_ob["s1-o1"]["state"], "no_responsive_claim")
        self.assertTrue(result["assessed"])

    def test_an_empty_ledger_is_not_sent_and_leaves_every_item_unresolved(self):
        result, supervisor = self.audit(None, records=[])
        self.assertEqual(supervisor.calls, [])
        self.assertTrue(all(o["state"] == "no_responsive_claim" for o in result["obligations"]))
        self.assertTrue(result["assessed"])
        self.assertEqual(result["skipped_reason"], "empty_ledger")

    def test_no_answer_leaves_every_item_not_assessed_never_unresolved(self):
        result, _ = self.audit(None)
        self.assertFalse(result["assessed"])
        self.assertTrue(all(o["state"] == "not_assessed" for o in result["obligations"]))
        self.assertEqual(result["outcome"], "capped_at_allowance")

    def test_an_internally_inconsistent_answer_is_no_answer(self):
        bad = {
            "rationale": "x",
            "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s3-o1": {"status": "unresolved", "supporting_proposition_ids": ["p1"]},
            },
        }
        result, supervisor = self.audit(bad)
        self.assertFalse(result["assessed"])
        self.assertEqual(result["outcome"], stages.INCONSISTENT)
        self.assertEqual(supervisor.records[-1]["outcome"], stages.INCONSISTENT)
        self.assertFalse(supervisor.records[-1]["usable"])

    def test_support_without_a_proposition_is_also_inconsistent(self):
        bad = {
            "rationale": "x",
            "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s3-o1": {"status": "responsive_support", "supporting_proposition_ids": []},
            },
        }
        result, _ = self.audit(bad)
        self.assertEqual(result["outcome"], stages.INCONSISTENT)


class RecoveryPlanTests(unittest.TestCase):
    coverage = {
        "obligations": [
            {"field_id": ob, "proposition_ids": (["p1"] if ob == "s3-o1" else [])} for ob in IDS
        ]  # fmt: skip
    }

    def plan(self, answer):
        supervisor = FakeSupervisor(answer, role="P")
        result = stages.run_recovery_plan(
            supervisor,
            question=QUESTION,
            obligations=OBLIGATIONS,
            subquestions=SUBQUESTIONS,
            records=[rec()],
            coverage=self.coverage,
        )
        return result, supervisor

    def answer(self, **overrides):
        plan = {ob: f"{ob}:PRESERVE_UNRESOLVED" for ob in IDS}
        plan.update({f"{k}-o1": v for k, v in overrides.items()})
        return {"rationale": "x", "plan": plan}

    def test_planned_actions_are_parsed_per_obligation(self):
        result, _ = self.plan(self.answer(s3="s3-o1:MARK_COVERED:p1", s4="s4-o1:NOMINATE", s5="s5-o1:DEEPEN"))
        self.assertEqual(result["state"], "planned")
        self.assertEqual(result["plan"]["s3-o1"], "MARK_COVERED:p1")
        self.assertEqual(result["plan"]["s4-o1"], "NOMINATE")
        self.assertEqual(result["plan"]["s5-o1"], "DEEPEN")
        self.assertEqual(result["plan"]["s1-o1"], "PRESERVE_UNRESOLVED")

    def test_the_first_planning_call_states_that_nothing_has_been_performed(self):
        _, supervisor = self.plan(self.answer())
        call = supervisor.calls[0]
        self.assertEqual(call["stage"], policy.RECOVERY_PLANNING)
        self.assertIn("- DEEPEN: not yet performed", call["prompt"])
        self.assertNotIn("(ALREADY PERFORMED)", call["prompt"])
        self.assertIn("Coverage audit, responsive support found in: p1", call["prompt"])
        self.assertIn("- s3-o1:MARK_COVERED:p1", call["prompt"])

    def test_no_answer_performs_no_planned_action_and_is_recorded(self):
        result, _ = self.plan(None)
        self.assertEqual(result["state"], "no_answer")
        self.assertEqual(result["plan"], {})
        self.assertEqual(result["reason_code"], "recovery_plan_no_answer")

    def test_the_legacy_plan_runs_the_shipped_sequence_for_every_obligation_without_a_model(self):
        result = stages.legacy_plan(OBLIGATIONS)
        self.assertEqual(result["source"], "legacy")
        self.assertEqual(set(result["plan"].values()), {"LEGACY"})
        self.assertEqual(list(result["plan"]), IDS)


class SupervisorTests(unittest.TestCase):
    def supervisor(self, response, base=None):
        client = SimpleNamespace(calls=[])

        def chat(model, prompt, **kwargs):
            client.calls.append({"model": model, "prompt": prompt, **kwargs})
            return response

        client.chat = chat
        binding = topo.Binding("ollama", "qwen3.5:9b", endpoint="isolated", think=True)
        return stages.Supervisor("P", binding, client, base or topo.SUPERVISOR_BASE_OPTIONS), client

    def test_a_call_goes_through_the_execution_policy_with_the_bindings_think_setting(self):
        response = {
            "status": "ok", "content": '{"x": 1}', "thinking": "", "done_reason": "stop",
            "timings": {"prompt_eval_count": 10, "eval_count": 5}, "wall_seconds": 1.0,
        }  # fmt: skip
        supervisor, client = self.supervisor(response)
        result = supervisor.call(policy.RECOVERY_PLANNING, "short prompt", {"type": "object"})
        (call,) = client.calls
        self.assertEqual(call["options"]["num_predict"], 8192)  # qwen3.5 recovery planning
        self.assertIs(call["think"], True)
        self.assertEqual(result.record["role"], "P")
        self.assertEqual(supervisor.records, [result.record])

    def test_a_prompt_that_cannot_fit_the_context_is_never_sent(self):
        supervisor, client = self.supervisor({})
        huge = "x" * 40_000  # ~13K estimated tokens against a 12,288 context
        result = supervisor.call("coverage_audit", huge, {"type": "object"})
        self.assertEqual(client.calls, [])
        self.assertIsNone(result.answer)
        self.assertEqual(result.record["outcome"], stages.PROMPT_TOO_LARGE)
        self.assertFalse(result.record["usable"])


class SealTests(unittest.TestCase):
    def test_the_sealed_ledger_carries_final_attachments_and_states_and_hides_no_claim(self):
        records = [rec(mapping_state="mapped", obligation_ids=["s3-o1"]), rec(sid="s4", claim="Other claim.", chunk=12)]
        coverage = stages.det_coverage(SUBQUESTIONS, records, authority={"kind": "det", "role": "R"})
        packets = [
            {"paper_id": 7, "candidate_spans": [{"chunk_id": 11, "span_id": "e1", "text": "A quote."}]},
            {"paper_id": 7, "candidate_spans": [{"chunk_id": 12, "span_id": "e1", "text": "A quote."}]},
        ]
        sealed = stages.seal(CONTRACT, SUBQUESTIONS, records, packets, coverage)
        rows = {r["proposition_id"]: r for r in sealed["verified_propositions"]}
        self.assertEqual(rows["p1"]["responsive_obligation_ids"], ["s3-o1"])
        self.assertEqual(rows["p2"]["responsive_obligation_ids"], [])
        self.assertEqual(len(sealed["obligation_states"]), 8)
        self.assertEqual(sealed["coverage_authority"], {"kind": "det", "role": "R"})
        self.assertTrue(sealed["coverage_assessed"])
        self.assertEqual(len(sealed["evidence_spans"]), 2)


if __name__ == "__main__":
    unittest.main()
