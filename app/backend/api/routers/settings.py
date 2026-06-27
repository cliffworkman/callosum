"""App-settings endpoints (BYOK): provider + per-provider key + data-egress consent from the UI.

``GET /settings`` returns STATUS ONLY — never a key value (only which providers have a key + the active one).
``PUT /settings`` sets the provider / per-provider key / local endpoint / model / egress consent, writing the
gitignored local store. The egress toggle is an explicit, default-off opt-in (invariant #3 unchanged). A `local`
endpoint must be a loopback address (422 otherwise) — that is what makes its "no egress" status honest (inc 149).
``POST /settings/test-key`` validates the active provider with a tiny non-library ping (cloud → gated on egress).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backend import app_settings
from app.backend.llm.providers import ALL_PROVIDERS, is_loopback_url, requires_egress
from integrations.gemini.generator import GeminiConfig

router = APIRouter()

# Per-provider stored-key field + env fallback (gemini keeps the inc-146 "api_key" field).
_KEY_FIELD = {
    "gemini": "api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "local": "local_api_key",
}
_KEY_ENV = {"gemini": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


class SettingsStatus(BaseModel):
    provider: str
    api_key_set: bool  # is a key available for the ACTIVE provider (UI store OR env)? (local needs none)
    api_key_source: str | None  # "ui" | "env" | None — NEVER the key value itself
    data_egress_enabled: bool
    egress_source: str  # "ui" (stored toggle) | "env" (CALLOSUM_ALLOW_DATA_EGRESS fallback)
    local_base_url: str | None = None
    model: str = ""  # the active provider's model override ("" = the provider default)
    provider_keys_set: dict[str, bool] = {}  # which cloud providers have a stored UI key


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


def _stored_key(stored: dict, provider: str) -> bool:
    val = stored.get(_KEY_FIELD.get(provider, "api_key"))
    return isinstance(val, str) and bool(val.strip())


def _status() -> SettingsStatus:
    stored = app_settings.load_settings()
    provider = stored.get("provider")
    if provider not in ALL_PROVIDERS:
        provider = "gemini"
    ui_key = _stored_key(stored, provider)
    env_key = bool(os.getenv(_KEY_ENV[provider])) if provider in _KEY_ENV else False
    stored_egress = stored.get("data_egress_enabled")
    if isinstance(stored_egress, bool):
        egress, egress_source = stored_egress, "ui"
    else:
        egress = os.getenv("CALLOSUM_ALLOW_DATA_EGRESS", "").strip().lower() in {"1", "true", "yes"}
        egress_source = "env"
    return SettingsStatus(
        provider=provider,
        api_key_set=ui_key or env_key,
        api_key_source="ui" if ui_key else ("env" if env_key else None),
        data_egress_enabled=egress,
        egress_source=egress_source,
        local_base_url=(stored.get("local_base_url") or None),
        model=(stored.get("model") or ""),
        provider_keys_set={p: _stored_key(stored, p) for p in ("gemini", "openai", "anthropic")},
    )


@router.get("/settings", response_model=SettingsStatus)
def get_settings() -> SettingsStatus:
    return _status()


@router.put("/settings", response_model=SettingsStatus)
def put_settings(update: SettingsUpdate) -> SettingsStatus:
    if update.provider is not None:
        if update.provider not in ALL_PROVIDERS:
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
        if target not in ALL_PROVIDERS:
            target = "gemini"
        app_settings.set_provider_key(target, update.api_key)  # max_length on the field already 422s an oversized key
    if update.data_egress_enabled is not None:
        app_settings.set_data_egress(update.data_egress_enabled)
    return _status()


class KeyTestResult(BaseModel):
    ok: bool
    detail: str


@router.post("/settings/test-key", response_model=KeyTestResult)
def test_key() -> KeyTestResult:
    """Validate the ACTIVE provider with a tiny non-library ping. Cloud providers are gated on egress ON (off ⟹
    no outbound call — the toggle's promise); a loopback local provider runs regardless. Always HTTP 200."""
    from app.backend.llm import providers  # late import so tests can monkeypatch providers.complete

    cfg = GeminiConfig.from_environment()
    if requires_egress(cfg.provider) and not cfg.data_egress_enabled:
        return KeyTestResult(
            ok=False, detail="Turn on “Allow AI features” first — Callosum won’t contact a provider while it’s off."
        )
    if requires_egress(cfg.provider) and not cfg.resolved_api_key():
        return KeyTestResult(ok=False, detail="No API key is set for this provider. Paste one above and Save.")
    try:
        result = providers.complete(cfg, "Reply with the single word OK.")
    except providers.ProviderError as exc:
        return KeyTestResult(ok=False, detail=f"Key test failed: {str(exc)[:300]}")
    text = (result.text or "").strip()
    return KeyTestResult(ok=True, detail="Works — the model responded." if text else "Authenticated.")
