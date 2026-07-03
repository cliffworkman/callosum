"""The unified LLM provider roster (inc 256 — custom providers).

Jeff's "Add model provider" request: the fixed gemini/openai/anthropic/local set becomes ONE editable list, and
a user can add arbitrary, user-named providers ``{name, base_url, wire_format, models[]}`` + a key.

**Storage split (Decision A — no keychain migration).** The four *builtin* presets are **synthesized** on every
read from module constants + the existing flat inc-149 settings (the per-provider keys, the ``local_base_url``,
the active ``model`` override). They are never persisted, so today's settings file + key storage are untouched.
Only *custom* providers are persisted (``custom_providers`` in the settings file), each with an id-keyed secret
(``provider_key::<uuid>``). The **active selection** reuses the flat ``provider`` (id) + ``model`` fields (full
back-compat with inc 149) — the roster is authoritative only for base_url / wire_format / models / name.

Egress is decided **endpoint-based** in ``app.backend.llm.providers.requires_egress`` (gemini SDK → egress;
otherwise egress iff the base_url is non-loopback), so a custom cloud provider is gated exactly like Gemini and a
custom loopback provider is honestly no-egress — invariant #3 stays intact for an arbitrary user URL.

This module depends only on ``app.backend.app_settings`` (a clean DAG; ``app_settings`` never imports this).
"""

from __future__ import annotations

import uuid
from urllib.parse import urlparse

from app.backend import app_settings

# The three user-selectable wire formats. The builtin ``gemini`` SDK format is deliberately NOT assignable to a
# custom provider (no SDK hijack — a custom provider can never claim ``gemini``).
CUSTOM_WIRE_FORMATS = ("messages", "chat_completions", "responses")

_BUILTIN_IDS = ("gemini", "openai", "anthropic", "local")
_DEFAULT_LOCAL_BASE = "http://localhost:11434"

# id -> (display name, wire_format, base_url, default model). ``local`` base_url is overlaid from ``local_base_url``.
_BUILTIN_META = {
    "gemini": ("Gemini", "gemini", None, "gemini-2.5-flash-lite"),
    "openai": ("OpenAI", "chat_completions", "https://api.openai.com", "gpt-4o-mini"),
    "anthropic": ("Anthropic", "messages", "https://api.anthropic.com", "claude-3-5-haiku-latest"),
    "local": ("Local", "chat_completions", None, ""),
}

# Boundary caps (rule #4). The router validates too; the store guards as defense-in-depth.
NAME_MAX_LEN = 80
BASE_URL_MAX_LEN = 500
MODEL_MAX_LEN = 120
MAX_MODELS = 32
MAX_CUSTOM_PROVIDERS = 50


# --- read: the synthesized roster (builtins + persisted customs) ---


def _builtin_records(stored: dict) -> list[dict]:
    local_base = (stored.get("local_base_url") or "").strip() or _DEFAULT_LOCAL_BASE
    records = []
    for pid in _BUILTIN_IDS:
        name, wire, base, default_model = _BUILTIN_META[pid]
        if pid == "local":
            base = local_base
        records.append(
            {
                "id": pid,
                "name": name,
                "wire_format": wire,
                "base_url": base,
                "models": [default_model] if default_model else [],
                "builtin": True,
            }
        )
    return records


def _load_customs(stored: dict) -> list[dict]:
    raw = stored.get("custom_providers")
    out: list[dict] = []
    if isinstance(raw, list):
        for p in raw:
            if isinstance(p, dict) and isinstance(p.get("id"), str):
                out.append(
                    {
                        "id": p["id"],
                        "name": str(p.get("name") or p["id"]),
                        "wire_format": (
                            p.get("wire_format") if p.get("wire_format") in CUSTOM_WIRE_FORMATS else "chat_completions"
                        ),
                        "base_url": p.get("base_url"),
                        "models": [str(m) for m in (p.get("models") or []) if isinstance(m, str)],
                        "builtin": False,
                    }
                )
    return out


def list_providers() -> list[dict]:
    """Every provider (four synthesized builtins first, then any persisted customs)."""
    stored = app_settings.load_settings()
    return _builtin_records(stored) + _load_customs(stored)


def provider_ids() -> list[str]:
    """The set of valid provider ids — used to validate the active-provider selection at the boundary."""
    return [p["id"] for p in list_providers()]


def is_builtin(pid: str) -> bool:
    """True for the four synthesized presets (which can't be edited/deleted as custom providers)."""
    return pid in _BUILTIN_IDS


def get_provider(pid: str) -> dict | None:
    return next((p for p in list_providers() if p["id"] == pid), None)


def active_provider() -> dict:
    """The record for the active selection (flat ``provider`` id), defaulting to the gemini builtin."""
    stored = app_settings.load_settings()
    pid = stored.get("provider")
    records = _builtin_records(stored) + _load_customs(stored)
    return next((p for p in records if p["id"] == pid), records[0])


