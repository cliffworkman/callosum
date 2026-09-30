"""Stage A (plural evidence anchors, 2026-09-29 authorization): cross-chunk continuation detection.

Two independent, required checks before two adjacent chunks are treated as one continuous source
passage: (1) contract_directed/seams.py's own geometry-aware verify_seam (reused unmodified -- same
attachment/checksum/extraction identity, contiguous stream offsets, same column, bounded vertical
gap, no intervening block BY GEOMETRY, and the linguistic left-open/right-continues check); (2)
section_unchanged -- a chunks.section equality check this module adds, closing a real gap verify_seam
does NOT close on its own: a chunk that is a single, recognized section heading (e.g. bare "Methods")
is silently skipped by make_chunk_drafts (confirmed empirically, see the docstring below) and produces
no chunk row at all -- so it can never appear in ANY chunk-table-sourced geometry index, including
verify_seam's own `page_boxes`. section_tracker.current_section still advances across a skipped
heading, so comparing chunks.section across the candidate pair catches exactly this case.
"""

from __future__ import annotations

import unittest

from experiments.ask_cli_revised import continuation as cont
from experiments.ask_cli_revised.contract_directed import seams


def _chunk(chunk_id, text, *, attachment_id=1, page=1, x0=0, y0=0, x1=100, y1=10, section=None,
           char_start=None, char_end=None, checksum="sha-a", tool="pymupdf", version="1"):  # fmt: skip
    return {
        "chunk_id": chunk_id, "attachment_id": attachment_id, "text": text, "section": section,
        "page_start": page, "page_end": page, "char_start": char_start, "char_end": char_end,
        "bbox_json": [{"page": page, "x0": x0, "y0": y0, "x1": x1, "y1": y1}],
        "extraction_tool": tool, "extraction_version": version, "source_attachment_checksum": checksum,
    }  # fmt: skip


class SectionUnchangedTests(unittest.TestCase):
    def test_same_section_is_unchanged(self):
        a = _chunk(1, "x", section="methods")
        b = _chunk(2, "y", section="methods")
        self.assertTrue(cont.section_unchanged(a, b))

    def test_different_section_is_changed(self):
        a = _chunk(1, "x", section="methods")
        b = _chunk(2, "y", section="results")
        self.assertFalse(cont.section_unchanged(a, b))

    def test_none_to_a_named_section_is_changed(self):
        """The empirically-confirmed real case: a skipped heading advances section_tracker's state
        from None to a real section, even though the heading itself produced no chunk row."""
        a = _chunk(1, "x", section=None)
        b = _chunk(2, "y", section="methods")
        self.assertFalse(cont.section_unchanged(a, b))


class PageBoxesForTests(unittest.TestCase):
    def test_builds_boxes_only_for_the_requested_page(self):
        chunks = [_chunk(1, "a", page=1), _chunk(2, "b", page=2), _chunk(3, "c", page=1)]
        boxes = cont.page_boxes_for(chunks, page=1)
        self.assertEqual(set(boxes), {1, 3})
        self.assertIsInstance(boxes[1], seams.Box)


class DetectContinuationTests(unittest.TestCase):
    def test_a_genuinely_continuous_pair_is_established(self):
        a = _chunk(
            1, "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a",
            char_start=0, char_end=98, section="results", y0=0, y1=10,
        )  # fmt: skip
        b = _chunk(
            2, "universal pathogen avoidance byproduct hypothesis.",
            char_start=99, char_end=149, section="results", y0=11, y1=21,
        )  # fmt: skip
        verdict = cont.detect_continuation(a, b, attachment_checksum="sha-a", chunks_on_attachment=[a, b])
        self.assertTrue(verdict["is_continuation"])
        self.assertEqual(verdict["seam_state"], "established")
        self.assertTrue(verdict["section_unchanged"])
        self.assertTrue(verdict["seam_checks"]["contiguous_stream_offsets"])

    def test_a_silently_skipped_heading_between_them_is_refused_even_though_offsets_look_contiguous(self):
        """Reproduces the empirically-confirmed extraction.py behavior directly: two chunks whose
        char_start/char_end are exactly contiguous (gap=1, as if nothing were skipped) but whose
        section differs, because a bare recognized heading block sat between them and was silently
        dropped by make_chunk_drafts without advancing the cursor. verify_seam's own geometry-based
        no_intervening_block check ALSO cannot see this (the heading produced no chunk row, so it's
        not in chunks_on_attachment/page_boxes either) -- only section_unchanged catches it."""
        a = _chunk(
            1, "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a",
            char_start=0, char_end=98, section=None, y0=0, y1=10,
        )  # fmt: skip
        b = _chunk(
            2, "universal pathogen avoidance byproduct hypothesis.",
            char_start=99, char_end=149, section="methods", y0=11, y1=21,
        )  # fmt: skip
        verdict = cont.detect_continuation(a, b, attachment_checksum="sha-a", chunks_on_attachment=[a, b])
        self.assertFalse(verdict["is_continuation"])
        self.assertFalse(verdict["section_unchanged"])
        self.assertIn("section_changed_between_chunks", verdict["seam_reasons"])
        # The geometry/offset checks alone would have looked clean -- proving section_unchanged is
        # doing real, independent work here, not just duplicating what verify_seam already refused.
        self.assertEqual(verdict["seam_state"], "established")

    def test_a_real_intervening_block_is_refused_by_the_reused_seam_verifier(self):
        """A genuine third chunk (its own persisted row) sits between the two candidates -- verify_seam's
        own no_intervening_block / contiguous_stream_offsets checks catch this without any help from
        section_unchanged."""
        a = _chunk(1, "the effect was significant for group a but not for", char_start=0, char_end=52, section="results", y0=0, y1=10)  # fmt: skip
        middle = _chunk(3, "Table 1 here", char_start=53, char_end=65, section="results", y0=11, y1=20)  # fmt: skip
        b = _chunk(2, "group b.", char_start=66, char_end=74, section="results", y0=21, y1=30)  # fmt: skip
        verdict = cont.detect_continuation(a, b, attachment_checksum="sha-a", chunks_on_attachment=[a, middle, b])
        self.assertFalse(verdict["is_continuation"])
        self.assertEqual(verdict["seam_state"], "not_established")

    def test_non_continuous_text_is_refused_even_with_perfect_geometry_and_offsets(self):
        """Two adjacent, offset-contiguous, same-section, vertically-stacked chunks whose text simply
        does not form one sentence -- the linguistic check inside verify_seam still refuses."""
        a = _chunk(1, "The association was null.", char_start=0, char_end=26, section="results", y0=0, y1=10)  # fmt: skip
        b = _chunk(2, "Participants completed a survey.", char_start=27, char_end=60, section="results", y0=11, y1=21)  # fmt: skip
        verdict = cont.detect_continuation(a, b, attachment_checksum="sha-a", chunks_on_attachment=[a, b])
        self.assertFalse(verdict["is_continuation"])


if __name__ == "__main__":
    unittest.main()
