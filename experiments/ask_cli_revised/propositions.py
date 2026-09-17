"""Stage 6 evidence selection/claim formation -> Stage 7 verification -> ledger entries.

Qwen no longer has to copy exact quotes, invent IDs, fill a semantic tuple, and map obligations in one call.
Deterministic code exposes exact source spans; Qwen selects span IDs, interprets one span into one claim, and
maps the resulting claim to natural-language answer obligations in separate low-entropy steps.
"""

from __future__ import annotations

import re

from sqlalchemy import Connection

from app.backend.pdf_processing.extraction import canonical_text_contains
from app.backend.summarization.generators import CandidateCitation
from app.backend.summarization.verification import LocalCitationVerifier, _source_chunk_for_id
from experiments.ask_cli_revised.qwen import QwenTasks
from experiments.ask_cli_revised.retrieval import ContextPacket
from experiments.ask_cli_revised.trace import TraceWriter

_EXCLUDED_EVIDENCE_ROLES = frozenset({"bibliographic", "structural"})
_EXCLUDED_CHUNK_TYPES = frozenset(
    {
        "reference_entry",
        "running_head/footer",
        "heading_fragment",
        "publication_metadata",
        "keyword_line",
        "citation_instruction",
        "table_cell_debris",
        "math_or_symbol",
    }
)
_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n{2,}")
MAX_SPANS_PER_PACKET = 36


def _split_exact_spans(text: str) -> list[str]:
    """Return sentence-ish exact substrings without normalizing source text.

    This is deliberately a navigation aid, not a linguistic parser. Bad sentence boundaries cost recall only;
    selected text is still checked as an exact substring of its source chunk before verification.
    """
    if not text.strip():
        return []
    spans: list[str] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        piece = text[start : match.start()].strip()
        if piece:
            spans.append(piece)
        start = match.end()
    tail = text[start:].strip()
    if tail:
        spans.append(tail)
    return spans or [text.strip()]


def _candidate_spans(packet: ContextPacket, trace: TraceWriter) -> list[dict]:
    candidates: list[dict] = []
    next_id = 1
    for chunk in packet.chunks:
        role = chunk.get("evidence_role")
        chunk_type = chunk.get("chunk_type")
        if role in _EXCLUDED_EVIDENCE_ROLES or chunk_type in _EXCLUDED_CHUNK_TYPES:
            trace.decision(
                "06_extract",
                "known_non_scientific_evidence_anchor",
                kept=False,
                chunk_id=chunk["chunk_id"],
                evidence_role=role,
                chunk_type=chunk_type,
            )
            continue
        for exact_text in _split_exact_spans(chunk["text"]):
            candidates.append(
                {
                    "span_id": f"e{next_id}",
                    "chunk_id": chunk["chunk_id"],
                    "text": exact_text,
                    "evidence_role": role,
                    "chunk_type": chunk_type,
                }
            )
            next_id += 1
            if len(candidates) >= MAX_SPANS_PER_PACKET:
                return candidates
    return candidates


def marshal_and_verify(
    conn: Connection,
    *,
    verifier: LocalCitationVerifier,
    qwen: QwenTasks,
    packet: ContextPacket,
    subquestion_text: str,
    obligations: list[dict],
    nomination_reason: list[str],
    origin: str,
    trace: TraceWriter,
    candidate_spans: list[dict] | None = None,
) -> list[dict]:
    """Return candidate proposition records with unchanged verifier results and complete provenance."""
    if packet.discarded:
        trace.decision(
            "06_extract",
            "context_controller_discarded_branch",
            kept=False,
            chunk_id=packet.retrieval_anchor_chunk_id,
        )
        return []

    spans = candidate_spans if candidate_spans is not None else _candidate_spans(packet, trace)
    if not spans:
        trace.decision(
            "06_extract",
            "no_evidence_eligible_spans",
            kept=False,
            chunk_id=packet.retrieval_anchor_chunk_id,
        )
        return []

    selected_ids = qwen.select_evidence(
        spans=spans,
        subquestion=subquestion_text,
        obligations=obligations,
    )
    span_by_id = {span["span_id"]: span for span in spans}
    context_text = "\n\n".join(f"[chunk {c['chunk_id']}]\n{c['text']}" for c in packet.chunks)

    staged: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for span_id in selected_ids:
        span = span_by_id[span_id]
        claim = qwen.form_claim(
            quote=span["text"],
            context_text=context_text,
            subquestion=subquestion_text,
        )
        if not claim:
            trace.decision(
                "06_extract",
                "selected_span_yielded_no_claim",
                kept=False,
                span_id=span_id,
                chunk_id=span["chunk_id"],
            )
            continue
        key = (span["chunk_id"], claim.casefold())
        if key in seen:
            trace.decision(
                "06_extract",
                "duplicate_candidate_claim",
                kept=False,
                span_id=span_id,
                chunk_id=span["chunk_id"],
            )
            continue
        seen.add(key)
        obligation_ids = qwen.map_obligations(claim=claim, obligations=obligations)
        staged.append(
            {
                "claim": claim,
                "obligation_ids": obligation_ids,
                "evidence_anchor_chunk_id": span["chunk_id"],
                "quote": span["text"],
                "span_id": span_id,
            }
        )

    if not staged:
        return []

    verify_items: list[tuple[str, CandidateCitation]] = []
    verify_anchors: list = []
    ready: list[dict] = []
    for candidate in staged:
        anchor_id = candidate["evidence_anchor_chunk_id"]
        try:
            anchor_chunk = _source_chunk_for_id(conn, anchor_id)
        except Exception:  # noqa: BLE001 - deterministic guard around model-selected source ID
            trace.decision("06_extract", "evidence_anchor_missing", kept=False, chunk_id=anchor_id)
            continue
        if not canonical_text_contains(needle=candidate["quote"], haystack=anchor_chunk.text):
            trace.decision(
                "06_extract",
                "deterministic_span_not_verbatim",
                kept=False,
                chunk_id=anchor_id,
                quote=candidate["quote"][:120],
            )
            continue
        verify_items.append(
            (
                candidate["claim"],
                CandidateCitation(chunk_id=anchor_id, quote=candidate["quote"]),
            )
        )
        verify_anchors.append(anchor_chunk)
        ready.append(candidate)

    if not verify_items:
        return []

    results = verifier.verify_many(conn, items=verify_items, source_chunks=verify_anchors)
    records: list[dict] = []
    for candidate, result in zip(ready, results, strict=True):
        records.append(
            {
                "subquestion_id": packet.subquestion_id,
                "obligation_ids": candidate["obligation_ids"],
                "paper_id": packet.paper_id,
                "retrieval_anchor_chunk_id": packet.retrieval_anchor_chunk_id,
                "evidence_anchor_chunk_id": candidate["evidence_anchor_chunk_id"],
                "evidence_span_id": candidate["span_id"],
                "proposition_text": candidate["claim"],
                "quote": candidate["quote"],
                "provenance": {
                    "nomination_reason": nomination_reason,
                    "retrieval_score": packet.retrieval_score,
                    "context_read": [c["chunk_id"] for c in packet.chunks],
                    "grown": packet.grown,
                    "origin": origin,
                },
                "verification": {
                    "status": result.status,
                    "retrieval": result.retrieval_confidence,
                    "quote": result.quote_confidence,
                    "support": result.support_confidence,
                    "contradiction": result.contradiction_confidence,
                    "page_start": result.page_start,
                    "page_end": result.page_end,
                    "coordinate_precision": result.coordinate_precision,
                },
            }
        )
    return records
