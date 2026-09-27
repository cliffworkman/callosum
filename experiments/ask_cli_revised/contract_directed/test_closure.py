import unittest

from experiments.ask_cli_revised.contract_directed import attribution as at
from experiments.ask_cli_revised.contract_directed import closure


def _clause_for(sid: str, state: str) -> dict:
    """One clause spanning the whole (synthetic) span text, `has_result_predicate=True` so these pre-existing
    fixtures (which predate the relation-bearing-clause requirement, Cliff's correction session 2026-09-27) keep
    exercising attribution/seam/pairing rules unaffected; that requirement has its own dedicated tests below
    (`RelationBearingClauseTests`)."""
    empty_cues = {"own": [], "own_interpretation": [], "prior": [], "hedge": []}
    return {
        "start": 0,
        "end": len(sid),
        "text": sid,
        "state": state,
        "bases": [],
        "cues": empty_cues,
        "has_result_predicate": True,
    }


def packet(parts, attribution=None):
    """parts: (span_id, role, unit_index, open) tuples; attribution defaults to own_established for every core span
    (never `linked_definition`/`study_context`, which need none)."""
    built = [
        {"span_id": sid, "role": role, "unit_index": idx, "open_left": False, "open_right": bool(is_open), "text": sid}
        for sid, role, idx, is_open in parts
    ]
    states = {
        p["span_id"]: at.OWN_ESTABLISHED for p in built if p["role"] not in ("linked_definition", "study_context")
    }
    states.update(attribution or {})
    attribution_full = {
        sid: {
            "state": state,
            "bases": [],
            "cues": {"own": [], "own_interpretation": [], "prior": [], "hedge": []},
            "flags": [],
            "model_class": None,
            "clauses": [_clause_for(sid, state)],
        }
        for sid, state in states.items()
    }
    return {"parts": built, "part_attribution": states, "attribution": attribution_full}


def slots(on_topic=("p1",), **named):
    """`on_topic` defaults to `["p1"]` — every fixture packet below has a span `p1` — so pre-existing tests (which
    predate the universal `on_topic` requirement) don't all need updating individually; a test exercising `on_topic`
    itself passes `on_topic=()` or another value explicitly."""
    out = {"on_topic": {"span_ids": list(on_topic)}}
    for name, value in named.items():
        if isinstance(value, tuple):
            out[name] = {"span_ids": list(value[0]), "value": value[1]}
        else:
            out[name] = {"span_ids": list(value)}
    return out


P1 = packet([("p1", "establishing", 3, False)])
FULL_RELATION = slots(
    relatum_a=["p1"], relatum_b=["p1"], relation_stated=["p1"], polarity=(["p1"], "association"), direction=["p1"]
)


class RelationshipClosureTests(unittest.TestCase):
    def test_one_finding_with_both_relata_relation_polarity_and_direction_closes(self):
        r = closure.derive_status("relationship", FULL_RELATION, P1)
        self.assertEqual(r["status"], closure.DIRECTLY, r)
        self.assertEqual(r["missing"], [])

    def test_an_association_without_a_stated_direction_is_only_partial(self):
        s = {k: v for k, v in FULL_RELATION.items() if k != "direction"}
        r = closure.derive_status("relationship", s, P1)
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertEqual(r["missing"], ["direction"])

    def test_a_null_result_closes_whether_without_a_direction(self):
        s = slots(relatum_a=["p1"], relatum_b=["p1"], relation_stated=["p1"], polarity=(["p1"], "none"))
        self.assertEqual(closure.derive_status("relationship", s, P1)["status"], closure.DIRECTLY)

    def test_a_source_that_does_not_say_whether_they_relate_does_not_close(self):
        s = slots(relatum_a=["p1"], relatum_b=["p1"], relation_stated=["p1"], polarity=(["p1"], "not_stated"))
        r = closure.derive_status("relationship", s, P1)
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertIn("polarity", r["missing"])

    def test_two_unrelated_passages_are_never_summed_into_a_relationship(self):
        pk = packet(
            [("p1", "establishing", 1, False), ("p2", "establishing", 9, False), ("p3", "establishing", 20, False)]
        )
        s = slots(
            relatum_a=["p1"],
            relatum_b=["p2"],
            relation_stated=["p3"],
            polarity=(["p3"], "association"),
            direction=["p3"],
        )
        r = closure.derive_status("relationship", s, pk)
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertEqual(set(r["missing"]), {"relatum_a", "relatum_b"})
        self.assertIn("relatum_a:not_tied_to_the_stated_relation", r["reasons"])

    def test_a_declared_adjacent_referent_may_carry_a_relatum(self):
        pk = packet([("p1", "referent", 4, False), ("p2", "establishing", 5, False)])
        s = slots(
            relatum_a=["p1"],
            relatum_b=["p2"],
            relation_stated=["p2"],
            polarity=(["p2"], "association"),
            direction=["p2"],
        )
        self.assertEqual(closure.derive_status("relationship", s, pk)["status"], closure.DIRECTLY)

    def test_a_qualifying_span_cannot_stand_in_for_a_relatum_far_from_the_relation(self):
        pk = packet([("p1", "qualifying", 4, False), ("p2", "establishing", 5, False)])
        s = slots(
            relatum_a=["p1"],
            relatum_b=["p2"],
            relation_stated=["p2"],
            polarity=(["p2"], "association"),
            direction=["p2"],
        )
        self.assertEqual(closure.derive_status("relationship", s, pk)["missing"], ["relatum_a"])


