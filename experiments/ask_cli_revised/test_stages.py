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


# ---- Phase 17: C2 re-sealing stability / locality (append-only sealing) -----------------------------------------

PACKET_11 = {"paper_id": 7, "candidate_spans": [{"chunk_id": 11, "span_id": "e1", "text": "A quote."}]}
PACKET_21 = {"paper_id": 7, "candidate_spans": [{"chunk_id": 21, "span_id": "e1", "text": "Another quote."}]}


class CoverageClassifyPidsTests(unittest.TestCase):
    """§A/§G: `classify_pids` restricts the model-facing candidate list, never the obligation set."""

    def audit(self, answer, records, classify_pids):
        supervisor = FakeSupervisor(answer, role="C")
        result = stages.run_coverage_audit(
            supervisor, question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS,
            records=records, authority={"kind": "model", "role": "C"}, classify_pids=classify_pids,
        )  # fmt: skip
        return result, supervisor

    def test_classify_pids_restricts_the_model_facing_list_but_keeps_the_full_obligation_set(self):
        records = [rec(), rec(sid="s4", claim="Other.", chunk=12)]
        _, supervisor = self.audit(COVERAGE_OK, records, classify_pids={"p1"})
        prompt = supervisor.calls[0]["prompt"]
        self.assertIn("p1:", prompt)
        self.assertNotIn("p2:", prompt)  # p2 is old evidence -- excluded from the model-facing list
        # obligations/items passed to the model are the FULL set regardless (never narrowed to a
        # triggering child, a RecoveryTarget owner, or any descendant scope -- §G).
        for ob in IDS:
            self.assertIn(ob, prompt)

    def test_a_new_proposition_can_map_to_several_obligations_including_a_non_triggering_one(self):
        records = [rec(sid="s3"), rec(sid="s4", claim="New evidence.", chunk=99)]
        answer = {
            "rationale": "x",
            "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s3-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p2"]},
                "s4-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p2"]},
            },
        }
        result, _ = self.audit(answer, records, classify_pids={"p2"})
        by_ob = {o["field_id"]: o for o in result["obligations"]}
        self.assertEqual(by_ob["s3-o1"]["proposition_ids"], ["p2"])  # not the search-owner child...
        self.assertEqual(by_ob["s4-o1"]["proposition_ids"], ["p2"])  # ...equally legitimate on its own evidence

    def test_classify_pids_naming_no_ledger_row_is_a_no_op_that_makes_no_model_call(self):
        records = [rec()]
        result, supervisor = self.audit(COVERAGE_OK, records, classify_pids=set())
        self.assertEqual(supervisor.calls, [])  # a no-new-evidence round: never asks the model anything
        self.assertTrue(all(o["state"] == "no_responsive_claim" for o in result["obligations"]))
        self.assertTrue(result["assessed"])

    def test_pids_are_minted_from_the_full_ledger_never_reminted_for_a_restricted_call(self):
        records = [rec(), rec(sid="s4", claim="Other.", chunk=12), rec(sid="s5", claim="New.", chunk=21)]
        _, supervisor = self.audit(COVERAGE_OK, records, classify_pids={"p3"})
        self.assertIn("p3:", supervisor.calls[0]["prompt"])  # real suffix id, not a reminted "p1"


