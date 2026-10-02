"""The q_aib v8 hierarchy loader: what it accepts, what it refuses, and what it records.

The positive tests read the preserved closure artifacts (read-only). Every negative test mutates a temporary COPY and
requires the loader to refuse it with a named problem. Nothing here calls a model.
"""

import copy
import hashlib
import json
import unittest
from pathlib import Path

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised.hierarchy_test_support import ArtifactCopy, needs_artifacts, rejection
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

IDS = ["c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12"]
APPROVED = {"c4", "c5", "c6", "c9", "c11", "c12"}
BY_CONSTRUCTION = {"c1", "c2", "c3", "c8", "c10"}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ProvenanceGuardTests(unittest.TestCase):
    def test_provenance_tokens_are_found_in_the_two_approved_texts_that_carry_them(self):
        no_reask = "it does not ask again which traits relate to the bias; the scales measure the traits asked about in c8 (RC-5)"
        retained = "c11 retains c10's cross-cultural evidence scope through its approved parent relationship (RC-6, nested under c10)"
        self.assertEqual(sorted(set(hc.provenance_tokens(no_reask))), ["RC-5", "c8"])
        self.assertEqual(sorted(set(hc.provenance_tokens(retained))), ["RC-6", "approved", "c10", "c11"])

    def test_ordinary_scientific_text_carries_no_token(self):
        for text in (
            "it does not presuppose that an association exists, has a direction, or is causal",
            "the request asks what the evidence establishes",
            "evidence that an intervention was attempted is not evidence that it worked",
            "is there any cross-cultural evidence for the anomalous is bad bias?",
            BENCHMARK_QUESTION,
        ):
            self.assertEqual(hc.provenance_tokens(text), [], text)

    def test_identifier_and_label_forms_are_all_caught(self):
        for text in (
            "CD-4",
            "D10",
            "RC-10",
            "M11",
            "S1",
            "W21",
            "C9",
            "researcher_approved",
            "deterministic_scaffold",
            "runnable_by_construction",
            "wording_provenance",
            "a" * 8 + " " + "f" * 64,
        ):
            self.assertTrue(hc.provenance_tokens(text), text)

    def test_networks_are_detected_case_insensitively(self):
        self.assertTrue(hc.mentions_networks("brain areas and Networks"))
        self.assertTrue(hc.mentions_networks("the default mode network"))
        self.assertFalse(hc.mentions_networks("brain areas"))

    def test_the_four_labels_are_fixed_constants(self):
        self.assertEqual(hc.LABELS["representation"], "accounted")
        self.assertEqual(hc.LABELS["child_item_states"], ["judged_responsive", "no_responsive_claim", "not_assessed"])
        self.assertEqual(hc.LABELS["obligation_fulfilment"], "not_assessed")
        self.assertEqual(hc.LABELS["parent_completeness"], "not_certified")