def active_model() -> str:
    """The resolved active model: the flat ``model`` override if set, else the active provider's first model."""
    stored = app_settings.load_settings()
    override = (stored.get("model") or "").strip()
    if override:
        return override
    models = active_provider()["models"]
    return models[0] if models else ""


# --- write: custom-provider CRUD (builtins are synthesized, never mutated here) ---


def add_custom(*, name: str, base_url: str, wire_format: str, models) -> dict:
    name = _norm_name(name)
    wire_format = _norm_wire(wire_format)
    base_url = _norm_base(base_url)
    models = _norm_models(models)
    stored = app_settings.load_settings()
    customs = _load_customs(stored)
    if len(customs) >= MAX_CUSTOM_PROVIDERS:
        raise ValueError(f"Too many custom providers (max {MAX_CUSTOM_PROVIDERS}).")
    rec = {
        "id": uuid.uuid4().hex,  # server-generated — a client can never inject / traverse via {id}
        "name": name,
        "wire_format": wire_format,
        "base_url": base_url,
        "models": models,
        "builtin": False,
    }
    customs.append(rec)
    _save_customs(stored, customs)
    return rec


def update_custom(pid: str, *, name=None, base_url=None, wire_format=None, models=None) -> dict | None:
    """Edit a custom provider. Returns the updated record, or ``None`` if ``pid`` is not a custom provider."""
    stored = app_settings.load_settings()
    customs = _load_customs(stored)
    for c in customs:
        if c["id"] == pid:
            if name is not None:
                c["name"] = _norm_name(name)
            if wire_format is not None:
                c["wire_format"] = _norm_wire(wire_format)
            if base_url is not None:
                c["base_url"] = _norm_base(base_url)
            if models is not None:
                c["models"] = _norm_models(models)
            _save_customs(stored, customs)
            return c
    return None


def delete_custom(pid: str) -> bool:
    """Remove a custom provider (+ its stored key). If it was the active provider, reset active to gemini."""
    stored = app_settings.load_settings()
    customs = _load_customs(stored)
    remaining = [c for c in customs if c["id"] != pid]
    if len(remaining) == len(customs):
        return False
    _save_customs(stored, remaining)
    app_settings.set_provider_key(pid, "")  # drop the orphaned secret (provider_key::<pid>)
    if app_settings.load_settings().get("provider") == pid:
        app_settings.set_provider("gemini")
        app_settings.set_model("")
    return True


def set_active(pid: str, model: str | None = None) -> None:
    """Set the active provider (+ optional model). Raises ``ValueError`` for an unknown id."""
    if pid not in provider_ids():
        raise ValueError(f"Unknown provider id: {pid!r}")
    app_settings.set_provider(pid)
    if model is not None:
        app_settings.set_model(model)


def _save_customs(stored: dict, customs: list[dict]) -> None:
    stored = dict(stored)
    stored["custom_providers"] = [
        {
            "id": c["id"],
            "name": c["name"],
            "wire_format": c["wire_format"],
            "base_url": c["base_url"],
            "models": c["models"],
        }
        for c in customs
    ]
    app_settings.save_settings(stored)


# --- boundary validation (raise ValueError → the router maps to 422) ---


def _norm_name(name) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("Provider name is required.")
    if len(name) > NAME_MAX_LEN:
        raise ValueError(f"Provider name too long (max {NAME_MAX_LEN}).")
    return name


def _norm_wire(w) -> str:
    if w not in CUSTOM_WIRE_FORMATS:
        raise ValueError(f"wire_format must be one of {CUSTOM_WIRE_FORMATS}.")
    return w


def _norm_base(u) -> str:
    u = (u or "").strip()
    if not u:
        raise ValueError("Base URL is required for a custom provider.")
    if len(u) > BASE_URL_MAX_LEN:
        raise ValueError(f"Base URL too long (max {BASE_URL_MAX_LEN}).")
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Base URL must be an http(s) URL (e.g. https://api.example.com).")
    u = u.rstrip("/")
    # The transports append the version themselves ({base}/v1/chat/completions etc.), so a base that already
    # ends in /v1 would double it — strip it off (users commonly paste the provider's documented /v1 base).
    if u.lower().endswith("/v1"):
        u = u[:-3].rstrip("/")
    return u


def _norm_models(models) -> list[str]:
    if not isinstance(models, (list, tuple)):
        raise ValueError("models must be a list.")
    out: list[str] = []
    for m in models:
        m = str(m or "").strip()
        if not m:
            continue
        if len(m) > MODEL_MAX_LEN:
            raise ValueError(f"Model name too long (max {MODEL_MAX_LEN}).")
        out.append(m)
    if len(out) > MAX_MODELS:
        raise ValueError(f"Too many models (max {MAX_MODELS}).")
    return out
