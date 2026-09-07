"""Stage 6 marshalling → Stage 7 verification → ledger entries.

Qwen proposes source-local propositions; deterministic code enforces the verbatim-quote precondition
against the EVIDENCE anchor chunk (possibly a grown neighbour, not the retrieval anchor), then the unchanged
verifier adjudicates. Only what verifies is eligible for the sealed ledger; everything is traced.
"""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.pdf_processing.extraction import canonical_text_contains
from app.backend.summarization.generators import CandidateCitation
from app.backend.summarization.verification import LocalCitationVerifier, _source_chunk_for_id
from experiments.ask_cli.qwen import QwenTasks
from experiments.ask_cli.retrieval import ContextPacket
from experiments.ask_cli.trace import TraceWriter


def _render(p: dict) -> str:
    core = " ".join(x for x in (p.get("subject"), p.get("relation"), p.get("object")) if x).strip()
    extras = "; ".join(x for x in (p.get("population"), p.get("measure"), p.get("qualifier")) if x)
    text = (core + (f" ({extras})" if extras else "")).strip()
    return text or p.get("quote", "")


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
) -> list[dict]:
    """Return a list of proposition records (each with its verification result + full provenance)."""
    raw_props = qwen.extract_propositions(
        packet_chunks=packet.chunks, subquestion=subquestion_text, obligations=obligations
    )
    records: list[dict] = []
    verify_items: list[tuple[str, CandidateCitation]] = []
    verify_anchors: list = []
    staged: list[dict] = []

    for p in raw_props:
        anchor_id = p["evidence_anchor_chunk_id"]
        try:
            anchor_chunk = _source_chunk_for_id(conn, anchor_id)
        except Exception:  # noqa: BLE001 — a hallucinated id that slipped validation
            trace.decision("06_extract", "evidence_anchor_missing", kept=False, chunk_id=anchor_id)
            continue
        if not canonical_text_contains(needle=p["quote"], haystack=anchor_chunk.text):
            trace.decision("06_extract", "quote_not_verbatim", kept=False, chunk_id=anchor_id, quote=p["quote"][:120])
            continue
        prop_text = _render(p)
        verify_items.append((prop_text, CandidateCitation(chunk_id=anchor_id, quote=p["quote"])))
        verify_anchors.append(anchor_chunk)
        staged.append({"p": p, "prop_text": prop_text, "anchor_chunk": anchor_chunk})

    if not verify_items:
        return records

    results = verifier.verify_many(conn, items=verify_items, source_chunks=verify_anchors)
    for staged_item, result in zip(staged, results, strict=True):
        p = staged_item["p"]
        records.append(
            {
                "subquestion_id": packet.subquestion_id,
                "obligation_ids": p.get("obligation_ids", []),
                "paper_id": packet.paper_id,
                "retrieval_anchor_chunk_id": packet.retrieval_anchor_chunk_id,
                "evidence_anchor_chunk_id": p["evidence_anchor_chunk_id"],
                "proposition_text": staged_item["prop_text"],
                "structured": {
                    k: p.get(k)
                    for k in ("subject", "relation", "object", "direction", "population", "measure", "qualifier")
                },
                "quote": p["quote"],
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