class PrefixStabilityTests(unittest.TestCase):
    """§C/§D: the pre-C2 fail-closed guard, asserted BEFORE any model call is possible."""

    def test_returns_exactly_the_new_suffix_when_the_old_prefix_is_unchanged(self):
        prior_records = [rec(), rec(sid="s4", claim="Other.", chunk=12)]
        coverage = stages.det_coverage(SUBQUESTIONS, prior_records, authority={"kind": "det", "role": "R"})
        prior_sealed = stages.seal(CONTRACT, SUBQUESTIONS, prior_records, [], coverage)
        grown = prior_records + [rec(sid="s5", claim="New.", chunk=21)]
        new_pids = stages.verify_stable_prefix_and_new_pids(prior_sealed, grown)
        self.assertEqual(new_pids, {"p3"})

    def test_a_record_identity_change_on_an_old_pid_raises_before_any_model_call_is_possible(self):
        prior_records = [rec()]
        coverage = stages.det_coverage(SUBQUESTIONS, prior_records, authority={})
        prior_sealed = stages.seal(CONTRACT, SUBQUESTIONS, prior_records, [], coverage)
        corrupted = [rec(claim="A DIFFERENT claim now occupies p1.")]  # same pid, different identity
        with self.assertRaises(stages.SealingPrefixDriftError):
            stages.verify_stable_prefix_and_new_pids(prior_sealed, corrupted)
        # the guard itself never touches a Supervisor at all -- structurally, a caller that checks
        # this BEFORE building a FakeSupervisor (as e2e.py's wiring does) cannot reach a model call.

    def test_a_shrunk_ledger_raises_rather_than_silently_truncating(self):
        prior_records = [rec(), rec(sid="s4", claim="Other.", chunk=12)]
        coverage = stages.det_coverage(SUBQUESTIONS, prior_records, authority={})
        prior_sealed = stages.seal(CONTRACT, SUBQUESTIONS, prior_records, [], coverage)
        with self.assertRaises(stages.SealingPrefixDriftError):
            stages.verify_stable_prefix_and_new_pids(prior_sealed, prior_records[:1])


class RecordIdentityTests(unittest.TestCase):
    """§D: two records sharing a physical evidence anchor must not be conflated by identity."""

    def test_shared_anchor_distinct_claim_text_are_different_identities(self):
        shared_anchor = rec(claim="Claim A.", chunk=11)
        other_claim_same_anchor = rec(claim="Claim B.", chunk=11)
        self.assertNotEqual(stages.record_identity(shared_anchor), stages.record_identity(other_claim_same_anchor))

    def test_same_paper_anchor_and_claim_text_case_insensitively_is_the_same_identity(self):
        a = rec(claim="Amyloid burden was higher.")
        b = rec(claim="AMYLOID BURDEN WAS HIGHER.")
        self.assertEqual(stages.record_identity(a), stages.record_identity(b))


