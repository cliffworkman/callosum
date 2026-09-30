"""Stage A (plural evidence anchors, 2026-09-29 authorization): _candidate_spans' continuation joining
and marshal_and_verify's plural-anchor persistence.

Covers the actual regression shape end to end: a sentence split across two adjacent, seam-verified,
section-unchanged chunks becomes ONE joined candidate span (never two independently-incomplete ones),
and the resulting persisted proposition carries a full, ordered `anchors` list alongside the existing
singular fields -- which stay populated (backward compatible with validate_ledger, confirmed by
reading it directly: it hard-requires evidence_anchor_chunk_id truthy/positive-int on every row) but
whose coordinate_precision is honestly downgraded to "region" whenever more than one anchor is
involved (invariant #2: a single "exact" rectangle cannot correctly represent text that spans two
real chunk locations, even though each individual anchor's OWN precision can independently be exact).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.backend.summarization.verification import VerificationResult
from experiments.ask_cli_revised import propositions
from experiments.ask_cli_revised.retrieval import ContextPacket


class FakeTrace:
    def __init__(self):
        self.decisions = []

    def decision(self, stage, reason_code, *, kept, **inputs):
        self.decisions.append((stage, reason_code, kept))


def _chunk(chunk_id, text, *, attachment_id=1, page=1, section="results", char_start=0, char_end=None,
           checksum="sha-a", tool="pymupdf", version="1", y0=0, y1=10):  # fmt: skip
    return {
        "chunk_id": chunk_id, "text": text, "section": section, "chunk_type": None, "evidence_role": None,
        "attachment_id": attachment_id, "page_start": page, "page_end": page,
        "char_start": char_start, "char_end": char_end if char_end is not None else char_start + len(text),
        "bbox_json": [{"page": page, "x0": 0, "y0": y0, "x1": 100, "y1": y1}],
        "extraction_tool": tool, "extraction_version": version, "source_attachment_checksum": checksum,
    }  # fmt: skip


# The real 14388/14389 regression shape, as separate chunk texts (mirrors TRIAGE_HANDBACK.md Finding 1).
CHUNK_A_TEXT = "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a"
CHUNK_B_TEXT = "universal pathogen avoidance byproduct hypothesis."


class CandidateSpansJoiningTests(unittest.TestCase):
    def _packet(self, chunk_a, chunk_b):
        return ContextPacket(
            retrieval_anchor_chunk_id=chunk_a["chunk_id"],
            subquestion_id="s1",
            paper_id=27,
            chunks=[chunk_a, chunk_b],
        )

    def test_a_genuinely_continuous_pair_is_joined_into_one_span_when_conn_is_given(self):
        chunk_a = _chunk(1, CHUNK_A_TEXT, char_start=0, char_end=98)
        chunk_b = _chunk(2, CHUNK_B_TEXT, char_start=99, char_end=149)
        packet = self._packet(chunk_a, chunk_b)
        with patch.object(propositions, "_attachment_checksum", return_value="sha-a"), \
             patch.object(propositions, "_attachment_chunks_ordered", return_value=[chunk_a, chunk_b]):  # fmt: skip
            spans = propositions._candidate_spans(packet, FakeTrace(), conn=object())
        joined = [s for s in spans if s.get("anchors")]
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0]["text"], CHUNK_A_TEXT + " " + CHUNK_B_TEXT)
        self.assertEqual([a["chunk_id"] for a in joined[0]["anchors"]], [1, 2])
        self.assertEqual(joined[0]["anchors"][0]["kind"], "continuation")
        # No leftover, separately-incomplete single-chunk spans for either half of the join.
        self.assertNotIn(CHUNK_A_TEXT, [s["text"] for s in spans if not s.get("anchors")])
        self.assertNotIn(CHUNK_B_TEXT, [s["text"] for s in spans if not s.get("anchors")])

    def test_without_conn_behavior_is_unchanged_two_separate_incomplete_spans(self):
        """Backward compatibility: every existing caller/test of _candidate_spans that never passes
        conn (the overwhelming majority) gets today's exact behavior, unmodified."""
        chunk_a = _chunk(1, CHUNK_A_TEXT, char_start=0, char_end=98)
        chunk_b = _chunk(2, CHUNK_B_TEXT, char_start=99, char_end=149)
        packet = self._packet(chunk_a, chunk_b)
        spans = propositions._candidate_spans(packet, FakeTrace())
        self.assertEqual([s["text"] for s in spans], [CHUNK_A_TEXT, CHUNK_B_TEXT])
        self.assertFalse(any(s.get("anchors") for s in spans))

    def test_a_non_continuous_pair_is_never_joined(self):
        chunk_a = _chunk(1, "The association was null.", char_start=0, char_end=26)
        chunk_b = _chunk(2, "Participants completed a survey.", char_start=27, char_end=60)
        packet = self._packet(chunk_a, chunk_b)
        with patch.object(propositions, "_attachment_checksum", return_value="sha-a"), \
             patch.object(propositions, "_attachment_chunks_ordered", return_value=[chunk_a, chunk_b]):  # fmt: skip
            spans = propositions._candidate_spans(packet, FakeTrace(), conn=object())
        self.assertFalse(any(s.get("anchors") for s in spans))
        self.assertEqual({s["text"] for s in spans}, {"The association was null.", "Participants completed a survey."})


