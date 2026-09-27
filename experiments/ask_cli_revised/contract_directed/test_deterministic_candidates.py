"""Task C: the closed-class instrument/manner fast path. A match is never auto-verified — every assertion here
checks that a candidate is CREATED (or correctly not created); eligibility, on_topic and attribution are unaffected
and are tested where they actually live (test_closure.py, test_attribution.py)."""

import unittest

from experiments.ask_cli_revised.contract_directed import deterministic_candidates as dc
from experiments.ask_cli_revised.contract_directed import units
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract, Unit

# The real Gate-1 paper-67 localization neighborhood's exact sentence units (copied verbatim from
# runs/pilot-001/qwen_calls.jsonl's localization prompt for nbhd 0824bb709d7d) — s20 is the sentence Qwen
# failed to select (F2); s7/s8 are the ones it picked instead; s19/s23/s24/s31 are real fragments from the
# same neighborhood.
S7 = "Five-point semantic differen- tial scales examined perceptions of the people in the photographs in terms of personality charac- teristics (e.g., anxious), internal attributes (e.g., contentedness), social traits."
S20 = (
    "Participants completed a Just World Beliefs Scale,31 which measures beliefs about interpersonal fairness "
    "toward oneself and others; the Interpersonal Reactivity Index,32 which mea- sures cognitive (perspective "
    "taking) and affective (empathic concern) empathy; and a subscale from the Three-Domain Disgust scale33 that "
    "measures sensitivity to pathogen-related disgust."
)
TRUNCATED_S20 = (
    "Participants completed a Just World Beliefs Scale,31 which mea"  # cut mid-word, as a real fragment would be
)


def unit(uid, text, *, open_left=False, open_right=False):
    piece = units.Piece(1, 0, len(text), text)
    return units.SentenceUnit(uid, (piece,), text, "none", None, open_left, open_right)


def c9_like() -> ChildContract:
    return ChildContract(
        child_id="c9", parent="c8", contract_text="which scales measure the traits?", contract_sha256="x",
        wording="which scales measure the traits?", wording_sha256="y", scope_carrier_wording=None,
        units=(Unit("M10", "operation", "using which scales?", False), Unit("W21", "requested_item", "scales", False)),
        primary_unit_id="M10", pair_requirement_ids=("RC-5#pair",), machine_side_constraints=(),
    )  # fmt: skip


def c5_like() -> ChildContract:
    """A child with NO operation/manner/requested_item unit at all — the detector must never apply."""
    return ChildContract(
        child_id="c5", parent="c4", contract_text="how do brain areas relate to behaviors?", contract_sha256="x",
        wording="how do brain areas relate to behaviors?", wording_sha256="y", scope_carrier_wording=None,
        units=(Unit("M5", "relationship", "brain areas relate to behaviors", False),), primary_unit_id="M5",
        pair_requirement_ids=(), machine_side_constraints=(),
    )  # fmt: skip


class FindCandidatesTests(unittest.TestCase):
    def test_applies_only_to_a_child_owning_an_operation_manner_or_requested_item_unit(self):
        self.assertTrue(dc.applies(c9_like()))
        self.assertFalse(dc.applies(c5_like()))

    def test_the_real_paper_67_sentence_is_matched_as_a_complete_proposition(self):
        candidates = dc.find_instrument_pairing_candidates([unit("s7", S7), unit("s20", S20)], c9_like())
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["establishing"], ["s20"])
        self.assertEqual(candidates[0]["provenance_class"], "methods")
        self.assertEqual(candidates[0]["source"], "deterministic_pattern:instrument_measurement_verb")

    def test_a_truncated_sentence_is_never_matched(self):
        """A fragment is exactly the 'identifiable problem' (a truncated result) that Cliff's brief says still
        needs a real model call — the detector must not guess at it."""
        frag = unit("s20", TRUNCATED_S20, open_right=True)
        self.assertEqual(dc.find_instrument_pairing_candidates([frag], c9_like()), [])

    def test_s7_alone_does_not_match(self):
        """S7 (semantic-differential scales, no explicit 'which/that measures' pairing clause) is the sentence
        Qwen wrongly picked in Gate 1 — it should not ALSO be a deterministic false positive."""
        self.assertEqual(dc.find_instrument_pairing_candidates([unit("s7", S7)], c9_like()), [])

    def test_no_candidates_for_a_child_with_no_relevant_unit_kind(self):
        self.assertEqual(dc.find_instrument_pairing_candidates([unit("s20", S20)], c5_like()), [])

    def test_the_construct_named_still_needs_on_topic_to_close_not_a_bypass(self):
        """The detector only makes a sentence AVAILABLE as a candidate; it asserts nothing about whether the
        construct it names is on-topic for the child asking — that gate lives in closure.py (test_closure.py's
        OnTopicGateTests), unaffected by this module."""
        candidates = dc.find_instrument_pairing_candidates(
            [unit("s99", "The XYZ Scale measures an unrelated trait.")], c9_like()
        )
        self.assertEqual(
            len(candidates), 1
        )  # the pattern matches; on_topic (a separate, later gate) may still refuse it


class OnlyInstrumentMannerTargetedTests(unittest.TestCase):
    def test_a_neighborhood_reached_only_via_unit_probes_for_eligible_kinds_qualifies(self):
        nbhd = {"routes": ["unit_probe:M10", "unit_probe:W21"]}
        self.assertTrue(dc.only_instrument_manner_targeted(nbhd, c9_like()))

    def test_an_abstract_page_route_disqualifies_even_alongside_an_eligible_unit_probe(self):
        """The neighborhood that is ALSO the paper's abstract page may hold other kinds of findings — the model's
        attention is not skipped there, even though the instrument pattern still matches and still contributes."""
        nbhd = {"routes": ["unit_probe:M10", "abstract_page"]}
        self.assertFalse(dc.only_instrument_manner_targeted(nbhd, c9_like()))

    def test_a_relationship_kind_unit_probe_disqualifies(self):
        """A mixed-kind neighborhood (this one also reached via a relationship-kind unit probe, as could happen in
        an 11-child run) is never skipped, even though the instrument pattern still matches and still contributes
        its own proposition alongside whatever the model itself returns."""
        nbhd = {"routes": ["unit_probe:M10", "unit_probe:M5"]}
        mixed_child = ChildContract(
            child_id="cX", parent="c4", contract_text="x", contract_sha256="x", wording="x", wording_sha256="y",
            scope_carrier_wording=None,
            units=(Unit("M10", "operation", "using which scales?", False), Unit("M5", "relationship", "y", False)),
            primary_unit_id="M10", pair_requirement_ids=(), machine_side_constraints=(),
        )  # fmt: skip
        self.assertFalse(dc.only_instrument_manner_targeted(nbhd, mixed_child))

    def test_no_routes_never_qualifies(self):
        self.assertFalse(dc.only_instrument_manner_targeted({"routes": []}, c9_like()))


if __name__ == "__main__":
    unittest.main()
