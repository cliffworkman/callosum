"""The diagnostic block attached to a feedback report (inc 265) — and, deliberately, what it leaves out.

A bug report is worth far more with the app's own state attached, but this is the one part of the report
the user didn't type, so it is held to the project's inspectability commitment: it is **fetchable before
submitting** (``GET /feedback/config`` returns exactly what would be attached), it is **rendered verbatim**
in the report the user reads, and it is **opt-out** (``include_diagnostics``).

What it deliberately excludes: the API key (or any secret), the database URL/path and the library folder
(they carry the user's name and directory layout), and any paper/annotation/summary content. Only
version-and-posture facts go in — the things that explain a bug without describing the library.
"""

from __future__ import annotations

import os
import platform
import sys

from app.backend import app_settings, providers_store
from app.backend.summarization.verification import VERIFICATION_VERSION

CLIENT_DIAGNOSTICS_MAX_KEYS = 24
CLIENT_DIAGNOSTIC_KEY_MAX_LEN = 40
CLIENT_DIAGNOSTIC_VALUE_MAX_LEN = 300


def server_diagnostics(
    *,
    db_revision: str | None = None,
    db_head_revision: str | None = None,
    db_reachable: bool = True,
) -> dict[str, str]:
    """Version + posture facts about this instance. Every value is a string, so the report renders as-is."""
    stored = app_settings.load_settings()
    provider = stored.get("provider")
    if provider not in providers_store.provider_ids():
        provider = "gemini"
    return {
        "app": "callosum",
        "verification_version": VERIFICATION_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),  # e.g. "macOS-15.0-arm64-arm-64bit" — no hostname, no user path
        "implementation": f"{platform.python_implementation()} {sys.version_info.major}.{sys.version_info.minor}",
        "db_reachable": _yn(db_reachable),
        "db_revision": db_revision or "unstamped",
        "db_head_revision": db_head_revision or "unknown",
        "db_at_head": _yn(bool(db_revision) and db_revision == db_head_revision),
        "ai_provider": str(provider),  # the provider id only — never the key, never the base URL
        "data_egress_enabled": _yn(_effective(stored.get("data_egress_enabled"), "CALLOSUM_ALLOW_DATA_EGRESS")),
        "help_assistant_enabled": _yn(
            _effective(stored.get("help_assistant_enabled"), "CALLOSUM_HELP_ASSISTANT_ENABLED")
        ),
        "remote_access_enabled": _yn(app_settings.stored_remote_access()),
        "read_only_mode": _yn(app_settings.read_only_mode()),
        "key_storage": "keychain" if app_settings.keychain_available() else "file",
    }


def clean_client_diagnostics(raw: dict | None) -> dict[str, str]:
    """Bound + stringify the browser-supplied half (user agent, viewport, open view).

    Untrusted input at the boundary (rule #4): the browser is the client, but a report is also a file we
    write, so cap the key count, key length, and value length rather than trusting whatever arrives.
    """
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, value in raw.items():
        if len(cleaned) >= CLIENT_DIAGNOSTICS_MAX_KEYS:
            break
        if not isinstance(key, str) or not key.strip():
            continue
        text = " ".join(str(value).split())  # collapse newlines/tabs so a value can't forge report structure
        if not text:
            continue
        cleaned[key.strip()[:CLIENT_DIAGNOSTIC_KEY_MAX_LEN]] = text[:CLIENT_DIAGNOSTIC_VALUE_MAX_LEN]
    return cleaned


def _effective(stored: object, env_var: str) -> bool:
    """A stored UI toggle overlays its env default — the same resolution ``GET /settings`` reports."""
    if isinstance(stored, bool):
        return stored
    return os.getenv(env_var, "").strip().lower() in {"1", "true", "yes"}


def _yn(value: bool) -> str:
    return "yes" if value else "no"
