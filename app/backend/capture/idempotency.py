"""Idempotent capture outcomes: a retry after a lost response returns the first result (#61 Phase 1).

This is the mechanism that prevents a **duplicate mutation** — and it is deliberately NOT the session
token's job. A session token is a bearer credential that is reusable until it expires, so a replayed
request inside its TTL succeeds at the transport layer; that is what bearer tokens do. Conflating the
two would let the audit claim replay protection it does not have.

So: the extension sends an ``Idempotency-Key`` with each capture. If the response is lost in flight
and the extension retries, the same key returns the original outcome instead of admitting the paper a
second time. Bounded and TTL'd, because an unbounded map keyed on client-supplied strings is a memory
DoS a hostile extension could drive.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

IDEMPOTENCY_TTL_S = 900.0  # a retry long after this is treated as a new intent, not a duplicate
IDEMPOTENCY_KEY_MAX_LEN = 128
MAX_REMEMBERED = 256  # bounded: client-supplied keys must not grow this map without limit

# {key: (expiry_monotonic, outcome)}. In-process only; a restart simply forgets, which is safe —
# the worst case is one duplicate admission after a crash mid-retry, and dedupe still catches it.
_outcomes: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = Lock()


def remembered(key: str | None, *, now: float | None = None) -> dict[str, Any] | None:
    """The stored outcome for this key, or None. Expired entries are pruned as a side effect."""
    if not key:
        return None
    now = time.monotonic() if now is None else now
    with _lock:
        _prune_locked(now)
        entry = _outcomes.get(key)
        return dict(entry[1]) if entry else None


def remember(key: str | None, outcome: dict[str, Any], *, now: float | None = None) -> None:
    """Record this capture's outcome so an identical retry replays it instead of mutating again."""
    if not key:
        return
    now = time.monotonic() if now is None else now
    with _lock:
        _prune_locked(now)
        if len(_outcomes) >= MAX_REMEMBERED and key not in _outcomes:
            oldest = min(_outcomes, key=lambda existing: _outcomes[existing][0])
            _outcomes.pop(oldest, None)
        _outcomes[key] = (now + IDEMPOTENCY_TTL_S, dict(outcome))


def clear() -> None:
    """Forget every remembered outcome (tests)."""
    with _lock:
        _outcomes.clear()


def _prune_locked(now: float) -> None:
    for key in [key for key, (expiry, _) in _outcomes.items() if expiry <= now]:
        _outcomes.pop(key, None)
