"""Shared external-API response cache helpers (read/upsert against ``external_api_cache``).

Used by the external metadata / acquisition adapters so each one carries only its own mapping logic. Keyed by
``(provider, cache_key)``; single-statement SQLite upsert with bounded retry. Cache writes are best-effort for
transient writer locks because the caller already has the provider response in hand.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError

from app.backend.persistence.schema import external_api_cache
from app.backend.persistence.sqlite_retry import is_sqlite_locked, retry_sqlite_locked


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
    try:
        retry_sqlite_locked(
            lambda: _put_cached_once(
                conn,
                provider,
                cache_key,
                request_json=request_json,
                response_json=response_json,
                status_code=status_code,
            )
        )
    except OperationalError as exc:
        # Cache writes are best-effort. A transient SQLite writer lock should not fail the feature that already has
        # the provider response in hand.
        if is_sqlite_locked(exc):
            return
        raise


def _put_cached_once(
    conn: Connection,
    provider: str,
    cache_key: str,
    *,
    request_json: dict[str, Any],
    response_json: dict[str, Any] | None,
    status_code: int | None,
) -> None:
    values = {"request_json": request_json, "response_json": response_json, "status_code": status_code}
    statement = (
        sqlite_insert(external_api_cache)
        .values(provider=provider, cache_key=cache_key, **values)
        .on_conflict_do_update(index_elements=["provider", "cache_key"], set_=values)
    )
    conn.execute(statement)
