"""What the E2E's models are shown for each approved child, and what they are not.

Model-facing text is the exact child wording, the parent's exact wording as scope context where a retained-scope
qualification is recorded (c11 only), and exact approved constraint texts under a neutral heading. It never carries an
approval, a hash, a clarification or decision identifier, a provenance label, or anything about brain networks.
"""

import copy
import json
import unittest

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised.hierarchy_test_support import needs_artifacts, rejection
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION
from experiments.ask_cli_revised.request_contract import obligation_display, request_subquestions

IDS = ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"]
FOCUS = "Requested focus (child question):\n"
CONTEXT = "Original request (context):\n"
SCOPE_HEAD = "Scope carried into this question (context, not a separate question to answer here):\n"
C10 = "is there any cross-cultural evidence for the anomalous is bad bias?"
NO_PRESUPPOSITION = "it does not presuppose that an association exists, has a direction, or is causal"


def constraints(*texts):
    return (
        " [Constraints for interpreting this question: " + " ".join(f"({i}) {t}" for i, t in enumerate(texts, 1)) + "]"
    )


@needs_artifacts
class SubquestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.child = {c["child_id"]: c for c in cls.contract["hierarchy"]["children"]}
        cls.subs = request_subquestions(cls.contract)  # dispatched on the contract version
        cls.by_id = {s["subquestion_id"]: s for s in cls.subs}
        cls.display = {cid: obligation_display(s["obligations"][0]) for cid, s in cls.by_id.items()}

    def test_the_request_boundary_dispatches_and_yields_one_subquestion_per_child(self):
        self.assertEqual(self.subs, hc.hierarchy_subquestions(self.contract))
        self.assertEqual([s["subquestion_id"] for s in self.subs], IDS)
        for s in self.subs:
            self.assertEqual(len(s["obligations"]), 1)
            o = s["obligations"][0]
            self.assertEqual(
                {s["subquestion_id"], o["field_id"], o["source_unit_id"], s["source_unit_id"]}, {s["subquestion_id"]}
            )
            self.assertEqual(o["coverage_basis"], "approved_child")
            self.assertEqual(s["question_hash"], self.contract["question_hash"])

    def test_the_exact_wording_is_the_note_and_the_focus_and_the_original_request_stays_as_context(self):
        for cid in IDS:
            wording = self.child[cid]["wording"]
            s = self.by_id[cid]
            self.assertEqual(s["obligations"][0]["note"], wording)
            self.assertTrue(s["text"].startswith(FOCUS + wording + "\n\n"), cid)
            self.assertTrue(s["text"].endswith(CONTEXT + BENCHMARK_QUESTION), cid)

    def test_c11_receives_c10s_scope_as_retrieval_context_and_in_the_assessment_item(self):
        s = self.by_id["c11"]
        self.assertIn(SCOPE_HEAD + C10 + "\n\n", s["text"])
        self.assertEqual(
            self.display["c11"],
            self.child["c11"]["wording"]
            + f' [Scope carried into this question, not a separate question to answer here: "{C10}"]'
            + constraints(
                "each reported culture is paired with how the bias was measured there when the evidence supports that pairing; no unsupported culture-measure pairing is invented",
                "no requirement for direct between-culture comparisons is introduced",
            ),
        )

    def test_c11_keeps_its_approved_wording_which_no_longer_says_cross_cultural(self):
        self.assertNotIn("cross-cultural", self.child["c11"]["wording"])
        self.assertEqual(self.by_id["c11"]["obligations"][0]["note"], self.child["c11"]["wording"])

    def test_no_other_child_receives_a_scope_block(self):
        for cid in IDS:
            if cid != "c11":
                self.assertNotIn("Scope carried", self.by_id[cid]["text"], cid)
                self.assertNotIn("Scope carried", self.display[cid], cid)

    def test_c9_is_never_given_c8s_question_as_an_additional_ask(self):
        c8 = self.child["c8"]["wording"]
        self.assertNotIn(c8, self.by_id["c9"]["text"])
        self.assertNotIn(c8, self.display["c9"])
        self.assertEqual(
            self.display["c9"], self.child["c9"]["wording"]
        )  # its recorded constraint carries provenance tokens: machine-side only

    def test_exact_approved_constraints_appear_under_the_neutral_heading(self):
        self.assertEqual(
            self.display["c4"],
            self.child["c4"]["wording"]
            + constraints(
                "the request asks what the evidence establishes",
                "it does not presuppose that any particular area is implicated, that an association exists, or that a finding is causal",
                "a downstream answer that finds no supported area must be able to say so",
            ),
        )
        self.assertEqual(
            self.display["c12"],
            self.child["c12"]["wording"]
            + constraints(
                "the question is about EFFECTIVE interventions",
                "evidence that an intervention was attempted is not evidence that it worked",
            ),
        )

    def test_c6_receives_only_the_recorded_no_presupposition_constraint_and_c5_receives_it_after_its_own_texts(self):
        self.assertEqual(self.display["c6"], self.child["c6"]["wording"] + constraints(NO_PRESUPPOSITION))
        self.assertEqual(
            self.display["c5"],
            self.child["c5"]["wording"]
            + constraints(
                "'whether and how' is kept as one compound operation",
                "the kinds of behaviors are asked",
                "the relationship is asked conditionally (whether it exists and how), never presupposed",
                NO_PRESUPPOSITION,
            ),
        )

    def test_children_with_no_constraint_show_their_exact_wording_and_nothing_else(self):
        for cid in ("c1", "c2", "c3", "c8", "c9", "c10"):
            self.assertEqual(self.display[cid], self.child[cid]["wording"], cid)

    def test_constraints_are_not_part_of_the_retrieval_text(self):
        for cid in IDS:
            self.assertNotIn("Constraints for interpreting", self.by_id[cid]["text"], cid)

    def test_every_model_facing_qualification_is_present_verbatim(self):
        for cid in IDS:
            for q in self.child[cid]["qualifications"]:
                self.assertEqual(q["text"] in self.display[cid], q["model_facing"], q["id"])

    def test_d1_a_no_human_review_meaning_reaches_any_model(self):
        for cid in ("c5", "c6"):
            for r in self.child[cid]["requirements"]:
                if r["class"] in ("human_review_meaning", "superseded_by_D10"):
                    self.assertNotIn(r["text"], self.by_id[cid]["text"], r["id"])
                    self.assertNotIn(r["text"], self.display[cid], r["id"])

    def test_no_provenance_identifier_or_network_reaches_any_model_facing_string(self):
        for cid in IDS:
            text = self.by_id[cid]["text"]
            focus_and_scope = text.split(CONTEXT)[0]
            for surface in (focus_and_scope, self.display[cid]):
                self.assertEqual(hc.provenance_tokens(surface), [], (cid, surface))
                self.assertFalse(hc.mentions_networks(surface), (cid, surface))

    def test_provenance_travels_on_the_obligation_record_and_nowhere_in_model_text(self):
        o = self.by_id["c9"]["obligations"][0]["hierarchy"]
        self.assertEqual(o["parent"], "c8")
        self.assertEqual(o["execution"]["state"], "researcher_approved")
        self.assertEqual(o["wording_provenance"], "deterministic_scaffold")
        self.assertEqual(o["approval"]["approval_ref"], "CD-1")
        self.assertTrue(o["wording_sha256"])
        blob = json.dumps(self.by_id["c9"]["obligations"][0]["hierarchy"])
        self.assertNotIn(blob, self.display["c9"])
        for token in ("CD-1", "RC-5", "deterministic_scaffold", "researcher_approved", o["wording_sha256"]):
            self.assertNotIn(token, self.by_id["c9"]["text"].split(CONTEXT)[0])
            self.assertNotIn(token, self.display["c9"])

    def test_the_per_item_record_omits_the_bulky_history_that_the_contract_already_holds(self):
        for s in self.subs:
            self.assertNotIn("history", s["obligations"][0]["hierarchy"])
        self.assertTrue(self.child["c9"]["history"])  # the recorded prior wordings stay in the contract itself

    def test_no_literal_source_unit_is_ever_a_fallback(self):
        contract = copy.deepcopy(self.contract)
        contract["source_units"] = [{"source_unit_id": "u1", "text": "SENTINEL FRAGMENT", "start": 0, "end": 5}]
        subs = hc.hierarchy_subquestions(contract)
        self.assertEqual(subs, self.subs)
        self.assertNotIn("SENTINEL", json.dumps(subs))
        self.assertEqual(len(subs), 11)

    def test_the_model_facing_hash_is_a_function_of_exactly_the_model_facing_text(self):
        first = hc.model_facing_sha256(self.contract)
        self.assertEqual(first, hc.model_facing_sha256(copy.deepcopy(self.contract)))
        changed = copy.deepcopy(self.contract)
        next(c for c in changed["hierarchy"]["children"] if c["child_id"] == "c1")["wording"] += "?"
        self.assertNotEqual(first, hc.model_facing_sha256(changed))


