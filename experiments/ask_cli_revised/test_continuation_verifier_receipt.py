"""Stage A release-readiness item 1 (2026-09-29): the continuation-anchor verification RECEIPT.

Proves, with a REAL app.backend.summarization.verification.LocalCitationVerifier instance -- not
the SimpleNamespace fake test_continuation_anchors.py uses to isolate the Stage A override logic --
exactly what text reaches each downstream stage for a genuine, seam-verified A+B continuation:

1. LocalCitationVerifier's own internal quote check (_quote_confidence, via canonical_text_contains)
2. LocalCitationVerifier's own internal NLI premise (support_scorer.support_and_contradiction_many)
3. The persisted sealed-ledger record (propositions.marshal_and_verify's output)
4. overview_evidence.build_units()'s per-unit passage/locators
5. Researcher-facing citation rendering (ledger_renderer._evidence_locator_line)

Only DB-touching internals (_embedding_lookup, locate_quote_for_attachment) are stubbed -- with
their own call arguments recorded too, so the stub boundary itself is inspectable. Every other line
of LocalCitationVerifier.verify_many, propositions.marshal_and_verify, and
overview_evidence.build_units runs for real, unmodified. No NLI threshold, encoder, or #20 semantics
are touched anywhere in this file.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.backend.summarization.generators import SourceChunk
from app.backend.summarization.verification import LocalCitationVerifier, VerificationConfig
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import propositions, stages
from experiments.ask_cli_revised.overview_test_support import CONTRACT, SUBQUESTIONS


class FakeTrace:
    def decision(self, *a, **k):
        pass


class RecordingSupportScorer:
    """A real object matching SupportScorer's actual call shape (support_and_contradiction_many),
    recording every `pairs` argument it is ever handed -- the exact NLI premise/hypothesis text."""

    def __init__(self):
        self.calls: list[list[tuple[str, str]]] = []

    def support_and_contradiction_many(self, pairs):
        self.calls.append(list(pairs))
        return [(0.9, 0.02) for _ in pairs]  # a fixed, high-support answer; not what this test checks


CHUNK_A_TEXT = "results suggest the anomalous-is-bad stereotype is culturally shared, providing evidence against a"
CHUNK_B_TEXT = "universal pathogen avoidance byproduct hypothesis."
JOINED_TEXT = CHUNK_A_TEXT + " " + CHUNK_B_TEXT
PAPER_ID, CHUNK_A_ID, CHUNK_B_ID = 27, 14388, 14389


def _real_verifier(support_scorer, quote_calls: list[tuple[str, str]]):
    """A REAL LocalCitationVerifier. model/vector_store are simple stand-ins whose own methods are
    never exercised by this test's path (retrieval_confidence is not what's being proven here);
    _embedding_lookup is stubbed only to avoid a real DB connection, with its own args recorded."""
    model = SimpleNamespace(encode_texts=lambda texts: [[0.0] * 8 for _ in texts], name="fake-model", version="1")
    # A genuine, high-confidence retrieval hit for the primary (cited) chunk -- retrieval_confidence
    # is not what this test is proving (the quote/NLI premise question is), but leaving it at a real
    # zero would make status "weak" rather than "verified" for an unrelated reason and, more
    # importantly, stages.seal()'s own _ledger() filter (status == "verified" only) would then drop
    # the record before it ever reaches sealed["verified_propositions"] -- silently emptying every
    # downstream stage this test also checks (build_units) for a reason that has nothing to do with
    # continuation anchors at all.
    vector_store = SimpleNamespace(
        search=lambda conn, *, vector, top_k, candidate_embedding_ids: [SimpleNamespace(embedding_id=1, distance=0.0)]
    )
    verifier = LocalCitationVerifier(
        model=model, vector_store=vector_store, config=VerificationConfig(), support_scorer=support_scorer
    )
    verifier._embedding_lookup = lambda conn, *, candidate_chunk_ids: {1: candidate_chunk_ids[0]}

    # canonical_text_contains is REAL and unpatched -- this wraps _quote_confidence only to RECORD
    # its (citation.quote, cited_chunk.text) inputs, exactly the pair the internal, structurally
    # single-chunk check receives before propositions.py's own override runs. locate_quote_for_
    # attachment (a real DB/filesystem lookup) is stubbed to `found=False` so the real
    # canonical_text_contains gate still runs and its true result still drives the return value.
    real_quote_confidence = verifier._quote_confidence

    def spying_quote_confidence(conn, *, citation, cited_chunk):
        quote_calls.append((citation.quote, cited_chunk.text))
        with patch(
            "app.backend.summarization.verification.locate_quote_for_attachment",
            return_value=SimpleNamespace(found=False),
        ):
            return real_quote_confidence(conn, citation=citation, cited_chunk=cited_chunk)

    verifier._quote_confidence = spying_quote_confidence
    return verifier


def _joined_packet():
    chunk_a = {
        "chunk_id": CHUNK_A_ID, "text": CHUNK_A_TEXT, "section": "results", "chunk_type": None,
        "evidence_role": None, "attachment_id": 1, "page_start": 5, "page_end": 5,
    }  # fmt: skip
    chunk_b = {
        "chunk_id": CHUNK_B_ID, "text": CHUNK_B_TEXT, "section": "results", "chunk_type": None,
        "evidence_role": None, "attachment_id": 1, "page_start": 5, "page_end": 5,
    }  # fmt: skip
    packet = SimpleNamespace(
        discarded=False, discard_reason=None, chunks=[chunk_a, chunk_b], subquestion_id="s1",
        paper_id=PAPER_ID, retrieval_anchor_chunk_id=CHUNK_A_ID, retrieval_score=0.8, grown=[CHUNK_B_ID],
    )  # fmt: skip
    span = {
        "span_id": "e1",
        "chunk_id": CHUNK_A_ID,
        "text": JOINED_TEXT,
        "evidence_role": None,
        "chunk_type": None,
        "anchors": [
            {"kind": "continuation", "chunk_id": CHUNK_A_ID, "span_id": "e1a", "text": CHUNK_A_TEXT},
            {"kind": "continuation", "chunk_id": CHUNK_B_ID, "span_id": "e1b", "text": CHUNK_B_TEXT},
        ],
    }
    return packet, span


class ContinuationVerifierReceiptTests(unittest.TestCase):
    def setUp(self):
        self.support_scorer = RecordingSupportScorer()
        self.quote_calls: list[tuple[str, str]] = []
        self.verifier = _real_verifier(self.support_scorer, self.quote_calls)
        self.packet, self.span = _joined_packet()
        self.claim = "Prevalence of the culturally shared stereotype was found, contradicting a universal hypothesis."

        qwen = MagicMock()
        qwen.select_evidence.return_value = ["e1"]
        qwen.form_claim.return_value = self.claim
        qwen.map_obligations.return_value = []

        def source_chunk_for_id(conn, chunk_id):
            text = CHUNK_A_TEXT if chunk_id == CHUNK_A_ID else CHUNK_B_TEXT
            return SourceChunk(
                chunk_id=chunk_id, paper_id=PAPER_ID, attachment_id=1, text=text, page_start=5, page_end=5,
                chunk_version="v1",
            )  # fmt: skip

        with (
            patch.object(propositions, "_source_chunk_for_id", side_effect=source_chunk_for_id),
            # propositions._verify_continuation_anchors' own per-anchor coordinate resolution (a
            # SEPARATE call from the one this test is spying on inside _quote_confidence) also needs
            # locate_quote_for_attachment; conn=None here, so this call is stubbed the same honest
            # "not found -> region fallback" way, real DB access not being this test's concern.
            patch.object(propositions, "locate_quote_for_attachment", return_value=SimpleNamespace(found=False)),
        ):
            self.records = propositions.marshal_and_verify(
                None,
                verifier=self.verifier,
                qwen=qwen,
                packet=self.packet,
                subquestion_text="q",
                obligations=[],
                nomination_reason=[],
                origin="recovery",
                trace=FakeTrace(),
                candidate_spans=[self.span],
            )

    # ---- 1. LocalCitationVerifier's own internal quote check --------------------------------

    def test_internal_quote_confidence_receives_the_full_joined_quote_against_only_the_primary_chunk(self):
        """This is the structural fact Stage A's design report was explicit about: the REAL,
        UNMODIFIED _quote_confidence receives the whole joined text as `citation.quote` but only
        the PRIMARY chunk's own text as `cited_chunk.text` -- these do NOT match (the joined text
        is not a substring of chunk A's text alone), so canonical_text_contains correctly returns
        False and the internal check alone would score 0.0. This is exactly the gap Stage A's
        propositions.py-level override (item 3 below) exists to correct -- proven here to actually
        fire, not assumed."""
        self.assertEqual(len(self.quote_calls), 1)
        received_quote, received_chunk_text = self.quote_calls[0]
        self.assertEqual(received_quote, JOINED_TEXT)
        self.assertEqual(received_chunk_text, CHUNK_A_TEXT)  # primary chunk ONLY, not chunk B
        self.assertNotIn(CHUNK_B_TEXT, received_chunk_text)

    # ---- 2. LocalCitationVerifier's own internal NLI premise --------------------------------

    def test_the_nli_premise_is_the_full_joined_quote_not_just_the_primary_chunk(self):
        """verify_many's own `pairs = [(citation.quote, sentence) ...]` (read fresh, unmodified) uses
        citation.quote -- which propositions.py sets to the full joined text -- as the premise. This
        is the real, unmodified NLI call path; the fixed (0.9, 0.02) answer is not what's being
        checked here, only what text the scorer was actually handed."""
        self.assertEqual(len(self.support_scorer.calls), 1)
        ((premise, hypothesis),) = self.support_scorer.calls[0]
        self.assertEqual(premise, JOINED_TEXT)
        self.assertIn(CHUNK_B_TEXT, premise)  # chunk B's own text DOES reach the NLI premise
        self.assertEqual(hypothesis, self.claim)

    # ---- 3. The persisted sealed-ledger record ----------------------------------------------

    def test_the_persisted_record_carries_both_anchors_with_exact_coordinates_and_corrected_quote_confidence(self):
        self.assertEqual(len(self.records), 1)
        record = self.records[0]
        self.assertEqual(record["quote"], JOINED_TEXT)
        self.assertEqual(record["evidence_anchor_chunk_id"], CHUNK_A_ID)  # primary, backward compatible
        self.assertEqual([a["chunk_id"] for a in record["anchors"]], [CHUNK_A_ID, CHUNK_B_ID])
        self.assertEqual(record["anchors"][0]["text"], CHUNK_A_TEXT)
        self.assertEqual(record["anchors"][1]["text"], CHUNK_B_TEXT)
        # The override corrected what the internal, structurally-single-chunk check alone could not
        # establish: quote_confidence is 1.0 (both anchors verbatim + honest reconstruction), and
        # coordinate_precision is "region" (never a false "exact" for text spanning two locations).
        self.assertEqual(record["verification"]["quote"], 1.0)
        self.assertEqual(record["verification"]["coordinate_precision"], "region")
        self.assertEqual(record["verification"]["status"], "verified")  # support=0.9 clears the real threshold

    # ---- 4. overview_evidence.build_units()'s per-unit passage/locators ---------------------

    def test_overview_build_units_gets_the_full_passage_and_both_locators(self):
        sealed = stages.seal(
            CONTRACT,
            SUBQUESTIONS,
            self.records,
            [{"paper_id": PAPER_ID, "candidate_spans": [self.span]}],
            stages.det_coverage(SUBQUESTIONS, self.records, authority={"kind": "det", "role": "R"}),
        )
        units, claims = oe.build_units(sealed)
        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertEqual(unit["passage"], JOINED_TEXT)
        self.assertEqual([loc["chunk_id"] for loc in unit["locators"]], [CHUNK_A_ID, CHUNK_B_ID])

    # ---- 5. Researcher-facing citation rendering --------------------------------------------

    def test_rendering_names_both_source_anchors(self):
        from experiments.ask_cli_revised.ledger_renderer import _evidence_locator_line

        line = _evidence_locator_line(self.records[0])
        self.assertIn(f"chunk {CHUNK_A_ID}", line)
        self.assertIn(f"chunk {CHUNK_B_ID}", line)


if __name__ == "__main__":
    unittest.main()
