"""Embedding generation and stale-record detection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, RowMapping, and_, insert, select, update

from app.backend.embeddings.models import EmbeddingModel, normalize_text
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.schema import chunks, embeddings, papers

PAPER_TEXT_VERSION = "paper-metadata-v1"
TargetType = Literal["chunk", "paper"]


@dataclass(frozen=True)
class StaleEmbedding:
    embedding_id: int
    target_type: str
    target_id: int
    reason: str


def embed_chunks(
    conn: Connection,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    chunk_ids: list[int] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[int]:
    rows = _chunk_rows(conn, chunk_ids)
    created: list[int] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        if on_progress:
            on_progress(index, total)  # inc 142: determinate progress for the long embed phase
        existing = _current_embedding(
            conn,
            target_type="chunk",
            target_id=int(row["id"]),
            model=model,
            source_text_version=str(row["chunk_version"]),
            source_chunk_version=str(row["chunk_version"]),
        )
        if existing is not None:
            created.append(int(existing["id"]))
            continue

        vector = model.encode_texts([str(row["text"])])[0]
        embedding_id = _insert_embedding_metadata(
            conn,
            target_type="chunk",
            target_id=int(row["id"]),
            model=model,
            vector_store=vector_store,
            source_text_version=str(row["chunk_version"]),
            source_chunk_version=str(row["chunk_version"]),
            dimension=len(vector),
        )
        vector_ref = vector_store.add(conn, embedding_id=embedding_id, vector=vector)
        _set_vector_ref(conn, embedding_id, vector_store.kind, vector_ref)
        created.append(embedding_id)
    return created


def embed_papers(
    conn: Connection,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    paper_ids: list[int] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[int]:
    rows = _paper_rows(conn, paper_ids)
    created: list[int] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        if on_progress:
            on_progress(index, total)  # inc 142: determinate progress for the long embed phase
        text = paper_embedding_text(row)
        if not normalize_text(text, model.normalization):
            continue
        existing = _current_embedding(
            conn,
            target_type="paper",
            target_id=int(row["id"]),
            model=model,
            source_text_version=PAPER_TEXT_VERSION,
            source_chunk_version=None,
        )
        if existing is not None:
            created.append(int(existing["id"]))
            continue

        vector = model.encode_texts([text])[0]
        embedding_id = _insert_embedding_metadata(
            conn,
            target_type="paper",
            target_id=int(row["id"]),
            model=model,
            vector_store=vector_store,
            source_text_version=PAPER_TEXT_VERSION,
            source_chunk_version=None,
            dimension=len(vector),
        )
        vector_ref = vector_store.add(conn, embedding_id=embedding_id, vector=vector)
        _set_vector_ref(conn, embedding_id, vector_store.kind, vector_ref)
        created.append(embedding_id)
    return created


def find_stale_embeddings(conn: Connection, *, model: EmbeddingModel) -> list[StaleEmbedding]:
    stale: list[StaleEmbedding] = []
    rows = conn.execute(select(embeddings)).mappings()
    for row in rows:
        embedding_id = int(row["id"])
        target_type = str(row["target_type"])
        target_id = int(row["target_id"])
        if (
            row["model_name"] != model.name
            or row["model_version"] != model.version
            or int(row["dimension"]) != model.dimension
            or row["normalization"] != model.normalization
        ):
            stale.append(StaleEmbedding(embedding_id, target_type, target_id, "embedding-model-changed"))
            continue
        if target_type == "chunk":
            chunk_row = conn.execute(select(chunks).where(chunks.c.id == target_id)).mappings().first()
            if chunk_row is None:
                stale.append(StaleEmbedding(embedding_id, target_type, target_id, "missing-source-chunk"))
            elif row["source_chunk_version"] != chunk_row["chunk_version"]:
                stale.append(StaleEmbedding(embedding_id, target_type, target_id, "chunk-version-changed"))
        elif target_type == "paper" and row["source_text_version"] != PAPER_TEXT_VERSION:
            stale.append(StaleEmbedding(embedding_id, target_type, target_id, "paper-text-version-changed"))
    return stale


def paper_embedding_text(row: RowMapping) -> str:
    parts = [
        row["title"],
        row["abstract"],
        row["venue"],
        str(row["year"]) if row["year"] is not None else None,
        row["first_author_family_name"],
    ]
    return " ".join(str(part) for part in parts if part)


def _chunk_rows(conn: Connection, chunk_ids: list[int] | None) -> list[RowMapping]:
    stmt = select(chunks)
    if chunk_ids:
        stmt = stmt.where(chunks.c.id.in_(chunk_ids))
    return list(conn.execute(stmt.order_by(chunks.c.id)).mappings())


def _paper_rows(conn: Connection, paper_ids: list[int] | None) -> list[RowMapping]:
    stmt = select(papers)
    if paper_ids:
        stmt = stmt.where(papers.c.id.in_(paper_ids))
    return list(conn.execute(stmt.order_by(papers.c.id)).mappings())


def _current_embedding(
    conn: Connection,
    *,
    target_type: TargetType,
    target_id: int,
    model: EmbeddingModel,
    source_text_version: str,
    source_chunk_version: str | None,
) -> RowMapping | None:
    return (
        conn.execute(
            select(embeddings).where(
                and_(
                    embeddings.c.target_type == target_type,
                    embeddings.c.target_id == target_id,
                    embeddings.c.model_name == model.name,
                    embeddings.c.model_version == model.version,
                    embeddings.c.dimension == model.dimension,
                    embeddings.c.normalization == model.normalization,
                    embeddings.c.source_text_version == source_text_version,
                    embeddings.c.source_chunk_version.is_(None)
                    if source_chunk_version is None
                    else embeddings.c.source_chunk_version == source_chunk_version,
                )
            )
        )
        .mappings()
        .first()
    )


def _insert_embedding_metadata(
    conn: Connection,
    *,
    target_type: TargetType,
    target_id: int,
    model: EmbeddingModel,
    vector_store: VectorStore,
    source_text_version: str,
    source_chunk_version: str | None,
    dimension: int,
) -> int:
    result = conn.execute(
        insert(embeddings).values(
            target_type=target_type,
            target_id=target_id,
            model_name=model.name,
            model_version=model.version,
            dimension=dimension,
            normalization=model.normalization,
            source_text_version=source_text_version,
            source_chunk_version=source_chunk_version,
            vector_store_kind=vector_store.kind,
            vector_store_ref="pending",
        )
    )
    return int(result.inserted_primary_key[0])


def _set_vector_ref(conn: Connection, embedding_id: int, kind: str, ref: str) -> None:
    conn.execute(
        update(embeddings).where(embeddings.c.id == embedding_id).values(vector_store_kind=kind, vector_store_ref=ref)
    )
