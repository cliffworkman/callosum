"""DOAJ (Directory of Open Access Journals) OA resolver, with DB-backed caching.

DOAJ-listed articles are gold open access. We return an ``OaLocation`` only when DOAJ exposes a direct
https PDF fulltext link (it often links an HTML landing page, which we will not present as a PDF). OA-ness
is DOAJ's assertion, not ours. Returns ``OaLocation`` or None; never raises.
"""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.api_cache import get_cached, put_cached

DOAJ_PROVIDER = "doaj"
DOAJ_BASE_URL = "https://doaj.org/api/search/articles"


class DoajFetcher(Protocol):
    def __call__(self, query: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a DOAJ article search."""


class DoajClient:
    def __init__(self, *, fetcher: DoajFetcher | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def lookup_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        if not ref.doi:
            return None
        doi = ref.doi.strip().lower()
        body = self._fetch(conn, f"doi:{doi}", "doi:" + doi)
        if body is None:
            return None
        return _oa_from_results(body)

    def _fetch(self, conn: Connection, query: str, cache_key: str) -> dict[str, Any] | None:
        cached = get_cached(conn, DOAJ_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return cached["response_json"] if status == 200 and isinstance(cached["response_json"], dict) else None
        try:
            status, body = self.fetcher(query, headers=_headers(), timeout=self.timeout)
        except Exception as exc:  # fail closed — never raise to the caller
            put_cached(
                conn,
                DOAJ_PROVIDER,
                cache_key,
                request_json={"query": query},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return None
        put_cached(
            conn, DOAJ_PROVIDER, cache_key, request_json={"query": query}, response_json=body, status_code=status
        )
        return body if status == 200 and isinstance(body, dict) else None


def _headers() -> dict[str, str]:
    return {"User-Agent": "Callosum/0.1 (local-first reference manager)", "Accept": "application/json"}


def _httpx_fetcher(query: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
    response = httpx.get(f"{DOAJ_BASE_URL}/{quote(query, safe=':')}", headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _oa_from_results(body: dict[str, Any]) -> OaLocation | None:
    results = body.get("results")
    if not isinstance(results, list) or not results:
        return None
    bibjson = (results[0] or {}).get("bibjson") or {}
    pdf_url = _pdf_link(bibjson)
    if pdf_url is None:
        return None
    try:
        return OaLocation(
            pdf_url=pdf_url, oa_color="gold", version="vor", source=DOAJ_PROVIDER, license=_license(bibjson)
        )
    except ValueError:
        return None


def _pdf_link(bibjson: dict[str, Any]) -> str | None:
    """A bibjson fulltext link that is an actual https PDF (content-type PDF or a .pdf URL); else None."""
    for link in bibjson.get("link") or []:
        if not isinstance(link, dict):
            continue
        url = link.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        ctype = str(link.get("content_type") or "").lower()
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return url
    return None


def _license(bibjson: dict[str, Any]) -> str | None:
    for lic in bibjson.get("license") or []:
        if isinstance(lic, dict) and lic.get("type"):
            return str(lic["type"])
    return None
