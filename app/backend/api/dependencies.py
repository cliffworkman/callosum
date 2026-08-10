"""Shared FastAPI dependencies for the Callosum API routers."""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import Engine

from app.backend import app_settings


def get_connection(request: Request):
    engine: Engine = request.app.state.engine
    with engine.connect() as conn:
        yield conn


def get_engine(request: Request) -> Engine:
    """The app engine, for short mutating handlers that wrap their read+write unit in ``run_write`` (transaction-level
    retry on a transient SQLite writer lock) instead of taking a single ``get_connection`` connection."""
    return request.app.state.engine


def require_superuser() -> None:
    """403s unless the currently signed-in identity (the single-slot ORCID session, inc 195) is a verified
    superuser. A reusable gate for any endpoint not yet proven safe for general release — inc 195 deferred
    what the flag gates; this is the mechanism, applied first to `GET /diagnostics`."""
    if not app_settings.oauth_account_status()["is_superuser"]:
        raise HTTPException(status_code=403, detail="Superuser access required")
