"""Local app-settings store (inc 146 — BYOK).

A tiny JSON file holding the user's Gemini API key + data-egress consent, set from the Settings UI. It
lives at ``~/.callosum/app-settings.json`` (overridable via ``CALLOSUM_SETTINGS_PATH``) — **outside the git
repo and outside the project's synced Dropbox folder**, so the secret never travels with a copy of the
library ``.sqlite``.

The key is a SECRET: it is never logged, never returned by the API (only a set/not-set status), and never
committed (the file is in the user's home dir). Environment variables (``GOOGLE_API_KEY`` /
``CALLOSUM_ALLOW_DATA_EGRESS``) remain the fallback, so existing ``.env`` setups are unaffected — the stored
value, when present, simply overlays the env default (see ``GeminiConfig.from_environment``).
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

# Generous cap — real Gemini keys are ~40 chars; the boundary validator (routers/settings.py) enforces it too.
API_KEY_MAX_LEN = 512


def settings_path() -> Path:
    """The settings-file location: ``CALLOSUM_SETTINGS_PATH`` if set, else ``~/.callosum/app-settings.json``."""
    override = os.getenv("CALLOSUM_SETTINGS_PATH")
    if override:
        return Path(override)
    return Path.home() / ".callosum" / "app-settings.json"


def load_settings() -> dict:
    """Return the stored settings dict, or ``{}`` if the file is absent/unreadable/malformed (fail-soft)."""
    try:
        with settings_path().open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)  # atomic
    try:  # best-effort owner-only perms (largely a no-op on Windows, meaningful on POSIX)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def set_api_key(key: str | None) -> None:
    """Store the key (trimmed); empty/whitespace/None clears it."""
    data = load_settings()
    key = (key or "").strip()
    if key:
        data["api_key"] = key
    else:
        data.pop("api_key", None)
    _write(data)


def set_data_egress(enabled: bool) -> None:
    """Persist the UI egress-consent choice (overlays the env default once set)."""
    data = load_settings()
    data["data_egress_enabled"] = bool(enabled)
    _write(data)


def stored_api_key() -> str | None:
    """The stored key, or None if unset/blank."""
    key = load_settings().get("api_key")
    return key if isinstance(key, str) and key.strip() else None


def stored_egress() -> bool | None:
    """The stored egress choice, or None if the user has never toggled it (→ fall back to env)."""
    val = load_settings().get("data_egress_enabled")
    return val if isinstance(val, bool) else None


# --- Multi-provider (inc 149): provider selection + per-provider keys + the local endpoint ---

# The gemini key stays under "api_key" (the inc-146 field) for back-compat; other providers get their own field.
_PROVIDER_KEY_FIELD = {
    "gemini": "api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "local": "local_api_key",
}


def set_provider(provider: str) -> None:
    data = load_settings()
    data["provider"] = provider
    _write(data)


def set_model(model: str | None) -> None:
    """Override the model name for the active provider; empty clears it (→ the provider's default)."""
    data = load_settings()
    model = (model or "").strip()
    if model:
        data["model"] = model
    else:
        data.pop("model", None)
    _write(data)


def set_local_base_url(url: str | None) -> None:
    data = load_settings()
    url = (url or "").strip()
    if url:
        data["local_base_url"] = url
    else:
        data.pop("local_base_url", None)
    _write(data)


def set_provider_key(provider: str, key: str | None) -> None:
    """Store a per-provider API key (gemini → the inc-146 ``api_key`` field). Empty/whitespace clears it."""
    field = _PROVIDER_KEY_FIELD.get(provider, "api_key")
    data = load_settings()
    key = (key or "").strip()
    if key:
        data[field] = key
    else:
        data.pop(field, None)
    _write(data)