def verified_result():
    # A real VerificationResult, not a SimpleNamespace: marshal_and_verify's Stage A override path
    # calls dataclasses.replace() on whatever verify_many returns, exactly as the real
    # LocalCitationVerifier does in production -- a fake must be the real (frozen) dataclass here.
    return VerificationResult(
        chunk_id=1, quote_text="x", status="verified", retrieval_confidence=0.9, quote_confidence=1.0,
        support_confidence=0.8, contradiction_confidence=0.0, page_start=1, page_end=1, bbox_json=None,
        coordinate_precision="exact", chunk_version_verified_against="v1", embedding_version_verified_against="v1",
    )  # fmt: skip


def _fake_status(*, retrieval_confidence, quote_confidence, support_confidence, contradiction_confidence=None):
    """Mirrors LocalCitationVerifier._status's real threshold logic (invariant #1: retrieval>=0.7,
    quote=1.0, support>=0.55) closely enough for these tests -- not a redefinition of the thresholds,
    just a same-shaped fake so marshal_and_verify's real call to verifier._status(...) has something
    to call, matching how every other fake `verifier` in this test suite already stands in for the
    real LocalCitationVerifier's public surface."""
    if contradiction_confidence is not None and contradiction_confidence >= 0.5 and contradiction_confidence > support_confidence:  # fmt: skip
        return "contradicted"
    if retrieval_confidence >= 0.7 and quote_confidence >= 1.0 and support_confidence >= 0.55:
        return "verified"
    if retrieval_confidence >= 0.7 or support_confidence >= 0.55:
        return "weak"
    return "unverified"


