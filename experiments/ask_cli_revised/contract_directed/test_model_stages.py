import json
import unittest

from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.contract_directed import answer, freeze, schemas
from experiments.ask_cli_revised.contract_directed import model_stages as ms
from experiments.ask_cli_revised.contract_directed.fakes import FakeClient, FakeLibrary, fake_chunk

DATA_PRESENT = (freeze.AB_ROOT / "runB" / "out" / "01_request_contract.json").is_file()


def env_for(responder, *, max_calls=1000):
    ledger = ms.Ledger(max_calls=max_calls, wall_seconds=3600)
    return ms.Env(client=FakeClient(responder), ledger=ledger), ledger


@unittest.skipUnless(DATA_PRESENT, "frozen private run data not present on this machine")
class ModelStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sub = freeze.load_frozen()
        cls.c5, cls.c9 = cls.sub.child("c5"), cls.sub.child("c9")

    # ---- triage -----------------------------------------------------------------------------------------------------------

    def triage_answer(self, quote="At the level of behavior, people were subjected to less prosociality."):
        return {
            "contribution_type": "original_empirical",
            "relation_to_child": "directly_addresses",
            "abstract_quote": quote,
            "reason": "states it",
        }

    def test_triage_without_an_abstract_makes_no_call_and_stays_reachable(self):
        env, ledger = env_for(lambda *a: self.fail("no call expected"))
        rec = ms.triage_paper(env, self.c5, {"id": 7, "title": "T", "abstract": None})
        self.assertEqual(rec["state"], "abstract_absent")
        self.assertEqual(rec["relation_to_child"], "cannot_tell")
        self.assertEqual(ledger.calls, 0)

    def test_triage_records_whether_the_quote_is_verbatim_and_never_gates(self):
        abstract = "<jats:p>At the level of behavior, people were subjected to less prosociality. Other text.</jats:p>"
        env, _ = env_for(lambda *a: self.triage_answer())
        good = ms.triage_paper(env, self.c5, {"id": 7, "title": "T", "abstract": abstract})
        self.assertTrue(good["quote_verbatim"])
        env2, _ = env_for(lambda *a: self.triage_answer("A sentence the abstract never contains."))
        bad = ms.triage_paper(env2, self.c5, {"id": 7, "title": "T", "abstract": abstract})
        self.assertFalse(bad["quote_verbatim"])
        self.assertEqual(bad["state"], "usable")  # a non-verbatim quote is flagged, the triage record is kept

    def test_the_child_only_appears_in_the_prompt_never_the_parent_or_a_sibling(self):
        env, _ = env_for(lambda *a: self.triage_answer())
        ms.triage_paper(env, self.c5, {"id": 7, "title": "T", "abstract": "Some abstract text here."})
        prompt = env.client.calls[0]["prompt"]
        self.assertIn(self.c5.contract_text, prompt)
        self.assertNotIn(self.sub.contract["original_question"], prompt)
        for other in self.sub.children:
            if other.child_id != "c5":
                self.assertNotIn(other.wording, prompt)

    # ---- mechanical failure is never a semantic verdict -------------------------------------------------------------------

    def test_capped_unparseable_and_failed_calls_are_no_answer_not_none_established(self):
        cases = {
            "capped_at_allowance": {
                "status": "ok",
                "content": "{}",
                "done_reason": "length",
                "timings": {},
                "wall_seconds": 0.1,
                "thinking": "",
            },
            "unparseable": "not json at all",
            "call_failed": {
                "status": "timeout",
                "content": "",
                "done_reason": None,
                "timings": {},
                "wall_seconds": 0.1,
                "thinking": "",
            },
        }
        for outcome, raw in cases.items():
            env, ledger = env_for(lambda *a, raw=raw: raw)
            rec = ms.triage_paper(env, self.c5, {"id": 7, "title": "T", "abstract": "Some abstract text here."})
            self.assertEqual(rec["state"], "no_answer", outcome)
            self.assertEqual(rec["outcome"], outcome)
            self.assertEqual(ledger.stages["triage"]["no_answer"], 1)
            self.assertEqual(ledger.stages["triage"]["usable"], 0)

    def test_a_valid_answer_that_finds_nothing_is_none_established_not_no_answer(self):
        lib = FakeLibrary([fake_chunk(1, "Some unrelated sentence about weather.")])
        nb = {
            "nbhd_id": "n",
            "paper_id": 1,
            "attachment_id": 9,
            "chunk_ids": [1],
            "attachment": {"id": 9, "role": "primary", "checksum": "abc", "is_primary": True},
        }
        env, ledger = env_for(lambda *a: {"propositions": [], "none_established": True})
        rec = ms.localize_neighborhood(env, self.c5, nb, lib)
        self.assertEqual(rec["state"], "none_established")
        self.assertEqual(ledger.stages["localization"]["none_established"], 1)
        self.assertEqual(ledger.stages["localization"].get("no_answer", 0), 0)

    # ---- localization: ids only, packets built by code --------------------------------------------------------------------

    def localization_case(self, proposition):
        lib = FakeLibrary(
            [fake_chunk(1, "We found less prosociality among high-SES participants. Some caveat applies here.")]
        )
        nb = {
            "nbhd_id": "n",
            "paper_id": 1,
            "attachment_id": 9,
            "chunk_ids": [1],
            "attachment": {"id": 9, "role": "primary", "checksum": "abc", "is_primary": True},
        }
        env, ledger = env_for(lambda *a: {"propositions": [proposition], "none_established": False})
        return ms.localize_neighborhood(env, self.c5, nb, lib), env, ledger

    def prop(self, **over):
        base = {
            "establishing": ["s1"],
            "qualifying": ["s2"],
            "referents": [],
            "provenance_class": "this_study_reports",
            "attribution_basis_phrase": "We found",
            "relation_polarity": "association",
            "unresolved": [],
        }
        return base | over

    def test_localization_builds_exact_packets_from_ids_only(self):
        rec, env, _ = self.localization_case(self.prop())
        self.assertEqual(rec["state"], "usable")
        [packet] = rec["packets"]
        self.assertEqual(packet["parts"][0]["text"], "We found less prosociality among high-SES participants.")
        self.assertEqual(packet["parts"][1]["role"], "qualifying")
        self.assertEqual(packet["part_attribution"]["p1"], "own_established")

    def test_an_id_outside_the_schema_is_a_mechanical_no_answer_never_a_semantic_result(self):
        rec, _, ledger = self.localization_case(self.prop(establishing=["s1", "s99"]))
        self.assertEqual(rec["state"], "no_answer")
        self.assertEqual(rec["outcome"], "schema_invalid")
        self.assertEqual(rec["packets"], [])
        self.assertEqual(ledger.stages["localization"]["no_answer"], 1)

    def test_the_defensive_validator_drops_invalid_ids_and_records_them_never_repairing(self):
        raw = {"propositions": [self.prop(establishing=["s1", "s99"], qualifying=["s77"])], "none_established": False}
        checked = schemas.validate_localization(raw, ["s1", "s2"])
        self.assertEqual(checked["state"], "usable")
        self.assertEqual(checked["propositions"][0]["establishing"], ["s1"])
        self.assertEqual(checked["propositions"][0]["qualifying"], [])
        self.assertTrue(any(i.get("unit_ids") == ["s77", "s99"] for i in checked["invalid"]))

    def test_a_proposition_with_no_valid_establishing_unit_is_preserved_not_dropped_silently(self):
        raw = {"propositions": [self.prop(establishing=["s99"])], "none_established": False}
        checked = schemas.validate_localization(raw, ["s1", "s2"])
        self.assertEqual(checked["state"], "unresolved_preserved")
        self.assertTrue(any(i.get("reason") == "no_valid_establishing_unit" for i in checked["invalid"]))

    def test_the_localization_prompt_marks_fragments_and_asks_for_ids_only(self):
        lib = FakeLibrary([fake_chunk(1, "It began here and continues in the"), fake_chunk(2, "next chunk of text.")])
        nb = {
            "nbhd_id": "n",
            "paper_id": 1,
            "attachment_id": 9,
            "chunk_ids": [1, 2],
            "attachment": {"id": 9, "role": "primary", "checksum": "abc", "is_primary": True},
        }
        env, _ = env_for(lambda *a: {"propositions": [], "none_established": True})
        ms.localize_neighborhood(env, self.c5, nb, lib)
        prompt = env.client.calls[0]["prompt"]
        self.assertIn("fragment: ends mid-sentence, the continuation is not verified", prompt)
        self.assertIn("never quotes or your own wording", prompt)
        self.assertIn("A section heading does not tell you who a statement is attributed to", prompt)

    # ---- eligibility: model reports slots, code derives the status --------------------------------------------------------

    def packet(self, attribution="own_established"):
        text = "The amygdala response correlated with less prosociality."
        empty_cues = {"own": [], "own_interpretation": [], "prior": [], "hedge": []}
        clause = {
            "start": 0,
            "end": len(text),
            "text": text,
            "state": attribution,
            "bases": [],
            "cues": empty_cues,
            "has_result_predicate": True,
        }
        return {
            "packet_id": "k1", "paper_id": 67, "found_under": ["c4"],
            "parts": [{"span_id": "p1", "role": "establishing", "unit_index": 3, "open_left": False, "open_right": False, "text": text, "section": "results", "page_start": 7, "join": "none", "note": None}],
            "part_attribution": {"p1": attribution},
            "attribution": {"p1": {"state": attribution, "bases": [], "cues": empty_cues, "flags": [], "model_class": None, "clauses": [clause]}},
        }  # fmt: skip

    def slots(self, **over):
        base = {
            "relatum_a": {"span_ids": ["p1"]}, "relatum_b": {"span_ids": ["p1"]}, "relation_stated": {"span_ids": ["p1"]},
            "polarity": {"span_ids": ["p1"], "value": "association"}, "direction": {"span_ids": ["p1"]},
            "population": {"span_ids": []}, "qualifiers": {"span_ids": []}, "on_topic": {"span_ids": ["p1"]},
        }  # fmt: skip
        return base | over

    def eligibility_answer(self, slots):
        return {
            "units": {
                "M5": {"slots": slots, "reason": "states it"},
                "M6": {
                    "slots": {
                        k: {"span_ids": []}
                        for k in ("kind_named", "tied_to_relation", "population", "qualifiers", "on_topic")
                    },
                    "reason": "no kinds",
                },
            }
        }

    def test_status_is_derived_by_code_and_a_cross_child_row_is_labelled(self):
        env, _ = env_for(lambda *a: self.eligibility_answer(self.slots()))
        rec = ms.judge_packet(env, self.c5, self.packet())
        self.assertEqual(rec["state"], "usable")
        self.assertEqual(rec["route_relation"], "cross_child")  # found under c4, judged for c5
        self.assertEqual(rec["per_unit"]["M5"]["status"], "directly_establishes")
        self.assertEqual(rec["per_unit"]["M6"]["status"], "not_addressed")

    def test_the_model_cannot_close_a_unit_on_an_unattributed_passage(self):
        env, _ = env_for(lambda *a: self.eligibility_answer(self.slots()))
        rec = ms.judge_packet(env, self.c5, self.packet(attribution="unresolved"))
        self.assertEqual(rec["per_unit"]["M5"]["status"], "partially_establishes")
        self.assertIn("relatum_a:attribution_unresolved", rec["per_unit"]["M5"]["reasons"])

    def test_the_eligibility_prompt_shows_only_the_packet_and_the_childs_own_units(self):
        env, _ = env_for(lambda *a: self.eligibility_answer(self.slots()))
        ms.judge_packet(env, self.c5, self.packet())
        prompt = env.client.calls[0]["prompt"]
        self.assertIn("Item M5 (relationship)", prompt)
        self.assertNotIn("Item M10", prompt)
        self.assertNotIn(self.sub.contract["original_question"], prompt)

    # ---- ledger -----------------------------------------------------------------------------------------------------------

    def test_ceilings_stop_the_run_and_a_too_large_prompt_is_not_sent(self):
        env, ledger = env_for(lambda *a: self.triage_answer(), max_calls=2)
        paper = {"id": 7, "title": "T", "abstract": "Abstract."}
        ms.triage_paper(env, self.c5, paper)
        ms.triage_paper(env, self.c5, paper)
        with self.assertRaises(ms.BudgetExceeded):
            ms.triage_paper(env, self.c5, paper)
        env2, ledger2 = env_for(lambda *a: self.fail("must not be sent"))
        huge = {"id": 7, "title": "T", "abstract": "x " * 40000}
        rec = ms.triage_paper(env2, self.c5, huge)
        self.assertEqual(rec["outcome"], "prompt_too_large")
        self.assertEqual(ledger2.calls, 0)
        self.assertEqual(ledger2.stages["triage"]["not_sent:prompt_too_large"], 1)

    def test_a_stage_with_too_many_no_answers_halts(self):
        env, ledger = env_for(lambda *a: "not json")
        ledger.halt_min_calls = 5
        paper = {"id": 7, "title": "T", "abstract": "Abstract."}
        for _ in range(5):
            ms.triage_paper(env, self.c5, paper)
        with self.assertRaises(ms.StageHalt):
            ms.triage_paper(env, self.c5, paper)

    # ---- answering --------------------------------------------------------------------------------------------------------

    def test_the_raw_answer_is_preserved_even_when_capped_and_the_prompt_is_the_baseline_template(self):
        capped = {
            "status": "ok",
            "content": "Partial answer that was cut o",
            "done_reason": "length",
            "timings": {},
            "wall_seconds": 0.1,
            "thinking": "",
        }
        env, ledger = env_for(lambda *a: capped)
        rec = ms.answer_child(env, self.c9, [])
        self.assertEqual(rec["raw_answer"], "Partial answer that was cut o")
        self.assertEqual(rec["answer_state"], "capped_at_allowance")
        self.assertTrue(rec["no_eligible_evidence"])
        self.assertIn(answer.NO_EVIDENCE_BLOCK, rec["prompt"])
        self.assertFalse(env.client.calls[0]["think"])
        self.assertIsNone(env.client.calls[0]["schema"])  # free prose, no structured-output format

    def test_answer_options_are_the_baselines(self):
        env, _ = env_for(lambda *a: "An answer.")
        ms.answer_child(env, self.c9, [])
        self.assertEqual(env.client.calls[0]["options"], topo.SUPERVISOR_BASE_OPTIONS)


