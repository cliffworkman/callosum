"""Bounded scoped snapshots for My Publications emerging citing topics (inc 390)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select

from app.backend.clustering.my_publication_topics import EmergingCitingTopic
from app.backend.persistence.schema import my_publication_emerging_topic_cache

MAX_CACHED_SCOPES = 16


def replace_emerging_topic_cache(
    conn: Connection,
    topics: list[EmergingCitingTopic],
    coverage: dict[str, Any],
    *,
    computed_at: str,
    scope_key: str = "all",
    scope: dict[str, Any] | None = None,
) -> None:
    """Atomically replace one scope, including a genuine empty result, then prune old scopes."""
    conn.execute(
        delete(my_publication_emerging_topic_cache).where(my_publication_emerging_topic_cache.c.scope_key == scope_key)
    )
    conn.execute(
        insert(my_publication_emerging_topic_cache).values(
            scope_key=scope_key,
            scope=scope or {"kind": "all", "domain_keys": [], "domain_labels": [], "paper_ids": []},
            topics=[topic.to_dict() for topic in topics],
            coverage=coverage,
            computed_at=computed_at,
        )
    )
    stale_ids = list(
        conn.execute(
            select(my_publication_emerging_topic_cache.c.id)
            .order_by(
                my_publication_emerging_topic_cache.c.computed_at.desc(),
                my_publication_emerging_topic_cache.c.id.desc(),
            )
            .offset(MAX_CACHED_SCOPES)
        ).scalars()
    )
    if stale_ids:
        conn.execute(
            delete(my_publication_emerging_topic_cache).where(my_publication_emerging_topic_cache.c.id.in_(stale_ids))
        )


def read_emerging_topic_cache(conn: Connection, *, scope_key: str = "all") -> dict[str, Any] | None:
    found = (
        conn.execute(
            select(my_publication_emerging_topic_cache).where(
                my_publication_emerging_topic_cache.c.scope_key == scope_key
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(found) if found is not None else None
