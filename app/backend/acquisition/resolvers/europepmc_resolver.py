"""Europe PMC resolver — OA full-text PDF (Increment B). Thin delegate, like the OpenAlex resolver."""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.europepmc import EuropePmcClient


class EuropePmcResolver:
    id = "europepmc"

    def __init__(self, *, client: EuropePmcClient | None = None) -> None:
        self._client = client

    def resolve(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        return (self._client or EuropePmcClient()).lookup_oa(conn, ref)
