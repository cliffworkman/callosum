"""Crossref-OA resolver — publisher PDF link + asserted license (Increment B).

Reuses the existing ``CrossrefClient`` (and its DOI cache) via ``crossref_oa_location``; conservative — only
yields an ``OaLocation`` when a license is registered (no guessing). Delegate, like the OpenAlex resolver.
"""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.crossref.adapter import CrossrefClient
from integrations.crossref.oa import crossref_oa_location


class CrossrefResolver:
    id = "crossref_oa"

    def __init__(self, *, client: CrossrefClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        return crossref_oa_location(conn, ref, client=self._client)
