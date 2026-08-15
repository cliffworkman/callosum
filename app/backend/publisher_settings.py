"""PUBLISHERS "where to submit" preferences (#40 SP1b): the open-science weighting + result breadth.

Split out of ``app_settings.py`` (backlog #30 Stage 2, task 9 — that file's own GROBID-url addition pushed it
back over the 600-line cap after inc 478's own superuser.py split had it sitting exactly at the boundary) to
keep it under the cap — the established leaf-module pattern (inc 137/220/262/264/478). Unlike ``superuser.py``,
this leaf depends on ``app_settings``'s public read/write API (``load_settings``/``save_settings``) rather than
being purely env-based, so — to avoid a two-way import — it is NOT re-exported back from ``app_settings.py``;
its one real call site (``routers/settings.py``) imports this module directly instead.

Local prefs, NOT secrets, and NEVER transmitted externally (the weighting reaches only the local
``/methods/publishers/run`` endpoint; it is never forwarded to OpenAlex/DOAJ). Stored in the file (returnable by
``GET /settings`` for the local UI). The first-use choice gate needs "no pre-selection", so both start as None
(unset) — ``publisher_defaults_set()`` is False until the user actively sets BOTH (never a pre-filled default).
"""

from __future__ import annotations

from app.backend import app_settings


def set_publisher_weighting(value: float | None) -> None:
    """The open-science weighting (0.0 = fit only … 1.0 = strongly favor open). None clears it (→ unset)."""
    data = app_settings.load_settings()
    if value is None:
        data.pop("publisher_weighting", None)
    else:
        data["publisher_weighting"] = float(value)
    app_settings.save_settings(data)


def stored_publisher_weighting() -> float | None:
    val = app_settings.load_settings().get("publisher_weighting")
    return float(val) if isinstance(val, (int, float)) else None


def set_publisher_breadth(value: str | None) -> None:
    """Result breadth ("focused" | "broad"). Empty/whitespace clears it (→ unset)."""
    data = app_settings.load_settings()
    v = (value or "").strip()
    if v:
        data["publisher_breadth"] = v
    else:
        data.pop("publisher_breadth", None)
    app_settings.save_settings(data)


def stored_publisher_breadth() -> str | None:
    val = app_settings.load_settings().get("publisher_breadth")
    return val if isinstance(val, str) and val.strip() else None


def publisher_defaults_set() -> bool:
    """True once the user has actively set BOTH consequential publisher defaults (the first-use gate is satisfied).
    Nothing is pre-selected — neither is set until the user chooses, so the weighting is one forced choice among
    peers (never the lone spotlighted one)."""
    return stored_publisher_weighting() is not None and stored_publisher_breadth() is not None
