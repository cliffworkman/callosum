"""Local-possession recovery from a remote-access lockout (inc 254).

When Remote access (inc 168) is ON but this browser holds no valid token, EVERY data call 401s — including
``GET /settings`` — so the user is locked out of the very UI that could fix it. This is the safe, in-app escape
hatch. It proves the caller is **at the machine** (not reaching in over a tunnel) by requiring a one-time code
the server writes to a **local file only a local user can open**, and its only privileged action is **disabling
remote access** (returning to the local-only default) — it NEVER reveals the token or any library data.

The endpoint (``routers/access.py`` → ``POST /access/recover``) is gate-exempt but rate-limited (see
``access_control.py``). A remote/tunnel caller can hit it but cannot read the local file → cannot obtain the
code; the code is 128-bit, single-use, and short-lived, so guessing is infeasible. Under the recommended
cloudflared allowlist the path isn't even forwarded — defense in depth, not the sole control.

The pending code lives only in-process (a module global) + the visible local file; it is never persisted to the
settings store and never logged.
"""

from __future__ import annotations

import secrets
import stat
import time
from pathlib import Path

from app.backend import app_settings

RECOVERY_CODE_TTL_S = 600.0  # a minted code is valid for 10 minutes
RECOVERY_CODE_MAX_LEN = 128  # submitted-code cap (the boundary validator enforces it); real codes are ~22 chars

# The single active recovery code, in-process only: {"code": str, "expires": float} or None. Not persisted.
_pending: dict | None = None


def recovery_file_path() -> Path:
    """Where the one-time code is written for the local user to read — beside the settings file, so
    ``CALLOSUM_SETTINGS_PATH`` keeps it hermetic under tests and outside the repo/synced folder in production."""
    return app_settings.settings_path().parent / "recovery-code.txt"


def start_recovery(now: float | None = None) -> Path:
    """Mint a fresh single-use recovery code, write it to the local file (owner-only), and return the file path.
    The code itself is NEVER logged or returned over the wire — only its location is."""
    global _pending
    now = time.time() if now is None else now
    code = secrets.token_urlsafe(16)  # 128 bits of entropy
    _pending = {"code": code, "expires": now + RECOVERY_CODE_TTL_S}
    path = recovery_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "callosum — remote-access recovery code (single use)\n"
        "===================================================\n\n"
        f"    {code}\n\n"
        "Paste this back into callosum to turn Remote access OFF and regain local access.\n"
        "It expires in 10 minutes. You can delete this file afterwards.\n",
        encoding="utf-8",
    )
    try:  # owner-only perms (meaningful on POSIX; largely a no-op on Windows, like the settings file)
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return path


def verify_recovery(code: str, now: float | None = None) -> bool:
    """True iff ``code`` matches the pending, unexpired code (constant-time compare). On success — OR on an
    expired code — the pending code is consumed and the local file removed; the CALLER then disables remote
    access. A wrong (but still-valid) guess leaves the code live so the user can retry with the real one."""
    global _pending
    now = time.time() if now is None else now
    pending = _pending
    if not pending or not isinstance(code, str) or not code:
        return False
    if now >= pending["expires"]:
        _pending = None
        _remove_file()
        return False
    if not secrets.compare_digest(code, pending["code"]):
        return False
    _pending = None
    _remove_file()
    return True


def clear_pending() -> None:
    """Drop any pending code + its file (used by tests, and after a successful recovery)."""
    global _pending
    _pending = None
    _remove_file()


def _remove_file() -> None:
    try:
        recovery_file_path().unlink()
    except OSError:
        pass  # nothing written yet, or already removed
