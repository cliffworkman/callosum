"""bioRxiv-by-category Feed source (backlog #28 SP2, inc 187). bioRxiv's API is date/category-based (not keyword),
so it belongs in the Feed, not Search. `fetch(category, limit)` pulls recent preprints over a date window and keeps
those in the subscribed category. Constant host; the URL path is server-derived dates (the category is filtered
client-side) → no SSRF. Public metadata; injectable fetcher (hermetic tests). v1: bioRxiv server only (medRxiv later)."""

from __future__ import annotations

import datetime
from typing import Any, Protocol

import httpx

from app.backend.discovery.feed import FeedEntry
from app.backend.discovery.providers import normalized_title

BIORXIV = "https://api.biorxiv.org"

# Common bioRxiv subject categories, surfaced to the Follow UI as a datalist (the value is free text, lowercased).
BIORXIV_CATEGORIES = [
    "neuroscience",
    "bioinformatics",
    "genetics",
    "genomics",
    "microbiology",
    "cell biology",
    "biophysics",
    "evolutionary biology",
    "ecology",
    "bioengineering",
    "developmental biology",
    "immunology",
    "molecular biology",
    "cancer biology",
    "plant biology",
    "systems biology",
    "synthetic biology",
    "physiology",
    "pharmacology and toxicology",
]


class CollectionFetcher(Protocol):
    def __call__(self, window_days: int, max_pages: int, *, timeout: float) -> list[dict[str, Any]]: ...


def _biorxiv_fetch(window_days: int, max_pages: int, *, timeout: float) -> list[dict[str, Any]]:
    """Pull recent bioRxiv detail pages over [today-window, today]. Constant host; dates are server-derived."""
    to = datetime.date.today()
    frm = to - datetime.timedelta(days=window_days)
    out: list[dict[str, Any]] = []
    cursor = 0
    for _ in range(max_pages):
        url = f"{BIORXIV}/details/biorxiv/{frm.isoformat()}/{to.isoformat()}/{cursor}/json"
        resp = httpx.get(url, timeout=timeout)
        if resp.status_code != 200:
            break
        coll = (resp.json() or {}).get("collection") or []
        if not isinstance(coll, list) or not coll:
            break
        out.extend(c for c in coll if isinstance(c, dict))
        cursor += len(coll)
    return out


def record_to_entry(rec: dict[str, Any]) -> FeedEntry | None:
    """Map one bioRxiv collection record → a FeedEntry. Drops entries with no title and no DOI."""
    if not isinstance(rec, dict):
        return None
    doi = (rec.get("doi") or "").strip().lower() or None
    title = (rec.get("title") or "").strip()
    if not title and not doi:
        return None
    authors = tuple(a.strip() for a in str(rec.get("authors") or "").split(";") if a.strip())
    date = (rec.get("date") or "").strip()
    year = int(date[:4]) if date[:4].isdigit() else None
    dedup_key = f"doi:{doi}" if doi else f"title:{normalized_title(title)}"
    return FeedEntry(
        dedup_key=dedup_key,
        title=title or str(doi),
        doi=doi,
        authors=authors,
        journal="bioRxiv",
        year=year,
        url=(f"https://www.biorxiv.org/content/{doi}v1" if doi else None),
        abstract=(rec.get("abstract") or "").strip() or None,
        posted_date=date or None,
    )


class BioRxivFeedSource:
    kind = "biorxiv_category"
    label = "bioRxiv category"
    placeholder = "e.g. neuroscience"
    suggestions = BIORXIV_CATEGORIES

    def __init__(
        self,
        fetcher: CollectionFetcher | None = None,
        window_days: int = 30,
        max_pages: int = 6,
        timeout: float = 20.0,
    ) -> None:
        self.fetcher = fetcher or _biorxiv_fetch
        self.window_days = window_days
        self.max_pages = max_pages
        self.timeout = timeout

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]:
        category = (value or "").strip().lower()
        if not category:
            return []
        raw = self.fetcher(self.window_days, self.max_pages, timeout=self.timeout) or []
        seen: set[str] = set()
        entries: list[FeedEntry] = []
        for rec in raw:
            if (rec.get("category") or "").strip().lower() != category:
                continue
            entry = record_to_entry(rec)
            if entry is None or entry.dedup_key in seen:
                continue  # a preprint with multiple versions appears as multiple rows — keep the first
            seen.add(entry.dedup_key)
            entries.append(entry)
        return entries[:limit]
