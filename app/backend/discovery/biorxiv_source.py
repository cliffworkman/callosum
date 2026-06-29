"""Preprint-by-category Feed source — bioRxiv (inc 187) + medRxiv (SP2c-3, inc 191). The API is date/category-based
(not keyword), so it belongs in the Feed, not Search. `fetch(category, limit)` pulls recent preprints over a date
window and keeps those in the subscribed category. Constant host; the URL path is the server name + server-derived
dates (the category is filtered client-side) → no SSRF. Public metadata; injectable fetcher (hermetic tests). One
class, instantiated per server (`server="biorxiv"|"medrxiv"`) → kinds `biorxiv_category` / `medrxiv_category`."""

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

# medRxiv's subject categories are clinical (distinct from bioRxiv's); surfaced to the Follow UI as a datalist.
MEDRXIV_CATEGORIES = [
    "infectious diseases",
    "epidemiology",
    "public and global health",
    "psychiatry and clinical psychology",
    "genetic and genomic medicine",
    "neurology",
    "oncology",
    "cardiovascular medicine",
    "health informatics",
    "pediatrics",
    "respiratory medicine",
    "endocrinology",
    "obstetrics and gynecology",
    "health policy",
    "intensive care and critical care medicine",
    "primary care research",
    "radiology and imaging",
]


class CollectionFetcher(Protocol):
    def __call__(self, window_days: int, max_pages: int, *, timeout: float) -> list[dict[str, Any]]: ...


def _biorxiv_fetch(
    window_days: int, max_pages: int, *, timeout: float, server: str = "biorxiv"
) -> list[dict[str, Any]]:
    """Pull recent detail pages over [today-window, today] from the given server. Constant host; the server name is
    a fixed literal ("biorxiv"/"medrxiv") and the dates are server-derived → no user input in the URL."""
    to = datetime.date.today()
    frm = to - datetime.timedelta(days=window_days)
    out: list[dict[str, Any]] = []
    cursor = 0
    for _ in range(max_pages):
        url = f"{BIORXIV}/details/{server}/{frm.isoformat()}/{to.isoformat()}/{cursor}/json"
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
    # The record's `server` field distinguishes bioRxiv vs medRxiv (journal label + the content URL host).
    server = (rec.get("server") or "biorxiv").strip().lower()
    journal = "medRxiv" if server == "medrxiv" else "bioRxiv"
    host = "www.medrxiv.org" if server == "medrxiv" else "www.biorxiv.org"
    return FeedEntry(
        dedup_key=dedup_key,
        title=title or str(doi),
        doi=doi,
        authors=authors,
        journal=journal,
        year=year,
        url=(f"https://{host}/content/{doi}v1" if doi else None),
        abstract=(rec.get("abstract") or "").strip() or None,
        posted_date=date or None,
    )


class BioRxivFeedSource:
    placeholder = "e.g. neuroscience"

    def __init__(
        self,
        server: str = "biorxiv",
        fetcher: CollectionFetcher | None = None,
        window_days: int = 30,
        max_pages: int = 6,
        timeout: float = 20.0,
    ) -> None:
        # Per-server instance metadata (one class → biorxiv + medrxiv); the Follow picker reads these via source_meta.
        self.server = server
        self.kind = f"{server}_category"
        self.label = ("bioRxiv" if server == "biorxiv" else "medRxiv") + " category"
        self.suggestions = BIORXIV_CATEGORIES if server == "biorxiv" else MEDRXIV_CATEGORIES
        # The default fetcher bakes in the server (keeps the CollectionFetcher signature stable for injected fakes).
        self.fetcher = fetcher or (lambda wd, mp, *, timeout: _biorxiv_fetch(wd, mp, timeout=timeout, server=server))
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
