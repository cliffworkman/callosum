"""Journal-by-ISSN Feed source (backlog #28 SP2c-2, inc 190). Follow a journal by its ISSN → its recent articles via
Crossref `/works?filter=issn:…&sort=published&order=desc`. Reuses the **already-audited** Crossref host; the ISSN is
**validated** then passed as a bound `filter` param (no SSRF). Public metadata; injectable fetcher (hermetic tests).
Drops into the FeedRegistry — no endpoint/UI change (the Follow picker is data-driven)."""

from __future__ import annotations

import re
from typing import Any, Protocol

import httpx

from app.backend.app_settings import resolved_mailto
from app.backend.discovery.crossref_provider import message_to_item
from app.backend.discovery.feed import FeedEntry

CROSSREF_WORKS = "https://api.crossref.org/works"
_SELECT = "DOI,title,abstract,author,container-title,issued,published,URL"
_ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dX]$")  # standard ISSN form, e.g. 1476-4687 / 0028-0836


class JournalFetcher(Protocol):
    def __call__(self, issn: str, rows: int, *, mailto: str | None, timeout: float) -> list[dict[str, Any]]: ...


def _crossref_journal_fetch(issn: str, rows: int, *, mailto: str | None, timeout: float) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": f"callosum/1.0 (mailto:{mailto})" if mailto else "callosum/1.0",
        "Accept": "application/json",
    }
    resp = httpx.get(
        CROSSREF_WORKS,
        params={"filter": f"issn:{issn}", "sort": "published", "order": "desc", "rows": rows, "select": _SELECT},
        headers=headers,
        timeout=timeout,
    )
    if resp.status_code != 200:
        return []
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    message = body.get("message") if isinstance(body, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    return items if isinstance(items, list) else []


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
    """Map one Crossref work → a FeedEntry (reuses the audited `message_to_item` + adds the publication date)."""
    item = message_to_item(message)  # handles title/doi/authors/journal/year/url/abstract + drops no-title-and-no-DOI
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


class JournalIssnFeedSource:
    kind = "journal_issn"
    label = "Journal (ISSN)"
    placeholder = "a journal ISSN, e.g. 1476-4687"
    suggestions: list[str] = []

    def __init__(self, fetcher: JournalFetcher | None = None, mailto: str | None = None, timeout: float = 15.0) -> None:
        self.fetcher = fetcher or _crossref_journal_fetch
        self.mailto = mailto if mailto is not None else resolved_mailto("CALLOSUM_CROSSREF_MAILTO")
        self.timeout = timeout

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]:
        issn = (value or "").strip().upper()
        if not _ISSN_RE.match(issn):  # validate the ISSN before any fetch → no junk reaches the Crossref filter
            return []
        rows = min(max(limit, 1), 50)
        raw = self.fetcher(issn, rows, mailto=self.mailto, timeout=self.timeout) or []
        seen: set[str] = set()
        out: list[FeedEntry] = []
        for entry in (record_to_feed_entry(m) for m in raw):
            if entry is None or entry.dedup_key in seen:
                continue
            seen.add(entry.dedup_key)
            out.append(entry)
        return out[:rows]
