import sqlite3
import unittest

from experiments.ask_cli_revised.contract_directed import freeze, seams, sections, units

DB = freeze.SLICE_ROOT / "library.sqlite"


def ro():
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    return con


class SegmentTests(unittest.TestCase):
    def test_offsets_are_exact_slices(self):
        text = "First sentence here. Second one follows! Third?  Fourth ends."
        spans = units.segment(text)
        self.assertEqual(
            [text[s:e] for s, e in spans], ["First sentence here.", "Second one follows!", "Third?", "Fourth ends."]
        )

    def test_abbreviations_decimals_and_initials_do_not_split(self):
        text = "Smith et al. reported this. The mean was 1.5 points. J. Doe agreed. See Fig. 2 for details."
        self.assertEqual(
            [text[s:e] for s, e in units.segment(text)],
            ["Smith et al. reported this.", "The mean was 1.5 points.", "J. Doe agreed.", "See Fig. 2 for details."],
        )

    def test_citation_numeral_after_period_still_ends_the_sentence(self):
        text = "They differ across cultures.25 While these studies did not examine it, they matter."
        self.assertEqual(
            [text[s:e] for s, e in units.segment(text)],
            ["They differ across cultures.25", "While these studies did not examine it, they matter."],
        )

    def test_terminal_and_continuation_predicates(self):
        self.assertTrue(units.ends_terminal("It ended."))
        self.assertTrue(units.ends_terminal("It ended.25"))
        self.assertFalse(units.ends_terminal("providing evidence against a"))
        self.assertTrue(units.starts_as_continuation("universal pathogen avoidance"))
        self.assertFalse(units.starts_as_continuation("The next sentence"))
        self.assertFalse(units.starts_as_continuation("25 participants"))

    def test_every_piece_is_an_exact_slice_over_random_text(self):
        text = "  Alpha beta.\n\nGamma delta! Epsilon. "
        for piece in units.chunk_pieces(1, text):
            self.assertEqual(text[piece.start : piece.end], piece.text)


def box_chunk(cid, y0, y1, x0=72.0, x1=540.0, *, char=(0, 10), text="a", page=3, **over):
    base = {
        "chunk_id": cid, "attachment_id": 1, "source_attachment_checksum": "abc", "extraction_tool": "pymupdf",
        "extraction_version": "1", "page_start": page, "page_end": page, "char_start": char[0], "char_end": char[1],
        "bbox_json": [{"page": page, "block": cid, "line": 0, "span": 0, "x0": x0, "y0": y0, "x1": x1, "y1": y1}], "text": text,
    }  # fmt: skip
    return base | over


def boxes_of(*chunks):
    return {c["chunk_id"]: seams.chunk_box(c) for c in chunks}


