"""Semantic Scholar client — citation contexts ("how this paper is cited", B4 SP1, inc 232) + recommendations
(a third beyond-library Cite source, backlog #30 Track C, inc 449).

Fetches the actual **citing sentences** (Semantic Scholar "contexts") for a paper so callosum can classify each one's
stance **locally** (support / contrast / mention), and separately, papers S2's own recommendation engine links to a
locally relevant paper (Graph API `graph/v1` vs Recommendations API `recommendations/v1` — different base URLs, same
host/auth). Mirrors the OpenAlex/Crossref adapters: injectable fetchers, DB-backed caching (``external_api_cache`` via
the shared ``integrations/api_cache`` helper), fail-closed. Egress is **public bibliographic metadata** — a DOI
leaves; citing sentences/recommended-paper metadata return — the OpenAlex/Crossref posture, **NOT** the Gemini
library-text gate. Semantic Scholar's recommendation ranking is its own opaque algorithm: only a recommended paper's
public metadata is ever parsed, never a score/rank value (Principles #7, no opaque composite scores). Semantic
Scholar (Allen Institute for AI) is the data source; credited in-panel (citation-context) + in
``THIRD-PARTY-NOTICES.md`` (credit-the-lineage).
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
S2_RECOMMENDATIONS_BASE_URL = "https://api.semanticscholar.org/recommendations/v1"
MAX_CITATIONS = 500  # cap on papers pulled per focal paper, either edge (rule #4; also a documented coverage limit)
MAX_S2_RECOMMENDATIONS_FETCH = 20  # fixed fetch+cache cap, independent of a caller's requested `limit` (rule #4)
S2_PAGE_SIZE = 1000  # Semantic Scholar's max page size for the citations endpoint
_DOI_RE = re.compile(
    r"^10\.\d+/\S+$"
)  # a DOI-shaped id (defense-in-depth; the value is also fully url-encoded → no SSRF)


def _valid_doi(doi: str | None) -> str | None:
    """Normalize + validate a DOI-shaped id; ``None`` for anything else (no request is ever made for it)."""
    normalized = (doi or "").strip().lower().replace("https://doi.org/", "")
    return normalized if _DOI_RE.match(normalized) else None


@dataclass(frozen=True)
class CitingContext:
    """One paper on the other end of a citation edge (the citing paper for the ``citations`` edge; the cited paper
    for the ``references`` edge), with the sentence(s) of the edge (may be empty if S2 has none). ``claim`` is that
    paper's own claim (title/abstract) to classify the sentence against — set only for the ``references`` edge, where
    each cited paper has its own claim; for ``citations`` it's None and the constant focal claim is used instead."""

    citing_title: str | None
    citing_year: int | None
    citing_authors: list[str]
    citing_doi: str | None
    sentences: list[str]
    is_influential: bool
    claim: str | None = None


@dataclass(frozen=True)
class RecommendedPaper:
    """One paper Semantic Scholar's recommendation engine linked to a focal (anchor) paper. The ranking that
    produced this candidate is S2's own opaque algorithm — never parsed/exposed as a score; only the paper's own
    public metadata is carried (Principles #7, no opaque composite scores)."""

    title: str | None
    doi: str | None
    pmid: str | None
    year: int | None
    authors: list[str]
    journal: str | None
    url: str | None
    abstract: str | None


