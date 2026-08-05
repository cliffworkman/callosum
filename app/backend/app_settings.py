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


def save_settings(data: dict) -> None:
    """Persist the full settings dict (atomic write, owner-only perms). Public wrapper over ``_write`` so the
    provider roster (inc 256, ``providers_store``) can save its non-secret list; secrets still route through the
    keychain/file secret store below, never this plaintext file."""
    _write(data)


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


# --- Institutional link resolver (OpenURL hand-off, inc 263) — a NON-secret local pref (a public URL, the
# user's library's own link-resolver base). Stored in the file + returnable by GET /settings, like contact_email.
# Default empty → the "Get via my library" hand-off is dormant (opt-in; the free-OA cascade stays the backbone).


def set_openurl_resolver_base(url: str | None) -> None:
    """Persist the institution's OpenURL link-resolver base. Empty/whitespace clears it (→ feature dormant)."""
    data = load_settings()
    url = (url or "").strip()
    if url:
        data["openurl_resolver_base"] = url
    else:
        data.pop("openurl_resolver_base", None)
    _write(data)


def stored_openurl_resolver_base() -> str | None:
    """The UI-set OpenURL resolver base, or None if unset/blank."""
    val = load_settings().get("openurl_resolver_base")
    return val if isinstance(val, str) and val.strip() else None


# --- Sync (accounts SP3b): opt-in (default OFF) config + the sealed keyring + the per-device cursor ---


def stored_sync_settings() -> dict:
    """``{enabled: bool, server_url: str | None}`` — opt-in egress, default OFF."""
    data = load_settings()
    return {
        "enabled": bool(data.get("sync_enabled", False)),
        "server_url": (data.get("sync_server_url") or None),
    }


def set_sync_settings(*, enabled: bool, server_url: str | None) -> None:
    data = load_settings()
    data["sync_enabled"] = bool(enabled)
    if (server_url or "").strip():
        data["sync_server_url"] = server_url.strip()
    else:
        data.pop("sync_server_url", None)
    _write(data)


def stored_sync_cursor() -> int:
    """The per-device pull high-water mark (the inc-198 cursor; the engine returns the new one each run)."""
    val = load_settings().get("sync_cursor", 0)
    return int(val) if isinstance(val, int) else 0


def set_sync_cursor(seq: int) -> None:
    data = load_settings()
    data["sync_cursor"] = int(seq)
    _write(data)


def set_sync_keyring(keyring: dict | None) -> None:
    """Store the SEALED sync keyring (SP3a: no plaintext / passphrase / DEK — safe at rest). Treated as a secret
    (keychain where available, else the local file), never returned over the wire."""
    _set_secret("sync_keyring", json.dumps(keyring) if keyring is not None else None)


def stored_sync_keyring() -> dict | None:
    raw = _get_secret("sync_keyring")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def sync_configured() -> bool:
    """True once a keyring exists (the user ran sync setup)."""
    return stored_sync_keyring() is not None


# --- Multi-provider (inc 149): provider selection + per-provider keys + the local endpoint ---

# The gemini key stays under "api_key" (the inc-146 field) for back-compat; other providers get their own field.
_PROVIDER_KEY_FIELD = {
    "gemini": "api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "local": "local_api_key",
}


def _key_field(provider: str) -> str:
    """The secret-store field for a provider's key. Builtins keep their fixed inc-149 fields (Decision A — no
    keychain migration); a custom provider id (inc 256) maps to ``provider_key::<id>``, so a user-named
    provider's key can never collide with (or overwrite) the shared ``api_key`` field."""
    return _PROVIDER_KEY_FIELD.get(provider) or f"provider_key::{provider}"


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


# --- PUBLISHERS "where to submit" preferences (#40 SP1b): the open-science weighting + result breadth ---
# Local prefs, NOT secrets, and NEVER transmitted externally (the weighting reaches only the local
# /methods/publishers/run endpoint; it is never forwarded to OpenAlex/DOAJ). Stored in the file (returnable by
# GET /settings for the local UI). The first-use choice gate needs "no pre-selection", so both start as None
# (unset) — `publisher_defaults_set()` is False until the user actively sets BOTH (never a pre-filled default).


