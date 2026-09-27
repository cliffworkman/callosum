import unittest

from experiments.ask_cli_revised.contract_directed import attribution as at
from experiments.ask_cli_revised.contract_directed import closure


def packet(parts, attribution=None):
    """parts: (span_id, role, unit_index, open) tuples; attribution defaults to own_established for every core span."""
    built = [
        {"span_id": sid, "role": role, "unit_index": idx, "open_left": False, "open_right": bool(is_open), "text": sid}
        for sid, role, idx, is_open in parts
    ]
    default = {p["span_id"]: at.OWN_ESTABLISHED for p in built if p["role"] != "linked_definition"}
    return {"parts": built, "part_attribution": {**default, **(attribution or {})}}


def slots(**named):
    out = {}
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
        pk = packet([("p1", "establishing", 3, True)])
        r = closure.derive_status("existence", slots(finding_of_type=["p1"], outcome_reported=["p1"]), pk)
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


if __name__ == "__main__":
    unittest.main()
