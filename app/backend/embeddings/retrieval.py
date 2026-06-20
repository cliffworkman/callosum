"""Similarity retrieval over stored embedding metadata and vectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, and_, not_, or_, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.schema import chunks, embeddings, papers


@dataclass(frozen=True)
class RetrievalHit:
    embedding_id: int
    target_type: str
    target_id: int
    score: float
    distance: float
    paper_id: int
    chunk_id: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    bbox_json: object | None = None
    title: str | None = None


def search_similar(
    conn: Connection,
    *,
    query: str | None = None,
    query_vector: list[float] | None = None,
    model: EmbeddingModel,
    vector_store: VectorStore,
    top_k: int = 5,
    target_types: tuple[Literal["chunk", "paper"], ...] = ("chunk", "paper"),
) -> list[RetrievalHit]:
    if query_vector is None:
        if query is None:
            raise ValueError("Either query or query_vector is required")
        query_vector = model.encode_texts([query])[0]

    candidate_ids = _candidate_embedding_ids(conn, model=model, target_types=target_types)
    vector_hits = vector_store.search(
        conn,
        vector=query_vector,
        top_k=top_k,
        candidate_embedding_ids=candidate_ids,
    )
    return [_resolve_hit(conn, hit.embedding_id, hit.distance) for hit in vector_hits]


def _candidate_embedding_ids(
    conn: Connection,
    *,
    model: EmbeddingModel,
    target_types: tuple[str, ...],
) -> set[int]:
    # Exclude embeddings that belong to a trashed (soft-deleted) paper — a paper-target embedding pointing at
    # a trashed paper, or a chunk-target embedding whose chunk belongs to one (inc 66). Keeps retrieval from
    # surfacing trashed content; bound-param subqueries (rule #3).
    trashed_papers = select(papers.c.id).where(papers.c.deleted_at.is_not(None))
    trashed_chunks = select(chunks.c.id).where(chunks.c.paper_id.in_(trashed_papers))
    belongs_to_trashed = or_(
        and_(embeddings.c.target_type == "paper", embeddings.c.target_id.in_(trashed_papers)),
        and_(embeddings.c.target_type == "chunk", embeddings.c.target_id.in_(trashed_chunks)),
    )
    rows = conn.execute(
        select(embeddings.c.id).where(
            embeddings.c.target_type.in_(target_types),
            embeddings.c.model_name == model.name,
            embeddings.c.model_version == model.version,
            embeddings.c.dimension == model.dimension,
            embeddings.c.normalization == model.normalization,
            not_(belongs_to_trashed),
        )
    )
    return {int(row[0]) for row in rows}


def _resolve_hit(conn: Connection, embedding_id: int, distance: float) -> RetrievalHit:
    embedding = conn.execute(select(embeddings).where(embeddings.c.id == embedding_id)).mappings().one()
    target_type = str(embedding["target_type"])
    if target_type == "chunk":
        chunk = conn.execute(select(chunks).where(chunks.c.id == embedding["target_id"])).mappings().one()
        paper = conn.execute(select(papers).where(papers.c.id == chunk["paper_id"])).mappings().one()
        return RetrievalHit(
            embedding_id=embedding_id,
            target_type=target_type,
            target_id=int(embedding["target_id"]),
            score=_score(distance),
            distance=distance,
            paper_id=int(chunk["paper_id"]),
            chunk_id=int(chunk["id"]),
            page_start=chunk["page_start"],
            page_end=chunk["page_end"],
            bbox_json=chunk["bbox_json"],
            title=paper["title"],
        )

    paper = conn.execute(select(papers).where(papers.c.id == embedding["target_id"])).mappings().one()
    return RetrievalHit(
        embedding_id=embedding_id,
        target_type=target_type,
        target_id=int(embedding["target_id"]),
        score=_score(distance),
        distance=distance,
        paper_id=int(paper["id"]),
        title=paper["title"],
    )


def _score(distance: float) -> float:
    return 1.0 / (1.0 + max(distance, 0.0))