class SeamSyntheticTests(unittest.TestCase):
    def verdict(self, a, b, others=(), checksum="abc", allow_column_switch=False):
        return seams.verify_seam(
            a,
            b,
            attachment_checksum=checksum,
            page_boxes=boxes_of(a, b, *others),
            allow_column_switch=allow_column_switch,
        )

    def setUp(self):
        self.a = box_chunk(
            1, 350.0, 362.0, char=(100, 200), text="results suggest the effect is shared, providing evidence against a"
        )
        self.b = box_chunk(2, 377.0, 389.0, x1=326.0, char=(201, 250), text="universal pathogen avoidance hypothesis.")

    def test_established_when_every_check_passes(self):
        v = self.verdict(self.a, self.b)
        self.assertEqual(v.state, "established", v.reasons)

    def test_not_established_across_pages(self):
        b = self.b | {"page_start": 4, "page_end": 4}
        self.assertEqual(self.verdict(self.a, b).state, "not_established")

    def test_not_established_when_stream_offsets_are_not_contiguous(self):
        v = self.verdict(self.a, self.b | {"char_start": 900, "char_end": 950})
        self.assertIn("contiguous_stream_offsets", v.reasons)

    def columns(self):
        a = box_chunk(1, 700.0, 712.0, x0=72.0, x1=300.0, char=(100, 200), text="the effect is shared and a")
        b = box_chunk(2, 60.0, 72.0, x0=320.0, x1=540.0, char=(201, 250), text="universal pathogen.")
        return a, b

    def test_a_column_switch_is_verified_when_a_ends_its_column_and_b_starts_the_next(self):
        a, b = self.columns()
        v = self.verdict(a, b, allow_column_switch=True)
        self.assertEqual(v.state, "established", v.reasons)
        self.assertTrue(v.checks["column_switch_verified"])

    def test_a_column_switch_is_refused_by_default_because_geometry_alone_cannot_verify_it(self):
        a, b = self.columns()
        v = self.verdict(a, b)  # default: column switches are not verified
        self.assertEqual(v.state, "not_established")
        self.assertFalse(seams.ALLOW_COLUMN_SWITCH)

    def test_a_column_switch_is_refused_if_body_text_lies_below_a_or_above_b(self):
        a, b = self.columns()
        below = box_chunk(
            3, 720.0, 732.0, x0=72.0, x1=300.0, char=(5000, 5100), text="Another paragraph continues below."
        )
        self.assertEqual(self.verdict(a, b, others=(below,), allow_column_switch=True).state, "not_established")
        above = box_chunk(
            4, 40.0, 52.0, x0=320.0, x1=540.0, char=(6000, 6100), text="A paragraph above the right column start."
        )
        self.assertEqual(self.verdict(a, b, others=(above,), allow_column_switch=True).state, "not_established")

    def test_bare_page_numbers_and_full_width_headers_do_not_block_a_column_switch(self):
        a, b = self.columns()
        page_number = box_chunk(5, 760.0, 770.0, x0=180.0, x1=190.0, char=(7000, 7002), text="13")
        header = box_chunk(6, 30.0, 40.0, x0=54.0, x1=558.0, char=(8000, 8100), text="Workman et al. The stereotype")
        self.assertEqual(
            self.verdict(a, b, others=(page_number, header), allow_column_switch=True).state, "established"
        )

    def test_a_column_switch_going_left_is_refused_because_reading_order_is_not_that(self):
        a, b = self.columns()
        reversed_b = box_chunk(2, 60.0, 72.0, x0=20.0, x1=60.0, char=(201, 250), text="universal pathogen.")
        self.assertEqual(self.verdict(a, reversed_b, allow_column_switch=True).state, "not_established")

    def test_not_established_with_an_intervening_block(self):
        between = box_chunk(3, 364.0, 376.0, char=(5000, 5100), text="Figure caption")
        v = self.verdict(self.a, self.b, others=(between,))
        self.assertIn("no_intervening_block", v.reasons)

    def test_not_established_when_the_left_text_is_complete_or_the_right_does_not_continue(self):
        self.assertIn("left_open", self.verdict(self.a | {"text": "A full sentence."}, self.b).reasons)
        self.assertIn("right_continues", self.verdict(self.a, self.b | {"text": "Universal pathogen."}).reasons)

    def test_not_established_for_a_different_attachment_or_checksum(self):
        self.assertIn("same_attachment", self.verdict(self.a, self.b | {"attachment_id": 2}).reasons)
        self.assertIn(
            "same_source_checksum", self.verdict(self.a, self.b | {"source_attachment_checksum": "zzz"}).reasons
        )
        self.assertIn("checksum_matches_attachment_row", self.verdict(self.a, self.b, checksum="other").reasons)

    def test_not_established_without_geometry_or_for_plain_text(self):
        a = self.a | {"bbox_json": None}
        self.assertEqual(
            seams.verify_seam(a, self.b, attachment_checksum="abc", page_boxes={}).state, "not_established"
        )
        plain = self.a | {"extraction_tool": "plain-text"}
        self.assertIn("geometry_extractor", self.verdict(plain, self.b | {"extraction_tool": "plain-text"}).reasons)

    def test_bbox_json_accepts_both_the_decoded_and_the_string_form(self):
        decoded = self.a["bbox_json"]
        import json

        self.assertEqual(seams.parse_bbox(json.dumps(decoded)), decoded)
        self.assertEqual(seams.parse_bbox(decoded), decoded)
        self.assertEqual(seams.parse_bbox(None), [])
        self.assertEqual(seams.parse_bbox("not json"), [])


class BuildUnitsTests(unittest.TestCase):
    def chunks(self):
        return [
            {"chunk_id": 1, "text": "First sentence. This one continues into the"},
            {"chunk_id": 2, "text": "next chunk. Then a new sentence."},
        ]

    def test_established_seam_builds_one_unit_with_two_exact_pieces(self):
        ok = seams.SeamVerdict("established", (), {})
        out = units.build_units(self.chunks(), lambda a, b: ok)
        joined = [u for u in out if u.join == "verified_seam"]
        self.assertEqual(len(joined), 1)
        self.assertEqual([p.chunk_id for p in joined[0].pieces], [1, 2])
        self.assertEqual(joined[0].text, "This one continues into the next chunk.")
        self.assertEqual(out[0].text, "First sentence.")
        for u in out:
            for p in u.pieces:
                src = {c["chunk_id"]: c["text"] for c in self.chunks()}[p.chunk_id]
                self.assertEqual(src[p.start : p.end], p.text)

    def test_unresolved_seam_keeps_two_open_fragments(self):
        bad = seams.SeamVerdict("not_established", ("no_intervening_block",), {})
        out = units.build_units(self.chunks(), lambda a, b: bad)
        self.assertFalse(any(u.join == "verified_seam" for u in out))
        left = next(u for u in out if u.text.startswith("This one"))
        right = next(u for u in out if u.text.startswith("next chunk"))
        self.assertTrue(left.open_right)
        self.assertTrue(right.open_left)
        self.assertEqual(left.seam["state"], "not_established")

    def test_a_complete_left_chunk_never_asks_the_verifier(self):
        calls = []
        chunks = [{"chunk_id": 1, "text": "All done."}, {"chunk_id": 2, "text": "another one."}]
        units.build_units(chunks, lambda a, b: calls.append((a, b)))
        self.assertEqual(calls, [])


