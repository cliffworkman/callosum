"""OSF resolver — preprint OA, covers PsyArXiv et al. (Increment B). Thin delegate, like OpenAlex."""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.osf import OsfClient


class OsfResolver:
    id = "osf"

    def __init__(self, *, client: OsfClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        return (self._client or OsfClient()).lookup_oa(conn, ref)
