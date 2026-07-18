"""Journal-by-title Feed source (inc 295). Follow a journal by its **title** → its recent articles via Crossref.

Resolve the title → the journal's ISSN (Crossref ``/journals?query=…``, top match), then fetch its recent works
(``/works?filter=issn:…&sort=published&order=desc``) for an *exact* list; fall back to a fuzzy
``/works?query.container-title=…`` when no ISSN matches. Reuses the **already-audited** Crossref host + the audited
``crossref_provider.message_to_item``; the title is passed as a **URL-encoded query param** (no SSRF), length-capped,
egress only on Refresh (the feed's opt-in polling). Injectable fetcher/lookup → hermetic tests. Drops into the
FeedRegistry — no endpoint/UI change (the Follow picker is data-driven). Replaces the earlier journal-by-ISSN source.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.backend.app_settings import resolved_mailto
from app.backend.discovery.crossref_provider import message_to_item
from app.backend.discovery.feed import FeedEntry

CROSSREF_WORKS = "https://api.crossref.org/works"
CROSSREF_JOURNALS = "https://api.crossref.org/journals"
_SELECT = "DOI,title,abstract,author,container-title,issued,published,URL"
MAX_TITLE_CHARS = 300


class WorksFetcher(Protocol):
    def __call__(self, params: dict[str, Any], *, mailto: str | None, timeout: float) -> list[dict[str, Any]]: ...


class IssnLookup(Protocol):
    def __call__(self, title: str, *, mailto: str | None, timeout: float) -> str | None: ...


def _headers(mailto: str | None) -> dict[str, str]:
    return {
        "User-Agent": f"callosum/1.0 (mailto:{mailto})" if mailto else "callosum/1.0",
        "Accept": "application/json",
    }


def _crossref_get_items(
    url: str, params: dict[str, Any], *, mailto: str | None, timeout: float
) -> list[dict[str, Any]]:
    resp = httpx.get(url, params=params, headers=_headers(mailto), timeout=timeout)
    if resp.status_code != 200:
        return []
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    message = body.get("message") if isinstance(body, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    return items if isinstance(items, list) else []


def _crossref_works_fetch(params: dict[str, Any], *, mailto: str | None, timeout: float) -> list[dict[str, Any]]:
    return _crossref_get_items(CROSSREF_WORKS, {**params, "select": _SELECT}, mailto=mailto, timeout=timeout)


def _crossref_issn_lookup(title: str, *, mailto: str | None, timeout: float) -> str | None:
    """Resolve a journal title → its ISSN via Crossref ``/journals?query=…`` (top match), or None."""
    items = _crossref_get_items(CROSSREF_JOURNALS, {"query": title, "rows": 1}, mailto=mailto, timeout=timeout)
    issns = items[0].get("ISSN") if items and isinstance(items[0], dict) else None
    return str(issns[0]) if isinstance(issns, list) and issns else None


def _published_date(message: dict[str, Any]) -> str | None:
    """The article's publication date as ``YYYY-MM-DD`` (or ``YYYY``) from the first available date field."""
    for key in ("published", "published-online", "published-print", "issued"):
        parts = ((message.get(key) or {}).get("date-parts") or [[]])[0]
        nums = [int(p) for p in parts if isinstance(p, int)]
        if nums:
            out = [str(nums[0])] + [f"{n:02d}" for n in nums[1:3]]
            return "-".join(out)
    return None


def record_to_feed_entry(message: dict[str, Any]) -> FeedEntry | None:
    """Map one Crossref work → a FeedEntry (reuses the audited ``message_to_item`` + adds the publication date)."""
    item = message_to_item(message)  # title/doi/authors/journal/year/url/abstract + drops no-title-and-no-DOI
    if item is None:
        return None
    return FeedEntry(
        dedup_key=item.dedup_key,
        title=item.title,
        doi=item.doi,
        authors=item.authors,
        journal=item.journal,
        year=item.year,
        url=item.url,
        abstract=item.abstract,
        posted_date=_published_date(message),
    )


class JournalTitleFeedSource:
    kind = "journal"
    label = "Journal"
    placeholder = "a journal title, e.g. Nature Neuroscience"
    suggestions: list[str] = []  # the Follow datalist is filled client-side from the user's own library journals

    def __init__(
        self,
        works_fetcher: WorksFetcher | None = None,
        issn_lookup: IssnLookup | None = None,
        mailto: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.works_fetcher = works_fetcher or _crossref_works_fetch
        self.issn_lookup = issn_lookup or _crossref_issn_lookup
        self.mailto = mailto if mailto is not None else resolved_mailto("CALLOSUM_CROSSREF_MAILTO")
        self.timeout = timeout

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]:
        title = (value or "").strip()
        if not title or len(title) > MAX_TITLE_CHARS:  # validate before any fetch → no junk reaches Crossref
            return []
        rows = min(max(limit, 1), 50)
        issn = self.issn_lookup(title, mailto=self.mailto, timeout=self.timeout)
        if issn:  # exact: the journal's ISSN-filtered recent works
            params = {"filter": f"issn:{issn}", "sort": "published", "order": "desc", "rows": rows}
        else:  # no ISSN match → a fuzzy container-title works query
            params = {"query.container-title": title, "sort": "published", "order": "desc", "rows": rows}
        raw = self.works_fetcher(params, mailto=self.mailto, timeout=self.timeout) or []
        seen: set[str] = set()
        out: list[FeedEntry] = []
        for entry in (record_to_feed_entry(m) for m in raw):
            if entry is None or entry.dedup_key in seen:
                continue
            seen.add(entry.dedup_key)
            out.append(entry)
        return out[:rows]
