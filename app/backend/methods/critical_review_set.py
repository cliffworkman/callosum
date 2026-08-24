"""Set critical review (backlog #12) — Tier-1 engine over a CHOSEN SET of papers.

Reuses the inc-266 single-paper primitives, scoping the cross-corpus contradiction detector to the SET (so only
INTRA-set disagreement surfaces) and composing each paper's ALREADY-STORED signals into an honest fact-matrix.
Fully local, no LLM, no network. Every heavy dependency is INJECTED (the ``critical_review_deps`` test seam)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorStore
from app.backend.methods.critical_review import (
    ContestedSearchScope,
    _stored_method_signals,
    extract_claim_sentences,
    make_chunk_resolver,
    search_contested_claim_scopes,
)
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.repository import get_paper
from app.backend.persistence.schema import attachments, chunks, embeddings, papers
from app.backend.summarization.verification import StanceScorer


def set_chunk_embedding_ids(conn: Connection, set_ids: list[int], exclude_id: int) -> set[int]:
    """Chunk-embedding ids for the OTHER papers IN THE SET — mirror of ``other_paper_chunk_embedding_ids``, but
    scoped to ``set_ids`` (and excluding ``exclude_id`` + soft-deleted papers). This is the set scoping: a
    contradicter is only retrieved when it belongs to another paper *in the chosen set*."""
    corpus = (
        embeddings.join(chunks, embeddings.c.target_id == chunks.c.id)
        .join(attachments, attachments.c.id == chunks.c.attachment_id)
        .join(papers, papers.c.id == chunks.c.paper_id)
    )
    rows = conn.execute(
        select(embeddings.c.id)
        .select_from(corpus)
        .where(
            embeddings.c.target_type == "chunk",
            chunks.c.paper_id.in_(set_ids),
            chunks.c.paper_id != exclude_id,
            papers.c.deleted_at.is_(None),
            attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES),
        )
    )
    return {int(r[0]) for r in rows}


def set_contested_claims(
    conn: Connection,
    set_ids: list[int],
    *,
    embed_model: EmbeddingModel,
    vector_store: VectorStore,
    stance_scorer: StanceScorer,
    on_stage: Callable[[str, str, int | None], None] | None = None,
) -> list[dict]:
    """For each paper in the set, the claims another paper *in the set* contradicts — reusing ``find_contested_claims``
    with ``other_chunk_ids`` scoped to the set. A signal (the disagreement the set already contains), never a verdict;
    each row carries the verbatim contradicting passage + both paper ids + page + stance + confidence."""
    resolve = make_chunk_resolver(conn)
    out: list[dict] = []
    scopes = [
        ContestedSearchScope(
            paper_id=paper_id,
            claim_sentences=extract_claim_sentences(conn, paper_id),
            other_chunk_ids=set_chunk_embedding_ids(conn, set_ids, paper_id),
        )
        for paper_id in set_ids
    ]
    reports = search_contested_claim_scopes(
        conn,
        scopes=scopes,
        embed_model=embed_model,
        vector_store=vector_store,
        stance_scorer=stance_scorer,
        resolve_chunk=resolve,
        on_stage=on_stage,
    )
    for paper_id, report in zip(set_ids, reports, strict=True):
        for c in report.contested_claims:
            out.append(
                {
                    "claim": c.claim,
                    "passage": c.passage,
                    "claim_paper_id": paper_id,
                    "other_paper_id": c.other_paper_id,
                    "page": c.page,
                    "stance": c.stance,
                    "confidence": c.confidence,
                }
            )
    return out


def set_aggregate(conn: Connection, set_ids: list[int], contested_claims: list[dict]) -> list[dict]:
    """One row per set paper: its ALREADY-STORED method signals + its intra-set contested-count. A FACT MATRIX
    (per-paper check statuses), NEVER a summed score or a ranking (PRINCIPLES: no opaque composite score). An empty
    ``method_signals`` means "these checks surfaced nothing on this paper", never "clean" (silence ≠ certificate)."""
    contested_by_paper: dict[int, int] = {}
    for claim in contested_claims:
        pid = int(claim["claim_paper_id"])
        contested_by_paper[pid] = contested_by_paper.get(pid, 0) + 1
    rows: list[dict] = []
    for paper_id in set_ids:
        paper = get_paper(conn, paper_id)
        rows.append(
            {
                "paper_id": paper_id,
                "title": str(paper["title"] or f"Paper {paper_id}"),
                "method_signals": _stored_method_signals(conn, paper_id),
                "contested_count": contested_by_paper.get(paper_id, 0),
            }
        )
    return rows
