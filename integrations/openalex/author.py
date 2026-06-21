"""OpenAlex author resolution + works fetch for My Publications (inc 78), with DB-backed caching.

Mirrors the inc-74 OA-location adapter + the Crossref pattern (injectable fetcher Protocol, `external_api_cache`,
fail-closed, frozen dataclasses, polite-pool `CALLOSUM_OPENALEX_MAILTO`). This is **metadata egress** (public
identifiers — name/ORCID/DOIs — like the Crossref DOI lookup), NOT the Gemini library-text egress gate, and it
is **LLM-free**. Returns dataclasses or None; never raises to the caller.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from integrations.api_cache import get_cached, put_cached

OPENALEX_ROOT = "https://api.openalex.org"
OPENALEX_AUTHOR_PROVIDER = "openalex_author"
OPENALEX_WORKS_PROVIDER = "openalex_works"
_WORKS_PER_PAGE = 200
_MAX_WORKS_PAGES = 5  # cap a prolific author at ~1000 works


@dataclass(frozen=True)
class ResolvedAuthor:
    author_id: str  # the bare OpenAlex id, e.g. "A5023888391"
    display_name: str
    orcid: str | None
    works_count: int
    matched_by: str  # "orcid" (high confidence) or "name" (lower confidence)


@dataclass(frozen=True)
class AuthorWork:
    doi: str | None  # normalized: "10.xxxx/yyyy" lower-case (no https://doi.org/ prefix)
    title: str | None
    year: int | None


class AuthorFetcher(Protocol):
    def __call__(
        self, url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a GET to an absolute OpenAlex URL."""


class OpenAlexAuthorClient:
    def __init__(self, *, fetcher: AuthorFetcher | None = None, mailto: str | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.mailto = mailto or os.environ.get("CALLOSUM_OPENALEX_MAILTO")
        self.timeout = timeout

    def resolve_author(self, conn: Connection, *, orcid: str | None = None, name: str | None = None) -> ResolvedAuthor | None:
        if orcid and orcid.strip():
            o = orcid.strip()
            body = self._fetch(conn, OPENALEX_AUTHOR_PROVIDER, "orcid:" + o.lower(), f"{OPENALEX_ROOT}/authors/orcid:{o}", {})
            return _author_from_obj(_pick_author(body), matched_by="orcid") if body is not None else None
        if name and name.strip():
            n = name.strip()
            key = "name:" + hashlib.sha256(n.lower().encode("utf-8")).hexdigest()[:24]
            body = self._fetch(
                conn, OPENALEX_AUTHOR_PROVIDER, key, f"{OPENALEX_ROOT}/authors",
                {"filter": f"display_name.search:{n}", "per-page": "1"},
            )
            return _author_from_obj(_pick_author(body), matched_by="name") if body is not None else None
        return None

    def fetch_author_works(self, conn: Connection, author_id: str) -> list[AuthorWork]:
        cached = get_cached(conn, OPENALEX_WORKS_PROVIDER, author_id)
        if cached is not None and isinstance(cached["response_json"], dict):
            works = cached["response_json"].get("works")
            if isinstance(works, list):
                return [AuthorWork(doi=w.get("doi"), title=w.get("title"), year=w.get("year")) for w in works]
        works, ok = self._fetch_all_works(author_id)
        if ok:  # only cache a real result — never cache a transient total failure
            put_cached(
                conn, OPENALEX_WORKS_PROVIDER, author_id,
                request_json={"author_id": author_id}, response_json={"works": [asdict(w) for w in works]}, status_code=200,
            )
        return works

    def _fetch(self, conn, provider, key, url, params) -> dict[str, Any] | None:
        cached = get_cached(conn, provider, key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return cached["response_json"] if status == 200 and isinstance(cached["response_json"], dict) else None
        try:
            status, body = self.fetcher(url, params={**params, **self._polite()}, headers=self._headers(), timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(conn, provider, key, request_json={"url": url}, response_json={"error": str(exc)}, status_code=None)
            return None
        put_cached(conn, provider, key, request_json={"url": url}, response_json=body, status_code=status)
        return body if status == 200 and isinstance(body, dict) else None

    def _fetch_all_works(self, author_id: str) -> tuple[list[AuthorWork], bool]:
        works: list[AuthorWork] = []
        any_ok = False
        cursor: str | None = "*"
        for _ in range(_MAX_WORKS_PAGES):
            params = {
                "filter": f"author.id:{author_id}",
                "per-page": str(_WORKS_PER_PAGE),
                "cursor": cursor or "*",
                "select": "id,doi,title,publication_year",
            }
            try:
                status, body = self.fetcher(
                    f"{OPENALEX_ROOT}/works", params={**params, **self._polite()}, headers=self._headers(), timeout=self.timeout
                )
            except Exception:
                break
            if status != 200 or not isinstance(body, dict):
                break
            any_ok = True
            for work in body.get("results") or []:
                parsed = _work_from_obj(work)
                if parsed is not None:
                    works.append(parsed)
            cursor = (body.get("meta") or {}).get("next_cursor")
            if not cursor:
                break
        return works, any_ok

    def _polite(self) -> dict[str, str]:
        return {"mailto": self.mailto} if self.mailto else {}

    def _headers(self) -> dict[str, str]:
        ua = "Callosum/0.1 (local-first reference manager)"
        if self.mailto:
            ua = f"{ua}; mailto:{self.mailto}"
        return {"User-Agent": ua, "Accept": "application/json"}


def _httpx_fetcher(url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
    response = httpx.get(url, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _pick_author(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    if isinstance(body.get("results"), list):  # the name-filter endpoint
        return body["results"][0] if body["results"] else None
    return body if body.get("id") else None  # the by-id (orcid) endpoint returns the author object


def _author_from_obj(obj: dict[str, Any] | None, *, matched_by: str) -> ResolvedAuthor | None:
    if not isinstance(obj, dict):
        return None
    raw_id = str(obj.get("id") or "")
    author_id = raw_id.rsplit("/", 1)[-1] if raw_id else ""
    if not author_id:
        return None
    return ResolvedAuthor(
        author_id=author_id,
        display_name=str(obj.get("display_name") or ""),
        orcid=_normalize_orcid(obj.get("orcid")),
        works_count=int(obj.get("works_count") or 0),
        matched_by=matched_by,
    )


def _work_from_obj(work: dict[str, Any]) -> AuthorWork | None:
    if not isinstance(work, dict):
        return None
    doi = _normalize_doi(work.get("doi") or (work.get("ids") or {}).get("doi"))
    title = work.get("title") or work.get("display_name")
    year = work.get("publication_year")
    return AuthorWork(doi=doi, title=str(title) if title else None, year=int(year) if isinstance(year, int) else None)


def _normalize_doi(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi or None


def _normalize_orcid(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    orcid = value.strip()
    for prefix in ("https://orcid.org/", "http://orcid.org/"):
        if orcid.startswith(prefix):
            orcid = orcid[len(prefix):]
    return orcid or None
