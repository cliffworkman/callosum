"""Single-snapshot local cache for My Publications grounded citation gaps (inc 386)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select

from app.backend.clustering.my_publication_gaps import MyPublicationCitationGap
from app.backend.persistence.schema import my_publication_citation_gap_cache


def replace_my_publication_citation_gap_cache(
    conn: Connection,
    candidates: list[MyPublicationCitationGap],
    coverage: dict[str, Any],
    *,
    computed_at: str,
) -> None:
    """Atomically replace the one bounded snapshot, including a real empty result."""
    conn.execute(delete(my_publication_citation_gap_cache))
    conn.execute(
        insert(my_publication_citation_gap_cache).values(
            id=1,
            candidates=[candidate.to_dict() for candidate in candidates],
            coverage=coverage,
            computed_at=computed_at,
        )
    )


def read_my_publication_citation_gap_cache(conn: Connection) -> dict[str, Any] | None:
    result = conn.execute(select(my_publication_citation_gap_cache).where(my_publication_citation_gap_cache.c.id == 1))
    found = result.mappings().one_or_none()
    return dict(found) if found is not None else None
