"""Stage 4 (within-paper chunk retrieval) + Stage 5 (bounded context growth).

Stage 4 searches ONLY chunks of the nominated papers (candidate-set vector search) and applies H1a hygiene
deprioritization. Stage 5 turns a retrieval anchor into a bounded context packet by reading neighbouring
chunks in the same attachment; a Qwen gate decides WHETHER/which direction to grow, deterministic code
bounds HOW FAR. The retrieval anchor and the eventual evidence anchor are distinct: extraction (Stage 6)
picks which inspected chunk actually supports each proposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Connection, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import current_chunk_embedding_ids
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.persistence.chunk_structure_repo import current_structure_roles
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks
from app.backend.summarization.generators import SourceChunk
from app.backend.summarization.pipeline import _source_chunk_from_row

WITHIN_PAPER_TOP_K = 8
PER_PAPER_CHUNK_CAP = 3
MAX_GROWTH_ITERS = 2
MAX_PACKET_CHARS = 6000  # ~1,500 tokens
_DEPRIORITIZED_ROLES = frozenset({"bibliographic", "structural"})


@dataclass
class RetrievalHit:
    chunk: SourceChunk
    subquestion_id: str
    score: float
    section: str | None
    chunk_type: str | None
    evidence_role: str | None


@dataclass
class ContextPacket:
    retrieval_anchor_chunk_id: int
    subquestion_id: str
    paper_id: int
    chunks: list[dict] = field(default_factory=list)  # [{chunk_id, text}] anchor + grown neighbours, in order
    grown: list[int] = field(default_factory=list)
    retrieval_score: float = 0.0


def _candidate_chunk_rows(conn: Connection, paper_ids: list[int]) -> list[SourceChunk]:
    if not paper_ids:
        return []
    stmt = (
        select(chunks)
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(chunks.c.paper_id.in_(paper_ids), attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
        .order_by(chunks.c.id)
    )
    return [_source_chunk_from_row(row) for row in conn.execute(stmt).mappings()]


def within_paper_retrieve(
    conn: Connection,
    *,
    subquestion_id: str,
    subquestion_text: str,
    paper_ids: list[int],
    model: EmbeddingModel,
    vector_store: SQLiteVecVectorStore,
) -> list[RetrievalHit]:
    pool = _candidate_chunk_rows(conn, paper_ids)
    if not pool:
        return []
    current = current_chunk_embedding_ids(conn, ((c.chunk_id, c.chunk_version) for c in pool), model=model)
    emb_to_chunk = {emb: cid for cid, emb in current.items()}
    if not emb_to_chunk:
        return []
    source_by_id = {c.chunk_id: c for c in pool}
    vec = model.encode_texts([subquestion_text])[0]
    hits = vector_store.search(
        conn, vector=vec, top_k=WITHIN_PAPER_TOP_K * 3, candidate_embedding_ids=set(emb_to_chunk)
    )
    roles = current_structure_roles(
        conn, [emb_to_chunk[h.embedding_id] for h in hits if h.embedding_id in emb_to_chunk]
    )

    ranked: list[RetrievalHit] = []
    for hit in hits:
        cid = emb_to_chunk.get(hit.embedding_id)
        if cid is None or cid not in source_by_id:
            continue
        chunk_type, role = roles.get(cid, (None, None))
        ranked.append(
            RetrievalHit(
                chunk=source_by_id[cid],
                subquestion_id=subquestion_id,
                score=max(0.0, 1.0 - float(hit.distance)),
                section=source_by_id[cid].section,
                chunk_type=chunk_type,
                evidence_role=role,
            )
        )
    # H1a hygiene: full-priority (scientific/unknown/absent) lead; bibliographic/structural after. Per-paper cap.
    full = [h for h in ranked if h.evidence_role not in _DEPRIORITIZED_ROLES]
    demoted = [h for h in ranked if h.evidence_role in _DEPRIORITIZED_ROLES]
    per_paper: dict[int, int] = {}
    out: list[RetrievalHit] = []
    for h in full + demoted:
        if per_paper.get(h.chunk.paper_id, 0) >= PER_PAPER_CHUNK_CAP:
            continue
        per_paper[h.chunk.paper_id] = per_paper.get(h.chunk.paper_id, 0) + 1
        out.append(h)
        if len(out) >= WITHIN_PAPER_TOP_K:
            break
    return out


def _attachment_chunks_ordered(conn: Connection, attachment_id: int) -> list[dict]:
    rows = conn.execute(
        select(chunks.c.id, chunks.c.char_start, chunks.c.text, chunks.c.section)
        .where(chunks.c.attachment_id == attachment_id)
        .order_by(chunks.c.char_start, chunks.c.id)
    ).all()
    return [
        {"chunk_id": int(r.id), "char_start": r.char_start, "text": str(r.text), "section": r.section} for r in rows
    ]


def grow_context(
    conn: Connection,
    *,
    hit: RetrievalHit,
    gate,  # callable(packet_text, subquestion) -> {grow, dead_end, ...} or None to skip Qwen gating
    subquestion_text: str,
) -> ContextPacket:
    """Bounded neighbour reader. Deterministic caps; a Qwen gate (if provided) chooses direction/dead-end.

    Never crosses body↔references (a neighbour whose section is 'references' is not added). The anchor stays
    in provenance; grown neighbours are interpretive context (extraction decides the real evidence anchor).
    """
    anchor = hit.chunk
    ordered = _attachment_chunks_ordered(conn, anchor.attachment_id)
    index = next((i for i, c in enumerate(ordered) if c["chunk_id"] == anchor.chunk_id), None)
    packet = ContextPacket(
        retrieval_anchor_chunk_id=anchor.chunk_id,
        subquestion_id=hit.subquestion_id,
        paper_id=anchor.paper_id,
        chunks=[{"chunk_id": anchor.chunk_id, "text": anchor.text}],
        retrieval_score=hit.score,
    )
    if index is None:
        return packet
    lo = hi = index
    for _ in range(MAX_GROWTH_ITERS):
        packet_text = "\n\n".join(c["text"] for c in packet.chunks)
        if len(packet_text) >= MAX_PACKET_CHARS:
            break
        decision = (
            gate(packet_text=packet_text, subquestion=subquestion_text)
            if gate is not None
            else {"grow": "both", "dead_end": False}
        )
        if decision.get("dead_end"):
            break
        grow = decision.get("grow", "none")
        if grow == "none":
            break
        added = False
        if grow in {"before", "both"} and lo - 1 >= 0:
            cand = ordered[lo - 1]
            if _addable(cand, anchor, packet):
                lo -= 1
                packet.chunks.insert(0, {"chunk_id": cand["chunk_id"], "text": cand["text"]})
                packet.grown.append(cand["chunk_id"])
                added = True
        if grow in {"after", "both"} and hi + 1 < len(ordered):
            cand = ordered[hi + 1]
            if _addable(cand, anchor, packet):
                hi += 1
                packet.chunks.append({"chunk_id": cand["chunk_id"], "text": cand["text"]})
                packet.grown.append(cand["chunk_id"])
                added = True
        if not added:
            break
    return packet


def _addable(cand: dict, anchor: SourceChunk, packet: ContextPacket) -> bool:
    if cand["chunk_id"] in {c["chunk_id"] for c in packet.chunks}:
        return False
    if (cand.get("section") or "").lower() == "references":  # never cross body -> references
        return False
    if len("\n\n".join(c["text"] for c in packet.chunks)) + len(cand["text"]) > MAX_PACKET_CHARS:
        return False
    return True
