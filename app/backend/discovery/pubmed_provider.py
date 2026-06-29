"""PubMed Search provider (backlog #28 SP1a, inc 186). Queries NCBI **E-utilities** (esearch → esummary) and drops
into the discovery SourceRegistry with **no endpoint/UI change** (the registry's promise). Its own injectable fetcher
(hermetic tests) — separate from the assistant's PubMed MCP (this is the app's own client). Public metadata; the
polite-pool `tool` + `email` params (email from Settings → Metadata access). No egress gate (public-metadata search,
like Crossref) — NOT the Gemini gate. v1 has no abstract (esummary doesn't carry it; efetch is deferred)."""

from __future__ import annotations

import html
import re
from dataclasses import replace
from typing import Any, Protocol

import httpx

from app.backend.app_settings import resolved_mailto
from app.backend.discovery.feed import FeedEntry
from app.backend.discovery.providers import Item, normalized_title

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "callosum"
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
_PMID_RE = re.compile(r"<PMID[^>]*>(\d+)</PMID>")
_ABSTRACT_RE = re.compile(r"<AbstractText[^>]*>(.*?)</AbstractText>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


class SearchFetcher(Protocol):
    def __call__(self, query: str, retmax: int, *, email: str | None, timeout: float) -> list[dict[str, Any]]: ...


def _eutils_search(
    query: str, retmax: int, *, email: str | None, timeout: float, sort: str = "relevance"
) -> list[dict[str, Any]]:
    """esearch (query → PMIDs) then esummary (PMIDs → records). Constant host; the query is a bound *param*. The
    Search provider sorts by relevance; the Feed source passes ``sort="date"`` for newest-first."""
    common: dict[str, Any] = {"db": "pubmed", "retmode": "json", "tool": TOOL}
    if email:
        common["email"] = email
    es_params = {**common, "term": query, "retmax": retmax}
    if sort:
        es_params["sort"] = sort
    es = httpx.get(f"{EUTILS}/esearch.fcgi", params=es_params, timeout=timeout)
    if es.status_code != 200:
        return []
    body = es.json() if es.headers.get("content-type", "").startswith("application/json") else {}
    idlist = (((body or {}).get("esearchresult") or {}).get("idlist")) or []
    ids = [i for i in idlist if isinstance(i, str) and i.isdigit()][:retmax]
    if not ids:
        return []
    su = httpx.get(f"{EUTILS}/esummary.fcgi", params={**common, "id": ",".join(ids)}, timeout=timeout)
    if su.status_code != 200:
        return []
    result = ((su.json() or {}).get("result") or {}) if su.text else {}
    return [result[i] for i in ids if isinstance(result.get(i), dict)]


def _doi(rec: dict[str, Any]) -> str | None:
    for aid in rec.get("articleids") or []:
        if isinstance(aid, dict) and aid.get("idtype") == "doi" and aid.get("value"):
            return str(aid["value"]).strip().lower()
    el = rec.get("elocationid")  # sometimes "doi: 10.x/y"
    if isinstance(el, str):
        m = _DOI_RE.search(el)
        if m:
            return m.group(0).lower()
    return None


def _year(rec: dict[str, Any]) -> int | None:
    m = re.match(r"\s*(\d{4})", str(rec.get("pubdate") or rec.get("epubdate") or ""))
    return int(m.group(1)) if m else None


def _authors(rec: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(a["name"]).strip() for a in (rec.get("authors") or []) if isinstance(a, dict) and a.get("name"))


def _parse_abstracts(xml: str) -> dict[str, str]:
    """Parse efetch PubMed XML → {pmid: abstract}. Targeted regex (NOT an XML parser) → no XXE/entity surface on
    the response (rule #4, the inc-75 arXiv pattern). Joins structured AbstractText sections; strips inline tags."""
    out: dict[str, str] = {}
    for article in xml.split("<PubmedArticle>")[1:]:
        pmid_m = _PMID_RE.search(article)
        chunks = _ABSTRACT_RE.findall(article)
        if not pmid_m or not chunks:
            continue
        text = html.unescape(_TAG_RE.sub("", " ".join(chunks))).strip()
        if text:
            out[pmid_m.group(1)] = text
    return out


class AbstractFetcher(Protocol):
    def __call__(self, pmids: list[str], *, email: str | None, timeout: float) -> dict[str, str]: ...


def fetch_abstracts(pmids: list[str], *, email: str | None, timeout: float) -> dict[str, str]:
    """efetch the abstracts for a set of PMIDs (one batched call). Constant host; ids are digit-validated PMIDs as a
    bound param → no SSRF. Fail-closed (non-200 → {}); abstracts are a nicety, never load-bearing."""
    ids = [p for p in pmids if isinstance(p, str) and p.isdigit()]
    if not ids:
        return {}
    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(ids),
        "rettype": "abstract",
        "retmode": "xml",
        "tool": TOOL,
    }
    if email:
        params["email"] = email
    resp = httpx.get(f"{EUTILS}/efetch.fcgi", params=params, timeout=timeout)
    if resp.status_code != 200 or not resp.text:
        return {}
    return _parse_abstracts(resp.text)


