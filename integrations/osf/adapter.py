"""OSF preprints resolver (covers PsyArXiv, SocArXiv, etc.), with DB-backed caching.

Resolves a DOI to an OSF preprint (``embed=primary_file`` returns the primary file's https download link in
one request) and returns it as a green/preprint ``OaLocation``. OSF preprints are author-deposited (green OA).
Returns ``OaLocation`` or None; never raises.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.api_cache import get_cached, put_cached

OSF_PROVIDER = "osf"
OSF_PREPRINTS_URL = "https://api.osf.io/v2/preprints/"


class OsfFetcher(Protocol):
    def __call__(self, doi: str, *, timeout: float) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for an OSF preprints DOI filter (with primary_file embedded)."""


class OsfClient:
    def __init__(self, *, fetcher: OsfFetcher | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def lookup_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        if not ref.doi:
            return None
        doi = ref.doi.strip().lower()
        body = self._fetch(conn, doi)
        if body is None:
            return None
        download = _download_url(body)
        if download is None:
            return None
        try:
            return OaLocation(pdf_url=download, oa_color="green", version="preprint", source=OSF_PROVIDER)
        except ValueError:
            return None

    def _fetch(self, conn: Connection, doi: str) -> dict[str, Any] | None:
        cache_key = "doi:" + doi
        cached = get_cached(conn, OSF_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return cached["response_json"] if status == 200 and isinstance(cached["response_json"], dict) else None
        try:
            status, body = self.fetcher(doi, timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(
                conn,
                OSF_PROVIDER,
                cache_key,
                request_json={"doi": doi},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return None
        put_cached(conn, OSF_PROVIDER, cache_key, request_json={"doi": doi}, response_json=body, status_code=status)
        return body if status == 200 and isinstance(body, dict) else None


def _download_url(body: dict[str, Any]) -> str | None:
    data = body.get("data")
    if not isinstance(data, list) or not data:
        return None
    embeds = (data[0] or {}).get("embeds") or {}
    primary = (embeds.get("primary_file") or {}).get("data") or {}
    download = (primary.get("links") or {}).get("download")
    return download if isinstance(download, str) and download.startswith("https://") else None


def _httpx_fetcher(doi: str, *, timeout: float) -> tuple[int, dict[str, Any] | None]:
    params = {"filter[doi]": doi, "embed": "primary_file"}
    response = httpx.get(
        OSF_PREPRINTS_URL,
        params=params,
        headers={"User-Agent": "Callosum/0.1 (local-first reference manager)", "Accept": "application/json"},
        timeout=timeout,
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