@needs_artifacts
class RealHierarchyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = hc.load_contract(BENCHMARK_QUESTION, pins=None)
        cls.h = cls.contract["hierarchy"]
        cls.child = {c["child_id"]: c for c in cls.h["children"]}

    def test_eleven_executable_children_in_hierarchy_order(self):
        self.assertEqual([c["child_id"] for c in self.h["children"]], IDS)
        self.assertTrue(self.h["readiness"]["all_executable"])
        self.assertEqual(self.h["readiness"]["counts"], {"researcher_approved": 6, "runnable_by_construction": 5})
        self.assertEqual(
            {i for i, c in self.child.items() if c["execution"]["state"] == "researcher_approved"}, APPROVED
        )

    def test_the_contract_carries_no_literal_source_units_to_fall_back_on(self):
        self.assertEqual(self.contract["version"], hc.HIER_VERSION)
        self.assertNotIn("source_units", self.contract)
        self.assertEqual(self.contract["semantic_completeness"], "not_certified")
        self.assertEqual(self.contract["original_question"], BENCHMARK_QUESTION)

    def test_c7_is_folded_into_c8_and_s1_is_background_never_a_child(self):
        self.assertEqual(self.h["folded"], {"c8": ["c7"]})
        self.assertNotIn("c7", self.child)
        self.assertEqual([b["id"] for b in self.h["background"]], ["S1"])
        self.assertNotIn("S1", self.child)

    def test_parent_of_reads_exactly_each_childs_own_parent_field(self):
        """Phase 20a: `parent_of` must be a pure, structural projection of the already-loaded
        contract -- never a second, independently-maintained copy of the topology."""
        parent_of = hc.parent_of(self.contract)
        self.assertEqual(set(parent_of), set(IDS))
        for cid in IDS:
            self.assertEqual(parent_of[cid], self.child[cid]["parent"])
        # At least one real, non-root parent relationship exists in this fixture -- proves the
        # function isn't vacuously returning "R" for everything.
        self.assertTrue(any(parent != "R" for parent in parent_of.values()))

    def test_parent_of_rejects_a_non_hierarchy_contract_exactly_like_assert_executable(self):
        with self.assertRaises(hc.HierarchyRejected):
            hc.parent_of({"version": "not-the-hierarchy-version"})

    def test_approved_wordings_equal_the_approval_hashes_and_keep_their_provenance(self):
        approvals = {
            a["child_id"]: a for a in json.loads(hc.DEFAULT_PATHS["approvals"].read_text(encoding="utf-8"))["approvals"]
        }
        for cid in APPROVED:
            self.assertEqual(self.child[cid]["wording_sha256"], approvals[cid]["wording_sha256"], cid)
            self.assertEqual(self.child[cid]["wording_sha256"], sha(self.child[cid]["wording"]), cid)
        prov = {cid: self.child[cid]["wording_provenance"] for cid in IDS}
        self.assertEqual(prov["c9"], "deterministic_scaffold")  # approval never converts a scaffold into anything else
        self.assertEqual(prov["c11"], "deterministic_scaffold")
        self.assertEqual(prov["c4"], "researcher_supplied")
        self.assertEqual(prov["c5"], "deterministic_preparation")
        self.assertEqual(prov["c12"], "deterministic_preparation")
        self.assertIsNone(prov["c6"])  # the c6 acceptance recorded no provenance kind; none is invented
        self.assertEqual(self.child["c9"]["provenance_labels"], ["DET", "HUMAN"])
        self.assertEqual(self.child["c4"]["approval"]["approval_ref"], "CD-4")

    def test_twenty_four_obligations_are_owned_and_accounted(self):
        obligations = self.h["obligations"]
        self.assertEqual(len(obligations), 24)
        self.assertEqual({o["owner"] for o in obligations} - set(IDS), set())
        self.assertTrue(all(o["representation"] == "accounted" for o in obligations))
        self.assertEqual(
            sorted(sum((c["owned_obligation_ids"] for c in self.h["children"]), [])),
            sorted(o["id"] for o in obligations),
        )
        owners = {o["id"]: o["owner"] for o in obligations}
        self.assertEqual(owners["M11"], "c10")
        self.assertEqual(owners["M12"], "c11")
        self.assertEqual(owners["W21"], "c9")

    def test_only_recorded_node_qualifications_exist_and_c6_has_none(self):
        counts = {cid: len(self.child[cid]["qualifications"]) for cid in IDS}
        self.assertEqual(
            counts,
            {"c1": 0, "c2": 0, "c3": 0, "c4": 3, "c5": 3, "c6": 0, "c8": 0, "c9": 1, "c10": 0, "c11": 3, "c12": 2},
        )

    def test_qualification_eligibility_excludes_exactly_the_two_texts_that_carry_provenance(self):
        excluded = {q["id"] for c in self.h["children"] for q in c["qualifications"] if not q["model_facing"]}
        self.assertEqual(excluded, {"c9#constraint:no-reask-traits", "c11#retained-scope:cross-cultural-evidence"})
        for c in self.h["children"]:
            for q in c["qualifications"]:
                if q["model_facing"]:
                    self.assertEqual(hc.provenance_tokens(q["text"]), [], q["id"])
                else:
                    self.assertTrue(q["excluded_reason"])

    def test_scope_is_carried_only_where_a_retained_scope_qualification_is_recorded(self):
        carriers = {cid: c["scope_carrier"] for cid, c in self.child.items() if c["scope_carrier"]}
        self.assertEqual(list(carriers), ["c11"])
        self.assertEqual(carriers["c11"]["from"], "c10")
        self.assertEqual(carriers["c11"]["via"], "RC-6")
        self.assertEqual(carriers["c11"]["wording"], self.child["c10"]["wording"])
        self.assertIn("cross-cultural", carriers["c11"]["wording"])
        self.assertIsNone(self.child["c9"]["scope_carrier"])  # c8's question is never injected into c9

    def test_d4_meanings_are_classified_and_none_is_operationalized_beyond_the_constraint(self):
        for cid, rc in (("c5", "RC-9"), ("c6", "RC-8")):
            reqs = {r["id"]: r for r in self.child[cid]["requirements"]}
            constraint = reqs[f"{rc}#constraint:no-presupposition"]
            self.assertEqual(constraint["class"], "active_constraint")
            self.assertTrue(constraint["model_facing"])
            self.assertEqual(
                constraint["text"], "it does not presuppose that an association exists, has a direction, or is causal"
            )
            networks = reqs[f"{rc}#scope:areas-and-networks"]
            self.assertEqual(networks["class"], "superseded_by_D10")
            self.assertFalse(networks["model_facing"])
            self.assertEqual(networks["state"], "optional_by_amendment")
            self.assertIn("OPTIONAL", networks["amendment"]["note"])
            review = [r for r in reqs.values() if r["class"] == "human_review_meaning"]
            self.assertEqual(
                sorted(r["id"].split("#")[1] for r in review),
                sorted(
                    [
                        "scope:documented-nature-direction",
                        "expression:where-supported",
                        "scope:" + ("measures-of-behavior" if cid == "c5" else "measures-implicit-explicit"),
                    ]
                ),
            )
            for r in review:
                self.assertFalse(
                    r["model_facing"], r["id"]
                )  # D-1 = A: recorded human-review meanings, not operationalized
                self.assertTrue(r["text"])
        for cid in ("c1", "c2", "c3", "c4", "c8", "c9", "c10", "c11", "c12"):
            self.assertEqual([r for r in self.child[cid]["requirements"] if r["class"] == "active_constraint"], [], cid)

    def test_the_exact_no_presupposition_text_is_read_from_the_pinned_record_not_typed_here(self):
        decisions = json.loads(hc.DEFAULT_PATHS["decisions"].read_text(encoding="utf-8"))
        rows = {r["id"]: r for a in decisions["annotations"] for r in a.get("requirements", [])}
        for cid, rc in (("c5", "RC-9"), ("c6", "RC-8")):
            req = next(r for r in self.child[cid]["requirements"] if r["id"] == f"{rc}#constraint:no-presupposition")
            self.assertEqual(req["text"], rows[req["id"]]["text"])

    def test_no_network_text_is_present_in_any_model_facing_component_of_any_child(self):
        for c in self.h["children"]:
            for text in hc.model_facing_components(c):
                self.assertFalse(hc.mentions_networks(text), (c["child_id"], text))
                self.assertEqual(hc.provenance_tokens(text), [], (c["child_id"], text))