class S2Fetcher(Protocol):
    def __call__(
        self, path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a GET to <base URL> + path (S2_BASE_URL for ``fetcher``,
        S2_RECOMMENDATIONS_BASE_URL for ``recommendations_fetcher`` — same shape, different base)."""


@dataclass
class SemanticScholarClient:
    fetcher: S2Fetcher | None = None
    recommendations_fetcher: S2Fetcher | None = None  # separate seam: a different base URL (recommendations/v1)
    api_key: str | None = None  # optional CALLOSUM_S2_API_KEY — raises rate limits; the API works without one
    timeout: float = 12.0
    _resolved_key: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.fetcher = self.fetcher or _httpx_fetcher
        self.recommendations_fetcher = self.recommendations_fetcher or _httpx_recommendations_fetcher
        self._resolved_key = self.api_key or os.environ.get("CALLOSUM_S2_API_KEY")

    def fetch_citation_contexts(self, conn: Connection, doi: str) -> list[CitingContext]:
        """The papers that CITE this DOI, each with its citing sentence(s) — "how this paper is cited" (SP1)."""
        return self._fetch_edge(conn, doi, edge="citations")

    def fetch_reference_contexts(self, conn: Connection, doi: str) -> list[CitingContext]:
        """The papers this DOI CITES, each with the focal paper's citing sentence(s) + that cited paper's own claim —
        "how this paper cites its sources" (SP2). Semantic Scholar has already linked each in-text citation to its
        reference, so no local citation parsing is needed."""
        return self._fetch_edge(conn, doi, edge="references")

    def fetch_recommendations(self, conn: Connection, doi: str, *, limit: int = 10) -> list[RecommendedPaper]:
        """Papers Semantic Scholar's recommendation engine links to this DOI ("recommended alongside" a locally
        relevant paper — beyond-library Track C, inc 449). Always fetches/caches the fixed
        ``MAX_S2_RECOMMENDATIONS_FETCH`` cap regardless of ``limit`` (a limit-independent cache entry), then
        slices to ``limit`` at return time."""
        valid_doi = _valid_doi(doi)
        if valid_doi is None:
            return []  # not a DOI-shaped id → no request is made (no SSRF)
        limit = max(1, min(limit, MAX_S2_RECOMMENDATIONS_FETCH))
        cache_key = f"recommendations:{valid_doi}"
        cached = get_cached(conn, S2_PROVIDER, cache_key)
        if cached is not None and cached["response_json"] is not None:
            return _parse_recommendations(cached["response_json"])[:limit]

        headers = {"x-api-key": self._resolved_key} if self._resolved_key else {}
        path = f"/papers/forpaper/DOI:{quote(valid_doi, safe='')}"
        params = {
            "fields": "title,abstract,year,authors,externalIds,venue,url",
            "limit": str(MAX_S2_RECOMMENDATIONS_FETCH),
        }
        try:
            status, body = self.recommendations_fetcher(path, params=params, headers=headers, timeout=self.timeout)
        except Exception:
            return []  # fail-closed, not cached (network/parse error must stay retryable)
        if status != 200 or not isinstance(body, dict):
            return []  # incl. a 404 for a DOI unknown to S2 — not cached, so it stays retryable like any miss

        payload = {"recommendedPapers": (body.get("recommendedPapers") or [])[:MAX_S2_RECOMMENDATIONS_FETCH]}
        put_cached(
            conn, S2_PROVIDER, cache_key, request_json={"doi": valid_doi}, response_json=payload, status_code=200
        )
        return _parse_recommendations(payload)[:limit]

    def _fetch_edge(self, conn: Connection, doi: str, *, edge: str) -> list[CitingContext]:
        """Shared paginate + cache + fail-closed fetch of a citation edge (``citations`` or ``references``)."""
        doi = _valid_doi(doi) or ""
        if not doi:
            return []  # not a DOI-shaped id → no request is made (no SSRF)
        other = "citingPaper" if edge == "citations" else "citedPaper"
        want_claim = edge == "references"  # the cited paper's own claim is the per-item hypothesis for SP2
        fields = f"contexts,isInfluential,{other}.title,{other}.year,{other}.authors,{other}.externalIds" + (
            f",{other}.abstract" if want_claim else ""
        )
        cache_key = f"{edge}:{doi}"
        cached = get_cached(conn, S2_PROVIDER, cache_key)
        if cached is not None and cached["response_json"] is not None:
            return _parse(cached["response_json"], other_key=other, want_claim=want_claim)

        headers = {"x-api-key": self._resolved_key} if self._resolved_key else {}
        results: list[dict[str, Any]] = []
        offset = 0
        got_ok = False
        while len(results) < MAX_CITATIONS:
            path = f"/paper/DOI:{quote(doi, safe='')}/{edge}"
            params = {
                "fields": fields,
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
        return _parse(payload, other_key=other, want_claim=want_claim)


def _parse(payload: dict[str, Any], *, other_key: str = "citingPaper", want_claim: bool = False) -> list[CitingContext]:
    out: list[CitingContext] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        op = item.get(other_key) or {}
        authors = [str((a or {}).get("name") or "").strip() for a in (op.get("authors") or []) if isinstance(a, dict)]
        ext = op.get("externalIds") or {}
        doi = ext.get("DOI") if isinstance(ext, dict) else None
        sentences = [str(s).strip() for s in (item.get("contexts") or []) if str(s).strip()]
        year = op.get("year")
        title = str(op.get("title")) if op.get("title") else None
        claim = None
        if want_claim:  # S2 abstracts are plain text — no cleaning needed
            claim = (str(op.get("abstract") or "").strip()) or (title or "")
        out.append(
            CitingContext(
                citing_title=title,
                citing_year=int(year) if isinstance(year, int) else None,
                citing_authors=[a for a in authors if a][:6],
                citing_doi=str(doi).lower().replace("https://doi.org/", "") if doi else None,
                sentences=sentences[:5],
                is_influential=bool(item.get("isInfluential")),
                claim=claim,
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


def _parse_recommendations(payload: dict[str, Any]) -> list[RecommendedPaper]:
    out: list[RecommendedPaper] = []
    for item in payload.get("recommendedPapers") or []:
        if not isinstance(item, dict):
            continue
        authors = [str((a or {}).get("name") or "").strip() for a in (item.get("authors") or []) if isinstance(a, dict)]
        ext = item.get("externalIds") or {}
        doi = ext.get("DOI") if isinstance(ext, dict) else None
        pmid = ext.get("PubMed") if isinstance(ext, dict) else None
        year = item.get("year")
        out.append(
            RecommendedPaper(
                title=str(item["title"]) if item.get("title") else None,
                doi=str(doi).lower().replace("https://doi.org/", "") if doi else None,
                pmid=str(pmid) if pmid else None,
                year=int(year) if isinstance(year, int) else None,
                authors=[a for a in authors if a][:6],
                journal=str(item["venue"]) if item.get("venue") else None,
                url=str(item["url"]) if item.get("url") else None,
                abstract=str(item["abstract"]) if item.get("abstract") else None,
            )
        )
    return out


def _httpx_recommendations_fetcher(
    path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, Any] | None]:
    response = httpx.get(S2_RECOMMENDATIONS_BASE_URL + path, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
