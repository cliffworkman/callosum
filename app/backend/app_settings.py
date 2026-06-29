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
import secrets
import stat
from pathlib import Path

# Generous cap — real Gemini keys are ~40 chars; the boundary validator (routers/settings.py) enforces it too.
API_KEY_MAX_LEN = 512
CONTACT_EMAIL_MAX_LEN = 254  # RFC-5321 max address length; the boundary validator enforces it too
ACCESS_TOKEN_MAX_LEN = 256  # remote-access bearer token (inc 168); generated tokens are ~43 chars


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


# --- Polite-pool contact email (inc 158): one UI-set email for Crossref / OpenAlex / Retraction Watch ---
# NOT a secret (it's sent to public metadata APIs as the polite-pool contact, exactly as the env vars did) → it
# is stored in the file (not the keychain) and may be returned by GET /settings, unlike the API key.


def set_contact_email(email: str | None) -> None:
    """Persist the polite-pool contact email. Empty/whitespace clears it (→ the per-source env-var fallback)."""
    data = load_settings()
    email = (email or "").strip()
    if email:
        data["contact_email"] = email
    else:
        data.pop("contact_email", None)
    _write(data)


def stored_contact_email() -> str | None:
    """The UI-set contact email, or None if unset/blank."""
    val = load_settings().get("contact_email")
    return val if isinstance(val, str) and val.strip() else None


def resolved_mailto(env_var: str) -> str | None:
    """The polite-pool contact for an external metadata API: the UI-set contact email (overlays) if present, else
    the given environment variable. One email in Settings serves Crossref / OpenAlex / Retraction Watch."""
    return stored_contact_email() or os.environ.get(env_var)


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


def _get_secret(field: str) -> str | None:
    """A stored secret (`field`) — from the OS keychain if present, else the local file. Either place is honored so
    a pre-keychain value is never lost (re-saving then migrates it to the keychain)."""
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


def _set_secret(field: str, value: str | None) -> None:
    """Store a secret (`field`). Empty/whitespace clears it. Uses the OS keychain when available (and removes any
    plaintext file copy — migration on save); else the gitignored file."""
    value = (value or "").strip()
    kr = _keyring()
    if kr is not None:
        try:
            if value:
                kr.set_password(_KEYCHAIN_SERVICE, field, value)
            else:
                try:
                    kr.delete_password(_KEYCHAIN_SERVICE, field)
                except Exception:
                    pass  # nothing stored to delete
            # Drop any plaintext copy left in the file (migrate away from file storage).
            data = load_settings()
            if field in data:
                data.pop(field, None)
                _write(data)
            return
        except Exception:
            pass  # keychain write failed → fall through to the file store
    data = load_settings()
    if value:
        data[field] = value
    else:
        data.pop(field, None)
    _write(data)


def get_provider_key(provider: str) -> str | None:
    """The stored key for a provider — keychain or file (inc 152)."""
    return _get_secret(_PROVIDER_KEY_FIELD.get(provider, "api_key"))


def set_provider_key(provider: str, key: str | None) -> None:
    """Store a per-provider API key (gemini → the inc-146 ``api_key`` field). Empty/whitespace clears it."""
    _set_secret(_PROVIDER_KEY_FIELD.get(provider, "api_key"), key)


# --- Remote access (inc 168): an opt-in, default-OFF bearer token gating callosum when reached via a tunnel ---
# The token is a SECRET (keychain/file, write-only over the wire, never logged). `remote_access_enabled` is a
# non-secret flag (file, like data_egress). Turning it ON is the explicit, default-off consent to expose the
# library remotely. Recovery if the token is lost: set CALLOSUM_DISABLE_REMOTE_ACCESS=1, or edit the settings file.
_ACCESS_TOKEN_FIELD = "access_token"


def generate_access_token() -> str:
    """A fresh URL-safe random token (~43 chars)."""
    return secrets.token_urlsafe(32)


def set_access_token(token: str | None) -> None:
    _set_secret(_ACCESS_TOKEN_FIELD, token)


def stored_access_token() -> str | None:
    return _get_secret(_ACCESS_TOKEN_FIELD)


def set_remote_access_enabled(enabled: bool) -> None:
    data = load_settings()
    data["remote_access_enabled"] = bool(enabled)
    _write(data)


