"""Stage 6 evidence selection/claim formation -> Stage 7 verification -> ledger entries.

Qwen no longer has to copy exact quotes, invent IDs, fill a semantic tuple, and map obligations in one call.
Deterministic code exposes exact source spans; Qwen selects span IDs, interprets one span into one claim, and
maps the resulting claim to natural-language answer obligations in separate low-entropy steps.
"""

from __future__ import annotations

import re
from dataclasses import replace

from sqlalchemy import Connection

from app.backend.pdf_processing.extraction import canonical_text_contains
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.summarization.generators import CandidateCitation
from app.backend.summarization.verification import (
    LocalCitationVerifier,
    _source_chunk_for_id,
    _with_coordinate_precision,
)
from experiments.ask_cli_revised import continuation
from experiments.ask_cli_revised.qwen import QwenTasks
from experiments.ask_cli_revised.retrieval import ContextPacket, _attachment_checksum, _attachment_chunks_ordered
from experiments.ask_cli_revised.trace import TraceWriter

# Stage A (plural evidence anchors, 2026-09-29 authorization): how a continuation join's two
# chunk-halves are concatenated into one persisted quote. A single space, matching what a reader
# sees when a mechanically-split sentence is read continuously -- never a fabricated separator that
# could itself be mistaken for source content.
JOIN_SEPARATOR = " "

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


def _eligible_chunks(packet: ContextPacket, trace: TraceWriter) -> list[tuple[dict, list[str]]]:
    """(chunk, its own sentence-split texts) for every chunk not excluded by role/type, in packet order."""
    out: list[tuple[dict, list[str]]] = []
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
        out.append((chunk, _split_exact_spans(chunk["text"])))
    return out


def _boundary_continuation(
    chunk_a: dict, texts_a: list[str], chunk_b: dict, texts_b: list[str], *, conn, trace: TraceWriter
) -> dict | None:
    """Stage A: does chunk_a's LAST split-off text genuinely continue into chunk_b's FIRST? A cheap
    linguistic pre-filter runs before the more expensive geometry/offset check (continuation.
    detect_continuation, which reuses contract_directed/seams.py's verify_seam unmodified plus this
    codebase's own section_unchanged addition -- see continuation.py's docstring for exactly why both
    are required). Returns the continuity verdict dict when a join is warranted, else None."""
    if conn is None or not texts_a or not texts_b:
        return None
    last_a, first_b = texts_a[-1], texts_b[0]
    from experiments.ask_cli_revised.contract_directed.units import ends_terminal, starts_as_continuation

    if ends_terminal(last_a) or not starts_as_continuation(first_b):
        return None
    attachment_id = chunk_a.get("attachment_id")
    if attachment_id is None:
        return None
    checksum = _attachment_checksum(conn, attachment_id)
    chunks_on_attachment = _attachment_chunks_ordered(conn, attachment_id)
    verdict = continuation.detect_continuation(
        chunk_a, chunk_b, attachment_checksum=checksum, chunks_on_attachment=chunks_on_attachment
    )
    trace.decision(
        "06_extract",
        "continuation_join_evaluated",
        kept=verdict["is_continuation"],
        chunk_a=chunk_a["chunk_id"],
        chunk_b=chunk_b["chunk_id"],
        seam_state=verdict["seam_state"],
        section_unchanged=verdict["section_unchanged"],
    )
    return verdict if verdict["is_continuation"] else None