@needs_artifacts
class AssertExecutableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)

    def mutated(self, fn, *, reseal):
        contract = copy.deepcopy(self.contract)
        fn(contract["hierarchy"], contract)
        if reseal:
            contract["hierarchy"]["integrity_sha256"] = hc.integrity_sha256(contract["hierarchy"])
        return contract

    def child(self, hier, cid):
        return next(c for c in hier["children"] if c["child_id"] == cid)

    def test_a_loaded_contract_is_executable(self):
        hc.assert_executable(self.contract)

    def test_a_contract_that_is_not_hierarchical_is_refused(self):
        rejection(self, lambda: hc.assert_executable({"version": "literal-request-v1"}), "version")
        rejection(self, lambda: hc.assert_executable({"version": hc.HIER_VERSION}), "hierarchy")

    def test_every_in_memory_mutation_is_refused_even_when_the_seal_is_recomputed(self):
        cases = {
            "wording changed": (
                lambda h, c: self.child(h, "c9").update(wording=self.child(h, "c9")["wording"] + " "),
                "c9",
            ),
            "child not executable": (lambda h, c: self.child(h, "c4")["execution"].update(executable=False), "c4"),
            "child dropped": (lambda h, c: h["children"].pop(3), "children"),
            "c11 scope removed": (lambda h, c: self.child(h, "c11").update(scope_carrier=None), "c11"),
            "c11 scope re-pointed at a different wording": (
                lambda h, c: self.child(h, "c11")["scope_carrier"].update(wording="is there any evidence?"),
                "c11",
            ),
            "scope injected into c9": (
                lambda h, c: self.child(h, "c9").update(scope_carrier=self.child(h, "c11")["scope_carrier"]),
                "c9",
            ),
            "token injected into a model-facing constraint": (
                lambda h, c: self.child(h, "c4")["qualifications"][0].update(
                    text="the request asks (RC-9) what the evidence establishes"
                ),
                "c4",
            ),
            "networks injected into a constraint": (
                lambda h, c: self.child(h, "c4")["qualifications"][0].update(
                    text="the request asks about brain networks"
                ),
                "network",
            ),
            "human-review meaning made model-facing": (
                lambda h, c: next(
                    r for r in self.child(h, "c5")["requirements"] if r["class"] == "human_review_meaning"
                ).update(model_facing=True),
                "model-facing",
            ),
            "readiness flag flipped": (lambda h, c: h["readiness"].update(all_executable=False), "readiness"),
        }
        for name, (fn, needle) in cases.items():
            for reseal in (False, True):
                with self.subTest(mutation=name, resealed=reseal):
                    rejection(
                        self, lambda fn=fn, reseal=reseal: hc.assert_executable(self.mutated(fn, reseal=reseal)), needle
                    )

    def test_a_contract_whose_children_do_not_match_the_seal_is_refused(self):
        contract = copy.deepcopy(self.contract)
        contract["hierarchy"]["obligations"][0]["owner"] = "c12"
        rejection(self, lambda: hc.assert_executable(contract), "seal")


if __name__ == "__main__":
    unittest.main()
