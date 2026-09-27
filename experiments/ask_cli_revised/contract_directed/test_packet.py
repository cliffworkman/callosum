import copy
import unittest

from experiments.ask_cli_revised.contract_directed import answer, freeze, neighborhood, packet, store

DB = freeze.SLICE_ROOT / "library.sqlite"


def proposition(establishing, qualifying=(), referents=(), cls=None, phrase=None):
    return {
        "establishing": list(establishing),
        "qualifying": list(qualifying),
        "referents": list(referents),
        "provenance_class": cls,
        "attribution_basis_phrase": phrase,
        "relation_polarity": "not_stated",
        "unresolved": [],
    }


class FakeLibrary:
    """Minimal stand-in: one attachment, two chunks, no seams, no links."""

    def __init__(self, chunks):
        self._chunks = chunks

    def attachment_chunks(self, attachment_id):
        return self._chunks

    def paper(self, paper_id):
        return {"id": paper_id, "abstract": None}

    def attachment(self, attachment_id):
        return {"id": attachment_id, "role": "primary", "checksum": "abc", "is_primary": True}

    def chunk(self, chunk_id):
        return next(c for c in self._chunks if c["chunk_id"] == chunk_id)

    def seam_verifier(self):
        from experiments.ask_cli_revised.contract_directed import seams

        return lambda a, b: seams.SeamVerdict("not_established", ("test",), {})


def fake_chunk(cid, text, **over):
    base = {
        "chunk_id": cid,
        "paper_id": 1,
        "attachment_id": 9,
        "text": text,
        "section": "results",
        "grobid_kind": None,
        "page_start": 1,
        "page_end": 1,
        "char_start": cid * 1000,
        "char_end": cid * 1000 + len(text),
    }
    return base | over


class SyntheticPacketTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            fake_chunk(1, "We found less prosociality among high-SES participants. It was small."),
            fake_chunk(2, "Another chunk."),
        ]
        self.lib = FakeLibrary(self.chunks)
        self.nb = {
            "nbhd_id": "n1",
            "paper_id": 1,
            "attachment_id": 9,
            "chunk_ids": [1, 2],
            "attachment": {"id": 9, "role": "primary", "checksum": "abc", "is_primary": True},
        }
        self.units, self.by_id = packet.neighborhood_units(self.nb, self.lib)

    def test_a_packet_carries_exact_pieces_locators_and_per_span_attribution(self):
        p = packet.build_packet(
            self.nb, self.units, self.by_id, proposition(["s1"], qualifying=["s2"]), library=self.lib, child_id="c5"
        )
        self.assertEqual(p["state"], "built")
        self.assertEqual([x["role"] for x in p["parts"]], ["establishing", "qualifying"])
        first = p["parts"][0]
        self.assertEqual(first["pieces"][0]["text"], "We found less prosociality among high-SES participants.")
        self.assertTrue(first["pieces"][0]["verbatim_ok"])
        self.assertEqual(p["part_attribution"]["p1"], "own_established")
        self.assertEqual(p["evidence_form"], "verbatim")
        self.assertEqual(p["found_under"], ["c5"])

    def test_packet_ids_are_deterministic_and_role_independent_of_child(self):
        a = packet.build_packet(self.nb, self.units, self.by_id, proposition(["s1"]), library=self.lib, child_id="c5")
        b = packet.build_packet(self.nb, self.units, self.by_id, proposition(["s1"]), library=self.lib, child_id="c6")
        self.assertEqual(a["packet_id"], b["packet_id"])
        merged = packet.merge_duplicates([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["found_under"], ["c5", "c6"])

    def test_a_piece_that_is_not_verbatim_in_its_chunk_is_never_shown(self):
        tampered = copy.deepcopy(self.by_id)
        tampered[1]["text"] = "Different text entirely."
        p = packet.build_packet(self.nb, self.units, tampered, proposition(["s1"]), library=self.lib, child_id="c5")
        self.assertEqual(p["state"], "unresolved_preserved")
        self.assertEqual(p["dropped_parts"][0]["reason"], "piece_not_verbatim_in_its_chunk")

    def test_shared_spans_across_packets_are_reported_as_one_source(self):
        a = packet.build_packet(self.nb, self.units, self.by_id, proposition(["s1"]), library=self.lib, child_id="c5")
        b = packet.build_packet(
            self.nb, self.units, self.by_id, proposition(["s1"], qualifying=["s2"]), library=self.lib, child_id="c6"
        )
        overlap = packet.overlapping_spans([a, b])
        self.assertEqual(len(overlap), 1)
        self.assertEqual(len(next(iter(overlap.values()))), 2)


@unittest.skipUnless(DB.is_file(), "disposable library copy not present")
class RealPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = store.Library(DB)

    @classmethod
    def tearDownClass(cls):
        cls.lib.close()

    def nbhd_around(self, chunk_id):
        chunk = self.lib.chunk(chunk_id)
        ordered = self.lib.attachment_chunks(chunk["attachment_id"])
        index = next(i for i, c in enumerate(ordered) if c["chunk_id"] == chunk_id)
        nb = neighborhood.build_neighborhood(ordered, index)
        nb["attachment"] = self.lib.attachment(chunk["attachment_id"])
        return nb

    def unit_id(self, units, startswith):
        return next(u.unit_id for u in units if u.text.startswith(startswith))

    def test_the_discussion_interpretation_is_speculation_and_carries_its_verified_dg_definition(self):
        nb = self.nbhd_around(35111)
        unit_list, by_id = packet.neighborhood_units(nb, self.lib)
        uid = self.unit_id(unit_list, "We suggest that dehumanization")
        p = packet.build_packet(
            nb, unit_list, by_id, proposition([uid], cls="this_study_reports"), library=self.lib, child_id="c5"
        )
        self.assertEqual(p["state"], "built")
        self.assertEqual(
            p["part_attribution"]["p1"], "speculation"
        )  # "We suggest": the model's own-study label cannot upgrade it
        linked = [x for x in p["parts"] if x["role"] == "linked_definition"]
        self.assertTrue(any("Dictator Game (DG)" in x["text"] for x in linked), [x["text"] for x in p["parts"]])
        dg = next(x for x in linked if "Dictator Game (DG)" in x["text"])
        self.assertEqual(dg["section"], "methods")
        self.assertIn("definition acronym", dg["note"])
        self.assertTrue(p["attachment"]["is_primary"])

    def test_a_sentence_that_mixes_own_detection_with_earlier_reports_is_mixed_not_own(self):
        nb = self.nbhd_around(35111)
        unit_list, by_id = packet.neighborhood_units(nb, self.lib)
        uid = self.unit_id(unit_list, "This research confirmed earlier reports")
        p = packet.build_packet(nb, unit_list, by_id, proposition([uid]), library=self.lib, child_id="c3")
        self.assertEqual(p["part_attribution"]["p1"], "mixed")

    def test_the_u9_sentence_is_assembled_across_a_verified_seam_from_the_alternate_attachment(self):
        nb = self.nbhd_around(14388)
        unit_list, by_id = packet.neighborhood_units(nb, self.lib)
        target = next(
            u
            for u in unit_list
            if "providing evidence against a universal pathogen avoidance byproduct hypothesis" in u.text
        )
        self.assertEqual(target.join, "verified_seam")
        self.assertTrue(target.text.startswith("These results suggest"), target.text)
        p = packet.build_packet(nb, unit_list, by_id, proposition([target.unit_id]), library=self.lib, child_id="c10")
        self.assertEqual(p["state"], "built")
        self.assertEqual(p["evidence_form"], "assembled_verified_seam")
        # a line-level chunked sentence: three chunks, two verified seams, every piece exact in its own chunk
        self.assertEqual([pc["chunk_id"] for pc in p["parts"][0]["pieces"]], [14387, 14388, 14389])
        self.assertEqual([j["state"] for j in target.seam["joins"]], ["established", "established"])
        self.assertTrue(all(pc["verbatim_ok"] for pc in p["parts"][0]["pieces"]))
        self.assertFalse(p["attachment"]["is_primary"])
        prompt, _, _ = answer.render_packet_prompt("q", [p])
        self.assertIn("attachment 78 (alternate attachment, role unset)", prompt)

    def test_the_abstract_result_sentence_is_own_established_via_the_authors_abstract(self):
        nb = self.nbhd_around(34974)
        unit_list, by_id = packet.neighborhood_units(nb, self.lib)
        uid = self.unit_id(unit_list, "Across these levels of organization")
        p = packet.build_packet(nb, unit_list, by_id, proposition([uid]), library=self.lib, child_id="c5")
        self.assertEqual(p["part_attribution"]["p1"], "own_established")
        self.assertIn("authors_abstract_result_statement", p["attribution"]["p1"]["bases"])


if __name__ == "__main__":
    unittest.main()
