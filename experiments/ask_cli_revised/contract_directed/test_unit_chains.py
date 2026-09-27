import unittest

from experiments.ask_cli_revised.contract_directed import seams, units


def verifier(established_pairs):
    """Established only for the listed (left_id, right_id) pairs."""

    def verify(a, b):
        ok = (a["chunk_id"], b["chunk_id"]) in established_pairs
        return seams.SeamVerdict("established" if ok else "not_established", () if ok else ("test_refusal",), {})

    return verify


LINES = [
    {"chunk_id": 1, "text": "Hadza with greater exposure to"},
    {"chunk_id": 2, "text": "other cultures expected the scarred face to be less moral. These"},
    {"chunk_id": 3, "text": "results suggest the stereotype is culturally shared, providing evidence against a"},
    {"chunk_id": 4, "text": "universal byproduct hypothesis."},
]


class ChainJoinTests(unittest.TestCase):
    def test_a_chain_of_three_chunks_joins_only_if_every_seam_verifies(self):
        out = units.build_units(LINES, verifier({(1, 2), (2, 3), (3, 4)}))
        joined = [u for u in out if u.join == "verified_seam"]
        self.assertEqual(len(joined), 2)
        self.assertEqual(
            joined[0].text, "Hadza with greater exposure to other cultures expected the scarred face to be less moral."
        )
        self.assertEqual(
            joined[1].text,
            "These results suggest the stereotype is culturally shared, providing evidence against a universal byproduct hypothesis.",
        )
        self.assertEqual([p.chunk_id for p in joined[1].pieces], [2, 3, 4])
        self.assertEqual(len(joined[1].seam["joins"]), 2)

    def test_one_failed_seam_cuts_the_chain_into_flagged_fragments(self):
        out = units.build_units(LINES, verifier({(2, 3)}))  # (3, 4) is refused
        texts = {u.text: u for u in out}
        left = texts["These results suggest the stereotype is culturally shared, providing evidence against a"]
        right = texts["universal byproduct hypothesis."]
        self.assertTrue(left.open_right and left.join == "verified_seam")
        self.assertTrue(right.open_left)
        self.assertEqual(left.seam["state"], "established")  # the joins that did verify are still recorded
        self.assertFalse(
            any("universal" in u.text and "results suggest" in u.text for u in out)
        )  # nothing crosses the refused seam

    def test_no_seam_is_established_by_adjacency_alone(self):
        out = units.build_units(LINES, verifier(set()))
        self.assertFalse(any(u.join == "verified_seam" for u in out))
        self.assertEqual(len(out), 5)  # every line/sentence stays its own unit

    def test_every_piece_of_every_unit_is_an_exact_slice(self):
        out = units.build_units(LINES, verifier({(1, 2), (2, 3), (3, 4)}))
        by_id = {c["chunk_id"]: c["text"] for c in LINES}
        for unit in out:
            for piece in unit.pieces:
                self.assertEqual(by_id[piece.chunk_id][piece.start : piece.end], piece.text)


class OpenFragmentSemanticsTests(unittest.TestCase):
    def test_a_heading_without_a_period_followed_by_a_new_sentence_is_complete_not_open(self):
        chunks = [{"chunk_id": 1, "text": "Participants"}, {"chunk_id": 2, "text": "We recruited forty people."}]
        out = units.build_units(chunks, verifier(set()))
        heading = next(u for u in out if u.text == "Participants")
        self.assertFalse(heading.open_right)
        self.assertFalse(heading.open_left)

    def test_a_line_that_stops_mid_sentence_and_whose_continuation_is_unverified_stays_open(self):
        chunks = [{"chunk_id": 1, "text": "The effect was"}, {"chunk_id": 2, "text": "larger in the second sample."}]
        out = units.build_units(chunks, verifier(set()))
        left = next(u for u in out if u.text == "The effect was")
        right = next(u for u in out if u.text.startswith("larger"))
        self.assertTrue(left.open_right)
        self.assertTrue(right.open_left)

    def test_a_non_adjacent_chunk_leaves_the_carried_unit_open(self):
        chunks = [
            {"chunk_id": 1, "text": "The effect was"},
            {"chunk_id": 2, "text": ""},
            {"chunk_id": 3, "text": "Another sentence."},
        ]
        left = next(u for u in units.build_units(chunks, verifier(set())) if u.text == "The effect was")
        self.assertTrue(left.open_right)


if __name__ == "__main__":
    unittest.main()