class SchemaCeilingTests(unittest.TestCase):
    def test_worst_case_output_fits_the_generation_allowance(self):
        allowance = topo.SUPERVISOR_BASE_OPTIONS["num_predict"]
        unit_ids = [f"s{i}" for i in range(1, 61)]
        cases = {
            "triage": schemas.triage_schema(),
            "localization": schemas.localization_schema(unit_ids),
        }
        for name, schema in cases.items():
            tokens = schemas.worst_case_output_chars(schema) / schemas.CHARS_PER_TOKEN
            self.assertLess(tokens, allowance, f"{name}: worst case {tokens:.0f} tokens vs allowance {allowance}")

    @unittest.skipUnless(DATA_PRESENT, "frozen private run data not present on this machine")
    def test_every_childs_eligibility_schema_fits_the_allowance(self):
        allowance = topo.SUPERVISOR_BASE_OPTIONS["num_predict"]
        for child in freeze.load_frozen().children:
            schema = schemas.eligibility_schema(child, [f"p{i}" for i in range(1, 8)])
            tokens = schemas.worst_case_output_chars(schema) / schemas.CHARS_PER_TOKEN
            self.assertLess(tokens, allowance, f"{child.child_id}: {tokens:.0f} tokens")

    def test_the_schema_bounds_every_growing_field(self):
        text = json.dumps(schemas.localization_schema(["s1", "s2"]))
        self.assertIn('"maxItems": 3', text)
        self.assertIn('"maxLength"', text)


class PromptTests(unittest.TestCase):
    def test_slot_definitions_cover_every_slot_the_prompt_can_show(self):
        from experiments.ask_cli_revised.contract_directed import closure

        for kind in closure.REQUIRED_SLOTS:
            for slot in closure.all_slot_names(kind, pair_required=True):
                self.assertIn(slot, closure.SLOT_DEFINITIONS)


if __name__ == "__main__":
    unittest.main()