def set_publisher_weighting(value: float | None) -> None:
    """The open-science weighting (0.0 = fit only … 1.0 = strongly favor open). None clears it (→ unset)."""
    data = load_settings()
    if value is None:
        data.pop("publisher_weighting", None)
    else:
        data["publisher_weighting"] = float(value)
    _write(data)


def stored_publisher_weighting() -> float | None:
    val = load_settings().get("publisher_weighting")
    return float(val) if isinstance(val, (int, float)) else None


def set_publisher_breadth(value: str | None) -> None:
    """Result breadth ("focused" | "broad"). Empty/whitespace clears it (→ unset)."""
    data = load_settings()
    v = (value or "").strip()
    if v:
        data["publisher_breadth"] = v
    else:
        data.pop("publisher_breadth", None)
    _write(data)


def stored_publisher_breadth() -> str | None:
    val = load_settings().get("publisher_breadth")
    return val if isinstance(val, str) and val.strip() else None


def publisher_defaults_set() -> bool:
    """True once the user has actively set BOTH consequential publisher defaults (the first-use gate is satisfied).
    Nothing is pre-selected — neither is set until the user chooses, so the weighting is one forced choice among
    peers (never the lone spotlighted one)."""
    return stored_publisher_weighting() is not None and stored_publisher_breadth() is not None


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
    """The stored key for a provider — keychain or file (inc 152); custom ids use ``provider_key::<id>``."""
    return _get_secret(_key_field(provider))


def set_provider_key(provider: str, key: str | None) -> None:
    """Store a per-provider API key (gemini → the inc-146 ``api_key`` field; a custom id → ``provider_key::<id>``).
    Empty/whitespace clears it."""
    _set_secret(_key_field(provider), key)


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


def set_onboarding_completed(done: bool) -> None:
    data = load_settings()
    data["onboarding_completed"] = bool(done)
    _write(data)


def stored_onboarding_completed() -> bool:
    """Whether the first-run wizard has been completed OR explicitly skipped (both count — re-nagging on every
    future launch after a skip would itself be the kind of pressure the wizard is designed to avoid)."""
    return bool(load_settings().get("onboarding_completed", False))


def read_only_mode() -> bool:
    """Whether this callosum instance is READ-ONLY (B5 mobile reading): CALLOSUM_READ_ONLY=1 makes the middleware
    reject every mutating method (anything but GET/HEAD/OPTIONS) with 403 — the method-level boundary for a
    tunnel-facing read-only deployment (an env var a remote caller can't set). Off by default → zero change."""
    return os.getenv("CALLOSUM_READ_ONLY", "").strip().lower() in {"1", "true", "yes"}


def set_agent_writes_enabled(enabled: bool) -> None:
    data = load_settings()
    data["agent_writes_enabled"] = bool(enabled)
    _write(data)


def stored_agent_writes() -> bool:
    """Whether AI-agent writes (the MCP write tools, B1 SP2) are allowed. Default OFF. The
    CALLOSUM_DISABLE_AGENT_WRITES env var force-disables it (a local recovery hatch)."""
    if os.getenv("CALLOSUM_DISABLE_AGENT_WRITES", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return bool(load_settings().get("agent_writes_enabled", False))


def set_usage_events_enabled(enabled: bool) -> None:
    data = load_settings()
    data["usage_events_enabled"] = bool(enabled)
    _write(data)


def stored_usage_events_enabled() -> bool:
    """Whether local usage instrumentation (backlog #38A) is recording events. Default **ON** — unlike every
    other flag in this file, since nothing here ever egresses (it behaves like any other local feature, not
    like the egress-consent gate); the toggle exists for anyone who'd rather not have even a local count kept."""
    return bool(load_settings().get("usage_events_enabled", True))


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
