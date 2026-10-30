"""Build one embedding profile's chunk index: resumable, cancellable, committed per paper.

The index is derived data added beside every other profile's vectors -- nothing is relabelled, replaced or
deleted. Each paper's missing chunks are encoded in one batched call (LATENCY.md: batch independent model work)
and committed together, so an interrupted or cancelled build resumes exactly where it stopped: currentness is the
same identity + chunk-version predicate retrieval uses, recomputed on every run, with no cursor to drift.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import Engine, select

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import current_chunk_embedding_ids, embed_chunks
from app.backend.embeddings.profiles import eligible_chunks_query
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.schema import chunks, papers
from app.backend.persistence.sqlite_retry import run_write


def pending_chunks_by_paper(engine: Engine, model: EmbeddingModel) -> dict[int, list[int]]:
    """{paper_id: chunk ids lacking a current vector for ``model``}, in paper-id order."""
    eligible = eligible_chunks_query().add_columns(chunks.c.paper_id).subquery()
    with engine.connect() as conn:
        rows = conn.execute(select(eligible.c.paper_id, eligible.c.id, eligible.c.chunk_version)).all()
        current = current_chunk_embedding_ids(conn, ((int(r[1]), str(r[2])) for r in rows), model=model)
    pending: dict[int, list[int]] = defaultdict(list)
    for paper_id, chunk_id, _version in sorted(rows):
        if int(chunk_id) not in current:
            pending[int(paper_id)].append(int(chunk_id))
    return dict(pending)


def build_profile_index(
    engine: Engine,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    on_progress: Callable[[int, int, str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict:
    pending = pending_chunks_by_paper(engine, model)
    with engine.connect() as conn:
        titles = dict(conn.execute(select(papers.c.id, papers.c.title).where(papers.c.id.in_(list(pending)))).all())
    stats = {"papers_pending": len(pending), "papers_indexed": 0, "chunks_indexed": 0, "cancelled": False}
    for index, (paper_id, chunk_ids) in enumerate(pending.items(), start=1):
        if should_cancel is not None and should_cancel():
            stats["cancelled"] = True
            break
        if on_progress is not None:
            on_progress(index, len(pending), f"Indexing {(titles.get(paper_id) or 'paper')[:60]}")
        run_write(
            engine,
            lambda conn, ids=chunk_ids: embed_chunks(conn, model=model, vector_store=vector_store, chunk_ids=ids),
        )
        stats["papers_indexed"] += 1
        stats["chunks_indexed"] += len(chunk_ids)
    return stats
