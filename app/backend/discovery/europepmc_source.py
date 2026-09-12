"""Europe PMC keyword Feed source (backlog #40, inc 592).

Complements the PubMed keyword source with Europe PMC's broader biomedical index (which also carries preprints
and Agricola/patent records). Contract probed live against the real API (2026-09-12):

* Endpoint ``https://www.ebi.ac.uk/europepmc/webservices/rest/search`` (JSON). Params: ``query`` (the keyword),
  ``format=json``, ``resultType=core`` (returns abstract + DOI + dates + journal), ``sort=P_PDATE_D desc``
  (most-recently-published first), ``pageSize`` (and ``page`` for deeper paging).
* Per ``resultList.result[]``: ``id`` + ``source`` (MED/PMC/PPR/…) form the record's stable identity, ``doi``,
  ``title``, ``authorString`` (comma-separated), ``journalInfo.journal.title``, ``pubYear``,
  ``firstPublicationDate`` (the date we sort/show by), ``abstractText``.
* No auth; light use has no documented rate limit. Constant host; the keyword is a query-string value → no SSRF.

Its own injectable fetcher (hermetic tests); the real fetch is size-capped via ``bounded_get``.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.backend.discovery.feed import FeedEntry
from app.backend.discovery.providers import normalized_title
from integrations.http_bounds import bounded_get

EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_MAX_BYTES = 8_000_000  # a core-result page with abstracts is a few hundred KB; a generous, still-bounded cap.


class EuropePmcFetcher(Protocol):
    def __call__(self, query: str, page_size: int, *, timeout: float) -> list[dict[str, Any]]: ...


def _europepmc_fetch(query: str, page_size: int, *, timeout: float) -> list[dict[str, Any]]:
    """Fetch the most-recently-published core results for ``query``. Constant host; ``query`` is a query-string
    parameter value, never interpolated into the host/path."""
    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "sort": "P_PDATE_D desc",
        "pageSize": page_size,
    }
    resp = bounded_get(EUROPEPMC, max_bytes=_MAX_BYTES, params=params, timeout=timeout)
    if resp.status_code != 200:
        return []
    body = resp.json() if resp.content else {}
    result = (body.get("resultList") or {}).get("result") or []
    return [r for r in result if isinstance(r, dict)]


def record_to_entry(rec: dict[str, Any]) -> FeedEntry | None:
    """Map one Europe PMC core result → a FeedEntry. Drops a record with no title and no doi."""
    if not isinstance(rec, dict):
        return None
    doi = (rec.get("doi") or "").strip().lower() or None
    title = (rec.get("title") or "").strip()
    if not title and not doi:
        return None
    authors = tuple(a.strip() for a in str(rec.get("authorString") or "").split(",") if a.strip())
    journal = ((rec.get("journalInfo") or {}).get("journal") or {}).get("title") or None
    pub_year = rec.get("pubYear")
    year = int(pub_year) if str(pub_year).isdigit() else None
    first_pub = (rec.get("firstPublicationDate") or "").strip() or None
    # Prefer DOI identity; otherwise the {source}:{id} pair (Europe PMC's own stable record key) is unique.
    source = (rec.get("source") or "").strip()
    rec_id = (str(rec.get("id") or "")).strip()
    if doi:
        dedup_key = f"doi:{doi}"
    elif source and rec_id:
        dedup_key = f"epmc:{source}:{rec_id}"
    else:
        dedup_key = f"title:{normalized_title(title)}"
    url = (
        f"https://doi.org/{doi}"
        if doi
        else (f"https://europepmc.org/abstract/{source}/{rec_id}" if source and rec_id else None)
    )
    return FeedEntry(
        dedup_key=dedup_key,
        title=title or str(doi),
        doi=doi,
        authors=authors,
        journal=journal,
        year=year,
        url=url,
        abstract=(rec.get("abstractText") or "").strip() or None,
        posted_date=first_pub,
    )


class EuropePmcFeedSource:
    kind = "europepmc_keyword"
    label = "Europe PMC keyword"
    placeholder = "e.g. hippocampus memory"
    suggestions: list[str] = []
    user_addable = True

    def __init__(self, fetcher: EuropePmcFetcher | None = None, page_size: int = 40, timeout: float = 25.0) -> None:
        self.fetcher = fetcher or _europepmc_fetch
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
