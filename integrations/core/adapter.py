"""CORE (core.ac.uk) green-OA repository resolver, with DB-backed caching.

CORE aggregates repository (green) full text and hosts the PDFs itself (an https ``downloadUrl``). It requires
a free API key sent as a Bearer token; the key comes ONLY from ``CALLOSUM_CORE_API_KEY`` (env / gitignored
``.env``) and is never logged or persisted. **Without a key the client returns None** (the resolver simply
skips, never raising). Honors CORE's terms via cached responses + a polite UA. Returns ``OaLocation`` or None.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.api_cache import get_cached, put_cached

CORE_PROVIDER = "core"
CORE_SEARCH_URL = "https://api.core.ac.uk/v3/search/works"


class CoreFetcher(Protocol):
    def __call__(self, query: str, *, api_key: str, timeout: float) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for an authenticated CORE works search."""


class CoreClient:
    def __init__(self, *, fetcher: CoreFetcher | None = None, api_key: str | None = None, timeout: float = 15.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        # Key from env only; never echoed/stored. None/empty → the client (and so the resolver) is a no-op.
        self.api_key = api_key if api_key is not None else os.environ.get("CALLOSUM_CORE_API_KEY")
        self.timeout = timeout

    def lookup_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        if not self.api_key:
            return None  # no key configured → skip (never error)
        query, cache_key = _query_for(ref)
        if query is None:
            return None
        body = self._fetch(conn, query, cache_key)
        if body is None:
            return None
        return _oa_from_results(body)

    def _fetch(self, conn: Connection, query: str, cache_key: str) -> dict[str, Any] | None:
        cached = get_cached(conn, CORE_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return cached["response_json"] if status == 200 and isinstance(cached["response_json"], dict) else None
        try:
            status, body = self.fetcher(query, api_key=self.api_key, timeout=self.timeout)
        except Exception as exc:  # fail closed (the message never includes the key — it's a header, not a URL)
            put_cached(
                conn, CORE_PROVIDER, cache_key, request_json={"query": query}, response_json={"error": str(exc)}, status_code=None
            )
            return None
        put_cached(conn, CORE_PROVIDER, cache_key, request_json={"query": query}, response_json=body, status_code=status)
        return body if status == 200 and isinstance(body, dict) else None


def _query_for(ref: PaperRef) -> tuple[str | None, str]:
    if ref.doi:
        doi = ref.doi.strip().lower()
        return f'doi:"{doi}"', "doi:" + doi
    if ref.title:
        title = ref.title.strip()
        return f'title:"{title}"', "title:" + hashlib.sha256(title.lower().encode("utf-8")).hexdigest()[:24]
    return None, ""


def _httpx_fetcher(query: str, *, api_key: str, timeout: float) -> tuple[int, dict[str, Any] | None]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Callosum/0.1 (local-first reference manager)",
        "Accept": "application/json",
    }
    response = httpx.get(CORE_SEARCH_URL, params={"q": query, "limit": "1"}, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _oa_from_results(body: dict[str, Any]) -> OaLocation | None:
    results = body.get("results")
    if not isinstance(results, list) or not results:
        return None
    work = results[0] or {}
    download_url = work.get("downloadUrl")
    if not isinstance(download_url, str) or not download_url.startswith("https://"):
        return None
    try:
        return OaLocation(pdf_url=download_url, oa_color="green", version="am", source=CORE_PROVIDER)
    except ValueError:
        return None
