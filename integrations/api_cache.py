"""Shared external-API response cache helpers (read/upsert against ``external_api_cache``).

Used by the external metadata / acquisition adapters so each one carries only its own mapping logic. Keyed by
``(provider, cache_key)``; single-statement SQLite upsert with bounded retry. Cache writes are best-effort for
transient writer locks because the caller already has the provider response in hand.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError

from app.backend.persistence.schema import external_api_cache
from app.backend.persistence.sqlite_retry import is_sqlite_locked, retry_sqlite_locked, run_write


def get_cached(conn: Connection, provider: str, cache_key: str, *, max_age_seconds: float | None = None):
    """Return a non-expired cached row, optionally requiring a bounded age."""
    row = (
        conn.execute(
            select(external_api_cache).where(
                external_api_cache.c.provider == provider,
                external_api_cache.c.cache_key == cache_key,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = _as_datetime(row.get("expires_at"))
    if expires_at is not None and expires_at <= now:
        return None
    if max_age_seconds is not None:
        fetched_at = _as_datetime(row.get("fetched_at"))
        if fetched_at is None or fetched_at < now - timedelta(seconds=max(0.0, max_age_seconds)):
            return None
    return row


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


def put_cached_committing(
    engine: Engine,
    provider: str,
    cache_key: str,
    *,
    request_json: dict[str, Any],
    response_json: dict[str, Any] | None,
    status_code: int | None,
) -> None:
    """Like ``put_cached``, but self-commits in its OWN short transaction (inc D). For callers running their fetch
    phase on a read connection (gap-finder / my-publications) so caching a provider response never holds the
    caller's write lock. Best-effort: a transient writer lock is swallowed (the caller already has the response)."""
    try:
        run_write(
            engine,
            lambda conn: _put_cached_once(
                conn,
                provider,
                cache_key,
                request_json=request_json,
                response_json=response_json,
                status_code=status_code,
            ),
        )
    except OperationalError as exc:
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
    values = {
        "request_json": request_json,
        "response_json": response_json,
        "status_code": status_code,
        "fetched_at": func.current_timestamp(),
        "expires_at": None,
    }
    statement = (
        sqlite_insert(external_api_cache)
        .values(provider=provider, cache_key=cache_key, **values)
        .on_conflict_do_update(index_elements=["provider", "cache_key"], set_=values)
    )
    conn.execute(statement)


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None
