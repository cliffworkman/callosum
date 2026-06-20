"""DOAJ resolver — gold OA confirmation (Increment B). Thin delegate, like the OpenAlex resolver."""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.doaj import DoajClient


class DoajResolver:
    id = "doaj"

    def __init__(self, *, client: DoajClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        return (self._client or DoajClient()).lookup_oa(conn, ref)
