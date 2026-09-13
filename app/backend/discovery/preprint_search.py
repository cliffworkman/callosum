"""Discovery Search providers for the preprint/database sources that expose a real free-text search API
(GitHub #77): **arXiv**, **Europe PMC**, and **PsyArXiv**.

These are distinct from the same-named *Feed* sources (which fetch recent items by category/keyword and return
``FeedEntry``): a discovery ``SourceProvider`` must implement ``search(query, limit) -> list[Item]`` for the
ad-hoc Discover → Search pipeline (fan-out + dedup + ``in_library`` marking). Each provider reuses the Feed
source's already-audited HTTP + parse and maps the result into the canonical ``Item`` (identity/dedup follow the
existing ``Item.dedup_key`` policy — provider is never a quality signal).

* **arXiv** — the Feed uses ``search_query=cat:<category>`` (a category feed, NOT search); search here issues
  ``search_query=all:<query>`` (free-text, relevance-ordered), reusing arXiv's Atom parse.
* **Europe PMC** / **PsyArXiv** — their Feed fetchers ALREADY issue a keyword/title search, so those are reused
  directly (parse unchanged).

bioRxiv/medRxiv are deliberately NOT here: their integration is a date-window category pull with no free-text
search API, and Crossref already indexes bioRxiv/medRxiv preprints in Search.

Latency note (LATENCY.md §11): ``SourceRegistry.search_all`` fans out **serially**, so "All sources" now issues
five sequential external calls. Each provider uses a bounded, interactive-friendly timeout so one slow source
cannot dominate; the fan-out is NOT parallelized here (arXiv ~1 req/3s and OSF rate-limit + result-ordering
determinism make casual concurrency inadvisable per §11 — it stays a measured future candidate). Choosing a
single source keeps a search fast.
"""

from __future__ import annotations

from app.backend.discovery.arxiv_source import _MAX_BYTES as _ARXIV_MAX_BYTES
from app.backend.discovery.arxiv_source import ARXIV, _safe_parse
from app.backend.discovery.arxiv_source import entry_to_feed as _arxiv_entry_to_feed
from app.backend.discovery.europepmc_source import _europepmc_fetch
from app.backend.discovery.europepmc_source import record_to_entry as _epmc_record_to_entry
from app.backend.discovery.feed import FeedEntry
from app.backend.discovery.providers import Item
from app.backend.discovery.psyarxiv_source import _osf_fetch
from app.backend.discovery.psyarxiv_source import record_to_entry as _osf_record_to_entry
from integrations.http_bounds import bounded_get

_ATOM = "{http://www.w3.org/2005/Atom}"
_SEARCH_TIMEOUT = 10.0  # interactive fan-out: bound one slow source so it can't dominate the serial search_all


def _feed_entry_to_item(fe: FeedEntry, source: str) -> Item:
    """Map a FeedEntry (the Feed sources' normalized record) into a discovery ``Item``. ``Item.dedup_key`` is
    recomputed from doi→pmid→title, so a DOI-less preprint dedups by normalized title against other providers —
    the existing cross-provider identity policy, unchanged."""
    return Item(
        title=fe.title,
        sources=(source,),
        doi=fe.doi,
        abstract=fe.abstract,
        authors=fe.authors,
        journal=fe.journal,
        year=fe.year,
        url=fe.url,
    )


def _dedup_items(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    out: list[Item] = []
    for item in items:
        if item.dedup_key in seen:
            continue
        seen.add(item.dedup_key)
        out.append(item)
    return out


# --- arXiv (free-text search; the Feed's cat: fetch is category-only, so search needs its own all: fetch) ------


def _arxiv_search_fetch(query: str, max_results: int, *, timeout: float) -> str:
    """Fetch raw Atom XML for a free-text arXiv search. Constant host; the query is a ``search_query`` value
    (``all:<query>``), never interpolated into the host/path. Relevance order (no ``sortBy``)."""
    params = {"search_query": f"all:{query}", "start": 0, "max_results": max_results}
    resp = bounded_get(ARXIV, max_bytes=_ARXIV_MAX_BYTES, params=params, timeout=timeout, follow_redirects=True)
    return resp.text if resp.status_code == 200 else ""


class ArxivSearchProvider:
    name = "arxiv"
    label = "arXiv"

    def __init__(self, fetcher=None, timeout: float = _SEARCH_TIMEOUT) -> None:
        self.fetcher = fetcher or _arxiv_search_fetch
        self.timeout = timeout

    def search(self, query: str, limit: int) -> list[Item]:
        q = (query or "").strip()
        if not q:
            return []
        rows = min(max(limit, 1), 50)
        root = _safe_parse(self.fetcher(q, rows, timeout=self.timeout) or "")
        if root is None:
            return []
        items = [
            _feed_entry_to_item(fe, self.name)
            for entry in root.findall(f"{_ATOM}entry")
            if (fe := _arxiv_entry_to_feed(entry)) is not None
        ]
        return _dedup_items(items)[:rows]


# --- Europe PMC / PsyArXiv (their Feed fetchers already ARE keyword/title searches — reused directly) ----------


class EuropePmcSearchProvider:
    name = "europepmc"
    label = "Europe PMC"

    def __init__(self, fetcher=None, timeout: float = _SEARCH_TIMEOUT) -> None:
        self.fetcher = fetcher or _europepmc_fetch
        self.timeout = timeout

    def search(self, query: str, limit: int) -> list[Item]:
        q = (query or "").strip()
        if not q:
            return []
        rows = min(max(limit, 1), 50)
        raw = self.fetcher(q, rows, timeout=self.timeout) or []
        items = [_feed_entry_to_item(fe, self.name) for rec in raw if (fe := _epmc_record_to_entry(rec)) is not None]
        return _dedup_items(items)[:rows]


class PsyArxivSearchProvider:
    name = "psyarxiv"
    label = "PsyArXiv"

    def __init__(self, fetcher=None, timeout: float = _SEARCH_TIMEOUT) -> None:
        self.fetcher = fetcher or _osf_fetch
        self.timeout = timeout

    def search(self, query: str, limit: int) -> list[Item]:
        q = (query or "").strip()
        if not q:
            return []
        rows = min(max(limit, 1), 50)
        raw = self.fetcher(q, rows, timeout=self.timeout) or []
        items = [_feed_entry_to_item(fe, self.name) for rec in raw if (fe := _osf_record_to_entry(rec)) is not None]
        return _dedup_items(items)[:rows]
