"""Phase 27b: the zero-findings path through the REAL ``e2e.execute()``, offline.

What is real: the v9 frozen sufficiency contract, the hierarchy, the deterministic mapping, ``execute()``'s whole
recovery block, the real ``__main__._recover`` control flow (plan action, query, reason codes), the persisted scoped-
search status, the final target computation, the gap report, the parent construction record, and the rendered answer.

What is scripted: the three search primitives (retrieval, nomination, hit processing) find nothing, and the recovery
query may refuse for named subquestions. No model, no network. Shared Ollama and JUNO are never touched.
"""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest import mock

from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised import e2e, sufficiency_freeze
from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised.hierarchy_test_support import HierHarness, r_by_claim
from experiments.ask_cli_revised.overview_test_support import Entail
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.test_e2e_run import ScriptedClient
from experiments.ask_cli_revised.test_parent_synthesis_wiring import (
    C12_OUTCOME_CLAIM,
    EVIDENCE,
    ParentS2Client,
    _profile_with_s,
)

C4 = "c4#suff:specific-region"
C4_HEADER = "## Searched, no supported result established"
C4_CATEGORIES = "a specific NAMED brain area; evidence that the named region bears on the bias"

# The real `_recover_round`, captured before any harness patches `e2e._recover_round`.
REAL_RECOVER_ROUND = e2e._recover_round


class _Qwen:
    """The one qwen method `_recover` calls. Returns a deterministic query, or NO ANSWER for refused subquestions."""

    def __init__(self, refused_texts):
        self.refused = set(refused_texts)

    def recovery_query(self, *, subquestion, obligation_note):
        return None if subquestion in self.refused else f"recovery query for {subquestion}"


class ZeroHitHarness(HierHarness):
    """A real hierarchy run whose recovery round goes through the REAL ``_recover`` with scripted, empty search."""

    refuse_ids: frozenset = frozenset()

    def _recover_round(self, conn, *, rt, qwen, subquestions, gaps, plan, sink, trace):
        refused = [sq["text"] for sq in subquestions if sq["subquestion_id"] in self.refuse_ids]
        with (
            mock.patch.object(cli.retrieval, "within_paper_retrieve", lambda *a, **k: []),
            mock.patch.object(cli.discovery, "nominate_papers", lambda *a, **k: ([], {})),
            mock.patch.object(cli, "_process_hits", lambda *a, **k: None),
        ):
            # `_recover` reads rt.model / rt.vector_store only to pass them to the patched primitives.
            return REAL_RECOVER_ROUND(
                conn,
                rt=SimpleNamespace(model=None, vector_store=None),
                qwen=_Qwen(refused),
                subquestions=subquestions,
                gaps=gaps,
                plan=plan,
                sink=sink,
                trace=trace,
            )


class ZeroFindingsExecuteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.contract_by_child = sufficiency_freeze.load_verified()
        cls.parent_of = hc.parent_of(cls.contract)

    def _run(self, *, allowed=True, refuse_ids=frozenset()):
        contract_by_child = copy.deepcopy(self.contract_by_child)
        contract_by_child["c4"]["requirements"][0]["empty_result_semantically_allowed"] = allowed
        shared = ScriptedClient(r=r_by_claim({C12_OUTCOME_CLAIM: ["c12"]}))
        s_client = ParentS2Client()
        harness = ZeroHitHarness(
            _profile_with_s(),
            self.contract,
            initial=EVIDENCE,
            recovery=[],
            clients={"shared": shared, "isolated": s_client},
        )
        harness.refuse_ids = frozenset(refuse_ids)
        self.addCleanup(harness.close)
        result = harness.run(
            entail=Entail(),
            sufficiency_contract=contract_by_child,
            sufficiency_parent_of=self.parent_of,
            sufficiency_recovery_gate_enabled=True,
            parent_synthesis_enabled=True,
        )
        return result, harness, s_client

    @staticmethod
    def _c4(targets):
        return {tid: t for tid, t in targets.items() if t["requirement_id"] == C4}

    def test_the_initial_search_obligation_is_present_and_identical_regardless_of_the_permission(self):
        on, _, _ = self._run(allowed=True)
        off, _, _ = self._run(allowed=False)
        initial_on = self._c4(on["sufficiency_recovery_targets_initial"])
        self.assertEqual(len(initial_on), 2)
        self.assertEqual({t["reason"] for t in initial_on.values()}, {"missing"})
        self.assertEqual(on["sufficiency_recovery_targets_initial"], off["sufficiency_recovery_targets_initial"])

    def test_a_completed_zero_support_search_closes_only_the_zero_evidence_deficit(self):
        result, _, _ = self._run(allowed=True)
        self.assertIn("W2", [s["stage"] for s in result["stage_log"]], "the recovery round must actually run")

        round_outcome = result["scoped_search_round"][C4]
        self.assertTrue(round_outcome["completed"])
        self.assertEqual({s["state"] for s in round_outcome["target_states"].values()}, {"completed"})
        self.assertEqual(
            {s["reason_code"] for s in round_outcome["target_states"].values()}, {"recovery_no_new_evidence"}
        )

        final_status = result["scoped_search_final"][C4]
        self.assertTrue(final_status["terminal"])

        self.assertEqual(self._c4(result["sufficiency_recovery_targets"]), {})

        record = result["parent_synthesis"]["record"]
        self.assertEqual([g for g in record["gap_report"] if g["requirement_id"] == C4], [])
        self.assertEqual(len(record["resolved_empty_outcomes"]), 1)
        outcome = record["resolved_empty_outcomes"][0]
        self.assertEqual(outcome["requirement_id"], C4)
        self.assertEqual(outcome["child_id"], "c4")
        self.assertEqual(outcome["outcome"], "searched_no_support_established")
        self.assertEqual("; ".join(outcome["category_descriptions"]), C4_CATEGORIES)

    def test_the_parent_answer_says_the_search_completed_and_names_no_absence(self):
        result, harness, _ = self._run(allowed=True)
        answer = (harness.trace.dir / "15_parent_answer.md").read_text(encoding="utf-8")
        self.assertIn(C4_HEADER, answer)
        self.assertIn(
            f"- The scoped search completed without establishing a supported result for {C4_CATEGORIES}.", answer
        )
        self.assertNotIn("no such effect", answer)
        self.assertNotIn("proves absence", answer)
        self.assertTrue(result["parent_synthesis"]["audit"]["ok"], result["parent_synthesis"]["audit"]["problems"])

    def test_the_persisted_status_is_inspectable_and_matches_what_was_consumed(self):
        result, harness, _ = self._run(allowed=True)
        persisted = (harness.trace.dir / "13c_scoped_search.json").read_text(encoding="utf-8")
        self.assertIn(C4, persisted)
        record = result["parent_synthesis"]["record"]
        self.assertEqual(record["scoped_search_status"], result["scoped_search_final"])
        self.assertEqual(result["parent_synthesis"]["record"]["resolved_empty_outcomes"][0]["requirement_id"], C4)

    def test_the_counterfactual_flag_false_runs_the_same_search_and_keeps_the_unresolved_gap(self):
        result, harness, _ = self._run(allowed=False)
        self.assertTrue(result["scoped_search_round"][C4]["completed"], "the search still ran")
        self.assertFalse(result["scoped_search_final"][C4]["terminal"])
        self.assertEqual(len(self._c4(result["sufficiency_recovery_targets"])), 2)
        record = result["parent_synthesis"]["record"]
        self.assertEqual(len([g for g in record["gap_report"] if g["requirement_id"] == C4]), 2)
        self.assertEqual(record["resolved_empty_outcomes"], [])
        answer = (harness.trace.dir / "15_parent_answer.md").read_text(encoding="utf-8")
        self.assertNotIn(C4_HEADER, answer)
        self.assertTrue(result["parent_synthesis"]["audit"]["ok"])

    def test_a_refused_query_is_never_an_empty_result(self):
        """NO ANSWER for the c4 subquestion: the search never ran, so nothing is terminal and the gap stays."""
        result, harness, _ = self._run(allowed=True, refuse_ids={"c4"})
        round_outcome = result["scoped_search_round"][C4]
        self.assertFalse(round_outcome["completed"])
        self.assertEqual(
            {s["reason_code"] for s in round_outcome["target_states"].values()}, {"recovery_query_no_answer"}
        )
        self.assertFalse(result["scoped_search_final"][C4]["terminal"])
        self.assertEqual(len(self._c4(result["sufficiency_recovery_targets"])), 2)
        record = result["parent_synthesis"]["record"]
        self.assertEqual(len([g for g in record["gap_report"] if g["requirement_id"] == C4]), 2)
        self.assertEqual(record["resolved_empty_outcomes"], [])
        answer = (harness.trace.dir / "15_parent_answer.md").read_text(encoding="utf-8")
        self.assertNotIn(C4_HEADER, answer)

    def test_the_realization_stage_has_no_channel_for_the_terminal_outcome(self):
        """S2 realizes ParentClaims only. In this run there are no claims, so S2 is never called at all (asserted
        below); the stronger guarantee is structural: neither the realization entry point nor its prompt builder
        accepts any outcome or scoped-search argument, so the projection cannot reach a model prompt."""
        import inspect

        from experiments.ask_cli_revised import parent_synthesis

        result, _, s_client = self._run(allowed=True)
        self.assertEqual(result["parent_synthesis"]["record"]["claim_ledger"], [])
        self.assertEqual(s_client.parent_calls, [])
        for function in (parent_synthesis.realize, parent_synthesis.build_prompt):
            names = set(inspect.signature(function).parameters)
            self.assertFalse(
                names & {"resolved", "resolved_empty_outcomes", "scoped_search", "scoped_search_status"}, function
            )


if __name__ == "__main__":
    unittest.main()
