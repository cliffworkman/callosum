"""SciELO journal-by-ISSN client for the PUBLISHERS "where to submit" tool (backlog #40).

One of the regional legitimacy indexes the equitable legitimacy gate names — "the indexes carrying legitimate
non-Western journals that Scopus/WoS miss" — never a gate on the *listing*, only a positive fact when present.

Mirrors ``integrations/doaj/journals.py`` exactly: ISSN validated ``^\\d{4}-\\d{3}[\\dX]$`` before any request (no
SSRF); injectable ``fetcher`` (a fake in tests); cached via ``integrations.api_cache``; fail-closed (any error ->
cached error row -> None, never raises). No auth; SciELO's ArticleMeta API is free and unauthenticated.

The response is a bare JSON array (not the ``{"results": [...]}`` DOAJ shape) -- empty ``[]`` means "not indexed",
confirmed directly against the live API with both a real and a nonexistent ISSN. A hit returns one object per
SciELO collection the journal appears in, using SciELO's legacy ISIS-JSON field-numbering convention
(``v100``=title, ``v310``=country, ``collection``=the collection/country code) -- only the few fields needed to
show inspectable evidence ("indexed in SciELO, collections X/Y") are parsed; the rest of the ISIS record is
ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import Connection

from integrations.api_cache import get_cached, put_cached
from integrations.http_bounds import METADATA_RESPONSE_CAP, bounded_get

SCIELO_PROVIDER = "scielo-journals"
SCIELO_BASE_URL = "https://articlemeta.scielo.org/api/v1/journal/"

_ISSN_RE = re.compile(r"\d{4}-\d{3}[\dX]", re.IGNORECASE)


@dataclass(frozen=True)
class ScieloJournal:
    """SciELO journal-level facts -- enough to show as inspectable evidence, not the full ISIS record."""

    codes: list[str] = field(default_factory=list)  # SciELO internal ids, one per collection hit
    collections: list[str] = field(default_factory=list)  # raw collection codes, e.g. ["scl", "spa"]
    title: str | None = None
    country: str | None = None


class ScieloJournalsFetcher(Protocol):
    def __call__(self, issn: str, *, headers: dict[str, str], timeout: float) -> tuple[int, Any]:
        """Return HTTP status + parsed JSON (a bare list, or None) for a SciELO journal-by-ISSN lookup."""


class ScieloJournalsClient:
    def __init__(self, *, fetcher: ScieloJournalsFetcher | None = None, timeout: float = 10.0):
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def fetch_journal(self, conn: Connection, issn: str) -> ScieloJournal | None:
        """SciELO journal facts for an ISSN (validated before the request). Fail-closed -> None."""
        issn = (issn or "").strip().upper()
        if not _ISSN_RE.fullmatch(issn):
            return None
        cache_key = f"journal:{issn}"
        cached = get_cached(conn, SCIELO_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            body = cached["response_json"]
            results = body.get("results") if isinstance(body, dict) else None
            return _scielo_from_results(results) if status == 200 else None
        try:
            status, body = self.fetcher(issn, headers=self._headers(), timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(
                conn,
                SCIELO_PROVIDER,
                cache_key,
                request_json={"issn": issn},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return None
        # SciELO returns a bare JSON array; wrap it so put_cached's dict[str, Any] | None contract holds.
        put_cached(
            conn,
            SCIELO_PROVIDER,
            cache_key,
            request_json={"issn": issn},
            response_json={"results": body} if isinstance(body, list) else None,
            status_code=status,
        )
        return _scielo_from_results(body) if status == 200 and isinstance(body, list) else None

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": "Callosum/0.1 (local-first reference manager)", "Accept": "application/json"}


def _scielo_from_results(results: list[Any] | None) -> ScieloJournal | None:
    if not results:
        return None  # incl. the confirmed [] "not indexed" shape -- no error, no exception
    collections: list[str] = []
    codes: list[str] = []
    title: str | None = None
    country: str | None = None
    for rec in results:
        if not isinstance(rec, dict):
            continue
        coll = rec.get("collection")
        if isinstance(coll, str) and coll and coll not in collections:
            collections.append(coll)
        code = rec.get("code")
        if isinstance(code, str) and code and code not in codes:
            codes.append(code)
        if title is None:
            title = _first_isis_value(rec.get("v100"))
        if country is None:
            country = _first_isis_value(rec.get("v310"))
    if not collections and not codes:
        return None
    return ScieloJournal(codes=codes, collections=collections, title=title, country=country)


def _first_isis_value(field_value: Any) -> str | None:
    """SciELO's ISIS-JSON type-3 fields are ``[{"_": "value"}, ...]`` -- the first entry's ``_`` key."""
    if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict) and field_value[0].get("_"):
        return str(field_value[0]["_"])
    return None


def _httpx_fetcher(issn: str, *, headers: dict[str, str], timeout: float) -> tuple[int, Any]:
    response = bounded_get(
        SCIELO_BASE_URL, max_bytes=METADATA_RESPONSE_CAP, params={"issn": issn}, headers=headers, timeout=timeout
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
