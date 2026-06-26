"""App-settings endpoints (inc 146 — BYOK): set the Gemini API key + data-egress consent from the UI.

``GET /settings`` returns STATUS ONLY — never the key value (only whether a key is set + where it came from).
``PUT /settings`` sets/clears the key and/or toggles egress, writing the gitignored local store. The egress
toggle is an explicit, default-off opt-in: it moves the consent surface from an env var to a labeled UI
control — invariant #3 is unchanged (the ``EgressGated*`` gate logic is untouched; it just reads the overlay).
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.backend import app_settings
from integrations.gemini.generator import GeminiConfig

router = APIRouter()


class SettingsStatus(BaseModel):
    api_key_set: bool  # is a key available (from the UI store OR the GOOGLE_API_KEY env var)?
    api_key_source: str | None  # "ui" | "env" | None — NEVER the key value itself
    data_egress_enabled: bool
    egress_source: str  # "ui" (stored toggle) | "env" (CALLOSUM_ALLOW_DATA_EGRESS fallback)


class SettingsUpdate(BaseModel):
    # api_key is applied only when set_api_key is True (so a status-preserving egress-only PUT can't clear it);
    # an empty/whitespace value with set_api_key=True clears the stored key.
    set_api_key: bool = False
    api_key: str | None = Field(default=None, max_length=app_settings.API_KEY_MAX_LEN)
    data_egress_enabled: bool | None = None


def _status() -> SettingsStatus:
    stored = app_settings.load_settings()
    stored_key = stored.get("api_key")
    ui_key = isinstance(stored_key, str) and bool(stored_key.strip())
    env_key = bool(os.getenv("GOOGLE_API_KEY"))
    stored_egress = stored.get("data_egress_enabled")
    if isinstance(stored_egress, bool):
        egress, egress_source = stored_egress, "ui"
    else:
        egress = os.getenv("CALLOSUM_ALLOW_DATA_EGRESS", "").strip().lower() in {"1", "true", "yes"}
        egress_source = "env"
    return SettingsStatus(
        api_key_set=ui_key or env_key,
        api_key_source="ui" if ui_key else ("env" if env_key else None),
        data_egress_enabled=egress,
        egress_source=egress_source,
    )


@router.get("/settings", response_model=SettingsStatus)
def get_settings() -> SettingsStatus:
    return _status()


@router.put("/settings", response_model=SettingsStatus)
def put_settings(update: SettingsUpdate) -> SettingsStatus:
    if update.set_api_key:
        # max_length on the field already 422s an oversized key; trim/clear happens in the store.
        app_settings.set_api_key(update.api_key)
    if update.data_egress_enabled is not None:
        app_settings.set_data_egress(update.data_egress_enabled)
    return _status()


class KeyTestResult(BaseModel):
    ok: bool
    detail: str


def _ping_gemini(model: str, api_key: str) -> tuple[bool, str]:
    """Make a minimal NON-LIBRARY call to confirm the key authenticates + can generate.

    Sends a fixed throwaway prompt (never library text). The key is never logged and never returned: any
    provider error is redacted (`replace(api_key, "***")`) + length-capped before it reaches `detail`.
    """
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents="Reply with the single word OK.")
        text = (getattr(response, "text", "") or "").strip()
        return True, "Key works — Gemini responded." if text else "Key authenticated."
    except Exception as exc:  # noqa: BLE001 — surface a sanitized message, never the key
        msg = str(exc).replace(api_key, "***") if api_key else str(exc)
        return False, f"Key test failed: {msg[:300]}"


@router.post("/settings/test-key", response_model=KeyTestResult)
def test_key() -> KeyTestResult:
    """Validate the active Gemini key with a tiny ping. Gated on egress ON — when AI is off, Callosum makes
    no outbound call (the egress toggle's promise stays ironclad; invariant #3). Always HTTP 200 (a result)."""
    cfg = GeminiConfig.from_environment()
    if not cfg.data_egress_enabled:
        return KeyTestResult(
            ok=False,
            detail="Turn on “Allow AI features” first — Callosum won’t contact Google while it’s off.",
        )
    key = cfg.resolved_api_key()
    if not key:
        return KeyTestResult(ok=False, detail="No API key is set. Paste one above and Save.")
    ok, detail = _ping_gemini(cfg.model, key)
    return KeyTestResult(ok=ok, detail=detail)
