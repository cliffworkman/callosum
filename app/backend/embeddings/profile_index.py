"""Build one embedding profile's chunk index: resumable, cancellable, committed in bounded batches.

The index is derived data added beside every other profile's vectors -- nothing is relabelled, replaced or
deleted, except this profile's own unusable rows (see ``repair_partial_vectors``). Work is planned as chunk *ids*
only; passage text is read one bounded batch at a time, encoded in one batched call (LATENCY.md) and committed in
the same short transaction as its vectors, so an interrupted, killed or cancelled build loses at most the batch in
flight and resumes exactly where it stopped. Currentness is the same identity + chunk-version predicate retrieval
uses, recomputed on every run, with no cursor to drift.

Batch size changes how many passages share one forward pass. Each passage is still encoded with its own attention
mask, so the vector is the same up to floating-point summation order; inc 610 measured the bound on the real
Arctic S checkpoint (see INCREMENT-610-NOTES.md).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import Connection, Engine, and_, delete, or_, select, text

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import current_chunk_embedding_ids, embed_chunks
from app.backend.embeddings.profiles import eligible_chunks_query
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.schema import chunks, embeddings
from app.backend.persistence.sqlite_retry import run_write

DEFAULT_INDEX_BATCH = 8


def pending_chunks_by_paper(engine: Engine, model: EmbeddingModel) -> dict[int, list[int]]:
    """{paper_id: chunk ids lacking a current vector for ``model``}, in paper-id order. Ids only, never text."""
    eligible = eligible_chunks_query().add_columns(chunks.c.paper_id).subquery()
    with engine.connect() as conn:
        rows = conn.execute(select(eligible.c.paper_id, eligible.c.id, eligible.c.chunk_version)).all()
        current = current_chunk_embedding_ids(conn, ((int(r[1]), str(r[2])) for r in rows), model=model)
    pending: dict[int, list[int]] = defaultdict(list)
    for paper_id, chunk_id, _version in sorted(rows):
        if int(chunk_id) not in current:
            pending[int(paper_id)].append(int(chunk_id))
    return dict(pending)


def pending_chunk_ids(engine: Engine, model: EmbeddingModel) -> list[int]:
    return [cid for ids in pending_chunks_by_paper(engine, model).values() for cid in ids]


def index_chunk_batch(
    engine: Engine,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    chunk_ids: list[int],
    on_commit: Callable[[Connection, int], None] | None = None,
) -> None:
    """Embed one bounded batch and commit it with ``on_commit`` (the durable checkpoint) in ONE transaction.

    ``embed_chunks`` re-checks currentness inside the transaction, so a chunk indexed by an earlier attempt (or
    whose version changed) is never duplicated; the vectors, their identity rows and the checkpoint commit or
    roll back together.
    """

    def write(conn: Connection) -> None:
        embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=chunk_ids)
        if on_commit is not None:
            on_commit(conn, len(chunk_ids))

    run_write(engine, write)


def _profile_rows(model: EmbeddingModel):  # type: ignore[no-untyped-def]
    return and_(
        embeddings.c.target_type == "chunk",
        embeddings.c.model_name == model.name,
        embeddings.c.model_version == model.version,
    )


def _load_sqlite_vec(conn: Connection) -> None:
    import sqlite_vec

    raw = conn.connection.driver_connection
    raw.enable_load_extension(True)
    try:
        sqlite_vec.load(raw)
    finally:
        raw.enable_load_extension(False)


def vector_integrity(conn: Connection, model: EmbeddingModel, *, dimension: int) -> dict:
    """Count this profile's rows that must never count as indexed (MiniLM rows are never inspected).

    * ``missing_vector``: an identity row with no stored vector (no ref, or no row in the vec table).
    * ``orphan``: a row whose chunk no longer exists.
    * ``stale``: a row whose chunk changed since it was embedded (left in place: currentness already ignores it,
      and it is the same evidence history every other profile keeps).
    * ``duplicate_current``: chunks with more than one current row (the oldest wins; reported, not deleted).
    """
    base = _profile_rows(model)
    table = f"callosum_vec_embeddings_{int(dimension)}"
    has_vec = conn.execute(text("SELECT 1 FROM sqlite_master WHERE name = :t"), {"t": table}).first() is not None
    missing_ref = conn.execute(
        select(embeddings.c.id).where(
            base, or_(embeddings.c.vector_store_ref.is_(None), embeddings.c.dimension != dimension)
        )
    ).scalars()
    missing = set(int(i) for i in missing_ref)
    if has_vec:
        _load_sqlite_vec(conn)  # the virtual table is unreadable on a connection without the extension
        # Constant table name built from an int; the profile filter is bound.
        rows = conn.execute(
            text(
                f"SELECT e.id FROM embeddings e LEFT JOIN {table} v ON v.rowid = e.id "  # nosec B608 -- int-derived table name
                "WHERE e.target_type = 'chunk' AND e.model_name = :n AND e.model_version = :v AND v.rowid IS NULL"
            ),
            {"n": model.name, "v": model.version},
        ).scalars()
        missing |= set(int(i) for i in rows)
    orphan = conn.execute(
        select(embeddings.c.id)
        .select_from(embeddings.outerjoin(chunks, chunks.c.id == embeddings.c.target_id))
        .where(base, chunks.c.id.is_(None))
    ).scalars()
    stale = conn.execute(
        select(embeddings.c.id)
        .select_from(embeddings.join(chunks, chunks.c.id == embeddings.c.target_id))
        .where(
            base,
            or_(
                embeddings.c.source_chunk_version != chunks.c.chunk_version,
                embeddings.c.source_text_version != chunks.c.chunk_version,
            ),
        )
    ).scalars()
    current_dupes = conn.execute(
        text(
            "SELECT COUNT(*) FROM (SELECT e.target_id FROM embeddings e JOIN chunks c ON c.id = e.target_id "
            "WHERE e.target_type = 'chunk' AND e.model_name = :n AND e.model_version = :v "
            "AND e.source_chunk_version = c.chunk_version AND e.source_text_version = c.chunk_version "
            "GROUP BY e.target_id HAVING COUNT(*) > 1)"
        ),
        {"n": model.name, "v": model.version},
    ).scalar_one()
    return {
        "missing_vector_ids": sorted(missing),
        "orphan_ids": sorted(int(i) for i in orphan),
        "stale_rows": len(list(stale)),
        "duplicate_current_chunks": int(current_dupes),
    }


def repair_partial_vectors(engine: Engine, model: EmbeddingModel, *, vector_store: VectorStore, dimension: int) -> dict:
    """Delete only this profile's identity rows that have no usable vector, so they are re-embedded rather than
    counted as indexed. Orphans of this profile are removed with their vectors. Every other model's rows are
    outside the predicate and are never read for deletion."""

    def write(conn: Connection) -> dict:
        found = vector_integrity(conn, model, dimension=dimension)
        doomed = sorted(set(found["missing_vector_ids"]) | set(found["orphan_ids"]))
        for embedding_id in doomed:
            vector_store.delete(conn, embedding_id=embedding_id, dimension=dimension)
        if doomed:
            conn.execute(delete(embeddings).where(_profile_rows(model), embeddings.c.id.in_(doomed)))
        return {**found, "repaired_rows": len(doomed)}

    return run_write(engine, write)


def build_profile_index(
    engine: Engine,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    on_progress: Callable[[int, int, str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    batch_size: int = DEFAULT_INDEX_BATCH,
    on_commit: Callable[[Connection, int], None] | None = None,
) -> dict:
    """Index every pending chunk in bounded batches. ``should_cancel`` is checked between batches."""
    pending = pending_chunks_by_paper(engine, model)
    queue = [cid for ids in pending.values() for cid in ids]
    stats = {"papers_pending": len(pending), "papers_indexed": 0, "chunks_indexed": 0, "cancelled": False}
    paper_of = {cid: pid for pid, ids in pending.items() for cid in ids}
    done_per_paper: dict[int, int] = defaultdict(int)
    size = max(1, int(batch_size))
    for start in range(0, len(queue), size):
        if should_cancel is not None and should_cancel():
            stats["cancelled"] = True
            break
        batch = queue[start : start + size]
        index_chunk_batch(engine, model=model, vector_store=vector_store, chunk_ids=batch, on_commit=on_commit)
        stats["chunks_indexed"] += len(batch)
        for cid in batch:
            done_per_paper[paper_of[cid]] += 1
        stats["papers_indexed"] = sum(1 for pid, n in done_per_paper.items() if n == len(pending[pid]))
        if on_progress is not None:
            on_progress(stats["chunks_indexed"], len(queue), "Indexing passages")
    return stats