@needs_artifacts
class LoaderRefusalTests(unittest.TestCase):
    def setUp(self):
        self.copy = ArtifactCopy()
        self.addCleanup(self.copy.close)

    def test_a_child_that_requires_approval_is_refused(self):
        self.copy.edit_node(
            "c4", lambda n: n["execution"].update(state="requires_researcher_approval", executable=False)
        )
        rejection(self, self.copy.load, "c4", "not executable")

    def test_a_non_executable_state_is_refused_even_when_the_executable_flag_still_says_true(self):
        for state in ("requires_researcher_approval", "not_executable"):
            with self.subTest(state=state):
                copy_ = ArtifactCopy()
                try:
                    copy_.edit_node(
                        "c1", lambda n, state=state: n["execution"].update(state=state)
                    )  # the boolean flag is left True
                    rejection(self, copy_.load, "c1", "not executable")
                finally:
                    copy_.close()

    def test_a_hard_status_is_not_overridden_by_an_approval(self):
        self.copy.edit_node(
            "c9", lambda n: n.update(status="semantic_conflict")
        )  # the approval record for c9 still exists
        rejection(self, self.copy.load, "c9", "semantic_conflict")

    def test_a_candidate_label_without_execution_authority_is_refused(self):
        self.copy.edit_node("c1", lambda n: n["execution"].update(executable=False))
        rejection(self, self.copy.load, "c1", "not executable")

        self.copy.close()
        self.copy = ArtifactCopy()
        self.addCleanup(self.copy.close)
        self.copy.edit_node("c1", lambda n: n.pop("execution"))
        rejection(self, self.copy.load, "c1")

    def test_one_character_change_to_an_approved_string_is_refused(self):
        for mutate in (lambda w: w + " ", lambda w: w.replace("which", "Which", 1), lambda w: w[:-1]):
            with self.subTest(mutation=mutate("which scales?")):
                copy_ = ArtifactCopy()
                try:
                    copy_.edit_node("c9", lambda n, mutate=mutate: n.update(wording=mutate(n["wording"])))
                    rejection(self, copy_.load, "c9")
                finally:
                    copy_.close()

    def test_a_changed_approval_hash_is_refused(self):
        def bad_hash(data):
            next(a for a in data["approvals"] if a["child_id"] == "c9")["wording_sha256"] = "0" * 64

        self.copy.edit("approvals", bad_hash)
        rejection(self, self.copy.load, "approval")

        def drop_wording_and_change_hash(data):
            row = next(a for a in data["approvals"] if a["child_id"] == "c9")
            row.pop("wording")
            row["wording_sha256"] = "0" * 64

        self.copy.close()
        self.copy = ArtifactCopy()
        self.addCleanup(self.copy.close)
        self.copy.edit("approvals", drop_wording_and_change_hash)
        rejection(self, self.copy.load, "c9")

    def test_a_duplicate_approval_is_refused(self):
        self.copy.edit(
            "approvals",
            lambda d: d["approvals"].append(copy.deepcopy(next(a for a in d["approvals"] if a["child_id"] == "c9"))),
        )
        rejection(self, self.copy.load, "c9", "more than one approval")

    def test_c11_without_its_parent_link_is_refused(self):
        self.copy.edit_node("c11", lambda n: n.update(parent="R", depth=1, nesting={"kind": "top_level"}))
        rejection(self, self.copy.load, "retained-scope", "c11")

    def test_c11_is_refused_when_the_parent_wording_lost_the_scope_words(self):
        old = "is there any evidence for the anomalous is bad bias?"
        self.copy.edit_node("c10", lambda n: (n.update(wording=old), n["execution"].update(wording_sha256=sha(old))))
        rejection(self, self.copy.load, "retained-scope", "cross")

    def test_c9_without_its_parent_link_is_refused(self):
        self.copy.edit_node("c9", lambda n: n.update(parent="R", depth=1, nesting={"kind": "top_level"}))
        rejection(self, self.copy.load, "c9 pairing")

    def test_c9_with_a_missing_pair_member_is_refused(self):
        self.copy.edit(
            "assembled",
            lambda d: d["contract_reconciliation"]["c9_pairing"]["members_present"].update({"which scales": False}),
        )
        rejection(self, self.copy.load, "c9 pairing", "which scales")

    def test_c9_that_asks_the_traits_again_is_refused(self):
        self.copy.edit("assembled", lambda d: d["contract_reconciliation"]["c9_pairing"].update(asks_traits_again=True))
        rejection(self, self.copy.load, "c9 pairing", "again")

    def test_networks_that_are_required_again_are_refused(self):
        def revive(n):
            for r in n["requirement_results"]:
                if r["id"] == "RC-9#scope:areas-and-networks":
                    r["state"] = "approved_words_missing"
                    r.pop("amended_by", None)

        self.copy.edit_node("c5", revive)
        rejection(self, self.copy.load, "networks")

    def test_a_qualification_that_mentions_networks_is_refused(self):
        self.copy.edit_node(
            "c4", lambda n: n["qualifications"][0].update(text=n["qualifications"][0]["text"] + " and networks")
        )
        rejection(self, self.copy.load, "network")

    def test_a_missing_d10_amendment_in_the_closure_record_is_refused(self):
        self.copy.edit("closure", lambda d: d.update(annotations=[]))
        rejection(self, self.copy.load, "amendment")

    def test_an_unclassifiable_requirement_is_refused_not_guessed(self):
        def rekind(data):
            for a in data["annotations"]:
                for r in a.get("requirements", []):
                    if r["id"] == "RC-9#scope:measures-of-behavior":
                        r["kind"] = "novel_kind"

        self.copy.edit("decisions", rekind)
        rejection(self, self.copy.load, "unclassified", "measures-of-behavior")

    def test_a_folded_id_or_a_background_id_may_not_appear_as_a_child(self):
        for cid in ("c7", "S1"):
            with self.subTest(child=cid):
                copy_ = ArtifactCopy()
                try:
                    copy_.edit(
                        "assembled",
                        lambda d, cid=cid: d["nodes"].append({**copy.deepcopy(d["nodes"][0]), "child_id": cid}),
                    )
                    rejection(self, copy_.load, cid)
                finally:
                    copy_.close()

    def test_a_missing_or_unreadable_artifact_is_refused_by_name(self):
        self.copy.paths["decisions"].unlink()
        rejection(self, self.copy.load, "decisions")


