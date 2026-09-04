"""Embedding generation and stale-record detection."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, RowMapping, and_, insert, select, update

from app.backend.embeddings.models import EmbeddingModel, normalize_text
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.document_roles import attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks, embeddings, papers
from app.backend.persistence.sql_batch import batched_rows

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
    document_roles: Iterable[str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[int]:
    rows = _chunk_rows(conn, chunk_ids, document_roles=document_roles)
    total = len(rows)
    # inc 418: one batched encode_texts() call for every row needing a fresh embedding, instead of one call per
    # row — same vectors out, computed together. Phase 1 classifies each row (existing embedding vs. needs one);
    # phase 2 batch-encodes; phase 3 walks rows again in original order to report progress + do the existing
    # insert/vector-store bookkeeping, preserving the exact per-row on_progress sequence tests assert on.
    #
    # Phase 1 was a per-row DB lookup ("cheap", and it is — once). At library scale it is the dominant cost of
    # the whole call: ~120s of pure lookups for a 716,670-chunk library, on a query-scoped synthesis where the
    # answer is almost always "every one of them is already embedded". It is now one batched set query with the
    # identical predicate — same rows classified the same way, asked once instead of once each.
    current = current_chunk_embedding_ids(
        conn, ((int(row["id"]), str(row["chunk_version"])) for row in rows), model=model
    )
    existing_ids: list[int | None] = []
    pending_texts: list[str] = []
    for row in rows:
        existing_id = current.get(int(row["id"]))
        existing_ids.append(existing_id)
        if existing_id is None:
            pending_texts.append(str(row["text"]))

    vectors = iter(model.encode_texts(pending_texts) if pending_texts else [])

    created: list[int] = []
    for index, (row, existing_id) in enumerate(zip(rows, existing_ids, strict=True), start=1):
        if on_progress:
            on_progress(index, total)  # inc 142: determinate progress for the long embed phase
        if existing_id is not None:
            created.append(existing_id)
            continue
        vector = next(vectors)
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
    total = len(rows)
    # inc 418: same batching technique as embed_chunks (see its comment) — classify each row first (empty text /
    # existing embedding / needs one), one batched encode_texts() call for every row that needs one, then a
    # second pass in original order for progress + the existing insert/vector-store bookkeeping. A row whose text
    # normalizes to empty still contributes nothing to `created` (unchanged from before).
    texts: list[str | None] = []
    existing_ids: list[int | None] = []
    pending_texts: list[str] = []
    for row in rows:
        text = paper_embedding_text(row)
        if not normalize_text(text, model.normalization):
            texts.append(None)
            existing_ids.append(None)
            continue
        texts.append(text)
        existing = _current_embedding(
            conn,
            target_type="paper",
            target_id=int(row["id"]),
            model=model,
            source_text_version=PAPER_TEXT_VERSION,
            source_chunk_version=None,
        )
        if existing is not None:
            existing_ids.append(int(existing["id"]))
        else:
            existing_ids.append(None)
            pending_texts.append(text)

    vectors = iter(model.encode_texts(pending_texts) if pending_texts else [])

    created: list[int] = []
    for index, (row, text, existing_id) in enumerate(zip(rows, texts, existing_ids, strict=True), start=1):
        if on_progress:
            on_progress(index, total)  # inc 142: determinate progress for the long embed phase
        if text is None:
            continue
        if existing_id is not None:
            created.append(existing_id)
            continue
        vector = next(vectors)
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


def _chunk_rows(
    conn: Connection, chunk_ids: list[int] | None, *, document_roles: Iterable[str] | None
) -> list[RowMapping]:
    if chunk_ids is not None:
        if document_roles is not None:
            raise ValueError("Pass chunk_ids or document_roles, not both")
        if not chunk_ids:
            return []
        # Batched: a library-wide caller passes every chunk id it holds, which overruns SQLite's
        # per-statement parameter cap on the runtime the packaged app ships. See sql_batch.
        rows = batched_rows(
            lambda batch: conn.execute(select(chunks).where(chunks.c.id.in_(batch))).mappings().all(),
            chunk_ids,
        )
        return sorted(rows, key=lambda row: int(row["id"]))  # batches arrive separately; restore id order
    else:
        if document_roles is None:
            raise ValueError("Embedding all chunks requires an explicit document_roles scope")
        stmt = (
            select(chunks)
            .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
            .where(attachment_document_role_clause(document_roles))
        )
    return list(conn.execute(stmt.order_by(chunks.c.id)).mappings())


def _paper_rows(conn: Connection, paper_ids: list[int] | None) -> list[RowMapping]:
    stmt = select(papers)
    if paper_ids:
        stmt = stmt.where(papers.c.id.in_(paper_ids))
    return list(conn.execute(stmt.order_by(papers.c.id)).mappings())


def current_chunk_embedding_ids(
    conn: Connection, pairs: Iterable[tuple[int, str]], *, model: EmbeddingModel
) -> dict[int, int]:
    """Set-based equivalent of ``_current_embedding`` for many chunks at once.

    Takes ``(chunk_id, chunk_version)`` pairs and returns ``{chunk_id: embedding_id}`` for exactly
    those chunks that already have a **current** embedding — the same predicate as
    ``_current_embedding`` (model identity plus both version columns equal to the chunk's own
    ``chunk_version``), evaluated once per batch instead of once per chunk.

    It takes pairs rather than rows so a caller that already holds the chunks (the synthesis
    ranking path holds ``SourceChunk``s, which carry ``chunk_version``) can classify them without
    re-reading every row back out of the database.

    ``_current_embedding`` takes ``.first()`` with no ORDER BY, so with duplicate rows for one key
    its choice is whatever SQLite returns first. This picks the **lowest** embedding id, which is
    both deterministic and the same row that ordering normally yields — the inc-438 tie-break
    convention (oldest embedding wins) rather than an arbitrary one.
    """
    wanted = {int(chunk_id): str(version) for chunk_id, version in pairs}
    if not wanted:
        return {}
    found = batched_rows(
        lambda batch: conn.execute(
            select(
                embeddings.c.id,
                embeddings.c.target_id,
                embeddings.c.source_text_version,
                embeddings.c.source_chunk_version,
            ).where(
                and_(
                    embeddings.c.target_type == "chunk",
                    embeddings.c.target_id.in_(batch),
                    embeddings.c.model_name == model.name,
                    embeddings.c.model_version == model.version,
                    embeddings.c.dimension == model.dimension,
                    embeddings.c.normalization == model.normalization,
                )
            )
        ).all(),
        list(wanted),
    )
    current: dict[int, int] = {}
    for embedding_id, target_id, text_version, chunk_version in found:
        version = wanted.get(int(target_id))
        # Both version columns must equal the chunk's own version, or the embedding is stale and the
        # chunk still needs re-embedding — the distinction that keeps edited text from being verified
        # against a vector of its previous wording.
        if version is None or text_version != version or chunk_version != version:
            continue
        existing = current.get(int(target_id))
        if existing is None or int(embedding_id) < existing:
            current[int(target_id)] = int(embedding_id)
    return current


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