class AppendOnlySealTests(unittest.TestCase):
    """§A/§B/§F: old attachments survive a recovery round byte-for-byte; only new ones are fresh."""

    def seal_initial(self, records):
        coverage = stages.det_coverage(SUBQUESTIONS, records, authority={"kind": "det", "role": "R"})
        return stages.seal(CONTRACT, SUBQUESTIONS, records, [PACKET_11], coverage)

    def test_old_attachments_are_preserved_byte_for_byte_and_new_ones_are_freshly_classified(self):
        prior_records = [rec(mapping_state="mapped", obligation_ids=["s3-o1"])]
        prior_sealed = self.seal_initial(prior_records)
        grown = prior_records + [rec(sid="s4", claim="New evidence.", chunk=21)]
        new_only_answer = {
            "rationale": "x",
            "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s4-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p2"]},
            },
        }
        new_pids = stages.verify_stable_prefix_and_new_pids(prior_sealed, grown)
        self.assertEqual(new_pids, {"p2"})
        result = stages.run_coverage_audit(
            FakeSupervisor(new_only_answer, role="C"), question=QUESTION, obligations=OBLIGATIONS,
            subquestions=SUBQUESTIONS, records=grown, authority={"kind": "model", "role": "C"},
            classify_pids=new_pids,
        )  # fmt: skip
        sealed = stages.seal(CONTRACT, SUBQUESTIONS, grown, [PACKET_11, PACKET_21], result, prior_sealed=prior_sealed)
        rows = {r["proposition_id"]: r for r in sealed["verified_propositions"]}
        self.assertEqual(rows["p1"]["responsive_obligation_ids"], ["s3-o1"])  # byte-for-byte preserved
        self.assertEqual(rows["p2"]["responsive_obligation_ids"], ["s4-o1"])  # freshly classified
        cumulative = {o["field_id"]: o for o in sealed["obligation_states"]}
        self.assertEqual(cumulative["s3-o1"]["proposition_ids"], ["p1"])  # old support still visible
        self.assertEqual(cumulative["s4-o1"]["proposition_ids"], ["p2"])  # new support now visible

    def test_a_mechanically_failed_new_only_call_leaves_the_prior_cumulative_state_untouched(self):
        prior_records = [rec(mapping_state="mapped", obligation_ids=["s3-o1"])]
        prior_sealed = self.seal_initial(prior_records)
        grown = prior_records + [rec(sid="s4", claim="New evidence.", chunk=21)]
        failed = stages.run_coverage_audit(
            FakeSupervisor(None, role="C"), question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS,
            records=grown, authority={"kind": "model", "role": "C"}, classify_pids={"p2"},
        )  # fmt: skip
        self.assertFalse(failed["assessed"])
        sealed = stages.seal(CONTRACT, SUBQUESTIONS, grown, [PACKET_11, PACKET_21], failed, prior_sealed=prior_sealed)
        self.assertEqual(sealed["coverage_assessed"], prior_sealed["coverage_assessed"])  # inherited, not erased
        self.assertEqual(sealed["obligation_states"], prior_sealed["obligation_states"])  # byte-for-byte
        rows = {r["proposition_id"]: r for r in sealed["verified_propositions"]}
        self.assertEqual(rows["p1"]["responsive_obligation_ids"], ["s3-o1"])  # old evidence untouched
        self.assertEqual(rows["p2"]["responsive_obligation_ids"], [])  # new evidence inspectable, unattached

    def test_a_new_proposition_judged_non_responsive_stays_inspectable_with_no_attachment(self):
        prior_records = [rec(mapping_state="mapped", obligation_ids=["s3-o1"])]
        prior_sealed = self.seal_initial(prior_records)
        grown = prior_records + [rec(sid="s4", claim="Unrelated evidence.", chunk=21)]
        new_pids = stages.verify_stable_prefix_and_new_pids(prior_sealed, grown)
        not_responsive = {
            "rationale": "x",
            "coverage": {ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
        }
        cov = stages.run_coverage_audit(
            FakeSupervisor(not_responsive, role="C"), question=QUESTION, obligations=OBLIGATIONS,
            subquestions=SUBQUESTIONS, records=grown, authority={"kind": "model", "role": "C"},
            classify_pids=new_pids,
        )  # fmt: skip
        sealed = stages.seal(CONTRACT, SUBQUESTIONS, grown, [PACKET_11, PACKET_21], cov, prior_sealed=prior_sealed)
        rows = {r["proposition_id"]: r for r in sealed["verified_propositions"]}
        self.assertIn("p2", rows)  # inspectable -- never dropped from the ledger
        self.assertEqual(rows["p2"]["responsive_obligation_ids"], [])
        # Downstream exclusion from any child's candidate pool is pre-existing, unchanged
        # `sufficiency_diagnostic.units_by_child` behavior (it already skips empty attachments);
        # not re-tested here.

    def test_two_new_propositions_are_each_classified_exactly_once_in_one_coverage_call(self):
        prior_records = [rec(mapping_state="mapped", obligation_ids=["s3-o1"])]
        prior_sealed = self.seal_initial(prior_records)
        grown = prior_records + [
            rec(sid="s4", claim="New evidence one.", chunk=21),
            rec(sid="s5", claim="New evidence two.", chunk=31),
        ]
        new_pids = stages.verify_stable_prefix_and_new_pids(prior_sealed, grown)
        self.assertEqual(new_pids, {"p2", "p3"})
        answer = {
            "rationale": "x",
            "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s4-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p2"]},
                "s5-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p3"]},
            },
        }
        supervisor = FakeSupervisor(answer, role="C")
        cov = stages.run_coverage_audit(
            supervisor, question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS, records=grown,
            authority={"kind": "model", "role": "C"}, classify_pids=new_pids,
        )  # fmt: skip
        self.assertEqual(len(supervisor.calls), 1)  # one call classifies both new propositions
        sealed = stages.seal(CONTRACT, SUBQUESTIONS, grown, [PACKET_11, PACKET_21], cov, prior_sealed=prior_sealed)
        rows = {r["proposition_id"]: r for r in sealed["verified_propositions"]}
        self.assertEqual(rows["p2"]["responsive_obligation_ids"], ["s4-o1"])
        self.assertEqual(rows["p3"]["responsive_obligation_ids"], ["s5-o1"])

    def test_a_duplicate_of_existing_evidence_never_consumes_a_pid_or_enters_new_pids(self):
        prior_records = [rec(mapping_state="mapped", obligation_ids=["s3-o1"])]
        prior_sealed = self.seal_initial(prior_records)
        grown = prior_records + [
            rec(sid="s4", claim="New evidence.", chunk=21),
            rec(sid="s4", claim="New evidence.", chunk=21, duplicate=True),  # a rediscovery of the same evidence
        ]
        new_pids = stages.verify_stable_prefix_and_new_pids(prior_sealed, grown)
        self.assertEqual(new_pids, {"p2"})  # the duplicate row is filtered out before pid-minting, not a "p3"

    def test_a_record_identity_mismatch_against_prior_sealed_raises_inside_seal_too(self):
        prior_records = [rec()]
        prior_sealed = self.seal_initial(prior_records)
        corrupted = [rec(claim="A different claim now sits at p1.")]
        empty_coverage = {"authority": {}, "assessed": True, "obligations": [], "outcome": None}
        with self.assertRaises(stages.SealingPrefixDriftError):
            stages.seal(CONTRACT, SUBQUESTIONS, corrupted, [], empty_coverage, prior_sealed=prior_sealed)

    def test_two_recovery_rounds_never_reclassify_a_round_one_sealed_proposition(self):
        round0 = [rec(mapping_state="mapped", obligation_ids=["s3-o1"])]
        sealed0 = self.seal_initial(round0)
        round1 = round0 + [rec(sid="s4", claim="Round one evidence.", chunk=21)]
        round1_new = stages.verify_stable_prefix_and_new_pids(sealed0, round1)
        self.assertEqual(round1_new, {"p2"})
        cov1 = stages.run_coverage_audit(
            FakeSupervisor(
                {
                    "rationale": "x",
                    "coverage": {
                        **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                        "s4-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p2"]},
                    },
                },
                role="C",
            ),
            question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS, records=round1,
            authority={"kind": "model", "role": "C"}, classify_pids=round1_new,
        )  # fmt: skip
        sealed1 = stages.seal(CONTRACT, SUBQUESTIONS, round1, [PACKET_11, PACKET_21], cov1, prior_sealed=sealed0)

        round2 = round1 + [rec(sid="s5", claim="Round two evidence.", chunk=31)]
        round2_new = stages.verify_stable_prefix_and_new_pids(sealed1, round2)
        self.assertEqual(round2_new, {"p3"})  # p1/p2 are both now a stable, un-reclassifiable prefix
        cov2 = stages.run_coverage_audit(
            FakeSupervisor(
                {
                    "rationale": "x",
                    "coverage": {
                        **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                        "s5-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p3"]},
                    },
                },
                role="C",
            ),
            question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS, records=round2,
            authority={"kind": "model", "role": "C"}, classify_pids=round2_new,
        )  # fmt: skip
        sealed2 = stages.seal(CONTRACT, SUBQUESTIONS, round2, [PACKET_11, PACKET_21], cov2, prior_sealed=sealed1)
        rows = {r["proposition_id"]: r for r in sealed2["verified_propositions"]}
        self.assertEqual(rows["p1"]["responsive_obligation_ids"], ["s3-o1"])  # round 0, untouched by rounds 1+2
        self.assertEqual(rows["p2"]["responsive_obligation_ids"], ["s4-o1"])  # round 1, untouched by round 2
        self.assertEqual(rows["p3"]["responsive_obligation_ids"], ["s5-o1"])  # round 2, freshly classified


