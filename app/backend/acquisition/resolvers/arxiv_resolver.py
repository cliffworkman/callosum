"""arXiv resolver — preprint OA (Increment B). Thin delegate, like the OpenAlex resolver."""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.arxiv import ArxivClient


class ArxivResolver:
    id = "arxiv"

    def __init__(self, *, client: ArxivClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        return (self._client or ArxivClient()).lookup_oa(conn, ref)
