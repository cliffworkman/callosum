"""DOAJ *journals* client for the PUBLISHERS "where to submit" tool (inc TBD, backlog #40).

Distinct from `adapter.py` (a DOI→article OA-PDF resolver): this reads DOAJ **journal**-level facts by ISSN —
APC (amount + currency), waiver policy, declared license family, the DOAJ Seal, subjects/keywords — the
OA-specific fields OpenAlex `/sources` lacks. Enriches an OA candidate's profile (a closed journal, absent from
DOAJ, simply has no DOAJ record and shows its OpenAlex facts only).

ISSN validated `^\\d{4}-\\d{3}[\\dX]$` before any request (no SSRF); injectable ``fetcher`` (a fake in tests);
cached via ``integrations.api_cache``; fail-closed (any error → cached error row → None, never raises). Optional
``CALLOSUM_DOAJ_API_KEY`` sent as a header only if present (never in a URL/cache/log).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote

from sqlalchemy import Connection

from integrations.api_cache import get_cached, put_cached
from integrations.http_bounds import METADATA_RESPONSE_CAP, bounded_get

DOAJ_JOURNALS_PROVIDER = "doaj-journals"
DOAJ_JOURNALS_BASE_URL = "https://doaj.org/api/search/journals"

_ISSN_RE = re.compile(r"\d{4}-\d{3}[\dX]", re.IGNORECASE)


@dataclass(frozen=True)
class DoajJournal:
    """DOAJ journal-level facts (the OA-specific profile fields)."""

    apc_amount: float | None = None
    apc_currency: str | None = None
    apc_has_waiver: bool = False
    waiver_url: str | None = None
    license: list[str] = field(default_factory=list)  # families, e.g. ["CC BY"]
    seal: bool = False
    subjects: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class DoajJournalsFetcher(Protocol):
    def __call__(self, query: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a DOAJ journal search."""


class DoajJournalsClient:
    def __init__(self, *, fetcher: DoajJournalsFetcher | None = None, timeout: float = 10.0):
        self.fetcher = fetcher or _httpx_fetcher

        self.timeout = timeout
        self.api_key = os.environ.get("CALLOSUM_DOAJ_API_KEY") or None

    def fetch_journal(self, conn: Connection, issn: str) -> DoajJournal | None:
        """DOAJ journal facts for an ISSN (validated before the request). Fail-closed → None."""
        issn = (issn or "").strip().upper()
        if not _ISSN_RE.fullmatch(issn):
            return None
        cache_key = f"journal:{issn}"
        cached = get_cached(conn, DOAJ_JOURNALS_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            body = cached["response_json"]
            return _journal_from_body(body) if status == 200 and isinstance(body, dict) else None
        try:
            status, body = self.fetcher(f"issn:{issn}", headers=self._headers(), timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(
                conn,
                DOAJ_JOURNALS_PROVIDER,
                cache_key,
                request_json={"issn": issn},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return None
        put_cached(
            conn, DOAJ_JOURNALS_PROVIDER, cache_key, request_json={"issn": issn}, response_json=body, status_code=status
        )
        return _journal_from_body(body) if status == 200 and isinstance(body, dict) else None

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": "Callosum/0.1 (local-first reference manager)", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"  # write-only: never logged/cached
        return headers


def _journal_from_body(body: dict[str, Any]) -> DoajJournal | None:
    results = body.get("results")
    if not isinstance(results, list) or not results:
        return None
    result = results[0] or {}
    bibjson = result.get("bibjson") if isinstance(result.get("bibjson"), dict) else {}
    apc = bibjson.get("apc") if isinstance(bibjson.get("apc"), dict) else {}
    amount, currency = _apc(apc)
    waiver = bibjson.get("waiver") if isinstance(bibjson.get("waiver"), dict) else {}
    has_waiver = bool(waiver.get("has_waiver"))
    waiver_url = str(waiver.get("url")) if waiver.get("url") else None
    licenses = [
        str(lic.get("type")) for lic in (bibjson.get("license") or []) if isinstance(lic, dict) and lic.get("type")
    ]
    # the Seal: DOAJ exposes it at admin.seal (newer) or bibjson.boai/bibjson.seal — read either, default False.
    admin = result.get("admin") if isinstance(result.get("admin"), dict) else {}
    seal = bool(admin.get("seal") or bibjson.get("seal") or bibjson.get("boai"))
    subjects = [str(s.get("term")) for s in (bibjson.get("subject") or []) if isinstance(s, dict) and s.get("term")][
        :12
    ]
    keywords = [str(k) for k in (bibjson.get("keywords") or []) if isinstance(k, str)][:20]
    return DoajJournal(
        apc_amount=amount,
        apc_currency=currency,
        apc_has_waiver=has_waiver,
        waiver_url=waiver_url,
        license=licenses,
        seal=seal,
        subjects=subjects,
        keywords=keywords,
    )


def _apc(apc: dict[str, Any]) -> tuple[float | None, str | None]:
    """DOAJ `bibjson.apc` → (amount, currency). `has_apc: false` → (0.0, None). A `max` list carries the price."""
    if apc.get("has_apc") is False:
        return (0.0, None)
    prices = apc.get("max")
    if isinstance(prices, list) and prices and isinstance(prices[0], dict):
        price = prices[0]
        amt = price.get("price")
        cur = price.get("currency")
        return (
            float(amt) if isinstance(amt, (int, float)) else None,
            str(cur) if cur else None,
        )
    return (None, None)


def _httpx_fetcher(query: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
    response = bounded_get(
        f"{DOAJ_JOURNALS_BASE_URL}/{quote(query, safe=':')}",
        max_bytes=METADATA_RESPONSE_CAP,
        headers=headers,
        timeout=timeout,
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
