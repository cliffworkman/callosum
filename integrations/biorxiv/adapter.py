"""bioRxiv / medRxiv preprint resolver, with DB-backed caching.

Resolves a ``10.1101/*`` DOI via the bioRxiv details API (trying the ``biorxiv`` then ``medrxiv`` servers,
which share the prefix) and returns the constructed ``.full.pdf`` URL as a green/preprint ``OaLocation``.
These servers host author-deposited preprints (green OA). Returns ``OaLocation`` or None; never raises.
"""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.api_cache import get_cached, put_cached

BIORXIV_PROVIDER = "biorxiv"
BIORXIV_DETAILS_BASE = "https://api.biorxiv.org/details"
_SERVERS = ("biorxiv", "medrxiv")
_HOSTS = {"biorxiv": "www.biorxiv.org", "medrxiv": "www.medrxiv.org"}


class BiorxivFetcher(Protocol):
    def __call__(self, server: str, doi: str, *, timeout: float) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a bioRxiv/medRxiv details lookup."""


class BiorxivClient:
    def __init__(self, *, fetcher: BiorxivFetcher | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def lookup_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        if not ref.doi:
            return None
        doi = ref.doi.strip().lower()
        for server in _SERVERS:
            record = self._fetch(conn, server, doi)
            if record is None:
                continue
            version = str(record.get("version") or "1")
            pdf_url = f"https://{_HOSTS[server]}/content/{doi}v{version}.full.pdf"
            try:
                return OaLocation(pdf_url=pdf_url, oa_color="green", version="preprint", source=server)
            except ValueError:
                return None
        return None

    def _fetch(self, conn: Connection, server: str, doi: str) -> dict[str, Any] | None:
        cache_key = f"{server}:{doi}"
        cached = get_cached(conn, BIORXIV_PROVIDER, cache_key)
        if cached is not None:
            body = cached["response_json"]
            return _record(body) if isinstance(body, dict) else None
        try:
            status, body = self.fetcher(server, doi, timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(
                conn,
                BIORXIV_PROVIDER,
                cache_key,
                request_json={"server": server, "doi": doi},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return None
        put_cached(
            conn,
            BIORXIV_PROVIDER,
            cache_key,
            request_json={"server": server, "doi": doi},
            response_json=body,
            status_code=status,
        )
        return _record(body) if status == 200 and isinstance(body, dict) else None


def _record(body: dict[str, Any]) -> dict[str, Any] | None:
    """The latest version record from a bioRxiv details payload, or None when the DOI is not found."""
    collection = body.get("collection")
    if not isinstance(collection, list) or not collection:
        return None
    last = collection[-1]
    return last if isinstance(last, dict) else None


def _httpx_fetcher(server: str, doi: str, *, timeout: float) -> tuple[int, dict[str, Any] | None]:
    url = f"{BIORXIV_DETAILS_BASE}/{server}/{quote(doi, safe='/')}"
    response = httpx.get(
        url,
        headers={"User-Agent": "Callosum/0.1 (local-first reference manager)", "Accept": "application/json"},
        timeout=timeout,
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
