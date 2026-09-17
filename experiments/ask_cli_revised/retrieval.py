"""Stage 4 within-paper retrieval plus Stage 5 bounded context growth.

Stage 4 searches only chunks belonging to nominated papers and retains H1a evidence metadata. Stage 5 treats
retrieval hits as reading anchors. Qwen decides whether the current text is already useful, needs local context,
or is a dead end. Deterministic code alone controls how far reading may expand.
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
MAX_PACKET_CHARS = 6000
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
    chunks: list[dict] = field(default_factory=list)
    grown: list[int] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    retrieval_score: float = 0.0
    discarded: bool = False


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
        conn,
        vector=vec,
        top_k=WITHIN_PAPER_TOP_K * 3,
        candidate_embedding_ids=set(emb_to_chunk),
    )
    roles = current_structure_roles(
        conn,
        [emb_to_chunk[h.embedding_id] for h in hits if h.embedding_id in emb_to_chunk],
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

    # Scientific/unknown/absent metadata stay full-priority. Known bibliographic/structural material is not
    # deleted, but it cannot displace a similarly ranked scientific candidate merely because vector search saw it.
    full = [h for h in ranked if h.evidence_role not in _DEPRIORITIZED_ROLES]
    demoted = [h for h in ranked if h.evidence_role in _DEPRIORITIZED_ROLES]
    per_paper: dict[int, int] = {}
    out: list[RetrievalHit] = []
    for hit in full + demoted:
        if per_paper.get(hit.chunk.paper_id, 0) >= PER_PAPER_CHUNK_CAP:
            continue
        per_paper[hit.chunk.paper_id] = per_paper.get(hit.chunk.paper_id, 0) + 1
        out.append(hit)
        if len(out) >= WITHIN_PAPER_TOP_K:
            break
    return out


def _attachment_chunks_ordered(conn: Connection, attachment_id: int) -> list[dict]:
    rows = conn.execute(
        select(chunks.c.id, chunks.c.char_start, chunks.c.text, chunks.c.section)
        .where(chunks.c.attachment_id == attachment_id)
        .order_by(chunks.c.char_start, chunks.c.id)
    ).all()
    chunk_ids = [int(row.id) for row in rows]
    roles = current_structure_roles(conn, chunk_ids) if chunk_ids else {}
    out: list[dict] = []
    for row in rows:
        chunk_id = int(row.id)
        chunk_type, evidence_role = roles.get(chunk_id, (None, None))
        out.append(
            {
                "chunk_id": chunk_id,
                "char_start": row.char_start,
                "text": str(row.text),
                "section": row.section,
                "chunk_type": chunk_type,
                "evidence_role": evidence_role,
            }
        )
    return out


def grow_context(
    conn: Connection,
    *,
    hit: RetrievalHit,
    gate,
    subquestion_text: str,
) -> ContextPacket:
    """Read locally until Qwen says the anchor is usable, hopeless, or needs bounded neighboring context."""
    anchor = hit.chunk
    ordered = _attachment_chunks_ordered(conn, anchor.attachment_id)
    index = next((i for i, c in enumerate(ordered) if c["chunk_id"] == anchor.chunk_id), None)
    anchor_dict = {
        "chunk_id": anchor.chunk_id,
        "text": anchor.text,
        "section": hit.section,
        "chunk_type": hit.chunk_type,
        "evidence_role": hit.evidence_role,
    }
    packet = ContextPacket(
        retrieval_anchor_chunk_id=anchor.chunk_id,
        subquestion_id=hit.subquestion_id,
        paper_id=anchor.paper_id,
        chunks=[anchor_dict],
        retrieval_score=hit.score,
    )
    if index is None:
        return packet

    lo = hi = index
    for iteration in range(MAX_GROWTH_ITERS + 1):
        packet_text = "\n\n".join(c["text"] for c in packet.chunks)
        if len(packet_text) >= MAX_PACKET_CHARS:
            break
        decision = (
            gate(packet_text=packet_text, subquestion=subquestion_text)
            if gate is not None
            else {"action": "accept"}
        )
        action = decision.get("action", "accept")
        packet.decisions.append(
            {
                "iteration": iteration,
                "action": action,
                "packet_chunks": [c["chunk_id"] for c in packet.chunks],
            }
        )
        if action == "discard":
            packet.discarded = True
            break
        if action == "accept":
            break
        if iteration >= MAX_GROWTH_ITERS:
            break

        added = False
        if action in {"before", "both"} and lo - 1 >= 0:
            candidate = ordered[lo - 1]
            if _addable(candidate, packet):
                lo -= 1
                packet.chunks.insert(0, _packet_chunk(candidate))
                packet.grown.append(candidate["chunk_id"])
                added = True
        if action in {"after", "both"} and hi + 1 < len(ordered):
            candidate = ordered[hi + 1]
            if _addable(candidate, packet):
                hi += 1
                packet.chunks.append(_packet_chunk(candidate))
                packet.grown.append(candidate["chunk_id"])
                added = True
        if not added:
            break
    return packet


def _packet_chunk(candidate: dict) -> dict:
    return {
        "chunk_id": candidate["chunk_id"],
        "text": candidate["text"],
        "section": candidate.get("section"),
        "chunk_type": candidate.get("chunk_type"),
        "evidence_role": candidate.get("evidence_role"),
    }


def _addable(candidate: dict, packet: ContextPacket) -> bool:
    if candidate["chunk_id"] in {c["chunk_id"] for c in packet.chunks}:
        return False
    if (candidate.get("section") or "").lower() == "references":
        return False
    existing = "\n\n".join(c["text"] for c in packet.chunks)
    if len(existing) + len(candidate["text"]) > MAX_PACKET_CHARS:
        return False
    return True