def _candidate_spans(packet: ContextPacket, trace: TraceWriter, *, conn=None) -> list[dict]:
    """`conn`, when given, enables Stage A continuation joining across adjacent chunks (recovery-
    round packets only reach here with a real connection -- see propositions._candidate_spans'
    callers). Omitting it (every pre-Stage-A caller, and any test that only cares about the
    unmodified per-chunk behavior) reproduces today's exact splitting, unchanged."""
    eligible = _eligible_chunks(packet, trace)
    candidates: list[dict] = []
    next_id = 1
    i = 0
    while i < len(eligible):
        chunk, texts = eligible[i]
        role, chunk_type = chunk.get("evidence_role"), chunk.get("chunk_type")
        verdict = None
        if i + 1 < len(eligible):
            next_chunk, next_texts = eligible[i + 1]
            verdict = _boundary_continuation(chunk, texts, next_chunk, next_texts, conn=conn, trace=trace)
        if verdict is not None:
            next_chunk, next_texts = eligible[i + 1]
            for exact_text in texts[:-1]:  # every non-boundary span of this chunk, unaffected
                candidates.append(
                    {"span_id": f"e{next_id}", "chunk_id": chunk["chunk_id"], "text": exact_text,
                     "evidence_role": role, "chunk_type": chunk_type}
                )  # fmt: skip
                next_id += 1
            joined_text = texts[-1] + JOIN_SEPARATOR + next_texts[0]
            candidates.append(
                {
                    "span_id": f"e{next_id}",
                    "chunk_id": chunk["chunk_id"],  # the PRIMARY anchor -- see marshal_and_verify
                    "text": joined_text,
                    "evidence_role": role,
                    "chunk_type": chunk_type,
                    "anchors": [
                        {"kind": "continuation", "chunk_id": chunk["chunk_id"], "span_id": f"e{next_id}a", "text": texts[-1]},
                        {"kind": "continuation", "chunk_id": next_chunk["chunk_id"], "span_id": f"e{next_id}b", "text": next_texts[0]},
                    ],  # fmt: skip
                    "continuity": verdict,
                }
            )
            next_id += 1
            if len(candidates) >= MAX_SPANS_PER_PACKET:
                return candidates
            eligible[i + 1] = (next_chunk, next_texts[1:])  # first text consumed by the join
            i += 1
            continue
        for exact_text in texts:
            candidates.append(
                {"span_id": f"e{next_id}", "chunk_id": chunk["chunk_id"], "text": exact_text,
                 "evidence_role": role, "chunk_type": chunk_type}
            )  # fmt: skip
            next_id += 1
            if len(candidates) >= MAX_SPANS_PER_PACKET:
                return candidates
        i += 1
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
    map_claims: bool = True,
) -> list[dict]:
    """Return candidate proposition records with unchanged verifier results and complete provenance.

    ``map_claims=False`` defers claim -> obligation mapping (the R role) until after source verification: records come
    back with ``obligation_ids == []`` and ``mapping_state == "pending"`` for the caller to attach later.
    """
    if packet.discarded:
        # A mechanical gate failure keeps its own reason code: it is not a semantic discard.
        reason = getattr(packet, "discard_reason", None)
        trace.decision(
            "06_extract",
            "gate_no_answer" if reason == "gate_no_answer" else "context_controller_discarded_branch",
            kept=False,
            chunk_id=packet.retrieval_anchor_chunk_id,
        )
        return []

    spans = candidate_spans if candidate_spans is not None else _candidate_spans(packet, trace, conn=conn)
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
        obligation_ids = qwen.map_obligations(claim=claim, obligations=obligations) if map_claims else []
        staged.append(
            {
                "claim": claim,
                "obligation_ids": obligation_ids,
                "evidence_anchor_chunk_id": span["chunk_id"],  # the PRIMARY anchor when anchors is set
                "quote": span["text"],
                "span_id": span_id,
                "anchors": span.get("anchors"),  # Stage A: present only for a continuation-joined span
            }
        )

    if not staged:
        return []

    verify_items: list[tuple[str, CandidateCitation]] = []
    verify_anchors: list = []
    ready: list[dict] = []
    anchor_overrides: dict[int, dict] = {}  # index into `ready` -> Stage A per-anchor verification detail
    for candidate in staged:
        anchor_id = candidate["evidence_anchor_chunk_id"]
        try:
            anchor_chunk = _source_chunk_for_id(conn, anchor_id)
        except Exception:  # noqa: BLE001 - deterministic guard around model-selected source ID
            trace.decision("06_extract", "evidence_anchor_missing", kept=False, chunk_id=anchor_id)
            continue
        anchors = candidate.get("anchors")
        if anchors:
            # Stage A: the whole quote spans >1 real chunk by construction -- checking it against any
            # ONE chunk's text is exactly the structural assumption this authorization asked to find
            # and correct. Verify each anchor's own text against its own chunk instead (never relaxed:
            # canonical_text_contains is reused unmodified, just applied per anchor).
            override = _verify_continuation_anchors(conn, anchors=anchors, quote=candidate["quote"])
            if override["quote_confidence"] == 0.0:
                trace.decision(
                    "06_extract",
                    "continuation_anchor_not_verbatim_or_reconstruction_mismatch",
                    kept=False,
                    chunk_id=anchor_id,
                    quote=candidate["quote"][:120],
                )
                continue
        else:
            override = None
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
        if override is not None:
            anchor_overrides[len(ready)] = override
        ready.append(candidate)

    if not verify_items:
        return []

    results = verifier.verify_many(conn, items=verify_items, source_chunks=verify_anchors)
    # Stage A: verify_many's own internal quote/coordinate computation assumes a whole quote lives in
    # one chunk (confirmed by reading it -- exactly the assumption this authorization asked to find
    # and correct). Its retrieval_confidence (chunk-id-driven) and support/contradiction (already
    # given the full, correct joined quote as premise -- `verify_many`'s own `pairs` construction
    # uses `citation.quote`, which IS the joined text here) stay from the one batched call, preserving
    # the "one embedding call, one NLI call for the whole batch" invariant (LATENCY.md); only the
    # quote/coordinate portion is overridden, from the per-anchor check just performed.
    if anchor_overrides:
        results = list(results)
        for index, override in anchor_overrides.items():
            result = results[index]
            status = verifier._status(
                retrieval_confidence=result.retrieval_confidence,
                quote_confidence=override["quote_confidence"],
                support_confidence=result.support_confidence,
                contradiction_confidence=result.contradiction_confidence,
            )
            results[index] = replace(
                result,
                status=status,
                quote_confidence=override["quote_confidence"],
                page_start=override["page_start"],
                page_end=override["page_end"],
                bbox_json=override["bbox_json"],
                coordinate_precision=override["coordinate_precision"],
            )
    records: list[dict] = []
    for index, (candidate, result) in enumerate(zip(ready, results, strict=True)):
        record = {
            "subquestion_id": packet.subquestion_id,
            "obligation_ids": candidate["obligation_ids"],
            "mapping_state": "mapped" if map_claims else "pending",
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
        if index in anchor_overrides:
            # Stage A: the full, ordered, per-anchor detail -- each with its own real chunk_id, exact
            # verbatim text, and its OWN (possibly "exact") page/coordinate resolution. Additive only;
            # every field above stays populated exactly as for a single-anchor proposition.
            record["anchors"] = anchor_overrides[index]["resolved_anchors"]
        records.append(record)
    return records


def _verify_continuation_anchors(conn: Connection, *, anchors: list[dict], quote: str) -> dict:
    """Stage A: verify a continuation-joined candidate's plural anchors, each against its OWN real
    chunk text -- never the whole joined `quote` against any single chunk (which is structurally
    impossible to satisfy and is exactly the assumption this authorization asked to find and fix).

    `quote_confidence` is 1.0 only when the reconstruction is honest (`quote` exactly equals the
    anchors' own texts joined by `JOIN_SEPARATOR` -- a defensive check; by construction in
    `_candidate_spans` this should always hold, but nothing downstream should ever trust that without
    checking) AND every anchor's own text is verbatim (`canonical_text_contains`, unrelaxed) in its
    own real chunk -- same all-or-nothing strictness a single-anchor claim already has. Otherwise 0.0,
    with no page/coordinate claim at all (never a guess).

    The returned singular `coordinate_precision` is always `"region"` (never `"exact"`, even when
    every individual anchor itself resolves `"exact"`) -- invariant #2's coordinate-honesty contract:
    a single rectangle cannot correctly represent text that spans more than one real chunk location.
    Each anchor's OWN `coordinate_precision` in `resolved_anchors` is independently resolved via the
    same `locate_quote_for_attachment` a single-anchor claim already uses, so a renderer that
    understands `anchors` can still show multiple exact rectangles.
    """
    reconstructed = JOIN_SEPARATOR.join(a["text"] for a in anchors)
    if quote != reconstructed:
        return {"quote_confidence": 0.0, "resolved_anchors": [], "page_start": None, "page_end": None, "bbox_json": None, "coordinate_precision": None}  # fmt: skip

    resolved: list[dict] = []
    all_verbatim = True
    for anchor in anchors:
        try:
            anchor_chunk = _source_chunk_for_id(conn, anchor["chunk_id"])
        except Exception:  # noqa: BLE001 - deterministic guard around a model-selected/constructed id
            all_verbatim = False
            resolved.append({**anchor, "verbatim": False, "page_start": None, "page_end": None, "coordinate_precision": None})  # fmt: skip
            continue
        verbatim = canonical_text_contains(needle=anchor["text"], haystack=anchor_chunk.text)
        if not verbatim:
            all_verbatim = False
            resolved.append({**anchor, "verbatim": False, "page_start": None, "page_end": None, "coordinate_precision": None})  # fmt: skip
            continue
        match = locate_quote_for_attachment(conn, anchor_chunk.attachment_id, anchor["text"])
        if match.found:
            page_start, page_end = match.page_start, match.page_end
            bbox_json, precision = _with_coordinate_precision(list(match.rectangles), "exact"), "exact"
        else:
            page_start, page_end = anchor_chunk.page_start, anchor_chunk.page_end
            bbox_json, precision = _with_coordinate_precision(anchor_chunk.bbox_json, "region"), "region"
        resolved.append(
            {**anchor, "verbatim": True, "page_start": page_start, "page_end": page_end,
             "bbox_json": bbox_json, "coordinate_precision": precision}
        )  # fmt: skip

    if not all_verbatim:
        return {"quote_confidence": 0.0, "resolved_anchors": resolved, "page_start": None, "page_end": None, "bbox_json": None, "coordinate_precision": None}  # fmt: skip

    page_starts = [r["page_start"] for r in resolved if r.get("page_start") is not None]
    page_ends = [r["page_end"] for r in resolved if r.get("page_end") is not None]
    return {
        "quote_confidence": 1.0,
        "resolved_anchors": resolved,
        "page_start": min(page_starts) if page_starts else None,
        "page_end": max(page_ends) if page_ends else None,
        "bbox_json": None,  # the singular field never claims one rectangle for plural anchors
        "coordinate_precision": "region",  # invariant #2: never "exact" when text spans >1 real anchor
    }
