"""Stage 4 within-paper retrieval plus Stage 5 bounded context growth.

Stage 4 searches only chunks belonging to nominated papers and retains H1a evidence metadata. Stage 5 treats
retrieval hits as reading anchors. Qwen decides whether the current text is already useful, needs local context,
or is a dead end. Deterministic code alone controls how far reading may expand.
"""

from __future__ import annotations

import re
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
# The gate could not produce a usable answer (call failed, capped, unparseable, or out of enum). This is a
# mechanical state, never a semantic accept/discard: the packet is neither accepted nor grown and does not enter
# evidence extraction, and it is recorded as its own discard reason so it can be counted and reported.
GATE_NO_ANSWER = "no_answer"
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
    # Why a packet was excluded: "gate_no_answer" (mechanical), "gate_discard" (semantic), "incomplete_clause".
    discard_reason: str | None = None


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
    """Every column here beyond the original five (chunk_id/char_start/text/section/chunk_type+
    evidence_role) exists for Stage A's continuation.detect_continuation -- char_end, page_start/end,
    bbox_json, extraction_tool/version, source_attachment_checksum, and attachment_id are exactly
    what contract_directed/seams.py::verify_seam needs (see its own docstring)."""
    rows = conn.execute(
        select(
            chunks.c.id,
            chunks.c.attachment_id,
            chunks.c.char_start,
            chunks.c.char_end,
            chunks.c.text,
            chunks.c.section,
            chunks.c.page_start,
            chunks.c.page_end,
            chunks.c.bbox_json,
            chunks.c.extraction_tool,
            chunks.c.extraction_version,
            chunks.c.source_attachment_checksum,
        )
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
                "attachment_id": int(row.attachment_id),
                "char_start": row.char_start,
                "char_end": row.char_end,
                "text": str(row.text),
                "section": row.section,
                "page_start": row.page_start,
                "page_end": row.page_end,
                "bbox_json": row.bbox_json,
                "extraction_tool": row.extraction_tool,
                "extraction_version": row.extraction_version,
                "source_attachment_checksum": row.source_attachment_checksum,
                "chunk_type": chunk_type,
                "evidence_role": evidence_role,
            }
        )
    return out


def _attachment_checksum(conn: Connection, attachment_id: int) -> str | None:
    """Stage A: the one non-per-chunk field `verify_seam` needs (`attachment_checksum`)."""
    row = conn.execute(select(attachments.c.checksum).where(attachments.c.id == attachment_id)).first()
    return row.checksum if row is not None else None


# A small, closed, fixed class of English function words that cannot themselves end a
# grammatical clause: articles, prepositions, coordinating/subordinating conjunctions, and
# the complementizer/relative-pronoun uses of "that"/"which". This is deliberately NOT a
# phrase or topic vocabulary (a growing blacklist of specific wordings such as "is needed
# to" or "future research") -- it is a bounded, standard part-of-speech class, checked only
# against a span's LAST WORD, so it generalizes to any sentence that happens to break off on
# one of these words rather than encoding any one manifestation of the underlying defect.
_INCOMPLETE_CLAUSE_TRAILING_WORDS = frozenset(
    {
        # Articles
        "a",
        "an",
        "the",
        # Coordinating conjunctions
        "and",
        "but",
        "or",
        "nor",
        "so",
        "yet",
        # Subordinating conjunctions
        "because",
        "although",
        "though",
        "while",
        "if",
        "unless",
        "until",
        "when",
        "whenever",
        "where",
        "wherever",
        "whereas",
        "whether",
        "since",
        "as",
        "than",
        # Complementizer / relative-pronoun uses that leave a clause open
        "that",
        "which",
        # Prepositions
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "into",
        "onto",
        "upon",
        "about",
        "above",
        "across",
        "after",
        "against",
        "along",
        "among",
        "around",
        "before",
        "behind",
        "below",
        "beneath",
        "beside",
        "between",
        "beyond",
        "concerning",
        "despite",
        "down",
        "during",
        "except",
        "inside",
        "near",
        "off",
        "out",
        "outside",
        "over",
        "past",
        "regarding",
        "through",
        "throughout",
        "toward",
        "towards",
        "under",
        "underneath",
        "unto",
        "up",
        "via",
        "within",
        "without",
    }
)

