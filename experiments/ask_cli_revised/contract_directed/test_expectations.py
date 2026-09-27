import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import expectations as ex
from experiments.ask_cli_revised.contract_directed import freeze

DB = freeze.SLICE_ROOT / "library.sqlite"
METHODS_SENTENCE = (
    "Participants completed a Just World Beliefs Scale, which measures beliefs about interpersonal fairness toward oneself "
    "and others; the Interpersonal Reactivity Index, which measures cognitive (perspective taking) and affective "
    "(empathic concern) empathy; and a subscale from the Three-Domain Disgust scale that measures sensitivity to "
    "pathogen-related disgust."
)


class PreRegistrationTests(unittest.TestCase):
    def test_the_frozen_record_is_versioned_hashed_and_carries_the_edit_log(self):
        record = ex.expectations_record()
        self.assertEqual(record["version"], ex.EXPECTATIONS_VERSION)
        self.assertEqual(len(record["sha256"]), 64)
        self.assertEqual(record["sha256"], ex.expectations_record()["sha256"])  # deterministic
        self.assertIn("BEFORE any live inference", record["edit_log"][0]["recorded"])
        self.assertIn("never changed in response to pilot results", record["edit_log"][0]["rule"])

    def test_the_three_authorized_edits_are_in_the_records(self):
        items = ex.EXPECTATIONS
        self.assertIn("SOURCE ITSELF establishes the link", items["N4"])
        self.assertIn("exact span, its locator, its attribution and the linking rationale", items["N4"])
        self.assertIn("independently mentioning its component concepts", items["N4"])
        self.assertIn("cannot establish effectiveness", items["N2"])
        self.assertIn("NOT reported as a live intervention-answer result", items["N2"])
        self.assertIn("instrument-to-construct pairings", items["E3"])
        self.assertIn("names without pairings", items["E3"])
        for key in ("I", "E1", "E2", "E4", "N1", "N3"):
            self.assertIn(key, items)  # every other pre-registered check is retained

    def test_any_change_to_an_expectation_changes_the_hash(self):
        before = ex.expectations_record()["sha256"]
        original = ex.EXPECTATIONS["E2"]
        try:
            ex.EXPECTATIONS["E2"] = original + " (changed)"
            self.assertNotEqual(before, ex.expectations_record()["sha256"])
        finally:
            ex.EXPECTATIONS["E2"] = original


class PairingTests(unittest.TestCase):
    def test_the_methods_sentence_pairs_every_scale_with_its_own_construct(self):
        self.assertEqual(set(ex.pairings_in_text(METHODS_SENTENCE).values()), {ex.PAIRED})

    def test_a_scale_paired_with_another_scales_construct_is_mispaired(self):
        swapped = (
            "Participants completed a Just World Beliefs Scale, which measures empathic concern and perspective taking; "
            "the Interpersonal Reactivity Index, which measures pathogen-related disgust sensitivity."
        )
        result = ex.pairings_in_text(swapped)
        self.assertEqual(result["Just World Beliefs Scale"], ex.MISPAIRED)
        self.assertEqual(result["Interpersonal Reactivity Index"], ex.MISPAIRED)

    def test_names_without_pairings_are_only_unpaired(self):
        names_only = "Participants completed the Just World Beliefs Scale, the Interpersonal Reactivity Index and the Three-Domain Disgust scale."
        result = ex.pairings_in_text(names_only)
        self.assertEqual(result["Just World Beliefs Scale"], ex.UNPAIRED)
        self.assertEqual(result["Three-Domain Disgust scale"], ex.UNPAIRED)  # the LAST name has no following construct

    def test_answer_pairings_take_the_best_state_per_scale_and_report_a_mispairing(self):
        good = "The Just World Beliefs Scale measures beliefs about fairness [P1]. The Interpersonal Reactivity Index measures empathy [P1]. The Three-Domain Disgust scale measures pathogen disgust sensitivity [P1]."
        self.assertEqual(set(ex.answer_pairings(good).values()), {ex.PAIRED})
        bad = good + " The Interpersonal Reactivity Index also measures pathogen disgust."
        self.assertEqual(ex.answer_pairings(bad)["Interpersonal Reactivity Index"], ex.MISPAIRED)
        names = "The scales are the Just World Beliefs Scale, the Interpersonal Reactivity Index and the Three-Domain Disgust scale."
        self.assertNotIn(ex.PAIRED, set(ex.answer_pairings(names).values()))

    @unittest.skipUnless(DB.is_file(), "disposable library copy not present")
    def test_the_real_chunk_35019_pairs_all_three(self):
        con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro&immutable=1", uri=True)
        try:
            text = con.execute("select text from chunks where id=35019").fetchone()[0]
        finally:
            con.close()
        self.assertEqual(set(ex.pairings_in_text(text).values()), {ex.PAIRED}, ex.pairings_in_text(text))


