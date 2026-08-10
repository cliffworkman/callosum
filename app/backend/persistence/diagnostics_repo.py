"""Superuser-only operational stats (inc 468). Mirrors the established count-query shape
(`gapfinder.py`'s live-paper count, `wanted_repo.py`'s with-PDF count) — one small read, no new tables."""

from __future__ import annotations

from sqlalchemy import Connection, func, select

from app.backend.persistence.schema import chunks, embeddings, papers


def library_stats(conn: Connection) -> dict[str, int]:
    paper_count = (
        conn.execute(select(func.count()).select_from(papers).where(papers.c.deleted_at.is_(None))).scalar() or 0
    )
    chunk_count = conn.execute(select(func.count()).select_from(chunks)).scalar() or 0
    embedding_count = conn.execute(select(func.count()).select_from(embeddings)).scalar() or 0
    return {"paper_count": paper_count, "chunk_count": chunk_count, "embedding_count": embedding_count}
