"""PsyArXiv preprint Feed source via the OSF preprints API (backlog #40, inc 592).

PsyArXiv is hosted on OSF, so this queries OSF's public JSON:API. Contract probed live against the real API
(2026-09-12):

* Endpoint ``https://api.osf.io/v2/preprints/`` (JSON:API). Params: ``filter[provider]=psyarxiv``,
  ``filter[title]=<keyword>`` (a whole-provider value-less feed doesn't fit the value-based Follow picker, so a
  PsyArXiv subscription is a **title keyword** — follow new PsyArXiv preprints about your topic, consistent with
  the PubMed/Europe PMC keyword sources), ``sort=-date_published`` (newest first), ``page[size]``,
  ``embed=contributors`` (so author names arrive in the SAME request — no N+1: authors are otherwise a
  *relationship*, which was the awkwardness to avoid).
* Per ``data[]``: ``attributes.title``, ``attributes.date_published`` (ISO datetime), ``attributes.description``
  (abstract), ``attributes.doi`` (**often null** for a preprint → dedup by the OSF guid instead), and the guid
  from ``links.self`` (``.../preprints/<guid>/`` — a ``_vN`` version suffix is stripped) → the public preprint
  page ``https://osf.io/<guid>/``. Authors come from the deeply-nested
  ``embeds.contributors.data[].embeds.users.data.attributes.full_name`` — parsed **defensively** (an
  unregistered or embed-less contributor is skipped, never a crash; authors are an optional FeedEntry field).
* No auth; OSF rate-limits anonymous callers, so a Feed refresh issues ONE request per poll. Constant host;
  only the fixed provider filter + paging enter the query → no SSRF.

Its own injectable fetcher (hermetic tests); the real fetch is size-capped via ``bounded_get``.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.backend.discovery.feed import FeedEntry
from app.backend.discovery.providers import normalized_title
from integrations.http_bounds import bounded_get

OSF_PREPRINTS = "https://api.osf.io/v2/preprints/"
_MAX_BYTES = 8_000_000  # a page of embedded-contributor preprints is a few hundred KB; generous but bounded.
_PROVIDER = "psyarxiv"


class OsfFetcher(Protocol):
    def __call__(self, query: str, page_size: int, *, timeout: float) -> list[dict[str, Any]]: ...


def _osf_fetch(query: str, page_size: int, *, timeout: float) -> list[dict[str, Any]]:
    """Fetch the newest PsyArXiv preprints whose title matches ``query`` (contributors embedded). Constant host;
    the fixed provider filter + the keyword (a query-string value) + paging vary → no user input in host/path."""
    params = {
        "filter[provider]": _PROVIDER,
        "filter[title]": query,
        "sort": "-date_published",
        "page[size]": page_size,
        "embed": "contributors",
    }
    resp = bounded_get(OSF_PREPRINTS, max_bytes=_MAX_BYTES, params=params, timeout=timeout)
    if resp.status_code != 200:
        return []
    body = resp.json() if resp.content else {}
    data = body.get("data") or []
    return [d for d in data if isinstance(d, dict)]


def _guid_from_self(self_link: str) -> str:
    """``https://api.osf.io/v2/preprints/m2jf8_v2/`` → ``m2jf8`` (strip trailing slash + a ``_vN`` version)."""
    if not self_link:
        return ""
    guid = self_link.rstrip("/").rsplit("/", 1)[-1]
    return guid.split("_")[0] if "_" in guid else guid


def _authors(rec: dict[str, Any]) -> tuple[str, ...]:
    """Defensively pull author full names from the embedded contributors. Any missing/oddly-shaped node is
    skipped rather than raising — authors are an optional FeedEntry field."""
    contributors = (((rec.get("embeds") or {}).get("contributors") or {}).get("data")) or []
    names: list[str] = []
    for c in contributors:
        if not isinstance(c, dict):
            continue
        user = (((c.get("embeds") or {}).get("users") or {}).get("data")) or {}
        full = ((user.get("attributes") or {}) if isinstance(user, dict) else {}).get("full_name")
        if isinstance(full, str) and full.strip():
            names.append(full.strip())
    return tuple(names)


def record_to_entry(rec: dict[str, Any]) -> FeedEntry | None:
    """Map one OSF preprint record → a FeedEntry. Drops a record with no title and no guid/doi."""
    if not isinstance(rec, dict):
        return None
    attrs = rec.get("attributes") or {}
    title = (attrs.get("title") or "").strip()
    doi = (attrs.get("doi") or "").strip().lower() or None
    guid = _guid_from_self((rec.get("links") or {}).get("self") or "")
    if not title and not doi and not guid:
        return None
    date_published = (attrs.get("date_published") or "").strip() or None
    year = int(date_published[:4]) if date_published and date_published[:4].isdigit() else None
    # A PsyArXiv preprint's DOI is frequently null, so the OSF guid is the stable identity.
    dedup_key = f"doi:{doi}" if doi else (f"osf:{guid}" if guid else f"title:{normalized_title(title)}")
    return FeedEntry(
        dedup_key=dedup_key,
        title=title or (doi or guid),
        doi=doi,
        authors=_authors(rec),
        journal="PsyArXiv",
        year=year,
        url=(f"https://osf.io/{guid}/" if guid else (f"https://doi.org/{doi}" if doi else None)),
        abstract=(attrs.get("description") or "").strip() or None,
        posted_date=date_published,
    )


class PsyArxivFeedSource:
    kind = "psyarxiv"
    label = "PsyArXiv keyword"
    placeholder = "e.g. working memory"
    suggestions: list[str] = []
    user_addable = True

    def __init__(self, fetcher: OsfFetcher | None = None, page_size: int = 40, timeout: float = 25.0) -> None:
        self.fetcher = fetcher or _osf_fetch
        self.page_size = page_size
        self.timeout = timeout

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]:
        query = (value or "").strip()
        if not query:
            return []
        raw = self.fetcher(query, self.page_size, timeout=self.timeout) or []
        seen: set[str] = set()
        out: list[FeedEntry] = []
        for rec in raw:
            fe = record_to_entry(rec)
            if fe is None or fe.dedup_key in seen:
                continue
            seen.add(fe.dedup_key)
            out.append(fe)
        return out[:limit]