class OfflineControlTests(unittest.TestCase):
    def test_every_offline_negative_control_passes(self):
        results = ex.offline_controls()
        self.assertEqual(
            {r["id"] for r in results}
            & {
                "N2.offline_control_speculation_does_not_establish_effectiveness",
                "N2.offline_control_an_own_reported_outcome_does_establish_it",
                "N4.offline_control_co_occurrence_is_not_a_relationship",
                "N4.offline_control_a_linked_definition_cannot_supply_the_finding_but_can_supply_the_measure",
            },
            {r["id"] for r in results},
        )
        for r in results:
            self.assertEqual(r["status"], ex.PASS, r)
            self.assertTrue(r["evidence"]["offline_only"])
            self.assertFalse(r["evidence"]["live_result"])


def part(sid, role, text, *, unit_index=1, linked_from=None, note=None, verbatim=True):
    return {
        "span_id": sid, "role": role, "unit_index": unit_index, "text": text, "open_left": False, "open_right": False,
        "linked_from": linked_from, "note": note,
        "pieces": [{"chunk_id": 1, "start": 0, "end": len(text), "text": text, "verbatim_ok": verbatim}],
    }  # fmt: skip


def bundle(parts, links=(), attribution=None):
    return {
        "state": "built", "packet_id": "k1", "paper_id": 67, "attachment": {"id": 67, "is_primary": True},
        "parts": parts, "links": list(links), "evidence_form": "verbatim",
        "part_attribution": attribution or {p["span_id"]: "own_established" for p in parts if p["role"] != "linked_definition"},
        "found_under": ["c9"],
    }  # fmt: skip


def elig(unit_slots, status="directly_establishes"):
    return {
        "state": "usable",
        "packet_id": "k1",
        "child_id": "c9",
        "per_unit": {"M10": {"status": status, "slot_spans": unit_slots, "missing": [], "reasons": []}},
    }


LINK = {"link_id": "L1", "verified": True, "basis": {"type": "definition_acronym", "designator": "DG"}}


class BundleAuditTests(unittest.TestCase):
    def audit(self, packet, record):
        return ex.n4_bundle_audit([packet], [record])

    def good_packet(self):
        return bundle(
            [
                part("p1", "establishing", "less generosity in the DG"),
                part(
                    "p2",
                    "linked_definition",
                    "In the Dictator Game (DG), players split $5.",
                    linked_from="L1",
                    note='linked by definition acronym "DG"',
                ),
            ],
            links=[LINK],
        )

    def test_a_source_linked_bundle_with_its_rationale_preserved_passes(self):
        violations, stats = self.audit(
            self.good_packet(), elig({"instrument_named": ["p2"], "paired_with_construct": ["p1"]})
        )
        self.assertEqual(violations, [])
        self.assertEqual(stats, {"closures_checked": 1, "linked_spans_used": 1})

    def test_a_linked_span_used_for_a_finding_bearing_slot_is_a_violation(self):
        violations, _ = self.audit(self.good_packet(), elig({"relation_stated": ["p2"]}))
        self.assertIn("linked_span_in_a_finding_bearing_slot", {v["violation"] for v in violations})

    def test_a_linked_span_without_a_verified_source_link_is_a_violation(self):
        packet = self.good_packet()
        packet["links"] = []
        violations, _ = self.audit(packet, elig({"instrument_named": ["p2"]}))
        self.assertIn("linked_span_without_a_verified_source_link", {v["violation"] for v in violations})

    def test_a_link_whose_rationale_was_not_preserved_is_a_violation(self):
        packet = self.good_packet()
        packet["parts"][1]["note"] = None
        violations, _ = self.audit(packet, elig({"instrument_named": ["p2"]}))
        self.assertIn("link_rationale_not_preserved", {v["violation"] for v in violations})

    def test_a_span_from_another_packet_a_missing_locator_or_a_non_own_core_span_is_a_violation(self):
        packet = self.good_packet()
        self.assertIn(
            "span_outside_its_packet",
            {v["violation"] for v in self.audit(packet, elig({"instrument_named": ["p9"]}))[0]},
        )
        broken = bundle([part("p1", "establishing", "x", verbatim=False)])
        self.assertIn(
            "locator_or_verbatim_check_missing",
            {v["violation"] for v in self.audit(broken, elig({"instrument_named": ["p1"]}))[0]},
        )
        speculative = bundle([part("p1", "establishing", "x")], attribution={"p1": "speculation"})
        self.assertIn(
            "core_span_not_own_established",
            {v["violation"] for v in self.audit(speculative, elig({"instrument_named": ["p1"]}))[0]},
        )

    def test_only_closures_are_audited(self):
        violations, stats = self.audit(
            self.good_packet(), elig({"relation_stated": ["p2"]}, status="partially_establishes")
        )
        self.assertEqual((violations, stats["closures_checked"]), ([], 0))


