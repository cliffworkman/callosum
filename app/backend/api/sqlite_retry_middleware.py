"""A backstop ASGI middleware that retries a mutating request on a transient SQLite writer lock.

Layer 2 of the "database is locked" hardening (Layer 1 is ``persistence.sqlite_retry.run_write``, the precise
in-request retry wired into the hot short-write endpoints). This is the catch-all for the long tail of pure-DB
write endpoints that weren't individually converted: if a handler raises an uncaught
``OperationalError: database is locked`` **before** producing any response, we re-run the whole request on a
fresh connection with bounded backoff.

Why this is safe:
- We retry **only** when nothing has been sent yet (``_started`` stays False). A lock error is raised from the
  DB write inside the handler, *before* the response is built — so nothing was sent and the request's
  transaction rolled back (nothing committed). Re-running a pure-DB handler is then side-effect-free.
- We **never** retry a request whose path is in ``REPLAY_UNSAFE_PREFIXES`` — the families that do more than a
  pure DB write (spawn a background job, call an external service, write a secret). Re-running those could
  double-spawn a job or re-issue a fetch, so they are excluded; the ``run_write`` layer (not replay) is the
  right tool where those also need lock-hardening.
- Only mutating methods are considered; GET/HEAD/OPTIONS pass straight through. Non-lock errors propagate
  immediately, un-retried.

The request body is buffered once and replayed on each attempt (a plain ``receive`` can be consumed only once).
"""

from __future__ import annotations

import asyncio

from sqlalchemy.exc import OperationalError

from app.backend.persistence.sqlite_retry import is_sqlite_locked

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Path prefixes whose handlers do MORE than a pure DB write (external fetch / background-job spawn / secret
# write / subprocess) — replaying them could double-execute the side effect, so they are NOT retried here.
REPLAY_UNSAFE_PREFIXES: tuple[str, ...] = (
    "/library",  # scan / watched-rescan → filesystem read + long import job
    "/settings",  # BYOK key / egress consent → keychain / secret file writes
    "/access",  # remote-access token + recovery
    "/sync",  # cross-device egress channel
    "/discovery",  # external metadata/discovery fetch
    "/acquire",  # full-text acquisition (external + job)
    "/enrich",  # external metadata enrichment
    "/gaps",  # gap-finder job
    "/summaries",  # summarize → egress generation job
    "/critical-read",  # scrutiny job (+ Tier-2 egress)
    "/reference-integrity",  # batch external checks
    "/methods",  # retraction batch / external registries
    "/workbench",  # assisted extraction → egress
    "/citations/render",  # citeproc node subprocess
)

# Substrings that mark a side-effectful action even under an otherwise-safe prefix (e.g. /papers/{id}/reprocess-pdf,
# /axes/{id}/score, /papers/{id}/fill-metadata, .../candidates/generate).
REPLAY_UNSAFE_SUBSTRINGS: tuple[str, ...] = (
    "/score",
    "/generate",
    "/reprocess-pdf",
    "/fill-metadata",
    "/reresolve",
    "/acquire",
    "/refresh",
)


def is_replay_safe(path: str) -> bool:
    """True when a mutating request to ``path`` may be safely re-run (a pure DB write, no external/job/secret side
    effect). Conservative: any prefix or substring match excludes it."""
    if path.startswith(REPLAY_UNSAFE_PREFIXES):
        return False
    return not any(token in path for token in REPLAY_UNSAFE_SUBSTRINGS)


class SqliteWriteRetryMiddleware:
    """Retry a replay-safe mutating request on a transient SQLite writer lock (bounded attempts + backoff)."""

    def __init__(self, app, *, attempts: int = 4, delay_seconds: float = 0.05) -> None:
        self.app = app
        self.attempts = max(1, attempts)
        self.delay_seconds = delay_seconds

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") not in _MUTATING_METHODS
            or not is_replay_safe(scope.get("path", ""))
        ):
            await self.app(scope, receive, send)
            return

        body = await _drain_body(receive)

        async def replay_receive():
            return {"type": "http.request", "body": body, "more_body": False}

        remaining = self.attempts
        while True:
            sent = {"started": False}

            async def guarded_send(message, _sent=sent):
                _sent["started"] = True
                await send(message)

            try:
                await self.app(scope, replay_receive, guarded_send)
                return
            except OperationalError as exc:
                remaining -= 1
                # Can't retry once bytes are on the wire, or once attempts are spent, or for a non-lock error.
                if sent["started"] or remaining <= 0 or not is_sqlite_locked(exc):
                    raise
                await asyncio.sleep(self.delay_seconds)


async def _drain_body(receive) -> bytes:
    """Read the full request body from the ASGI receive channel so it can be replayed on each attempt."""
    chunks: list[bytes] = []
    more = True
    while more:
        message = await receive()
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body", b""))
        more = message.get("more_body", False)
    return b"".join(chunks)