class SectionTests(unittest.TestCase):
    def test_family_and_state(self):
        self.assertEqual(sections.family_of("methods"), ("methods", "labeled"))
        self.assertEqual(sections.family_of(None, "results"), ("results", "grobid"))
        self.assertEqual(sections.family_of(None, None), (None, "unknown"))
        self.assertEqual(sections.family_of("weird"), (None, "unknown"))

    def test_kind_directed_families_are_a_union_in_first_seen_order(self):
        self.assertEqual(sections.families_for_units(["operation"]), ("methods", "results", "abstract"))
        self.assertEqual(
            sections.families_for_units(["relationship", "kinds", "operation"]),
            ("results", "discussion", "abstract", "methods"),
        )

    def test_pools_are_unions_that_keep_unlabeled_chunks_and_never_references(self):
        chunks = [
            {"chunk_id": 1, "section": "methods"},
            {"chunk_id": 2, "section": "introduction"},
            {"chunk_id": 3, "section": None},
            {"chunk_id": 4, "section": "references"},
            {"chunk_id": 5, "section": None, "grobid_kind": "discussion"},
        ]
        self.assertEqual([c["chunk_id"] for c in sections.family_pool(chunks, ("methods",))], [1, 3])

    def test_a_paper_without_any_labels_gets_its_whole_pool(self):
        chunks = [{"chunk_id": i, "section": None} for i in range(5)]
        self.assertEqual(len(sections.family_pool(chunks, ("methods",))), 5)


@unittest.skipUnless(DB.is_file(), "disposable library copy not present")
class RealSeamTests(unittest.TestCase):
    """The U9 seam and its negatives, on the real frozen library."""

    @classmethod
    def setUpClass(cls):
        cls.con = ro()

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def chunk(self, cid):
        row = dict(self.con.execute("select * from chunks where id=?", (cid,)).fetchone())
        row["chunk_id"] = row["id"]
        return row

    def page_boxes(self, attachment_id, page):
        rows = self.con.execute(
            "select * from chunks where attachment_id=? and page_start=?", (attachment_id, page)
        ).fetchall()
        out = {}
        for r in rows:
            d = dict(r)
            d["chunk_id"] = d["id"]
            box = seams.chunk_box(d)
            if box is not None:
                out[d["chunk_id"]] = box
        return out

    def attachment_checksum(self, attachment_id):
        return self.con.execute("select checksum from attachments where id=?", (attachment_id,)).fetchone()["checksum"]

    def test_u9_seam_14388_to_14389_is_established(self):
        a, b = self.chunk(14388), self.chunk(14389)
        v = seams.verify_seam(a, b, attachment_checksum=self.attachment_checksum(78), page_boxes=self.page_boxes(78, 3))
        self.assertEqual(v.state, "established", (v.reasons, v.checks))
        out = units.build_units([a, b], lambda x, y: v)
        joined = [u for u in out if u.join == "verified_seam"]
        self.assertEqual(len(joined), 1)
        self.assertTrue(joined[0].text.endswith("hypothesis."))
        self.assertIn("providing evidence against a universal pathogen avoidance byproduct hypothesis", joined[0].text)

    def test_u9_pieces_are_verbatim_in_their_own_chunks(self):
        a, b = self.chunk(14388), self.chunk(14389)
        v = seams.verify_seam(a, b, attachment_checksum=self.attachment_checksum(78), page_boxes=self.page_boxes(78, 3))
        out = units.build_units([a, b], lambda x, y: v)
        joined = next(u for u in out if u.join == "verified_seam")
        by_id = {14388: a["text"], 14389: b["text"]}
        for piece in joined.pieces:
            self.assertEqual(by_id[piece.chunk_id][piece.start : piece.end], piece.text)

    def test_reversed_or_distant_chunks_are_not_a_seam(self):
        a, b = self.chunk(14389), self.chunk(14388)  # reversed
        v = seams.verify_seam(a, b, attachment_checksum=self.attachment_checksum(78), page_boxes=self.page_boxes(78, 3))
        self.assertEqual(v.state, "not_established")
        far = self.chunk(14429)
        v = seams.verify_seam(
            self.chunk(14388), far, attachment_checksum=self.attachment_checksum(78), page_boxes=self.page_boxes(78, 3)
        )
        self.assertEqual(v.state, "not_established")


if __name__ == "__main__":
    unittest.main()
