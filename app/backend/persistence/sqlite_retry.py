"""Bounded retry helpers for short SQLite write operations."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

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