class ProvenanceClosureTests(unittest.TestCase):
    def test_an_unresolved_or_recounted_statement_cannot_close_a_finding(self):
        for state in (at.UNRESOLVED, at.OTHER_STUDY, at.SPECULATION, at.MIXED):
            pk = packet([("p1", "establishing", 3, False)], attribution={"p1": state})
            r = closure.derive_status("relationship", FULL_RELATION, pk)
            self.assertEqual(r["status"], closure.PARTIAL, state)
            self.assertIn(f"relatum_a:attribution_{state}", r["reasons"])

    def test_a_proposed_intervention_does_not_close_effectiveness(self):
        pk = packet([("p1", "establishing", 3, False)], attribution={"p1": at.SPECULATION})
        s = slots(finding_of_type=["p1"], outcome_reported=["p1"])
        r = closure.derive_status("existence", s, pk)
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertEqual(set(r["missing"]), {"finding_of_type", "outcome_reported"})

    def test_an_own_reported_outcome_closes_existence(self):
        s = slots(finding_of_type=["p1"], outcome_reported=["p1"])
        self.assertEqual(closure.derive_status("existence", s, P1)["status"], closure.DIRECTLY)


class LinkedBundleClosureTests(unittest.TestCase):
    def bundle(self):
        return packet([("p1", "establishing", 3, False), ("p2", "linked_definition", None, False)])

    def test_a_linked_definition_may_supply_the_instrument_but_not_the_finding(self):
        s = slots(instrument_named=["p2"], paired_with_construct=["p1"])
        self.assertEqual(closure.derive_status("operation", s, self.bundle())["status"], closure.DIRECTLY)
        s = slots(
            relatum_a=["p1"],
            relatum_b=["p1"],
            relation_stated=["p2"],
            polarity=(["p2"], "association"),
            direction=["p1"],
        )
        r = closure.derive_status("relationship", s, self.bundle())
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertIn("relation_stated:only_linked_spans_supplied", r["reasons"])

    def test_pairing_and_construct_pairing_must_come_from_the_core_finding(self):
        s = slots(instrument_named=["p1"], paired_with_construct=["p2"])
        r = closure.derive_status("operation", s, self.bundle())
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertIn("paired_with_construct:only_linked_spans_supplied", r["reasons"])


class PairAndSeamTests(unittest.TestCase):
    def test_a_child_with_a_pair_requirement_needs_the_explicit_pairing(self):
        s = slots(population_named=["p1"], tied_to_finding=["p1"])
        r = closure.derive_status("population", s, P1, pair_required=True)
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertEqual(r["missing"], ["pairing_expressed"])
        self.assertEqual(closure.derive_status("population", s, P1, pair_required=False)["status"], closure.DIRECTLY)
        s2 = {**s, "pairing_expressed": {"span_ids": ["p1"]}}
        self.assertEqual(closure.derive_status("population", s2, P1, pair_required=True)["status"], closure.DIRECTLY)

    def test_a_needed_span_that_is_an_unresolved_seam_fragment_cannot_close(self):
        pk = packet([("p0", "establishing", 2, False), ("p1", "establishing", 3, True)])
        r = closure.derive_status(
            "existence", slots(on_topic=["p0"], finding_of_type=["p1"], outcome_reported=["p1"]), pk
        )
        self.assertEqual(r["status"], closure.PARTIAL)
        self.assertIn("finding_of_type:seam_unresolved", r["reasons"])

    def test_invalid_span_ids_are_dropped_and_recorded(self):
        r = closure.derive_status("existence", slots(finding_of_type=["p1", "zz"], outcome_reported=["p1"]), P1)
        self.assertEqual(r["status"], closure.DIRECTLY)
        self.assertEqual(r["invalid_span_ids"], ["zz"])

    def test_nothing_reported_is_not_addressed(self):
        self.assertEqual(closure.derive_status("existence", {}, P1)["status"], closure.NOT_ADDRESSED)

    def test_slot_tables_are_defined_for_every_frozen_content_kind(self):
        for kind in ("requested_item", "relationship", "kinds", "operation", "manner", "population", "existence"):
            for slot in closure.all_slot_names(kind, pair_required=True):
                self.assertIn(slot, closure.SLOT_DEFINITIONS, (kind, slot))