def write_run(tmp: Path, packets, eligibility, answer=None):
    (tmp / "07_packets.jsonl").write_text("\n".join(json.dumps(p) for p in packets), encoding="utf-8")
    (tmp / "08_eligibility.jsonl").write_text("\n".join(json.dumps(e) for e in eligibility), encoding="utf-8")
    (tmp / "14_ledger.json").write_text("{}", encoding="utf-8")
    if answer is not None:
        (tmp / "12_answers").mkdir()
        (tmp / "12_answers" / "c9_raw_answer.txt").write_text(answer, encoding="utf-8")
        diag = {
            "prompt_leakage": {
                "contains_parent_question": False,
                "contains_other_child_wording": [],
                "contains_machine_claim_marker": False,
            },
            "acronym_expansions_not_in_any_passage": [],
            "directional_terms_not_in_cited_passages": [],
        }
        (tmp / "12_answers" / "c9_record.json").write_text(
            json.dumps({"child_id": "c9", "diagnostics": diag}), encoding="utf-8"
        )


class E3EvaluationTests(unittest.TestCase):
    def evaluate(self, sentence, answer):
        with tempfile.TemporaryDirectory() as tmp:
            packet = bundle([part("p1", "establishing", sentence)])
            packet["parts"][0]["pieces"][0]["chunk_id"] = 35019
            write_run(
                Path(tmp), [packet], [elig({"instrument_named": ["p1"], "paired_with_construct": ["p1"]})], answer
            )
            return {r["id"]: r for r in ex.evaluate(tmp, children_in_run=["c9"])}

    GOOD_ANSWER = "The Just World Beliefs Scale measures beliefs about interpersonal fairness [P1]. The Interpersonal Reactivity Index measures cognitive and affective empathy [P1]. The Three-Domain Disgust scale measures pathogen-related disgust sensitivity [P1]."

    def test_correct_pairings_in_evidence_and_answer_pass(self):
        results = self.evaluate(METHODS_SENTENCE, self.GOOD_ANSWER)
        self.assertEqual(results["E3.c9_evidence_carries_instrument_construct_pairings"]["status"], ex.PASS)
        self.assertEqual(results["E3.c9_answer_pairs_each_scale_with_its_construct"]["status"], ex.PASS)
        self.assertEqual(results["E3.c9_constructs_vs_measures"]["status"], ex.REVIEW)  # always a human item

    def test_scale_names_alone_are_a_review_item_never_a_pass(self):
        names = "The scales are the Just World Beliefs Scale, the Interpersonal Reactivity Index and the Three-Domain Disgust scale [P1]."
        results = self.evaluate(METHODS_SENTENCE, names)
        self.assertEqual(results["E3.c9_answer_pairs_each_scale_with_its_construct"]["status"], ex.REVIEW)

    def test_a_mispaired_answer_fails(self):
        wrong = "The Just World Beliefs Scale measures empathic concern and perspective taking [P1]. The Interpersonal Reactivity Index measures pathogen disgust [P1]."
        results = self.evaluate(METHODS_SENTENCE, wrong)
        self.assertEqual(results["E3.c9_answer_pairs_each_scale_with_its_construct"]["status"], ex.FAIL)

    def test_evidence_with_only_the_names_is_not_a_pass(self):
        results = self.evaluate(
            "Participants completed the Just World Beliefs Scale and the Interpersonal Reactivity Index.",
            self.GOOD_ANSWER,
        )
        self.assertNotEqual(results["E3.c9_evidence_carries_instrument_construct_pairings"]["status"], ex.PASS)

    def test_the_n_results_and_offline_controls_are_present_and_c12_is_not_reported_live(self):
        results = self.evaluate(METHODS_SENTENCE, self.GOOD_ANSWER)
        self.assertEqual(results["N2.live_c12_intervention_answer"]["status"], ex.NOT_EVALUABLE)
        self.assertEqual(results["N2.offline_control_speculation_does_not_establish_effectiveness"]["status"], ex.PASS)
        self.assertIn("N4.source_grounded_bundles_only", results)


if __name__ == "__main__":
    unittest.main()
