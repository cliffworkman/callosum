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
    """Store the Gemini key (the inc-146 entry point) — routes through the per-provider keychain/file store."""
    set_provider_key("gemini", key)


def set_data_egress(enabled: bool) -> None:
    """Persist the UI egress-consent choice (overlays the env default once set)."""
    data = load_settings()
    data["data_egress_enabled"] = bool(enabled)
    _write(data)


def set_help_assistant_enabled(enabled: bool) -> None:
    """Persist the UI help-assistant toggle (its OWN gate, independent of egress; overlays the env default)."""
    data = load_settings()
    data["help_assistant_enabled"] = bool(enabled)
    _write(data)


def stored_api_key() -> str | None:
    """The stored Gemini key (keychain or file), or None if unset/blank."""
    return get_provider_key("gemini")


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


# --- OS-keychain storage (inc 152): optional `keyring`, file fallback ---
# Per-provider keys go to the OS vault when `keyring` is installed with a working backend; otherwise they stay in
# the gitignored settings file (the inc-146 behavior). `keyring` is an OPTIONAL dependency — the app + tests work
# without it. Service name + usernames are constants (no request data reaches keyring).
_KEYCHAIN_SERVICE = "callosum"


def _keyring():
    """Return the `keyring` module iff importable AND it has a usable backend, else None (→ file fallback)."""
    try:
        import keyring
        from keyring.backends import fail

        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
        return keyring
    except Exception:
        return None


def keychain_available() -> bool:
    return _keyring() is not None


def get_provider_key(provider: str) -> str | None:
    """The stored key for a provider — from the OS keychain if present, else the local file. Either place is
    honored so a pre-keychain key is never lost (re-saving then migrates it to the keychain)."""
    field = _PROVIDER_KEY_FIELD.get(provider, "api_key")
    kr = _keyring()
    if kr is not None:
        try:
            v = kr.get_password(_KEYCHAIN_SERVICE, field)
            if v and v.strip():
                return v
        except Exception:
            pass  # backend error → fall through to the file
    v = load_settings().get(field)
    return v if isinstance(v, str) and v.strip() else None


def set_provider_key(provider: str, key: str | None) -> None:
    """Store a per-provider API key (gemini → the inc-146 ``api_key`` field). Empty/whitespace clears it. Uses the
    OS keychain when available (and removes any plaintext file copy — migration on save); else the file."""
    field = _PROVIDER_KEY_FIELD.get(provider, "api_key")
    key = (key or "").strip()
    kr = _keyring()
    if kr is not None:
        try:
            if key:
                kr.set_password(_KEYCHAIN_SERVICE, field, key)
            else:
                try:
                    kr.delete_password(_KEYCHAIN_SERVICE, field)
                except Exception:
                    pass  # nothing stored to delete
            # Drop any plaintext copy left in the file (migrate away from inc-146 file storage).
            data = load_settings()
            if field in data:
                data.pop(field, None)
                _write(data)
            return
        except Exception:
            pass  # keychain write failed → fall through to the file store
    data = load_settings()
    if key:
        data[field] = key
    else:
        data.pop(field, None)
    _write(data)
