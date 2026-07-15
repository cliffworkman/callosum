"""App-settings endpoints (BYOK): provider + per-provider key + data-egress consent from the UI.

``GET /settings`` returns STATUS ONLY — never a key value (only which providers have a key + the active one).
``PUT /settings`` sets the provider / per-provider key / local endpoint / model / egress consent, writing the
gitignored local store. The egress toggle is an explicit, default-off opt-in (invariant #3 unchanged). A `local`
endpoint must be a loopback address (422 otherwise) — that is what makes its "no egress" status honest (inc 149).
``POST /settings/test-key`` validates the active provider with a tiny non-library ping (cloud → gated on egress).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend import app_settings, providers_store
from app.backend.acquisition.openurl import RESOLVER_BASE_MAX_LEN, resolver_base_valid
from app.backend.api.dependencies import get_connection
from app.backend.llm.cache import repair_summary_cache
from app.backend.llm.providers import is_loopback_url, requires_egress
from integrations.gemini.generator import GeminiConfig

router = APIRouter()

# Per-provider env-var fallback (gemini's is GOOGLE_API_KEY). Stored keys live in app_settings (keychain or file).
_KEY_ENV = {"gemini": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}

# PUBLISHERS "where to submit" (#40 SP1b) result-breadth allowlist (the panel maps these to a top_k).
PUBLISHER_BREADTHS = {"focused", "broad"}


class AccountStatus(BaseModel):
    """SP1 optional-account status — the VERIFIED identity only, never the tokens."""

    configured: bool  # is OIDC sign-in configured on this Callosum (issuer + client_id present)?
    signed_in: bool
    display_name: str | None = None
    orcid: str | None = None  # present for an ORCID login; None for email/Google (SP2)
    email: str | None = None  # present for email/Google logins (SP2); the user's own identity, never a token
    expires_at: int | None = None
    is_superuser: bool = False  # verified-ORCID superuser (CALLOSUM_SUPERUSER_ORCIDS allowlist); capabilities TBD


class SettingsStatus(BaseModel):
    provider: str
    api_key_set: bool  # is a key available for the ACTIVE provider (UI store OR env)? (local needs none)
    api_key_source: str | None  # "ui" | "env" | None — NEVER the key value itself
    data_egress_enabled: bool
    egress_source: str  # "ui" (stored toggle) | "env" (CALLOSUM_ALLOW_DATA_EGRESS fallback)
    local_base_url: str | None = None
    model: str = ""  # the active provider's model override ("" = the provider default)
    provider_keys_set: dict[str, bool] = {}  # which cloud providers have a stored UI key
    help_assistant_enabled: bool = False  # the AI help assistant's OWN gate (independent of egress)
    help_source: str = "env"  # "ui" | "env"
    key_storage: str = "file"  # "keychain" (OS vault, if `keyring` is available) | "file" (gitignored local store)
    contact_email: str = ""  # polite-pool contact for Crossref/OpenAlex/Retraction Watch (NOT a secret)
    contact_email_source: str | None = None  # "ui" | "env" | None
    openurl_resolver_base: str = ""  # inc 263: the institution's OpenURL link-resolver base (NOT a secret; "" = unset)
    remote_access_enabled: bool = False  # inc 168: gate callosum behind a bearer token (for the Google Docs tunnel)
    access_token_set: bool = False  # is a remote-access token stored? — NEVER the token value
    agent_writes_enabled: bool = False  # B1 SP2: allow the MCP agent write tools (default off)
    # PUBLISHERS "where to submit" (#40 SP1b) — local prefs, never transmitted externally. Both None until the
    # user sets them (the first-use choice gate; no pre-selection); publisher_defaults_set gates the panel's output.
    publisher_weighting: float | None = None
    publisher_breadth: str | None = None
    publisher_defaults_set: bool = False
    account: AccountStatus  # SP1: optional "Sign in with ORCID" status — the verified identity, never tokens


class SettingsUpdate(BaseModel):
    provider: str | None = None
    set_api_key: bool = False
    api_key: str | None = Field(default=None, max_length=app_settings.API_KEY_MAX_LEN)
    api_key_provider: str | None = None  # which provider the key is for (default: provider / active / gemini)
    set_local_base_url: bool = False
    local_base_url: str | None = Field(default=None, max_length=500)
    set_model: bool = False
    model: str | None = Field(default=None, max_length=200)
    data_egress_enabled: bool | None = None
    help_assistant_enabled: bool | None = None
    set_contact_email: bool = False
    contact_email: str | None = Field(default=None, max_length=app_settings.CONTACT_EMAIL_MAX_LEN)
    set_openurl_resolver_base: bool = False
    openurl_resolver_base: str | None = Field(default=None, max_length=RESOLVER_BASE_MAX_LEN)
    remote_access_enabled: bool | None = None
    agent_writes_enabled: bool | None = None  # B1 SP2
    # PUBLISHERS prefs (#40 SP1b) — each gated by its set_* flag so the first-use gate can persist both together.
    set_publisher_weighting: bool = False
    publisher_weighting: float | None = None
    set_publisher_breadth: bool = False
    publisher_breadth: str | None = None


def _stored_key(provider: str) -> bool:
    return app_settings.get_provider_key(provider) is not None  # keychain or file


def _status() -> SettingsStatus:
    stored = app_settings.load_settings()
    provider = stored.get("provider")
    if provider not in providers_store.provider_ids():
        provider = "gemini"
    ui_key = _stored_key(provider)
    env_key = bool(os.getenv(_KEY_ENV[provider])) if provider in _KEY_ENV else False
    stored_egress = stored.get("data_egress_enabled")
    if isinstance(stored_egress, bool):
        egress, egress_source = stored_egress, "ui"
    else:
        egress = os.getenv("CALLOSUM_ALLOW_DATA_EGRESS", "").strip().lower() in {"1", "true", "yes"}
        egress_source = "env"
    stored_help = stored.get("help_assistant_enabled")
    if isinstance(stored_help, bool):
        help_enabled, help_source = stored_help, "ui"
    else:
        help_enabled = os.getenv("CALLOSUM_HELP_ASSISTANT_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        help_source = "env"
    contact = app_settings.stored_contact_email()
    if contact:
        contact_source = "ui"
    elif os.getenv("CALLOSUM_CROSSREF_MAILTO") or os.getenv("CALLOSUM_OPENALEX_MAILTO"):
        contact_source = "env"
    else:
        contact_source = None
    return SettingsStatus(
        provider=provider,
        api_key_set=ui_key or env_key,
        api_key_source="ui" if ui_key else ("env" if env_key else None),
        data_egress_enabled=egress,
        egress_source=egress_source,
        local_base_url=(stored.get("local_base_url") or None),
        model=(stored.get("model") or ""),
        provider_keys_set={p: _stored_key(p) for p in ("gemini", "openai", "anthropic")},
        help_assistant_enabled=help_enabled,
        help_source=help_source,
        key_storage="keychain" if app_settings.keychain_available() else "file",
        contact_email=contact or "",
        contact_email_source=contact_source,
        openurl_resolver_base=app_settings.stored_openurl_resolver_base() or "",
        remote_access_enabled=app_settings.stored_remote_access(),
        access_token_set=app_settings.stored_access_token() is not None,
        agent_writes_enabled=app_settings.stored_agent_writes(),
        publisher_weighting=app_settings.stored_publisher_weighting(),
        publisher_breadth=app_settings.stored_publisher_breadth(),
        publisher_defaults_set=app_settings.publisher_defaults_set(),
        account=AccountStatus(configured=app_settings.oidc_configured(), **app_settings.oauth_account_status()),
    )


@router.get("/settings", response_model=SettingsStatus)
def get_settings() -> SettingsStatus:
    return _status()


@router.put("/settings", response_model=SettingsStatus)
def put_settings(update: SettingsUpdate) -> SettingsStatus:
    if update.provider is not None:
        if update.provider not in providers_store.provider_ids():
            raise HTTPException(status_code=422, detail=f"Unknown provider: {update.provider}")
        app_settings.set_provider(update.provider)
    if update.set_local_base_url:
        url = (update.local_base_url or "").strip()
        if url and not is_loopback_url(url):
            raise HTTPException(
                status_code=422,
                detail="The local endpoint must be a loopback address (127.0.0.1 / localhost) — nothing leaves the machine.",
            )
        app_settings.set_local_base_url(url)
    if update.set_model:
        app_settings.set_model(update.model)
    if update.set_api_key:
        target = update.api_key_provider or update.provider or app_settings.load_settings().get("provider") or "gemini"
        if target not in providers_store.provider_ids():
            target = "gemini"
        app_settings.set_provider_key(target, update.api_key)  # max_length on the field already 422s an oversized key
    if update.data_egress_enabled is not None:
        app_settings.set_data_egress(update.data_egress_enabled)
    if update.help_assistant_enabled is not None:
        app_settings.set_help_assistant_enabled(update.help_assistant_enabled)
    if update.set_contact_email:
        email = (update.contact_email or "").strip()
        if email and "@" not in email:
            raise HTTPException(status_code=422, detail="Contact email must be a valid email address.")
        app_settings.set_contact_email(email)
    if update.set_openurl_resolver_base:
        base = (update.openurl_resolver_base or "").strip()
        if base and not resolver_base_valid(base):
            raise HTTPException(status_code=422, detail="The link resolver must be an http(s) URL.")
        app_settings.set_openurl_resolver_base(base)
    if update.remote_access_enabled is not None:
        # Enabling without a token would lock the local UI out (the gate would 401 every call, including the one
        # that mints a token) — so require a token first (the UI mints one before flipping this on).
        if update.remote_access_enabled and app_settings.stored_access_token() is None:
            raise HTTPException(status_code=422, detail="Generate an access token before enabling remote access.")
        app_settings.set_remote_access_enabled(update.remote_access_enabled)
    if update.agent_writes_enabled is not None:
        app_settings.set_agent_writes_enabled(update.agent_writes_enabled)
    if update.set_publisher_weighting:
        w = update.publisher_weighting
        if w is not None and not (0.0 <= w <= 1.0):
            raise HTTPException(status_code=422, detail="The open-science weighting must be between 0.0 and 1.0.")
        app_settings.set_publisher_weighting(w)
    if update.set_publisher_breadth:
        b = (update.publisher_breadth or "").strip()
        if b and b not in PUBLISHER_BREADTHS:
            raise HTTPException(status_code=422, detail=f"Unknown result breadth: {b}")
        app_settings.set_publisher_breadth(b or None)
    return _status()


class AccessTokenResult(BaseModel):
    token: str  # the new token — returned ONCE so the user can copy it into the add-on; never returned again


@router.post("/settings/access-token", response_model=AccessTokenResult)
def mint_access_token() -> AccessTokenResult:
    """Generate + store a fresh remote-access token, returning the value ONCE (it's a secret thereafter — GET
    /settings only ever reports access_token_set). Regenerating invalidates the previous token."""
    token = app_settings.generate_access_token()
    app_settings.set_access_token(token)
    return AccessTokenResult(token=token)


class KeyTestResult(BaseModel):
    ok: bool
    detail: str


class RepairSummaryCacheResult(BaseModel):
    scanned: int
    removed: int


@router.post("/settings/test-key", response_model=KeyTestResult)
def test_key() -> KeyTestResult:
    """Validate the ACTIVE provider with a tiny non-library ping. Cloud providers are gated on egress ON (off ⟹
    no outbound call — the toggle's promise); a loopback local provider runs regardless. Always HTTP 200."""
    from app.backend.llm import providers  # late import so tests can monkeypatch providers.complete

    cfg = GeminiConfig.from_environment()
    if requires_egress(cfg) and not cfg.data_egress_enabled:
        return KeyTestResult(
            ok=False, detail="Turn on “Allow AI features” first — Callosum won’t contact a provider while it’s off."
        )
    if requires_egress(cfg) and not cfg.resolved_api_key():
        return KeyTestResult(ok=False, detail="No API key is set for this provider. Paste one above and Save.")
    try:
        result = providers.complete(cfg, "Reply with the single word OK.")
    except providers.ProviderError as exc:
        return KeyTestResult(ok=False, detail=f"Key test failed: {str(exc)[:300]}")
    text = (result.text or "").strip()
    return KeyTestResult(ok=True, detail="Works — the model responded." if text else "Authenticated.")


@router.post("/settings/repair-summary-cache", response_model=RepairSummaryCacheResult)
def repair_summary_cache_endpoint(conn: Connection = Depends(get_connection)) -> RepairSummaryCacheResult:
    result = repair_summary_cache(conn)
    conn.commit()
    return RepairSummaryCacheResult(**result)
