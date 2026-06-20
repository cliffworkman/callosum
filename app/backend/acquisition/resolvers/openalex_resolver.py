"""OpenAlex resolver — the primary (and, in Increment A, only) provider in the resolver registry.

Keeps the integrations client pure (like the Crossref adapter) and the registry's `OaLocation` currency in
the app layer. Increment B adds sibling resolvers (DOAJ/CORE/preprints/Crossref) the same way.
"""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.openalex import OpenAlexClient


class OpenAlexResolver:
    id = "openalex"

    def __init__(self, *, client: OpenAlexClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        client = self._client or OpenAlexClient()
        return client.lookup_best_oa(conn, ref)