_TRAILING_WORD = re.compile(r"[A-Za-z']+$")


def _ends_mid_clause(text: str) -> bool:
    """True if ``text`` visibly breaks off before a grammatical clause completes.

    A text ending in terminal punctuation is never flagged. Otherwise this looks only at
    the last word: an ordinary content word (noun, verb, adjective, ...) is never flagged
    even without a trailing period -- title- or list-style text that merely lacks
    punctuation is not "incomplete" by this test. Only a text whose last word is one of the
    small closed class above (a word that grammatically demands something after it) is
    flagged, regardless of the text's topic.
    """
    stripped = text.rstrip()
    if not stripped or stripped[-1] in ".!?":
        return False
    match = _TRAILING_WORD.search(stripped)
    if match is None:
        return False
    return match.group(0).casefold() in _INCOMPLETE_CLAUSE_TRAILING_WORDS


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
    # hit.section/.chunk_type/.evidence_role come from the retrieval hit's own classification (may be
    # fresher than what's in `ordered`); every other field -- needed only for Stage A continuation
    # detection -- comes from `ordered[index]` when available, `_packet_chunk`'s own None defaults
    # otherwise (index is None: no positional match, growth is unavailable, handled just below).
    base = ordered[index] if index is not None else {"chunk_id": anchor.chunk_id, "text": anchor.text}
    anchor_dict = _packet_chunk({**base, "section": hit.section, "chunk_type": hit.chunk_type, "evidence_role": hit.evidence_role})  # fmt: skip
    packet = ContextPacket(
        retrieval_anchor_chunk_id=anchor.chunk_id,
        subquestion_id=hit.subquestion_id,
        paper_id=anchor.paper_id,
        chunks=[anchor_dict],
        retrieval_score=hit.score,
    )
    if index is None:
        # Growth is architecturally unavailable here -- there is no positional index into
        # the attachment's chunk ordering to grow from. If the lone anchor chunk itself is
        # visibly incomplete, there is no seam left to try; fail closed rather than let it
        # become a claim (rule 4 below).
        if _ends_mid_clause(anchor.text):
            packet.discarded = True
            packet.discard_reason = "incomplete_clause"
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
        # A missing action is NO ANSWER, never an implicit accept.
        action = decision.get("action") or GATE_NO_ANSWER
        packet.decisions.append(
            {
                "iteration": iteration,
                "action": action,
                "packet_chunks": [c["chunk_id"] for c in packet.chunks],
            }
        )
        if action == GATE_NO_ANSWER:
            packet.discarded = True
            packet.discard_reason = "gate_no_answer"
            break
        if action == "discard":
            packet.discarded = True
            packet.discard_reason = "gate_discard"
            break
        if action == "accept":
            if not _ends_mid_clause(packet_text):
                break
            # The gate said "accept" -- a genuine semantic judgment -- but the packet's own text
            # visibly breaks off before a clause completes. Do not trust that "accept" as final:
            # prefer the existing "grow after" mechanism to try to reach the rest of the sentence
            # first (rule 3 below), and only fail closed if no further neighboring chunk is
            # available or the growth budget is exhausted (rule 4 below).
            if iteration >= MAX_GROWTH_ITERS or hi + 1 >= len(ordered):
                packet.discarded = True
                packet.discard_reason = "incomplete_clause"
                break
            candidate = ordered[hi + 1]
            if not _addable(candidate, packet):
                packet.discarded = True
                packet.discard_reason = "incomplete_clause"
                break
            hi += 1
            packet.chunks.append(_packet_chunk(candidate))
            packet.grown.append(candidate["chunk_id"])
            continue
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

    if not packet.discarded and packet.chunks:
        final_text = "\n\n".join(c["text"] for c in packet.chunks)
        if _ends_mid_clause(final_text):
            packet.discarded = True
            packet.discard_reason = "incomplete_clause"
    return packet


