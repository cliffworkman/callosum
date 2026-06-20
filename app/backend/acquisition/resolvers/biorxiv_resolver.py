"""bioRxiv / medRxiv resolver — preprint OA (Increment B). Thin delegate, like the OpenAlex resolver."""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.biorxiv import BiorxivClient


class BiorxivResolver:
    id = "biorxiv"

    def __init__(self, *, client: BiorxivClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        return (self._client or BiorxivClient()).lookup_oa(conn, ref)
