"""Bounded retry helpers for short SQLite write operations."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import TypeVar

from sqlalchemy import Connection, Engine
from sqlalchemy.exc import OperationalError

T = TypeVar("T")


def is_sqlite_locked(exc: OperationalError) -> bool:
    """Return True when SQLAlchemy wrapped a transient SQLite writer-lock error."""
    return "database is locked" in str(getattr(exc, "orig", exc)).lower()


def retry_sqlite_locked(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    delay_seconds: float = 0.05,
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    """Retry a short operation if SQLite reports a transient writer lock.

    This is intentionally scoped to short writes. It does not make long background jobs hold write
    locks earlier, and it does not hide non-lock database errors.
    """
    remaining = max(1, attempts)
    while True:
        try:
            return operation()
        except OperationalError as exc:
            remaining -= 1
            if remaining <= 0 or not is_sqlite_locked(exc):
                raise
            sleeper(delay_seconds)


def run_write(
    engine: Engine,
    operation: Callable[[Connection], T],
    *,
    attempts: int = 5,
    delay_seconds: float = 0.05,
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    """Run a SHORT read+write unit of work with **transaction-level** retry on a transient SQLite writer lock.

    Opens a FRESH connection per attempt, runs ``operation(conn)``, commits, and returns its result. On a
    ``database is locked`` error the WHOLE unit is retried on a new connection (a fresh snapshot) with bounded
    backoff — the granularity a snapshot-upgrade BUSY actually needs. Retrying a single ``conn.execute`` on the
    same still-open transaction can't clear it: the transaction keeps its stale snapshot / poisoned state.

    Non-lock errors and any non-``OperationalError`` (e.g. an ``HTTPException`` a 404 check raised inside the
    closure) propagate immediately, un-retried. The final attempt re-raises the lock error.

    Scoped to SHORT writes only. Do NOT wrap a multi-minute background job in this: a late collision would
    restart the entire job. Long jobs keep their own single ``engine.begin()`` unit.
    """
    remaining = max(1, attempts)
    while True:
        try:
            with engine.connect() as conn:
                result = operation(conn)
                conn.commit()
                return result
        except OperationalError as exc:
            remaining -= 1
            if remaining <= 0 or not is_sqlite_locked(exc):
                raise
            sleeper(delay_seconds)


def commit_each(
    engine: Engine,
    items: Iterable[T],
    process: Callable[[Connection, T], object],
    *,
    on_item_error: str = "skip",
    logger: object | None = None,
) -> list:
    """Process each item in its OWN short transaction (via ``run_write``), releasing the SQLite write lock between
    items — the long-job counterpart to ``run_write``. ``on_item_error="skip"`` logs a non-lock failure and
    continues (resilient batch: one bad item never aborts the run); ``"raise"`` propagates it. Returns the per-item
    results in order (``None`` for a skipped item). A transient writer lock on an item is retried by ``run_write``,
    not skipped."""
    results: list = []
    for item in items:
        try:
            results.append(run_write(engine, lambda conn, it=item: process(conn, it)))
        except Exception as exc:  # noqa: BLE001 — batch resilience is the contract
            if on_item_error == "raise":
                raise
            if logger is not None:
                logger.warning("commit_each: skipped an item: %s: %s", type(exc).__name__, exc)
            results.append(None)
    return results