# ---- Cliff's corrections, session 2026-09-27: on_topic mechanics, relation-bearing clauses, pairing derivation ----

from experiments.ask_cli_revised.contract_directed.freeze import ChildContract, Unit  # noqa: E402


def _real_attribution(texts: dict[str, str], *, section: str | None = None) -> dict:
    """Build a packet's `attribution` dict from the REAL `at.derive_attribution` (never hand-faked states), for
    tests that exercise clause-scoped acceptance against real corpus sentences."""
    return {sid: at.derive_attribution([text], section=section) for sid, text in texts.items()}


class OnTopicGateTests(unittest.TestCase):
    """`on_topic` is a required, MODEL-judged slot — closure.py cannot itself decide whether a passage is on-topic
    (that would defeat the point of asking the model). What these tests prove is the MECHANICAL consequence: a
    unit whose model-reported `on_topic` is empty (exactly what the model would do for a genuinely off-topic
    passage, e.g. an unrelated dmPFC/social-scenes finding) can never close no matter how completely its other
    slots are filled — but those other slots are still recorded, preserving the passage as an inspectable lead
    rather than discarding it. A `study_context` part IS an eligible `on_topic` source; a `linked_definition` part
    is not (it may only ever supply a descriptive slot, never even the topical-relevance judgment)."""

    def test_a_structurally_complete_but_off_topic_finding_never_closes(self):
        pk = packet([("p1", "establishing", 1, False)])
        s = slots(
            on_topic=[], relatum_a=["p1"], relatum_b=["p1"], relation_stated=["p1"],
            polarity=(["p1"], "association"), direction=["p1"],
        )  # fmt: skip
        r = closure.derive_status("relationship", s, pk)
        self.assertEqual(r["status"], closure.NOT_ADDRESSED)
        self.assertEqual(set(r["slot_spans"]["relatum_a"]), {"p1"})  # preserved as a lead, not discarded

    def test_study_context_is_an_eligible_on_topic_source(self):
        pk = packet([("p1", "establishing", 1, False), ("p2", "study_context", None, False)])
        r = closure.derive_status(
            "existence", slots(on_topic=["p2"], finding_of_type=["p1"], outcome_reported=["p1"]), pk
        )
        self.assertEqual(r["status"], closure.DIRECTLY)

    def test_a_linked_definition_cannot_supply_on_topic(self):
        pk = packet([("p1", "establishing", 1, False), ("p2", "linked_definition", None, False)])
        r = closure.derive_status(
            "existence", slots(on_topic=["p2"], finding_of_type=["p1"], outcome_reported=["p1"]), pk
        )
        self.assertNotEqual(r["status"], closure.DIRECTLY)

    def test_an_on_topic_fragment_is_unresolved_not_accepted(self):
        pk = packet([("p1", "establishing", 1, False), ("p2", "establishing", 2, True)])
        r = closure.derive_status(
            "existence", slots(on_topic=["p2"], finding_of_type=["p1"], outcome_reported=["p1"]), pk
        )
        self.assertNotEqual(r["status"], closure.DIRECTLY)