class MarshalAndVerifyPluralAnchorTests(unittest.TestCase):
    def _joined_packet_and_span(self):
        chunk_a = _chunk(1, CHUNK_A_TEXT, page=5)
        chunk_b = _chunk(2, CHUNK_B_TEXT, page=5)
        packet = SimpleNamespace(
            discarded=False,
            discard_reason=None,
            chunks=[chunk_a, chunk_b],
            subquestion_id="s1",
            paper_id=27,
            retrieval_anchor_chunk_id=1,
            retrieval_score=0.8,
            grown=[2],
        )
        span = {
            "span_id": "e1",
            "chunk_id": 1,
            "text": CHUNK_A_TEXT + " " + CHUNK_B_TEXT,
            "evidence_role": None,
            "chunk_type": None,
            "anchors": [
                {"kind": "continuation", "chunk_id": 1, "span_id": "e1a", "text": CHUNK_A_TEXT},
                {"kind": "continuation", "chunk_id": 2, "span_id": "e1b", "text": CHUNK_B_TEXT},
            ],
        }
        return packet, span, chunk_a, chunk_b

    def test_a_joined_span_persists_anchors_and_downgrades_singular_precision_to_region(self):
        packet, span, chunk_a, chunk_b = self._joined_packet_and_span()
        qwen = MagicMock()
        qwen.select_evidence.return_value = ["e1"]
        qwen.form_claim.return_value = "The stereotype is culturally shared, evidence against a universal hypothesis."
        qwen.map_obligations.return_value = ["s1-o1"]
        verifier = SimpleNamespace(
            verify_many=lambda conn, items, source_chunks: [verified_result() for _ in items],
            _status=_fake_status,
        )

        def source_chunk_for_id(conn, chunk_id):
            return SimpleNamespace(text=CHUNK_A_TEXT if chunk_id == 1 else CHUNK_B_TEXT, attachment_id=1,
                                    page_start=5, page_end=5, bbox_json=chunk_a["bbox_json"])  # fmt: skip

        with patch.object(propositions, "_source_chunk_for_id", side_effect=source_chunk_for_id), \
             patch.object(propositions, "locate_quote_for_attachment",
                           return_value=SimpleNamespace(found=False)):  # fmt: skip
            records = propositions.marshal_and_verify(
                None,
                verifier=verifier,
                qwen=qwen,
                packet=packet,
                subquestion_text="q",
                obligations=[{"field_id": "s1-o1", "note": "x"}],
                nomination_reason=[],
                origin="recovery",
                trace=FakeTrace(),
                candidate_spans=[span],
            )

        self.assertEqual(len(records), 1)
        record = records[0]
        # Backward-compatible singular fields stay populated, from the PRIMARY (first) anchor.
        self.assertEqual(record["evidence_anchor_chunk_id"], 1)
        self.assertEqual(record["evidence_span_id"], "e1")
        self.assertEqual(record["quote"], CHUNK_A_TEXT + " " + CHUNK_B_TEXT)
        # The coordinate-honesty contract: never claim a single exact rectangle for two real locations.
        self.assertEqual(record["verification"]["coordinate_precision"], "region")
        # The full, ordered, per-anchor detail is preserved separately.
        self.assertEqual(len(record["anchors"]), 2)
        self.assertEqual(record["anchors"][0]["chunk_id"], 1)
        self.assertEqual(record["anchors"][1]["chunk_id"], 2)
        self.assertEqual(record["verification"]["status"], "verified")

    def test_a_reconstruction_mismatch_is_rejected_defensively(self):
        """Belt-and-suspenders: if `quote` ever drifted from its own anchors' texts (should never happen
        by construction, but the check exists so a future refactor cannot silently break it), the
        candidate is refused rather than persisted with an unproven quote."""
        packet, span, chunk_a, chunk_b = self._joined_packet_and_span()
        span["text"] = "something that does not match the anchors at all"
        qwen = MagicMock()
        qwen.select_evidence.return_value = ["e1"]
        verifier = SimpleNamespace(verify_many=lambda conn, items, source_chunks: [verified_result() for _ in items])
        with patch.object(propositions, "_source_chunk_for_id", return_value=SimpleNamespace(text="x", attachment_id=1, page_start=1, page_end=1, bbox_json=None)):  # fmt: skip
            records = propositions.marshal_and_verify(
                None,
                verifier=verifier,
                qwen=qwen,
                packet=packet,
                subquestion_text="q",
                obligations=[],
                nomination_reason=[],
                origin="recovery",
                trace=FakeTrace(),
                candidate_spans=[span],
            )
        self.assertEqual(records, [])

    def test_each_anchors_own_text_must_be_verbatim_in_its_own_chunk(self):
        """canonical_text_contains is never relaxed: if one anchor's text is NOT actually verbatim in
        its own chunk (a corrupted/foreign anchor), the whole candidate is refused."""
        packet, span, chunk_a, chunk_b = self._joined_packet_and_span()
        qwen = MagicMock()
        qwen.select_evidence.return_value = ["e1"]
        verifier = SimpleNamespace(
            verify_many=lambda conn, items, source_chunks: [verified_result() for _ in items],
            _status=_fake_status,
        )

        def source_chunk_for_id(conn, chunk_id):
            # chunk 2's real text does NOT contain the anchor's claimed text -- a corrupted anchor.
            text = CHUNK_A_TEXT if chunk_id == 1 else "totally unrelated real chunk text"
            return SimpleNamespace(text=text, attachment_id=1, page_start=5, page_end=5, bbox_json=None)

        with patch.object(propositions, "_source_chunk_for_id", side_effect=source_chunk_for_id), \
             patch.object(propositions, "locate_quote_for_attachment", return_value=SimpleNamespace(found=False)):  # fmt: skip
            records = propositions.marshal_and_verify(
                None,
                verifier=verifier,
                qwen=qwen,
                packet=packet,
                subquestion_text="q",
                obligations=[],
                nomination_reason=[],
                origin="recovery",
                trace=FakeTrace(),
                candidate_spans=[span],
            )
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
