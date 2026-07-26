"""Bounded scoped snapshots for My Publications grounded citation gaps (incs 386/389)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select

from app.backend.clustering.my_publication_gaps import MyPublicationCitationGap
from app.backend.persistence.schema import my_publication_citation_gap_cache

MAX_CACHED_SCOPES = 16


def replace_my_publication_citation_gap_cache(
    conn: Connection,
    candidates: list[MyPublicationCitationGap],
    coverage: dict[str, Any],
    *,
    computed_at: str,
    scope_key: str = "all",
    scope: dict[str, Any] | None = None,
) -> None:
    """Atomically replace one bounded scope, including a real empty result, then prune old scopes."""
    conn.execute(
        delete(my_publication_citation_gap_cache).where(my_publication_citation_gap_cache.c.scope_key == scope_key)
    )
    conn.execute(
        insert(my_publication_citation_gap_cache).values(
            scope_key=scope_key,
            scope=scope or {"kind": "all", "domain_keys": [], "domain_labels": [], "paper_ids": []},
            candidates=[candidate.to_dict() for candidate in candidates],
            coverage=coverage,
            computed_at=computed_at,
        )
    )
    stale_ids = list(
        conn.execute(
            select(my_publication_citation_gap_cache.c.id)
            .order_by(
                my_publication_citation_gap_cache.c.computed_at.desc(),
                my_publication_citation_gap_cache.c.id.desc(),
            )
            .offset(MAX_CACHED_SCOPES)
        ).scalars()
    )
    if stale_ids:
        conn.execute(
            delete(my_publication_citation_gap_cache).where(my_publication_citation_gap_cache.c.id.in_(stale_ids))
        )


def read_my_publication_citation_gap_cache(
    conn: Connection,
    *,
    scope_key: str = "all",
) -> dict[str, Any] | None:
    result = conn.execute(
        select(my_publication_citation_gap_cache).where(my_publication_citation_gap_cache.c.scope_key == scope_key)
    )
    found = result.mappings().one_or_none()
    return dict(found) if found is not None else None