def recovery_neighborhood_context(conn: Connection, *, hit: RetrievalHit, subquestion_text: str) -> ContextPacket:
    """Recovery-only: a bounded, deterministic neighborhood around the anchor (contract_directed's own
    `neighborhood.build_neighborhood`, MAX_SIDE=3, section/reference/sentence-continuity aware), used instead of
    `grow_context`'s narrower model-gated +/-2 growth. `subquestion_text` is accepted only so this function is
    swappable with `grow_context` at the `_process_hits` call site (see its `context_fn` parameter); the
    neighborhood's own boundary rules are purely structural and do not read it.

    This is Phase 2 Section 5's "deterministic neighborhood construction around a nominated anchor" -- a distinct
    step from "model-based evidence nomination" (the recovery plan's own DEEPEN/NOMINATE decision and the
    recovery-query reformulation that chooses WHICH anchor to retrieve, both unchanged upstream of this call).
    Called only from the recovery round (`_recover`); the initial pass keeps `grow_context` exactly as before.
    """
    from experiments.ask_cli_revised.contract_directed import neighborhood as nbhd

    anchor = hit.chunk
    ordered_raw = _attachment_chunks_ordered(conn, anchor.attachment_id)
    ordered = [{**row, "attachment_id": anchor.attachment_id, "paper_id": anchor.paper_id} for row in ordered_raw]
    index = next((i for i, c in enumerate(ordered) if c["chunk_id"] == anchor.chunk_id), None)
    base = ordered[index] if index is not None else {"chunk_id": anchor.chunk_id, "text": anchor.text}
    anchor_dict = _packet_chunk({**base, "section": hit.section, "chunk_type": hit.chunk_type, "evidence_role": hit.evidence_role})  # fmt: skip
    packet = ContextPacket(
        retrieval_anchor_chunk_id=anchor.chunk_id,
        subquestion_id=hit.subquestion_id,
        paper_id=anchor.paper_id,
        chunks=[anchor_dict],
        retrieval_score=hit.score,
    )
    if index is None:
        # Same fail-closed rule grow_context uses when there is no positional index to grow from.
        if _ends_mid_clause(anchor.text):
            packet.discarded = True
            packet.discard_reason = "incomplete_clause"
        return packet

    result = nbhd.build_neighborhood(ordered, index)
    by_id = {c["chunk_id"]: c for c in ordered}
    packet.chunks = [_packet_chunk(by_id[chunk_id]) for chunk_id in result["chunk_ids"]]
    packet.grown = [chunk_id for chunk_id in result["chunk_ids"] if chunk_id != anchor.chunk_id]
    packet.decisions = [
        {
            "mechanism": "deterministic_neighborhood",
            "nbhd_id": result["nbhd_id"],
            "boundary": result["boundary"],
            "rule_trace": result["rule_trace"],
        }
    ]
    if _ends_mid_clause("\n\n".join(c["text"] for c in packet.chunks)):
        packet.discarded = True
        packet.discard_reason = "incomplete_clause"
    return packet


def _packet_chunk(candidate: dict) -> dict:
    """Every extra key beyond the original five exists for Stage A's continuation detection
    (`continuation.detect_continuation`), which needs `contract_directed/seams.py::verify_seam`'s full
    input shape on each `packet.chunks` entry. All are `.get()` with a `None` default: a caller that
    only ever provided the original five keys (any existing test's own hand-built candidate dict)
    still produces a valid packet chunk, just one continuation detection cannot evaluate -- it fails
    closed on missing data rather than erroring."""
    return {
        "chunk_id": candidate["chunk_id"],
        "text": candidate["text"],
        "section": candidate.get("section"),
        "chunk_type": candidate.get("chunk_type"),
        "evidence_role": candidate.get("evidence_role"),
        "attachment_id": candidate.get("attachment_id"),
        "char_start": candidate.get("char_start"),
        "char_end": candidate.get("char_end"),
        "page_start": candidate.get("page_start"),
        "page_end": candidate.get("page_end"),
        "bbox_json": candidate.get("bbox_json"),
        "extraction_tool": candidate.get("extraction_tool"),
        "extraction_version": candidate.get("extraction_version"),
        "source_attachment_checksum": candidate.get("source_attachment_checksum"),
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