@needs_artifacts
class PinTests(unittest.TestCase):
    def setUp(self):
        self.copy = ArtifactCopy()
        self.addCleanup(self.copy.close)
        self.pins = self.copy.dir / "pins.json"
        self.sheet = self.copy.dir / "sheet.md"
        self.review = self.copy.dir / "review.json"
        hc.freeze(paths=self.copy.paths, pins_path=self.pins, sheet_path=self.sheet)

    def load(self, **kwargs):
        return hc.load_contract(BENCHMARK_QUESTION, **self.copy.paths, pins=self.pins, review=self.review, **kwargs)

    def test_freeze_writes_an_unreviewed_candidate_and_never_a_review(self):
        self.assertEqual(
            sorted(p.name for p in self.copy.dir.iterdir() if p.name in {"pins.json", "sheet.md", "review.json"}),
            ["pins.json", "sheet.md"],
        )
        pins = json.loads(self.pins.read_text(encoding="utf-8"))
        self.assertTrue(pins["status"].startswith("UNREVIEWED"))
        self.assertNotIn("reviewed_by", pins)
        self.assertEqual(pins["d1"]["option"], "A")

    def test_the_freshly_frozen_pins_verify_the_artifacts_they_came_from(self):
        contract = self.load()
        self.assertEqual(contract["hierarchy"]["verification"], {"pins": "verified", "review": "unreviewed"})

    def test_the_pins_record_every_input_hash_and_the_child_table(self):
        pins = json.loads(self.pins.read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(pins["inputs"]), ["approvals_sha256", "assembled_sha256", "closure_sha256", "decisions_sha256"]
        )
        self.assertEqual(
            sorted(pins["code_inputs"]), ["decompose/execution.py", "decompose/tree.py", "hierarchy_contract.py"]
        )
        self.assertEqual([c["child_id"] for c in pins["children"]], IDS)
        self.assertEqual(pins["question_sha256"], sha(BENCHMARK_QUESTION))
        self.assertEqual(pins["obligations"]["count"], 24)

    def test_a_consistent_tamper_passes_the_structural_checks_and_is_caught_only_by_the_pins(self):
        new = "how does the anomalous is bad bias manifest in the brain"
        self.copy.edit_node("c1", lambda n: (n.update(wording=new), n["execution"].update(wording_sha256=sha(new))))
        self.assertIsNotNone(self.copy.load())  # structurally coherent: no problem without the pins
        rejection(self, self.load, "pin", "c1")

    def test_a_reformatted_but_equivalent_input_file_is_still_a_pin_drift(self):
        data = self.copy.read("decisions")
        self.copy.paths["decisions"].write_text(json.dumps(data, indent=3, ensure_ascii=False), encoding="utf-8")
        rejection(self, self.load, "decisions_sha256")

    def test_a_drifted_code_input_is_refused(self):
        pins = json.loads(self.pins.read_text(encoding="utf-8"))
        pins["code_inputs"]["decompose/execution.py"] = "0" * 64
        self.pins.write_text(json.dumps(pins), encoding="utf-8")
        rejection(self, self.load, "code input", "execution.py")

    def test_a_different_question_is_refused(self):
        rejection(
            self,
            lambda: hc.load_contract(BENCHMARK_QUESTION + " ", **self.copy.paths, pins=self.pins, review=self.review),
            "question",
        )

    def test_pins_that_make_a_human_review_meaning_model_facing_are_refused_under_d1_a(self):
        pins = json.loads(self.pins.read_text(encoding="utf-8"))
        target = next(k for k, v in pins["requirements"].items() if v["class"] == "human_review_meaning")
        pins["requirements"][target]["model_facing"] = True
        self.pins.write_text(json.dumps(pins), encoding="utf-8")
        rejection(self, self.load, "model-facing", target)

    def test_unreviewed_pins_are_allowed_structurally_and_refused_for_a_live_run(self):
        self.assertEqual(self.load()["hierarchy"]["verification"]["review"], "unreviewed")
        rejection(self, lambda: self.load(require_review=True), "review")

    def test_a_review_must_name_the_current_pins_hash(self):
        self.review.write_text(
            json.dumps(
                {"reviewed_by": "a reviewer", "reviewed_at": "2026-09-26", "pins_sha256": "0" * 64, "inputs_sha256": {}}
            ),
            encoding="utf-8",
        )
        rejection(self, lambda: self.load(require_review=True), "pins_sha256")

    def test_a_review_recorded_against_the_current_pins_is_accepted(self):
        pins = json.loads(self.pins.read_text(encoding="utf-8"))
        self.review.write_text(
            json.dumps(
                {
                    "reviewed_by": "a reviewer",
                    "reviewed_at": "2026-09-26",
                    "pins_sha256": hc.pins_sha256(self.pins),
                    "inputs_sha256": pins["inputs"],
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            self.load(require_review=True)["hierarchy"]["verification"], {"pins": "verified", "review": "reviewed"}
        )

    def test_a_review_goes_stale_when_the_pins_are_regenerated(self):
        pins = json.loads(self.pins.read_text(encoding="utf-8"))
        self.review.write_text(
            json.dumps(
                {
                    "reviewed_by": "r",
                    "reviewed_at": "d",
                    "pins_sha256": hc.pins_sha256(self.pins),
                    "inputs_sha256": pins["inputs"],
                }
            ),
            encoding="utf-8",
        )
        pins["status"] = "UNREVIEWED_CANDIDATE (regenerated)"
        self.pins.write_text(json.dumps(pins), encoding="utf-8")
        rejection(self, lambda: self.load(require_review=True), "pins_sha256")

    def test_the_review_sheet_shows_inputs_children_model_facing_text_and_the_open_review(self):
        sheet = self.sheet.read_text(encoding="utf-8")
        for needle in (
            "UNREVIEWED",
            "Get-FileHash",
            "assembled_sha256",
            "Requested focus (child question):",
            "human_review_meaning",
            "superseded_by_D10",
            "c9#constraint:no-reask-traits",
            "c11#retained-scope:cross-cultural-evidence",
            '"reviewed_by"',
        ):
            self.assertIn(needle, sheet)
        for cid in IDS:
            self.assertIn(f"| {cid} |", sheet)
        self.assertNotIn('"reviewed_by": "Cliff"', sheet)
        self.assertNotIn("Lucien", sheet)


@needs_artifacts
class RealPinsTests(unittest.TestCase):
    def test_the_generated_pin_candidate_verifies_the_preserved_artifacts(self):
        contract = hc.load_contract(BENCHMARK_QUESTION)
        self.assertEqual(contract["hierarchy"]["verification"]["pins"], "verified")
        pins = json.loads(Path(hc.FROZEN_PATH).read_text(encoding="utf-8"))
        self.assertTrue(pins["status"].startswith("UNREVIEWED"))
        self.assertNotIn("reviewed_by", pins)


if __name__ == "__main__":
    unittest.main()
