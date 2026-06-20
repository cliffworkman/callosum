"""Shared external-API response cache helpers (read/upsert against ``external_api_cache``).

Used by the Increment-B OA resolver adapters (DOAJ, Europe PMC, CORE, arXiv, bioRxiv, OSF) so each one
carries only its own mapping logic. Keyed by ``(provider, cache_key)``; upsert. (The pre-existing
openalex/crossref adapters keep their own private copies — not refactored here, to keep this feature's
diff minimal.)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, insert, select, update

from app.backend.persistence.schema import external_api_cache


def get_cached(conn: Connection, provider: str, cache_key: str):
    """The cached row mapping for (provider, cache_key), or None."""
    return (
        conn.execute(
            select(external_api_cache).where(
                external_api_cache.c.provider == provider,
                external_api_cache.c.cache_key == cache_key,
            )
        )
        .mappings()
        .first()
    )


def put_cached(
    conn: Connection,
    provider: str,
    cache_key: str,
    *,
    request_json: dict[str, Any],
    response_json: dict[str, Any] | None,
    status_code: int | None,
) -> None:
    """Insert or update the cached response for (provider, cache_key)."""
    existing = get_cached(conn, provider, cache_key)
    values = {"request_json": request_json, "response_json": response_json, "status_code": status_code}
    if existing is None:
        conn.execute(insert(external_api_cache).values(provider=provider, cache_key=cache_key, **values))
    else:
        conn.execute(update(external_api_cache).where(external_api_cache.c.id == int(existing["id"])).values(**values))
