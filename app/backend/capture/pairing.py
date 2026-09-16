"""Browser-capture pairing: the per-install secret + the short-lived session tokens it mints (#61 Phase 1).

Two mechanisms, deliberately separate, because they solve different problems:

**Pairing secret** — a durable, rotatable per-install secret proving "I am a local program the user
paired", written to an owner-only file beside the settings file. The Stage 2 connector host reads it;
nothing else can.

**Session token** — a short-lived bearer token the host exchanges the pairing secret for, and the
browser extension actually sends on ``/capture/*``. Bounded blast radius: it grants capture and
nothing else, it expires on its own, and regenerating the pairing secret revokes future sessions.

Why a FILE and not the OS keychain
----------------------------------
The connector host is **Rust**; this secret is written by **Python**. Python's ``keyring`` on Windows
stores through ``WinVaultKeyring``, whose target-name scheme includes a ``username@service``
*compound-name fallback* — a library-internal, version-dependent detail. Making a Rust binary
re-implement that would be an unstable cross-language contract, and exactly the kind of Stage 1
decision Stage 2 would have to tear out.

A plain file is language-neutral, and it is not a new invention: ``api/access_recovery`` already
proves local-machine possession with "a one-time code the server writes to a local file only a local
user can open", placed beside the settings file so ``CALLOSUM_SETTINGS_PATH`` keeps it hermetic under
tests and outside the repo/synced folder in production. Capture pairing adopts that rule verbatim, so
the host's lookup is a two-line, language-neutral computation.

The keychain remains right for secrets only Python reads (the Gemini key, the Remote Access token).
It is the wrong tool for an inter-process handshake.

The threat model is unchanged by the choice: a hostile webpage and an unapproved extension can read
**neither** store, and a local process running as the user could read either one *and* could call the
API directly anyway.

Replay
------
A session token is a bearer token and is **intentionally reusable until it expires** — a replayed
request inside its TTL does succeed at the transport layer. Preventing a duplicate *mutation* is the
idempotency key's job (see ``capture/idempotency.py``), not the token's. Expiry is the token's
security property; those are two mechanisms, not one.
"""

from __future__ import annotations

import secrets
import stat
import time
from pathlib import Path
from threading import Lock

from app.backend import app_settings

# A minted session lasts long enough for a human to click capture a few times without a re-handshake,
# and short enough that a leaked token is not a standing grant.
SESSION_TTL_S = 900.0  # 15 minutes
PAIRING_SECRET_MAX_LEN = 256  # submitted-secret cap at the boundary; real secrets are ~43 chars
SESSION_TOKEN_MAX_LEN = 256
# Bounded so a buggy or hostile host cannot grow this map without limit; oldest sessions are evicted.
MAX_ACTIVE_SESSIONS = 32

_PAIRING_FILE_NAME = "capture-pairing.json"

# Active session tokens: {token: expiry_monotonic}. In-process only — never persisted, never logged.
# A restart invalidates every session, which is correct: the host re-handshakes on demand.
_sessions: dict[str, float] = {}
_lock = Lock()


def pairing_file_path() -> Path:
    """Where the pairing secret lives — beside the settings file.

    Same placement rule as ``access_recovery.recovery_file_path``: ``CALLOSUM_SETTINGS_PATH`` keeps it
    hermetic under tests, and in production it sits in ``~/.callosum/`` rather than the repo or a
    synced folder. The Rust connector host computes this identically.
    """
    return app_settings.settings_path().parent / _PAIRING_FILE_NAME


def read_pairing_secret() -> str | None:
    """The stored pairing secret, or None when capture has never been paired on this install."""
    path = pairing_file_path()
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    secret = data.get("pairing_secret") if isinstance(data, dict) else None
    return secret if isinstance(secret, str) and secret.strip() else None


def ensure_pairing_secret() -> str:
    """The pairing secret, minting + persisting one on first use. Idempotent."""
    existing = read_pairing_secret()
    if existing:
        return existing
    return rotate_pairing_secret()


def rotate_pairing_secret() -> str:
    """Mint a fresh pairing secret, replacing any previous one, and drop every active session.

    This is the revocation path: an old host copy holding the previous secret can no longer obtain a
    session, and tokens already issued stop working immediately rather than lingering until TTL.
    """
    secret = secrets.token_urlsafe(32)  # ~43 chars, 256 bits
    path = pairing_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps({"pairing_secret": secret, "note": "callosum browser-capture pairing — local only"}, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)  # atomic, mirroring app_settings._write
    try:  # owner-only perms (meaningful on POSIX; largely a no-op on Windows, like the settings file)
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    with _lock:
        _sessions.clear()
    return secret


def issue_session(presented_secret: str, *, now: float | None = None) -> str | None:
    """Exchange the pairing secret for a short-lived session token, or None if it does not match.

    Constant-time comparison, matching ``access_control``'s convention — a timing oracle on a local
    secret is a small risk, but the cheap defense is already the house pattern.
    """
    stored = read_pairing_secret()
    if not stored or not presented_secret:
        return None
    if not secrets.compare_digest(presented_secret, stored):
        return None
    now = time.monotonic() if now is None else now
    token = secrets.token_urlsafe(32)
    with _lock:
        _prune_locked(now)
        if len(_sessions) >= MAX_ACTIVE_SESSIONS:  # evict the soonest-to-expire rather than grow unbounded
            oldest = min(_sessions, key=lambda key: _sessions[key])
            _sessions.pop(oldest, None)
        _sessions[token] = now + SESSION_TTL_S
    return token


def session_is_valid(token: str | None, *, now: float | None = None) -> bool:
    """Whether this token is a live session. Expired tokens are pruned as a side effect."""
    if not token:
        return False
    now = time.monotonic() if now is None else now
    with _lock:
        _prune_locked(now)
        expiry = _sessions.get(token)
        return expiry is not None and expiry > now


def clear_sessions() -> None:
    """Drop every active session (tests, and the rotate path)."""
    with _lock:
        _sessions.clear()


def _prune_locked(now: float) -> None:
    for token in [token for token, expiry in _sessions.items() if expiry <= now]:
        _sessions.pop(token, None)
