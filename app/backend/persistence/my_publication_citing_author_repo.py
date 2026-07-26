"""Bounded scoped snapshots for My Publications citing-author evidence (inc 391)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select

from app.backend.clustering.my_publication_citing_authors import CitingAuthor
from app.backend.persistence.schema import my_publication_citing_author_cache

MAX_CACHED_SCOPES = 16


def replace_citing_author_cache(
    conn: Connection,
    authors: list[CitingAuthor],
    coverage: dict[str, Any],
    *,
    computed_at: str,
    scope_key: str = "all",
    scope: dict[str, Any] | None = None,
) -> None:
    """Atomically replace one scope, including a genuine empty result, then prune old scopes."""
    conn.execute(
        delete(my_publication_citing_author_cache).where(my_publication_citing_author_cache.c.scope_key == scope_key)
    )
    conn.execute(
        insert(my_publication_citing_author_cache).values(
            scope_key=scope_key,
            scope=scope or {"kind": "all", "domain_keys": [], "domain_labels": [], "paper_ids": []},
            authors=[author.to_dict() for author in authors],
            coverage=coverage,
            computed_at=computed_at,
        )
    )
    stale_ids = list(
        conn.execute(
            select(my_publication_citing_author_cache.c.id)
            .order_by(
                my_publication_citing_author_cache.c.computed_at.desc(),
                my_publication_citing_author_cache.c.id.desc(),
            )
            .offset(MAX_CACHED_SCOPES)
        ).scalars()
    )
    if stale_ids:
        conn.execute(
            delete(my_publication_citing_author_cache).where(my_publication_citing_author_cache.c.id.in_(stale_ids))
        )


def read_citing_author_cache(conn: Connection, *, scope_key: str = "all") -> dict[str, Any] | None:
    found = (
        conn.execute(
            select(my_publication_citing_author_cache).where(
                my_publication_citing_author_cache.c.scope_key == scope_key
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(found) if found is not None else None
