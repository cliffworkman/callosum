"""Shared FastAPI dependencies for the Callosum API routers."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import Engine


def get_connection(request: Request):
    engine: Engine = request.app.state.engine
    with engine.connect() as conn:
        yield conn


def get_engine(request: Request) -> Engine:
    """The app engine, for short mutating handlers that wrap their read+write unit in ``run_write`` (transaction-level
    retry on a transient SQLite writer lock) instead of taking a single ``get_connection`` connection."""
    return request.app.state.engine
