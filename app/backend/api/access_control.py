"""Remote-access gate (inc 168): a bearer-token requirement + rate-limiting, OFF by default.

When the user enables **Remote access** (Settings) — so callosum can be reached via a cloudflared tunnel for the
Google Docs add-on and, since SP4, the Word-on-the-web relay — every request must carry a valid
``Authorization: Bearer <token>``, EXCEPT ``GET /health`` (liveness), the static app shell (``GET /``, which
carries no library data), and the 5 fixed Word task-pane asset files (SP4, ``/integrations/word/{taskpane.html,
taskpane.js, taskpane_core.js, taskpane.css, icon.png}`` — Office issues a PLAIN resource fetch for these
[the top-level ``SourceLocation`` navigation, then ``<script src>``/``<link href>`` inside that HTML], which can
never carry a custom header, so they need the same "carries no library data" exemption as the shell; the manifest
routes are deliberately NOT exempt, since a user downloads those directly from their own local callosum and they
never need to cross the tunnel). cloudflared forwards to ``localhost``, so the app **cannot** tell a tunnel
request from the local browser (both are loopback, and the ``Host`` header is attacker-controllable) — therefore
the token is the **only** safe boundary for everything else, applied uniformly.

When remote access is OFF (the default), the middleware is a pure pass-through: **zero change** for localhost-only
users (and the whole existing test suite). The flag + token are read fresh per request from ``app_settings`` so the
Settings toggle takes effect live. Recovery if the token is lost: the in-app lockout screen
(``POST /access/recover``, inc 254 — proves local possession via a local-file code, then disables the gate),
``CALLOSUM_DISABLE_REMOTE_ACCESS=1`` (a local-only hatch), or edit the settings file.

**inc 511 — a second, legitimate caller of that same hatch.** Desktop Word talks to a dedicated HTTPS process
(``tools/run_https.py``, :8443) that is architecturally never the port a cloudflared tunnel targets (the
checked-in ``adapters/googledocs/cloudflared-config.yml`` only ever forwards to the plain HTTP dev port, with an
explicit warning against pointing it at :8443). That script sets ``CALLOSUM_DISABLE_REMOTE_ACCESS=1`` in its OWN
process before starting, so desktop Word never needs a token even while Remote Access is on for a Google Docs/
Word-on-the-web collaborator elsewhere — a genuinely different, separately-running process keeps enforcing the
gate for the tunnel-facing port unaffected. This is NOT the same as trusting loopback origin in general (still
unsafe — see above); it is trusting a specific process that structurally never receives tunnel-relayed traffic.
"""

from __future__ import annotations

import secrets
import time
from collections import deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.backend import app_settings

# Reachable without a token even when remote access is on — none exposes library data.
# `/oauth/callback` (SP1) is a browser navigation back from the sign-in provider, so it carries no Authorization
# header (the inc-172 navigation gotcha); it carries only an opaque code+state validated against the stored PKCE
# verifier (app/backend/api/auth/router.py), so exempting it is safe.
# The 5 Word task-pane files (SP4) are fixed, request-input-free static assets (app/backend/api/routers/word.py's
# own per-filename-route allowlist) Office fetches as a plain resource load, never a header-carrying `fetch()` —
# same rationale as the shell. Never add a route here that reads request data or the library.
_EXEMPT_PATHS = frozenset(
    {
        "/",
        "/health",
        "/oauth/callback",
        "/integrations/word/taskpane.html",
        "/integrations/word/taskpane.js",
        "/integrations/word/taskpane_core.js",
        "/integrations/word/taskpane.css",
        "/integrations/word/icon.png",
    }
)

# inc 254: the lockout-recovery endpoint is reachable WITHOUT a token (the user is locked out and can't supply
# one), but — unlike the static-shell exemptions above — it is RATE-LIMITED, and local-machine possession (a
# one-time code the server writes to a local file; see access_recovery.py), not the token, is what authorizes
# it. It only ever DISABLES remote access. Keep it OUT of _EXEMPT_PATHS so it still passes through the limiter.
_RECOVERY_PATHS = frozenset({"/access/recover"})

# B5 (inc 237): read-only mode (CALLOSUM_READ_ONLY=1) forbids every mutating method. GET/HEAD/OPTIONS pass; anything
# else → 403. This is the METHOD-level read-only boundary the cloudflared path allowlist can't provide (a path like
# `/papers/5` serves both GET read and DELETE/PATCH writes — cloudflared matches path, not method).
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

RATE_LIMIT_WINDOW = 60.0  # seconds
RATE_LIMIT_MAX = 120  # requests per window (generous; only active when remote access is on)


class RateLimiter:
    """A tiny in-memory sliding-window limiter — no dependency, thread-safe, bounded (one deque per key)."""

    def __init__(self, max_requests: int | None = None, window: float | None = None) -> None:
        # Resolve at construction (not def-time) so tests can monkeypatch the module limits before create_app.
        self.max = RATE_LIMIT_MAX if max_requests is None else max_requests
        self.window = RATE_LIMIT_WINDOW if window is None else window
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


def _bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


class AccessControlMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limiter: RateLimiter | None = None) -> None:
        super().__init__(app)
        self._limiter = limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next):
        if app_settings.read_only_mode() and request.method not in _READ_METHODS:
            return JSONResponse({"detail": "This callosum instance is read-only."}, status_code=403)
        if not app_settings.stored_remote_access():
            return await call_next(request)  # OFF (the default) → no-op
        if request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)  # CORS preflight + the static shell / liveness
        if request.url.path in _RECOVERY_PATHS:
            # Lockout recovery (inc 254): no token (the user can't supply one), but rate-limited — and it can
            # ONLY disable remote access, gated on a code written to a local file a tunnel caller can't read.
            if not self._limiter.allow("recover"):
                return JSONResponse(
                    {"detail": "Too many recovery attempts — wait a minute."},
                    status_code=429,
                    headers={"Retry-After": str(int(RATE_LIMIT_WINDOW))},
                )
            return await call_next(request)
        token = app_settings.stored_access_token()
        provided = _bearer(request.headers.get("authorization"))
        if not token or not provided or not secrets.compare_digest(provided, token):
            return JSONResponse({"detail": "Remote access requires a valid access token."}, status_code=401)
        if not self._limiter.allow("remote"):
            return JSONResponse(
                {"detail": "Rate limit exceeded — slow down."},
                status_code=429,
                headers={"Retry-After": str(int(RATE_LIMIT_WINDOW))},
            )
        return await call_next(request)
