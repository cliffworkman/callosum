"""Per-user rate limiting for the sync server (backlog #15).

A tiny in-memory sliding-window limiter, deliberately standalone (no import from ``app.backend`` — `sync_server`
is a fenced, independently-deployable service; see ``.claude/security-audits/2026-06-29_sync-server.md``). Shape
mirrors ``app/backend/api/access_control.py::RateLimiter`` (the main app's own hand-rolled limiter) but is
reimplemented here rather than imported, since importing would pull the whole main-app package tree into a
deployable meant to stand alone.

Keyed by the caller's OIDC ``sub`` (the only identity this server has — see ``auth.py``), not by IP: a user's
requests across however many devices they sync share one bucket, since there is no per-device claim in the
token to key on more finely.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock


class RateLimiter:
    """A tiny in-memory sliding-window limiter — no dependency, thread-safe, bounded (one deque per key)."""

    def __init__(self, max_requests: int, window: float) -> None:
        self.max = max_requests
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            dq = self._hits.setdefault(key, deque())
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.max:
                return False
            dq.append(now)
            return True

    def retry_after(self, key: str, now: float | None = None) -> int:
        """Seconds until the oldest hit in this key's window expires (a `Retry-After` hint). 0 if not limited."""
        now = time.monotonic() if now is None else now
        with self._lock:
            dq = self._hits.get(key)
            if not dq:
                return 0
            remaining = self.window - (now - dq[0])
            return max(0, int(remaining) + 1)
