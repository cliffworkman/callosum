"""Europe PMC OA resolver, with DB-backed caching.

Europe PMC exposes an ``isOpenAccess`` flag and a sanctioned https full-text PDF endpoint. We resolve a
DOI/PMID to a record and, **only when the record asserts open access**, return an ``OaLocation`` pointing at
``/{source}/{pmcid}/fullTextPDF``. The OA judgment is Europe PMC's, not ours. Returns ``OaLocation`` or None;
never raises.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.acquisition.registry import OaColor, OaLocation, PaperRef
from integrations.api_cache import get_cached, put_cached

EUROPEPMC_PROVIDER = "europepmc"
EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_REST_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


class EuropePmcFetcher(Protocol):
    def __call__(self, query: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a Europe PMC search."""


class EuropePmcClient:
    def __init__(self, *, fetcher: EuropePmcFetcher | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def lookup_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        query, cache_key = _query_for(ref)
        if query is None:
            return None
        body = self._fetch(conn, query, cache_key)
        if body is None:
            return None
        return _oa_from_search(body)

    def _fetch(self, conn: Connection, query: str, cache_key: str) -> dict[str, Any] | None:
        cached = get_cached(conn, EUROPEPMC_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return cached["response_json"] if status == 200 and isinstance(cached["response_json"], dict) else None
        try:
            status, body = self.fetcher(query, headers=_headers(), timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(
                conn,
                EUROPEPMC_PROVIDER,
                cache_key,
                request_json={"query": query},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return None
        put_cached(
            conn, EUROPEPMC_PROVIDER, cache_key, request_json={"query": query}, response_json=body, status_code=status
        )
        return body if status == 200 and isinstance(body, dict) else None


def _query_for(ref: PaperRef) -> tuple[str | None, str]:
    if ref.doi:
        doi = ref.doi.strip().lower()
        return f"DOI:{doi}", "doi:" + doi
    if ref.pmid:
        pmid = str(ref.pmid).strip()
        return f"EXT_ID:{pmid} AND SRC:MED", "pmid:" + pmid
    return None, ""


def _headers() -> dict[str, str]:
    return {"User-Agent": "Callosum/0.1 (local-first reference manager)", "Accept": "application/json"}


def _httpx_fetcher(query: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
    params = {"query": query, "format": "json", "resultType": "core", "pageSize": "1"}
    response = httpx.get(EUROPEPMC_SEARCH_URL, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _oa_from_search(body: dict[str, Any]) -> OaLocation | None:
    results = (body.get("resultList") or {}).get("result")
    if not isinstance(results, list) or not results:
        return None
    record = results[0] or {}
    if str(record.get("isOpenAccess") or "").upper() != "Y":  # Europe PMC's own OA assertion
        return None
    pmcid = record.get("pmcid")
    if not isinstance(pmcid, str) or not pmcid:
        return None
    pdf_url = f"{EUROPEPMC_REST_BASE}/PMC/{pmcid}/fullTextPDF"
    lic = record.get("license")
    color: OaColor = "gold" if str(lic or "").lower().startswith("cc") else "green"
    try:
        return OaLocation(
            pdf_url=pdf_url, oa_color=color, version="vor", source=EUROPEPMC_PROVIDER, license=str(lic) if lic else None
        )
    except ValueError:
        return None