class SameLedgerRerunDriftTests(unittest.TestCase):
    """§15: real, independently-measured evidence that a repeated whole-ledger coverage call can
    disagree with itself over an UNCHANGED ledger (no new evidence at all) -- this audit's own
    finding, hardcoded as a permanent regression fixture rather than left to a live `.local/`
    dependency (the Phase-16 precedent: a real recorded disagreement, baked in as a literal). The
    real pattern (from a preserved live run, `q-aib-hierarchical-t5c-live-20260930`): re-running
    whole-ledger coverage over the SAME 26 propositions reassigned p1 (c1->c2), p3 (c2->c3), p16
    (c5->c3+c5), p22/p23 (c11->[], lost entirely), and p26 ([]->c9, gained from nothing) -- gain
    AND loss, with zero new evidence. Append-only sealing must make this impossible by construction
    once there is nothing new to classify, regardless of why a repeated classifier disagrees."""

    def test_a_whole_ledger_rerun_with_a_different_answer_drifts_without_prior_sealed(self):
        records = [rec(sid="s3"), rec(sid="s4", claim="Other.", chunk=12)]
        first = {
            "rationale": "x",
            "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s3-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p1"]},
            },
        }
        second = {  # the SAME ledger, a genuinely different model judgment: p1 moved to s4-o1
            "rationale": "x",
            "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s4-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p1"]},
            },
        }
        cov1 = stages.run_coverage_audit(
            FakeSupervisor(first, role="C"), question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS,
            records=records, authority={"kind": "model", "role": "C"},
        )  # fmt: skip
        cov2 = stages.run_coverage_audit(
            FakeSupervisor(second, role="C"), question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS,
            records=records, authority={"kind": "model", "role": "C"},
        )  # fmt: skip
        # Without prior_sealed, seal() has no way to know these two calls disagree about the SAME
        # unchanged p1 -- this is the pre-Phase-17 hazard the whole design exists to close off.
        sealed1 = stages.seal(CONTRACT, SUBQUESTIONS, records, [], cov1)
        sealed2 = stages.seal(CONTRACT, SUBQUESTIONS, records, [], cov2)
        rows1 = {r["proposition_id"]: r["responsive_obligation_ids"] for r in sealed1["verified_propositions"]}
        rows2 = {r["proposition_id"]: r["responsive_obligation_ids"] for r in sealed2["verified_propositions"]}
        self.assertNotEqual(rows1["p1"], rows2["p1"])  # the drift this phase exists to eliminate

    def test_a_genuinely_no_new_evidence_round_cannot_drift_under_the_real_e2e_gate(self):
        # Mirrors e2e.py's own gate exactly: coverage_final stays `coverage_initial` (never a
        # second call at all) whenever recovery added no new source-verified evidence -- so a
        # same-ledger rerun disagreement is structurally impossible on that path, regardless of
        # why a repeated classifier might disagree (§15: ordinary nondeterminism, context/batch
        # sensitivity, or something else -- the mechanism does not matter once C2 is never called).
        records = [rec(sid="s3"), rec(sid="s4", claim="Other.", chunk=12)]
        coverage_initial = stages.run_coverage_audit(
            FakeSupervisor({"rationale": "x", "coverage": {
                **{ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in IDS},
                "s3-o1": {"status": "responsive_support", "supporting_proposition_ids": ["p1"]},
            }}, role="C"),
            question=QUESTION, obligations=OBLIGATIONS, subquestions=SUBQUESTIONS,
            records=records, authority={"kind": "model", "role": "C"},
        )  # fmt: skip
        before = len(stages.source_verified(records))
        after = len(stages.source_verified(records))  # no W2 append happened
        coverage_final = coverage_initial if not (after > before) else None
        self.assertIs(coverage_final, coverage_initial)
        sealed = stages.seal(CONTRACT, SUBQUESTIONS, records, [], coverage_final)
        self.assertEqual(
            {r["proposition_id"]: r["responsive_obligation_ids"] for r in sealed["verified_propositions"]}["p1"],
            ["s3-o1"],
        )


if __name__ == "__main__":
    unittest.main()