def stored_remote_access() -> bool:
    """Whether remote access is enabled. The CALLOSUM_DISABLE_REMOTE_ACCESS env var force-disables it (a local
    recovery hatch if the access token is lost — a remote caller can't set env vars on the user's machine)."""
    if os.getenv("CALLOSUM_DISABLE_REMOTE_ACCESS", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return bool(load_settings().get("remote_access_enabled", False))


# --- Optional account (SP1): "Sign in with ORCID" via OIDC to the callosum account platform (Authentik) ---
# Sign-in is OFF until an issuer + client_id are configured (env, set by the maintainer at standup). Tokens are
# SECRETS (keychain/file via _set_secret, write-only over the wire); GET /settings reports only a non-secret status.
# Identity-only — no library data is ever sent on sign-in (the egress gate is untouched). The in-flight PKCE flow
# (state + code_verifier) is stored the same way and is single-use (popped on the callback). A public/native client
# (PKCE, no client secret — RFC 8252).
_OAUTH_SESSION_FIELD = "oauth_session"
_OAUTH_FLOW_FIELD = "oauth_flow"


def oidc_config() -> dict | None:
    """The OIDC client config from the environment, or None if sign-in isn't configured (no issuer/client_id)."""
    issuer = (os.getenv("CALLOSUM_OIDC_ISSUER") or "").strip().rstrip("/")
    client_id = (os.getenv("CALLOSUM_OIDC_CLIENT_ID") or "").strip()
    if not issuer or not client_id:
        return None
    return {
        "issuer": issuer,
        "client_id": client_id,
        "scopes": (os.getenv("CALLOSUM_OIDC_SCOPES") or "openid profile").strip(),
        "orcid_claim": (os.getenv("CALLOSUM_OIDC_CLAIM_ORCID") or "orcid").strip(),
        "redirect_override": (os.getenv("CALLOSUM_OAUTH_REDIRECT") or "").strip() or None,
    }


def oidc_configured() -> bool:
    return oidc_config() is not None


def set_oauth_flow(*, state: str, code_verifier: str, redirect_uri: str) -> None:
    """Persist the single-use, in-flight PKCE flow (popped on the callback)."""
    _set_secret(
        _OAUTH_FLOW_FIELD, json.dumps({"state": state, "code_verifier": code_verifier, "redirect_uri": redirect_uri})
    )


def pop_oauth_flow() -> dict | None:
    """Return + clear the stored flow (single-use → no replay). None if absent/malformed."""
    raw = _get_secret(_OAUTH_FLOW_FIELD)
    _set_secret(_OAUTH_FLOW_FIELD, None)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def set_oauth_session(session: dict) -> None:
    """Store the signed-in session (tokens + the verified identity). Tokens are secrets — never returned by the API."""
    _set_secret(_OAUTH_SESSION_FIELD, json.dumps(session))


def stored_oauth_session() -> dict | None:
    raw = _get_secret(_OAUTH_SESSION_FIELD)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def clear_oauth_session() -> None:
    _set_secret(_OAUTH_SESSION_FIELD, None)


# --- Superuser (accounts SP1 follow-on, inc 195): a verified-ORCID allowlist ---
# A superuser is identified by their VERIFIED ORCID claim (from the signed-in session), matched against the
# `CALLOSUM_SUPERUSER_ORCIDS` env allowlist (comma/semicolon-separated bare iDs). Configured via the gitignored
# `.env` — never hardcoded in the public repo. It is NOT self-asserted (you can't claim it via the API). What being
# a superuser GATES is deferred — for now it's just an honest, verified flag.


def _normalize_orcid(value: str | None) -> str | None:
    """A bare ORCID iD (``0000-0002-2206-0325``) from a value that may be a full ``https://orcid.org/…`` URL.
    Uppercases the checksum X; returns None for blanks."""
    v = (value or "").strip()
    if not v:
        return None
    if "orcid.org/" in v:
        v = v.rsplit("orcid.org/", 1)[1]
    v = v.strip().strip("/").upper()
    return v or None


def superuser_orcids() -> set[str]:
    """The normalized superuser-ORCID allowlist from ``CALLOSUM_SUPERUSER_ORCIDS`` (comma/semicolon-separated)."""
    raw = os.getenv("CALLOSUM_SUPERUSER_ORCIDS", "")
    out: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        n = _normalize_orcid(part)
        if n:
            out.add(n)
    return out


def is_superuser_orcid(orcid: str | None) -> bool:
    """True iff the (verified) ORCID iD is in the allowlist. Match is normalization-insensitive (URL vs bare; X case)."""
    n = _normalize_orcid(orcid)
    return bool(n and n in superuser_orcids())


def oauth_account_status() -> dict:
    """The NON-secret signed-in status for GET /settings — the verified identity (+ a derived superuser flag),
    NEVER the tokens."""
    s = stored_oauth_session()
    if not s:
        return {
            "signed_in": False,
            "display_name": None,
            "orcid": None,
            "email": None,
            "expires_at": None,
            "is_superuser": False,
        }
    return {
        "signed_in": True,
        "display_name": s.get("display_name"),
        "orcid": s.get("orcid"),
        "email": s.get("email"),
        "expires_at": s.get("expires_at"),
        "is_superuser": is_superuser_orcid(s.get("orcid")),
    }