def summary_to_item(rec: dict[str, Any]) -> Item | None:
    """Map one esummary record → a normalized Item. Drops entries with no title and no DOI."""
    if not isinstance(rec, dict):
        return None
    title = (rec.get("title") or "").strip().rstrip(".")
    pmid = str(rec.get("uid") or "").strip() or None
    doi = _doi(rec)
    if not title and not doi:
        return None
    journal = (rec.get("fulljournalname") or rec.get("source") or "").strip() or None
    return Item(
        title=title or str(doi or pmid),
        sources=("pubmed",),
        doi=doi,
        pmid=pmid,
        authors=_authors(rec),
        journal=journal,
        year=_year(rec),
        url=(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None),
    )


class PubMedSearchProvider:
    name = "pubmed"

    def __init__(self, fetcher: SearchFetcher | None = None, email: str | None = None, timeout: float = 15.0) -> None:
        self.fetcher = fetcher or _eutils_search
        self.email = email if email is not None else resolved_mailto("CALLOSUM_CROSSREF_MAILTO")
        self.timeout = timeout

    def search(self, query: str, limit: int) -> list[Item]:
        q = (query or "").strip()
        if not q:
            return []
        retmax = min(max(limit, 1), 50)
        raw = self.fetcher(q, retmax, email=self.email, timeout=self.timeout) or []
        items = [it for it in (summary_to_item(r) for r in raw) if it is not None]
        return items[:retmax]


def record_to_feed_entry(rec: dict[str, Any]) -> FeedEntry | None:
    """Map one esummary record → a FeedEntry (the Feed's stored subset). Newest-first ordering uses posted_date."""
    if not isinstance(rec, dict):
        return None
    title = (rec.get("title") or "").strip().rstrip(".")
    pmid = str(rec.get("uid") or "").strip() or None
    doi = _doi(rec)
    if not title and not doi:
        return None
    dedup_key = f"doi:{doi}" if doi else (f"pmid:{pmid}" if pmid else f"title:{normalized_title(title)}")
    pubdate = str(rec.get("sortpubdate") or rec.get("pubdate") or rec.get("epubdate") or "").strip()
    return FeedEntry(
        dedup_key=dedup_key,
        title=title or str(doi or pmid),
        doi=doi,
        authors=_authors(rec),
        journal=(rec.get("fulljournalname") or rec.get("source") or "").strip() or None,
        year=_year(rec),
        url=(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None),
        posted_date=(pubdate.split(" ")[0] or None),  # sortpubdate is "YYYY/MM/DD HH:MM"
    )


class PubMedKeywordFeedSource:
    """A saved PubMed query as a Feed source (SP2c, inc 189). Polls esearch sorted by date → recent matches."""

    kind = "pubmed_query"
    label = "PubMed search"
    placeholder = "a PubMed query, e.g. CRISPR off-target"
    suggestions: list[str] = []

    def __init__(
        self,
        fetcher: SearchFetcher | None = None,
        email: str | None = None,
        timeout: float = 15.0,
        abstract_fetcher: AbstractFetcher | None = None,
    ) -> None:
        self.fetcher = fetcher or _eutils_search
        self.abstract_fetcher = abstract_fetcher or fetch_abstracts  # efetch enrichment (SP2c-3); injectable for tests
        self.email = email if email is not None else resolved_mailto("CALLOSUM_CROSSREF_MAILTO")
        self.timeout = timeout

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]:
        q = (value or "").strip()
        if not q:
            return []
        retmax = min(max(limit, 1), 50)
        raw = self.fetcher(q, retmax, email=self.email, timeout=self.timeout, sort="date") or []
        pmids = [str(r.get("uid")) for r in raw if r.get("uid")]
        try:
            abstracts = self.abstract_fetcher(pmids, email=self.email, timeout=self.timeout) if pmids else {}
        except Exception:  # noqa: BLE001 — abstracts are a nicety; a failed efetch never sinks the poll
            abstracts = {}
        seen: set[str] = set()
        out: list[FeedEntry] = []
        for rec in raw:
            entry = record_to_feed_entry(rec)
            if entry is None or entry.dedup_key in seen:
                continue
            seen.add(entry.dedup_key)
            uid = str(rec.get("uid") or "")
            if uid in abstracts and not entry.abstract:
                entry = replace(entry, abstract=abstracts[uid])
            out.append(entry)
        return out[:retmax]
