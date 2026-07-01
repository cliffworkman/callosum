"""Semantic Scholar Graph API client — citation contexts for "how this paper is cited" (B4 SP1, inc 232).

Fetches the actual **citing sentences** (Semantic Scholar "contexts") for a paper so callosum can classify each one's
stance **locally** (support / contrast / mention). Mirrors the OpenAlex/Crossref adapters: an injectable ``fetcher``,
DB-backed caching (``external_api_cache`` via the shared ``integrations/api_cache`` helper), fail-closed. Egress is
**public bibliographic metadata** — a DOI leaves; citing sentences + citing-paper metadata return — the OpenAlex/
Crossref posture, **NOT** the Gemini library-text gate. Semantic Scholar (Allen Institute for AI) is the data source;
credited in-panel + in ``THIRD-PARTY-NOTICES.md`` (credit-the-lineage).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import Connection

from integrations.api_cache import get_cached, put_cached

S2_PROVIDER = "semantic-scholar"
S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
S2_CITATION_FIELDS = (
    "contexts,isInfluential,citingPaper.title,citingPaper.year,citingPaper.authors,citingPaper.externalIds"
)
MAX_CITATIONS = 500  # cap on citing papers pulled per focal paper (rule #4; also a documented coverage limit)
S2_PAGE_SIZE = 1000  # Semantic Scholar's max page size for the citations endpoint
_DOI_RE = re.compile(
    r"^10\.\d+/\S+$"
)  # a DOI-shaped id (defense-in-depth; the value is also fully url-encoded → no SSRF)


@dataclass(frozen=True)
class CitingContext:
    """One paper that cites the focal paper, with the sentence(s) where it does so (may be empty if S2 has none)."""

    citing_title: str | None
    citing_year: int | None
    citing_authors: list[str]
    citing_doi: str | None
    sentences: list[str]
    is_influential: bool


class S2Fetcher(Protocol):
    def __call__(
        self, path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a GET to S2_BASE_URL + path."""


@dataclass
class SemanticScholarClient:
    fetcher: S2Fetcher | None = None
    api_key: str | None = None  # optional CALLOSUM_S2_API_KEY — raises rate limits; the API works without one
    timeout: float = 12.0
    _resolved_key: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.fetcher = self.fetcher or _httpx_fetcher
        self._resolved_key = self.api_key or os.environ.get("CALLOSUM_S2_API_KEY")

    def fetch_citation_contexts(self, conn: Connection, doi: str) -> list[CitingContext]:
        """The papers that cite this DOI, each with its citing sentence(s). Cached; capped; fail-closed → []."""
        doi = (doi or "").strip().lower().replace("https://doi.org/", "")
        if not _DOI_RE.match(doi):
            return []  # not a DOI-shaped id → no request is made (no SSRF)
        cache_key = f"contexts:{doi}"
        cached = get_cached(conn, S2_PROVIDER, cache_key)
        if cached is not None and cached["response_json"] is not None:
            return _parse(cached["response_json"])

        headers = {"x-api-key": self._resolved_key} if self._resolved_key else {}
        results: list[dict[str, Any]] = []
        offset = 0
        got_ok = False
        while len(results) < MAX_CITATIONS:
            path = f"/paper/DOI:{quote(doi, safe='')}/citations"
            params = {
                "fields": S2_CITATION_FIELDS,
                "offset": str(offset),
                "limit": str(min(S2_PAGE_SIZE, MAX_CITATIONS - len(results))),
            }
            try:
                status, body = self.fetcher(path, params=params, headers=headers, timeout=self.timeout)
            except Exception:
                break  # fail-closed (network/parse error → whatever we already have; don't cache a partial failure)
            if status != 200 or not isinstance(body, dict):
                break
            got_ok = True
            data = body.get("data") or []
            results.extend(d for d in data if isinstance(d, dict))
            nxt = body.get("next")
            if not data or nxt is None:
                break
            offset = int(nxt)

        payload = {"data": results[:MAX_CITATIONS]}
        if got_ok:  # only cache a real answer (a transient failure must be retryable, not cached as "0 citations")
            put_cached(conn, S2_PROVIDER, cache_key, request_json={"doi": doi}, response_json=payload, status_code=200)
        return _parse(payload)


def _parse(payload: dict[str, Any]) -> list[CitingContext]:
    out: list[CitingContext] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        cp = item.get("citingPaper") or {}
        authors = [str((a or {}).get("name") or "").strip() for a in (cp.get("authors") or []) if isinstance(a, dict)]
        ext = cp.get("externalIds") or {}
        doi = ext.get("DOI") if isinstance(ext, dict) else None
        sentences = [str(s).strip() for s in (item.get("contexts") or []) if str(s).strip()]
        year = cp.get("year")
        out.append(
            CitingContext(
                citing_title=str(cp.get("title")) if cp.get("title") else None,
                citing_year=int(year) if isinstance(year, int) else None,
                citing_authors=[a for a in authors if a][:6],
                citing_doi=str(doi).lower().replace("https://doi.org/", "") if doi else None,
                sentences=sentences[:5],
                is_influential=bool(item.get("isInfluential")),
            )
        )
    return out


def _httpx_fetcher(
    path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, Any] | None]:
    response = httpx.get(S2_BASE_URL + path, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
