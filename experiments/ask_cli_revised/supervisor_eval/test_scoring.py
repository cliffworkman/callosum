"""Hard-gate scoring, exercised with synthetic supervisors (no model, no I/O).

A perfect supervisor must pass every gate; each deliberately-broken supervisor must fail exactly the
gate it violates. Diagnostic behavior must never rescue or sink a model.
"""

import json
import unittest

from experiments.ask_cli_revised.supervisor_eval import cases, scoring

OBS = cases.OBLIGATION_IDS


def perfect_output(spec):
    fam = spec["family"]
    if fam == "A":
        return {"rationale": "ok", "responsive_obligation_ids": list(spec["expected"]["required"])}
    if fam == "B":
        cov = {ob: {"status": "unresolved", "supporting_proposition_ids": []} for ob in OBS}
        cov["s1-o1"] = {"status": "responsive_support", "supporting_proposition_ids": ["p3"]}
        cov["s2-o1"] = {"status": "responsive_support", "supporting_proposition_ids": ["p4"]}
        return {"rationale": "ok", "coverage": cov}
    plan = {
        "s1-o1": "s1-o1:NO_RECOVERY_NEEDED",
        "s2-o1": "s2-o1:NO_RECOVERY_NEEDED",
        "s3-o1": "s3-o1:PRESERVE_UNRESOLVED",
        "s4-o1": "s4-o1:NOMINATE",
        "s5-o1": "s5-o1:PRESERVE_UNRESOLVED",
        "s6-o1": "s6-o1:PRESERVE_UNRESOLVED",
    }
    return {"rationale": "ok", "plan": plan}


def call_for(spec, output, **overrides):
    rec = {
        "case_id": spec["case_id"],
        "status": "ok",
        "done_reason": "stop",
        "content": json.dumps(output),
        "thinking": None,
        "timings": {},
        "wall_seconds": 1.0,
    }
    rec.update(overrides)
    return rec


def run(mutate=None, drop=None, override=None):
    """Score a supervisor: perfect outputs, optionally mutated per case."""
    specs = cases.build_case_specs()
    calls = []
    for spec in specs:
        if drop and spec["case_id"] in drop:
            continue
        out = perfect_output(spec)
        if mutate:
            out = mutate(spec, out) or out
        calls.append(call_for(spec, out, **((override or {}).get(spec["case_id"], {}))))
    return scoring.score_model(specs, calls)


def gates(result):
    return {g: v["status"] for g, v in result["gates"].items()}