class RelationBearingClauseTests(unittest.TestCase):
    """A clean clause that never states a result cannot validate a relationship stated only in a different,
    speculative clause of the same sentence — Cliff's correction: attribution rescue must attach to the SAME
    clause that actually carries the claimed content, not any clean clause in the vicinity."""

    MIXED_SENTENCE = (
        "Participants completed extensive testing; this might also indicate that disgust sensitivity is "
        "associated with reduced prosociality toward affected individuals."
    )

    def test_a_relationship_stated_only_in_a_speculative_clause_does_not_close(self):
        pk = {
            "parts": [
                {"span_id": "p1", "role": "establishing", "unit_index": 1, "open_left": False, "open_right": False, "text": self.MIXED_SENTENCE},
            ],
            "attribution": _real_attribution({"p1": self.MIXED_SENTENCE}),
        }  # fmt: skip
        s = slots(
            on_topic=["p1"], relatum_a=["p1"], relatum_b=["p1"], relation_stated=["p1"],
            polarity=(["p1"], "association"), direction=["p1"],
        )  # fmt: skip
        r = closure.derive_status("relationship", s, pk)
        self.assertNotEqual(r["status"], closure.DIRECTLY)
        self.assertIn("relation_stated:no_relation_bearing_accepted_clause", r["reasons"])

    def test_the_same_sentences_own_established_clause_still_supports_a_descriptive_slot(self):
        """The factual clause ("Participants completed extensive testing") has no result predicate of its own, so
        it cannot support `relation_stated` — but it is still `own_established` and can support a purely
        descriptive slot (e.g. naming that testing occurred), proving the gate is scoped to relation-bearing slots
        only, not a blanket rejection of the whole span."""
        pk = {
            "parts": [{"span_id": "p1", "role": "establishing", "unit_index": 1, "open_left": False, "open_right": False, "text": self.MIXED_SENTENCE}],
            "attribution": _real_attribution({"p1": self.MIXED_SENTENCE}),
        }  # fmt: skip
        r = closure.derive_status(
            "requested_item", slots(on_topic=["p1"], item_named=["p1"], tied_to_subject=["p1"]), pk
        )
        self.assertEqual(r["status"], closure.DIRECTLY)


HADZA_SENTENCE = (
    "We presented 123 Hadza across ten camps pairs of morphed Hadza faces—each with one face altered to include "
    "a scar—and asked who they expected to be more moral and a better forager."
)
UNRELATED_POPULATION_PART = "European participants were also recruited for a separate control condition."
UNRELATED_MEASURE_PART = (
    "The Interpersonal Reactivity Index,32 which measures cognitive empathy, was administered to a different sample."
)


def _pair_child(kind_a: str, kind_b: str) -> ChildContract:
    units = (Unit("M12", kind_a, "the population", False), Unit("M13", kind_b, "the manner", False))
    return ChildContract(
        child_id="c11", parent="c4", contract_text="in which cultures, and how measured?", contract_sha256="x",
        wording="in which cultures, and how measured?", wording_sha256="y", scope_carrier_wording=None,
        units=units, primary_unit_id="M12", pair_requirement_ids=("RC-6#pair",), machine_side_constraints=(),
    )  # fmt: skip


