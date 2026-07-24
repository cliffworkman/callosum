"""Short-lived exact-byte cache between remote CSL validation and install."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

_TTL_SECONDS = 5 * 60
_MAX_INSTALLS = 8
_lock = threading.Lock()
_prepared: dict[str, "PreparedInstall"] = {}


@dataclass(frozen=True)
class PreparedInstall:
    mode: str
    source: str
    created_at: float
    candidates: tuple[Any, ...]


def store_prepared(mode: str, source: str, candidates: list[Any]) -> str:
    now = time.monotonic()
    token = secrets.token_urlsafe(24)
    with _lock:
        expired = [key for key, value in _prepared.items() if now - value.created_at > _TTL_SECONDS]
        for key in expired:
            _prepared.pop(key, None)
        while len(_prepared) >= _MAX_INSTALLS:
            oldest = min(_prepared, key=lambda key: _prepared[key].created_at)
            _prepared.pop(oldest, None)
        _prepared[token] = PreparedInstall(mode, source, now, tuple(candidates))
    return token


def get_prepared(token: str, *, mode: str, source: str) -> tuple[Any, ...]:
    now = time.monotonic()
    with _lock:
        prepared = _prepared.get(str(token or ""))
    if prepared is None or now - prepared.created_at > _TTL_SECONDS:
        raise ValueError("The citation style preflight expired; validate it again")
    if prepared.mode != mode or prepared.source != source:
        raise ValueError("The citation style preflight does not match this install request")
    return prepared.candidates


def discard_prepared(token: str) -> None:
    with _lock:
        _prepared.pop(token, None)
