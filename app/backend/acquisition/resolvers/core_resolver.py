"""CORE resolver — green/repository OA (Increment B). No API key configured → no-op (cascade continues)."""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.core import CoreClient


class CoreResolver:
    id = "core"

    def __init__(self, *, client: CoreClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        return (self._client or CoreClient()).lookup_oa(conn, ref)