class CrossUnitPairingTests(unittest.TestCase):
    """`pairing_expressed` may be derived — never invented — only when ONE proposition genuinely connects both
    paired things: the same clause is the accepted evidence for both units' primary slots, or an existing verified
    link connects the two accepted spans. A shared span id filled via two DIFFERENT clauses is not enough
    (Cliff's correction, session 2026-09-27: the real gap was an EMPTY pairing slot, not a contaminated one)."""

    def test_pair_partners_maps_the_two_content_units_to_each_other(self):
        child = _pair_child("population", "manner")
        self.assertEqual(closure.pair_partners(child), {"M12": "M13", "M13": "M12"})

    def test_the_real_hadza_sentence_establishes_the_pairing_from_one_clause(self):
        pk = {
            "parts": [{"span_id": "p1", "role": "establishing", "unit_index": 1, "open_left": False, "open_right": False, "text": HADZA_SENTENCE}],
            "attribution": _real_attribution({"p1": HADZA_SENTENCE}),
        }  # fmt: skip
        pop = closure.derive_status(
            "population",
            slots(on_topic=["p1"], population_named=["p1"], tied_to_finding=["p1"]),
            pk,
            pair_required=True,
        )
        man = closure.derive_status(
            "manner", slots(on_topic=["p1"], manner_described=["p1"], tied_to_subject=["p1"]), pk, pair_required=True
        )
        self.assertEqual(pop["missing"], ["pairing_expressed"])  # the model itself offered no pairing_expressed
        self.assertEqual(man["missing"], ["pairing_expressed"])
        bonus = closure.derive_pairing_bonus("population", pop, "manner", man, pk)
        self.assertIsNotNone(bonus)
        self.assertEqual(bonus["source"], "same_clause")
        pop2 = closure.apply_pairing_bonus(pop, bonus)
        self.assertEqual(pop2["status"], closure.DIRECTLY)
        self.assertEqual(pop2["reasons"][-1], f"pairing_expressed:derived_from_pair_partner:{bonus['source']}")

    @unittest.expectedFailure
    def test_a_shared_clause_that_explicitly_excludes_one_population_from_the_measurement_still_pairs_KNOWN_GAP(self):
        """Cliff's correction (session 2026-09-27, second round): matching clause offsets are not sufficient if
        the proposition does not connect the requested relata. A clause can name two populations while explicitly
        stating that only ONE of them underwent the measurement — same-clause identity alone cannot see that
        distinction. This is a REPORTED, NOT-YET-FIXED gap (marked `expectedFailure` so it stays visible in the
        suite rather than silently passing or being dropped): fixing it would need the derivation to recognize an
        explicit exclusion/contrast marker within the shared clause, which is a real, if narrow, change to the
        pairing architecture — out of scope for a verification-only pass; see `GATE1_REPAIR_HANDBACK.md`'s
        proposed options for Cliff's decision."""
        text = (
            "We found that among the Hadza and U.S. participants who viewed the stimuli, only the U.S. "
            "participants completed the paper-and-pencil ratings."
        )
        pk = {
            "parts": [{"span_id": "p1", "role": "establishing", "unit_index": 1, "open_left": False, "open_right": False, "text": text}],
            "attribution": _real_attribution({"p1": text}),
        }  # fmt: skip
        pop = closure.derive_status(
            "population",
            slots(on_topic=["p1"], population_named=["p1"], tied_to_finding=["p1"]),
            pk,
            pair_required=True,
        )
        man = closure.derive_status(
            "manner", slots(on_topic=["p1"], manner_described=["p1"], tied_to_subject=["p1"]), pk, pair_required=True
        )
        bonus = closure.derive_pairing_bonus("population", pop, "manner", man, pk)
        self.assertIsNone(
            bonus, "the clause explicitly excludes Hadza from the measurement; same-clause identity must not pair them"
        )

    def test_an_unrelated_population_mention_and_measurement_in_different_parts_do_not_pair(self):
        """Realistic shape: the population mention and the measurement description are two DIFFERENT localized
        spans (as they would be if the model selected two separate sentence units), not two clauses of one span —
        so their offsets can never coincide and no verified link connects them."""
        pk = {
            "parts": [
                {"span_id": "p1", "role": "establishing", "unit_index": 1, "open_left": False, "open_right": False, "text": UNRELATED_POPULATION_PART},
                {"span_id": "p2", "role": "establishing", "unit_index": 5, "open_left": False, "open_right": False, "text": UNRELATED_MEASURE_PART},
            ],
            "attribution": _real_attribution({"p1": UNRELATED_POPULATION_PART, "p2": UNRELATED_MEASURE_PART}, section="methods"),
        }  # fmt: skip
        pop = closure.derive_status(
            "population",
            slots(on_topic=["p1"], population_named=["p1"], tied_to_finding=["p1"]),
            pk,
            pair_required=True,
        )
        man = closure.derive_status(
            "manner", slots(on_topic=["p2"], manner_described=["p2"], tied_to_subject=["p2"]), pk, pair_required=True
        )
        bonus = closure.derive_pairing_bonus("population", pop, "manner", man, pk)
        self.assertIsNone(bonus)

    def test_a_verified_link_can_also_connect_the_two_accepted_spans(self):
        pk = packet(
            [("p1", "establishing", 1, False), ("p2", "linked_definition", None, False)],
        )
        pk["links"] = [{"link_id": "lk1", "verified": True}]
        pk["parts"][1]["linked_from"] = "lk1"
        pop = closure.derive_status(
            "population",
            slots(on_topic=["p1"], population_named=["p1"], tied_to_finding=["p1"]),
            pk,
            pair_required=True,
        )
        man = closure.derive_status(
            "manner", slots(on_topic=["p1"], manner_described=["p2"], tied_to_subject=["p1"]), pk, pair_required=True
        )
        bonus = closure.derive_pairing_bonus("population", pop, "manner", man, pk)
        self.assertIsNotNone(bonus)
        self.assertEqual(bonus["source"], "verified_link")

    def test_the_link_path_never_reaches_a_span_id_outside_the_given_packet(self):
        """`derive_pairing_bonus` takes exactly ONE packet; a span id that is not among ITS OWN parts cannot be
        connected via the verified-link path — there is no mechanism here that could reach into a different
        packet, even one built from the same source text."""
        pk = packet([("p1", "establishing", 1, False)])
        pop = closure.derive_status(
            "population",
            slots(on_topic=["p1"], population_named=["p1"], tied_to_finding=["p1"]),
            pk,
            pair_required=True,
        )
        # A result claiming its primary evidence is span "zz" (never a part of `pk`) cannot be linked to anything.
        fake_man = {
            "missing": [closure.PAIRING_SLOT],
            "primary_slot_evidence": {"span_id": "zz", "start": 99, "end": 100, "text": "nowhere"},
        }
        bonus = closure.derive_pairing_bonus("population", pop, "manner", fake_man, pk)
        self.assertIsNone(bonus)


if __name__ == "__main__":
    unittest.main()