class PerfectSupervisorTests(unittest.TestCase):
    def test_perfect_supervisor_passes_every_gate(self):
        result = run()
        self.assertEqual(gates(result), {g: "PASS" for g in ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")})
        self.assertIs(result["qualified"], True)


class TaskAFailureTests(unittest.TestCase):
    def test_first_item_anchoring_is_caught(self):
        def anchor(spec, out):
            if spec["family"] == "A":
                out["responsive_obligation_ids"] = [spec["obligation_order"][0]]

        result = run(anchor)
        self.assertEqual(gates(result)["G5"], "FAIL")
        self.assertEqual(gates(result)["G4"], "FAIL")  # A3 picks whatever is listed first
        self.assertIs(result["qualified"], False)

    def test_generic_neuroscience_mapped_to_the_nearest_brain_obligation_fails_G4(self):
        # The corrected contract: dmPFC -> s2 ("specific brain areas") is a false positive too.
        def nearest(spec, out):
            if spec["base_id"] == "A3":
                out["responsive_obligation_ids"] = ["s2-o1"]

        result = run(nearest)
        self.assertEqual(gates(result)["G4"], "FAIL")
        self.assertEqual(gates(result)["G3"], "PASS")
        self.assertIs(result["qualified"], False)

    def test_dmPFC_to_scales_is_the_original_failure_and_fails_G4(self):
        def scales(spec, out):
            if spec["base_id"] == "A3":
                out["responsive_obligation_ids"] = ["s3-o1"]

        self.assertEqual(gates(run(scales))["G4"], "FAIL")

    def test_years_of_school_mapped_to_cultures_measurement_fails_G4(self):
        def measure(spec, out):
            if spec["base_id"] == "A5":
                out["responsive_obligation_ids"] = ["s5-o1"]

        self.assertEqual(gates(run(measure))["G4"], "FAIL")

    def test_missing_the_cross_cultural_obligation_fails_G3(self):
        def miss(spec, out):
            if spec["base_id"] == "A2":
                out["responsive_obligation_ids"] = []

        self.assertEqual(gates(run(miss))["G3"], "FAIL")

    def test_positive_with_a_forbidden_extra_fails_G3(self):
        def extra(spec, out):
            if spec["case_id"] == "A1.original":
                out["responsive_obligation_ids"] = ["s1-o1", "s3-o1"]

        self.assertEqual(gates(run(extra))["G3"], "FAIL")

    def test_positive_with_an_allowed_diagnostic_extra_still_passes(self):
        def extra(spec, out):
            if spec["base_id"] == "A1":
                out["responsive_obligation_ids"] = ["s1-o1", "s2-o1"]

        result = run(extra)
        self.assertEqual(gates(result)["G3"], "PASS")
        self.assertEqual(result["cases"]["A1.original"]["diagnostic_selected"], ["s2-o1"])

    def test_the_EBQ_positive_must_find_scales_and_not_unrelated_items(self):
        def wrong(spec, out):
            if spec["base_id"] == "A7":
                out["responsive_obligation_ids"] = ["s3-o1", "s1-o1"]

        self.assertEqual(gates(run(wrong))["G3"], "FAIL")

    def test_order_dependent_selection_fails_G5(self):
        def flaky(spec, out):
            if spec["case_id"] == "A1.reversed":
                out["responsive_obligation_ids"] = ["s2-o1"]  # drops the required s1 only when reordered

        result = run(flaky)
        self.assertEqual(gates(result)["G5"], "FAIL")
        self.assertEqual(gates(result)["G3"], "FAIL")

    def test_stable_but_diagnostic_choice_across_orderings_passes_G5(self):
        def stable(spec, out):
            if spec["base_id"] == "A2":
                out["responsive_obligation_ids"] = ["s4-o1", "s1-o1"]

        self.assertEqual(gates(run(stable))["G5"], "PASS")

    def test_A6_diagnostic_cannot_sink_or_rescue_a_model(self):
        def wild(spec, out):
            if spec["base_id"] == "A6":
                out["responsive_obligation_ids"] = ["s6-o1", "s3-o1"]

        result = run(wild)
        self.assertIs(result["qualified"], True)
        self.assertEqual(result["cases"]["A6.original"]["verdict"], "diagnostic")

    def test_duplicate_ids_are_removed_after_parsing_not_penalized(self):
        def dup(spec, out):
            if spec["base_id"] == "A1":
                out["responsive_obligation_ids"] = ["s1-o1", "s1-o1"]

        result = run(dup)
        self.assertEqual(gates(result)["G3"], "PASS")
        self.assertEqual(result["cases"]["A1.original"]["duplicates"], ["s1-o1"])

    def test_nearest_category_selection_on_clear_negatives_is_reported_even_when_gates_pass(self):
        # a model that passes cleanly reports zero; the counter exists so a pass isn't mistaken for purity
        self.assertEqual(run()["diagnostics"]["negative_cases_with_any_selection"], 0)


class MechanicalAndIdTests(unittest.TestCase):
    def test_invented_obligation_id_fails_G2_and_G1(self):
        def invent(spec, out):
            if spec["case_id"] == "A1.original":
                out["responsive_obligation_ids"] = ["s1-o1", "s7-o1"]

        result = run(invent)
        self.assertEqual(gates(result)["G2"], "FAIL")
        self.assertEqual(gates(result)["G1"], "FAIL")
        self.assertIn("s7-o1", result["gates"]["G2"]["detail"][0])

    def test_invented_action_id_fails_G2(self):
        def invent(spec, out):
            if spec["case_id"] == "C1.original":
                out["plan"]["s6-o1"] = "s6-o1:RESEARCH_ELSEWHERE"

        self.assertEqual(gates(run(invent))["G2"], "FAIL")

    def test_truncated_generation_fails_G1(self):
        result = run(override={"A4.original": {"done_reason": "length"}})
        self.assertEqual(gates(result)["G1"], "FAIL")
        self.assertIn("length", result["gates"]["G1"]["detail"][0])

    def test_timeout_fails_G1(self):
        result = run(override={"B1.original": {"status": "timeout", "content": ""}})
        self.assertEqual(gates(result)["G1"], "FAIL")

    def test_unparseable_output_fails_G1(self):
        result = run(override={"A5.original": {"content": "I think none of them."}})
        self.assertEqual(gates(result)["G1"], "FAIL")

    def test_a_missing_call_fails_G1(self):
        result = run(drop={"C1.reversed"})
        self.assertEqual(gates(result)["G1"], "FAIL")
        self.assertIs(result["qualified"], False)

    def test_think_prefix_is_tolerated_but_recorded(self):
        content = "<think>hmm</think>" + json.dumps(perfect_output(cases.build_case_specs()[0]))
        result = run(override={"A1.original": {"content": content}})
        self.assertEqual(gates(result)["G1"], "PASS")


class TaskBTests(unittest.TestCase):
    def test_generic_neuroscience_attached_to_any_obligation_fails_G6(self):
        def attach(spec, out):
            if spec["family"] == "B":
                out["coverage"]["s2-o1"]["supporting_proposition_ids"] = ["p4", "p5"]

        self.assertEqual(gates(run(attach))["G6"], "FAIL")

    def test_the_dmPFC_retrieved_for_scales_cannot_close_scales(self):
        def close(spec, out):
            if spec["family"] == "B":
                out["coverage"]["s3-o1"] = {"status": "responsive_support", "supporting_proposition_ids": ["p5"]}

        self.assertEqual(gates(run(close))["G6"], "FAIL")

    def test_mentalizing_attached_to_cultures_fails_G6(self):
        def close(spec, out):
            if spec["family"] == "B":
                out["coverage"]["s5-o1"] = {"status": "responsive_support", "supporting_proposition_ids": ["p6"]}

        self.assertEqual(gates(run(close))["G6"], "FAIL")

    def test_promoting_a_gap_with_no_evidence_fails_G6(self):
        def promote(spec, out):
            if spec["family"] == "B":
                out["coverage"]["s4-o1"] = {"status": "responsive_support", "supporting_proposition_ids": ["p1"]}

        self.assertEqual(gates(run(promote))["G6"], "FAIL")

    def test_missing_the_clear_positive_fails_G6(self):
        def miss(spec, out):
            if spec["family"] == "B":
                out["coverage"]["s1-o1"] = {"status": "unresolved", "supporting_proposition_ids": []}

        self.assertEqual(gates(run(miss))["G6"], "FAIL")

    def test_internally_inconsistent_status_is_a_mechanical_failure(self):
        def inconsistent(spec, out):
            if spec["case_id"] == "B1.original":
                out["coverage"]["s3-o1"] = {"status": "unresolved", "supporting_proposition_ids": ["p2"]}

        self.assertEqual(gates(run(inconsistent))["G1"], "FAIL")

    def test_ambiguous_choices_are_diagnostic_only(self):
        def wander(spec, out):
            if spec["family"] == "B":
                out["coverage"]["s3-o1"] = {"status": "responsive_support", "supporting_proposition_ids": ["p3"]}
                out["coverage"]["s2-o1"] = {"status": "responsive_support", "supporting_proposition_ids": ["p1", "p4"]}

        result = run(wander)
        self.assertEqual(gates(result)["G6"], "PASS")
        self.assertIs(result["qualified"], True)


class TaskCTests(unittest.TestCase):
    def _plan(self, **changes):
        def mutate(spec, out):
            if spec["family"] == "C":
                out["plan"].update(changes)

        return mutate

    def test_marking_scales_covered_with_generic_evidence_fails_G7(self):
        for close in ("s3-o1:MARK_COVERED:p5", "s3-o1:MARK_COVERED:p2", "s3-o1:NO_RECOVERY_NEEDED"):
            self.assertEqual(gates(run(self._plan(**{"s3-o1": close})))["G7"], "FAIL", close)

    def test_repeating_the_exhausted_search_when_broadening_exists_fails_G7(self):
        self.assertEqual(gates(run(self._plan(**{"s4-o1": "s4-o1:DEEPEN"})))["G7"], "FAIL")

    def test_giving_up_when_a_broader_action_is_available_fails_G7(self):
        self.assertEqual(gates(run(self._plan(**{"s4-o1": "s4-o1:PRESERVE_UNRESOLVED"})))["G7"], "FAIL")

    def test_an_exhausted_gap_must_be_preserved_not_searched_again(self):
        for again in ("s5-o1:DEEPEN", "s5-o1:NOMINATE"):
            self.assertEqual(gates(run(self._plan(**{"s5-o1": again})))["G7"], "FAIL", again)

    def test_the_exhausted_scales_gap_cannot_be_searched_again(self):
        # s3 has no required_choice of its own: only the repeat rule stops a re-search here
        for again in ("s3-o1:DEEPEN", "s3-o1:NOMINATE"):
            self.assertEqual(gates(run(self._plan(**{"s3-o1": again})))["G7"], "FAIL", again)

    def test_preserving_the_exhausted_scales_gap_passes(self):
        self.assertEqual(gates(run(self._plan(**{"s3-o1": "s3-o1:PRESERVE_UNRESOLVED"})))["G7"], "PASS")

    def test_closing_a_gap_with_no_evidence_fails_G7(self):
        self.assertEqual(gates(run(self._plan(**{"s6-o1": "s6-o1:NO_RECOVERY_NEEDED"})))["G7"], "FAIL")

    def test_diagnostic_obligations_do_not_affect_G7(self):
        result = run(
            self._plan(**{"s1-o1": "s1-o1:PRESERVE_UNRESOLVED", "s2-o1": "s2-o1:DEEPEN", "s6-o1": "s6-o1:NOMINATE"})
        )
        self.assertEqual(gates(result)["G7"], "PASS")


class CorpusAbsenceTests(unittest.TestCase):
    def test_absence_claim_is_flagged_for_adjudication(self):
        def absent(spec, out):
            if spec["case_id"] == "B1.original":
                out["rationale"] = "There is no cross-cultural evidence in the literature."

        result = run(absent)
        self.assertEqual(gates(result)["G8"], "NEEDS_ADJUDICATION")
        self.assertIsNone(result["qualified"])  # pending, neither qualified nor failed

    def test_honest_unresolved_language_is_not_flagged(self):
        def honest(spec, out):
            out["rationale"] = (
                "None of the supplied propositions supports this item. No verified evidence was surfaced."
            )

        self.assertEqual(gates(run(honest))["G8"], "PASS")

    def test_detector_examples(self):
        hit = scoring.corpus_absence_hits
        self.assertTrue(hit("The library contains no such evidence."))
        self.assertTrue(hit("Evidence for interventions does not exist."))
        self.assertTrue(hit("This is absent from the corpus."))
        self.assertFalse(hit("No verified evidence was surfaced for s4."))
        self.assertFalse(hit("The claim addresses attitudes, so it answers s1."))

    def test_a_failed_gate_outranks_pending_adjudication(self):
        def both(spec, out):
            if spec["base_id"] == "A3":
                out["responsive_obligation_ids"] = ["s2-o1"]
            if spec["case_id"] == "B1.original":
                out["rationale"] = "No evidence exists in the corpus."

        self.assertIs(run(both)["qualified"], False)


if __name__ == "__main__":
    unittest.main()
