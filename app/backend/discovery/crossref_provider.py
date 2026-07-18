"""Crossref Search provider (backlog #28, inc 183). Queries Crossref's `/works?query=` (keyword/title/author);
covers journals AND preprints (bioRxiv/medRxiv are DOI-indexed in Crossref). Its own injectable fetcher (hermetic
tests) — separate from the DOI-resolution CrossrefClient (which caches per DOI). Public metadata; polite-pool
mailto from Settings → Metadata access. No egress gate (not the Gemini gate)."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.backend.app_settings import resolved_mailto
from app.backend.discovery.providers import Item
from app.backend.metadata.abstract_display import abstract_plain_text

CROSSREF_SEARCH_URL = "https://api.crossref.org/works"
_SELECT = "DOI,title,abstract,author,container-title,issued,URL,type"


class SearchFetcher(Protocol):
    def __call__(self, query: str, rows: int, *, headers: dict[str, str], timeout: float) -> list[dict[str, Any]]: ...


def _httpx_search(query: str, rows: int, *, headers: dict[str, str], timeout: float) -> list[dict[str, Any]]:
    resp = httpx.get(
        CROSSREF_SEARCH_URL,
        params={"query": query, "rows": rows, "select": _SELECT},
        headers=headers,
        timeout=timeout,
    )
    if resp.status_code != 200:
        return []
    body = resp.json()
    message = body.get("message") if isinstance(body, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    return items if isinstance(items, list) else []


def _first(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    text = str(value).strip() if value else ""
    return text or None


def _author_name(author: Any) -> str | None:
    if not isinstance(author, dict):
        return None
    family = (author.get("family") or "").strip()
    given = (author.get("given") or "").strip()
    if family and given:
        return f"{family}, {given}"
    return family or (author.get("name") or "").strip() or None


def _year(message: dict[str, Any]) -> int | None:
    issued = message.get("issued") or {}
    try:
        return int(issued.get("date-parts", [[None]])[0][0])
    except (TypeError, ValueError, IndexError):
        return None


def message_to_item(message: dict[str, Any]) -> Item | None:
    """Map one Crossref `message.items[i]` to a normalized Item. Drops entries with no title and no DOI."""
    if not isinstance(message, dict):
        return None
    title = _first(message.get("title"))
    doi = message.get("DOI")
    if not title and not doi:
        return None
    abstract = abstract_plain_text(message.get("abstract")) if message.get("abstract") else None
    authors = tuple(filter(None, (_author_name(a) for a in (message.get("author") or []))))
    return Item(
        title=title or str(doi),
        sources=("crossref",),
        doi=str(doi).lower() if doi else None,
        abstract=abstract or None,
        authors=authors,
        journal=_first(message.get("container-title")),
        year=_year(message),
        url=_first(message.get("URL")),
    )


class CrossrefSearchProvider:
    name = "crossref"
    label = "Crossref"

    def __init__(self, fetcher: SearchFetcher | None = None, mailto: str | None = None, timeout: float = 15.0) -> None:
        self.fetcher = fetcher or _httpx_search
        self.mailto = mailto if mailto is not None else resolved_mailto("CALLOSUM_CROSSREF_MAILTO")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        ua = f"callosum/1.0 (mailto:{self.mailto})" if self.mailto else "callosum/1.0"
        return {"User-Agent": ua, "Accept": "application/json"}

    def search(self, query: str, limit: int) -> list[Item]:
        q = (query or "").strip()
        if not q:
            return []
        rows = min(max(limit, 1), 50)
        raw = self.fetcher(q, rows, headers=self._headers(), timeout=self.timeout) or []
        items = [it for it in (message_to_item(m) for m in raw) if it is not None]
        return items[:rows]
