"""Shared FastAPI dependencies for the Callosum API routers."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import Engine


def get_connection(request: Request):
    engine: Engine = request.app.state.engine
    with engine.connect() as conn:
        yield conn
