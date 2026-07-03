"""The unified LLM provider roster endpoints (inc 256 — custom providers).

Jeff's "Add model provider" request: the four fixed presets (gemini/openai/anthropic/local) and any user-added
custom providers are ONE editable list. This sub-router owns the roster read + the custom-provider CRUD; the
*active* selection, the per-provider API key, the model override, and the egress toggle stay on ``PUT /settings``
(unchanged contract) — this only adds the list + the ``{name, base_url, wire_format, models[]}`` editor.

Security posture (see ``.claude/security-audits/2026-07-03_custom-providers.md``):
- **No key ever leaves** — ``GET`` reports only ``key_set`` (bool), never a value (like the inc-146 status).
- **Egress is endpoint-based** — a custom provider with a non-loopback ``base_url`` is gated exactly like Gemini
  (``app.backend.llm.providers.requires_egress`` decides from the config), so invariant #3 holds for any URL.
- **Server-generated ids** — a custom provider's id is a server ``uuid4().hex`` (never client-supplied), so an
  ``{id}`` path parameter can't be steered onto a builtin's key field or traverse anything.
- **Boundary caps + http(s)-only base URLs** validated in ``providers_store`` (rule #4); ``ValueError`` → 422.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backend import app_settings, providers_store

router = APIRouter()

# Env-var fallback that also counts as "a key is available" for the builtins (mirrors settings.py).
_KEY_ENV = {"gemini": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


class ProviderInfo(BaseModel):
    id: str
    name: str
    wire_format: str
    base_url: str | None = None
    models: list[str] = []
    builtin: bool
    key_set: bool  # is a key available (stored UI key OR, for a builtin, its env fallback)? — NEVER the value
    active: bool  # is this the currently-selected provider?


class RosterResponse(BaseModel):
    providers: list[ProviderInfo]
    active_provider: str
    active_model: str
    wire_formats: list[str] = list(providers_store.CUSTOM_WIRE_FORMATS)  # the user-selectable transports


class CreateProviderRequest(BaseModel):
    name: str = Field(max_length=providers_store.NAME_MAX_LEN)
    base_url: str = Field(max_length=providers_store.BASE_URL_MAX_LEN)
    wire_format: str
    models: list[str] = []


class UpdateProviderRequest(BaseModel):
    """All fields optional — only the ones present are changed (a partial edit)."""

    name: str | None = Field(default=None, max_length=providers_store.NAME_MAX_LEN)
    base_url: str | None = Field(default=None, max_length=providers_store.BASE_URL_MAX_LEN)
    wire_format: str | None = None
    models: list[str] | None = None


def _key_set(pid: str) -> bool:
    if app_settings.get_provider_key(pid):
        return True
    env = _KEY_ENV.get(pid)
    return bool(os.getenv(env)) if env else False


def _info(rec: dict, *, active_id: str) -> ProviderInfo:
    return ProviderInfo(
        id=rec["id"],
        name=rec["name"],
        wire_format=rec["wire_format"],
        base_url=rec.get("base_url"),
        models=rec.get("models") or [],
        builtin=rec.get("builtin", False),
        key_set=_key_set(rec["id"]),
        active=(rec["id"] == active_id),
    )


@router.get("/settings/providers", response_model=RosterResponse)
def list_providers() -> RosterResponse:
    active = providers_store.active_provider()
    return RosterResponse(
        providers=[_info(p, active_id=active["id"]) for p in providers_store.list_providers()],
        active_provider=active["id"],
        active_model=providers_store.active_model(),
    )


@router.post("/settings/providers", response_model=ProviderInfo)
def create_provider(req: CreateProviderRequest) -> ProviderInfo:
    try:
        rec = providers_store.add_custom(
            name=req.name, base_url=req.base_url, wire_format=req.wire_format, models=req.models
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _info(rec, active_id=providers_store.active_provider()["id"])


@router.put("/settings/providers/{pid}", response_model=ProviderInfo)
def update_provider(pid: str, req: UpdateProviderRequest) -> ProviderInfo:
    # Builtins are synthesized, not stored — they can't be edited (only their key + active/model, via PUT /settings).
    if providers_store.is_builtin(pid):
        raise HTTPException(status_code=400, detail="Builtin providers can't be edited.")
    try:
        rec = providers_store.update_custom(
            pid, name=req.name, base_url=req.base_url, wire_format=req.wire_format, models=req.models
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if rec is None:
        raise HTTPException(status_code=404, detail="Unknown custom provider.")
    return _info(rec, active_id=providers_store.active_provider()["id"])


@router.delete("/settings/providers/{pid}")
def delete_provider(pid: str) -> dict:
    if providers_store.is_builtin(pid):
        raise HTTPException(status_code=400, detail="Builtin providers can't be deleted.")
    if not providers_store.delete_custom(pid):
        raise HTTPException(status_code=404, detail="Unknown custom provider.")
    return {"ok": True}
