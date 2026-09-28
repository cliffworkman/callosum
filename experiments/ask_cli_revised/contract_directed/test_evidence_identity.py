"""Tests for stable evidence identity and collision detection (2026-09-27)."""

import unittest

from experiments.ask_cli_revised.contract_directed import evidence_identity as ident

SPAN_A = {"paper_id": 68, "chunk_id": 43327, "span_id": "p1", "start": 248, "end": 436, "text": "text A"}
SPAN_B = {"paper_id": 68, "chunk_id": 43327, "span_id": "p2", "start": 437, "end": 617, "text": "text B"}
# Same coarse key as SPAN_A's paper/chunk, but "p1" reused for a genuinely different offset/text -- exactly the
# real risk `packet.py::_part`'s packet-local numbering creates.
COLLIDING_SPAN = {"paper_id": 68, "chunk_id": 43327, "span_id": "p1", "start": 900, "end": 950, "text": "text C"}
LEGITIMATE_DUPLICATE = {**SPAN_A}  # the identical span, cited twice (e.g. by two different manifest rows)


class CanonicalLocatorTests(unittest.TestCase):
    def test_uses_offsets_when_present(self):
        self.assertEqual(ident.canonical_locator(SPAN_A), (68, 43327, 248, 436))

    def test_falls_back_to_span_id_when_offsets_absent(self):
        span = {"paper_id": 68, "chunk_id": 43327, "span_id": "p1", "text": "x"}
        self.assertEqual(ident.canonical_locator(span), (68, 43327, "p1", None))


class CoarseKeyTests(unittest.TestCase):
    def test_ignores_offsets(self):
        self.assertEqual(ident.coarse_key(SPAN_A), (68, 43327, "p1"))
        self.assertEqual(ident.coarse_key(COLLIDING_SPAN), (68, 43327, "p1"))  # same coarse key, different span


class AssertNoCoarseKeyCollisionTests(unittest.TestCase):
    def test_distinct_spans_with_distinct_coarse_keys_pass(self):
        ident.assert_no_coarse_key_collision([SPAN_A, SPAN_B])  # raises nothing

    def test_the_same_span_cited_twice_is_not_a_collision(self):
        ident.assert_no_coarse_key_collision([SPAN_A, LEGITIMATE_DUPLICATE])  # raises nothing

    def test_two_different_spans_sharing_a_coarse_key_is_a_collision(self):
        """The real risk this module exists for: packet-local `span_id` numbering restarts at "p1" for every
        packet, so two genuinely different spans (different offsets, different text) can share the exact same
        (paper_id, chunk_id, span_id) key."""
        with self.assertRaises(ident.SpanIdentityCollision):
            ident.assert_no_coarse_key_collision([SPAN_A, COLLIDING_SPAN])

    def test_collision_message_names_the_conflicting_offsets_and_texts(self):
        with self.assertRaisesRegex(ident.SpanIdentityCollision, r"248, 436.*900, 950|900, 950.*248, 436"):
            ident.assert_no_coarse_key_collision([SPAN_A, COLLIDING_SPAN])

    def test_two_spans_without_offsets_sharing_a_coarse_key_but_different_text_is_also_a_collision(self):
        a = {"paper_id": 1, "chunk_id": 2, "span_id": "p1", "text": "one thing"}
        b = {"paper_id": 1, "chunk_id": 2, "span_id": "p1", "text": "a different thing entirely"}
        with self.assertRaises(ident.SpanIdentityCollision):
            ident.assert_no_coarse_key_collision([a, b])

    def test_an_empty_list_is_fine(self):
        ident.assert_no_coarse_key_collision([])


class BuildLocatorIndexTests(unittest.TestCase):
    def test_builds_the_expected_index(self):
        units = [
            {"unit_id": "U1", "paper_id": 68, "locators": [{"chunk_id": 43327, "span_id": "p1"}]},
            {"unit_id": "U2", "paper_id": 68, "locators": [{"chunk_id": 43327, "span_id": "p2"}]},
        ]
        index = ident.build_locator_index(units)
        self.assertEqual(index[(68, 43327, "p1")], "U1")
        self.assertEqual(index[(68, 43327, "p2")], "U2")

    def test_the_same_unit_repeating_its_own_locator_is_fine(self):
        units = [{"unit_id": "U1", "paper_id": 68, "locators": [{"chunk_id": 43327, "span_id": "p1"}]}]
        ident.build_locator_index(units)  # raises nothing

    def test_two_different_units_claiming_the_same_locator_raises(self):
        units = [
            {"unit_id": "U1", "paper_id": 68, "locators": [{"chunk_id": 43327, "span_id": "p1"}]},
            {"unit_id": "U2", "paper_id": 68, "locators": [{"chunk_id": 43327, "span_id": "p1"}]},
        ]
        with self.assertRaises(ident.DuplicateOverviewUnitLocator):
            ident.build_locator_index(units)


class MatchSpanToSavedUnitTests(unittest.TestCase):
    def test_no_match_returns_none(self):
        index, by_id = {}, {}
        self.assertIsNone(ident.match_span_to_saved_unit(SPAN_A, index, by_id))

    def test_a_match_with_agreeing_text_succeeds(self):
        index = {(68, 43327, "p1"): "U1"}
        by_id = {"U1": {"passage": "text A"}}
        self.assertEqual(ident.match_span_to_saved_unit(SPAN_A, index, by_id), "U1")

    def test_a_match_with_disagreeing_text_raises(self):
        index = {(68, 43327, "p1"): "U1"}
        by_id = {"U1": {"passage": "a different sentence"}}
        with self.assertRaises(ident.SavedRecordTextMismatch):
            ident.match_span_to_saved_unit(SPAN_A, index, by_id)

    def test_a_matched_unit_missing_its_passage_field_raises_rather_than_trusting_the_locator_alone(self):
        index = {(68, 43327, "p1"): "U1"}
        by_id = {"U1": {}}
        with self.assertRaises(ident.SavedRecordTextMismatch):
            ident.match_span_to_saved_unit(SPAN_A, index, by_id)


if __name__ == "__main__":
    unittest.main()
