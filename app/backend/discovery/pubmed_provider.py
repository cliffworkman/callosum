"""PubMed Search provider (backlog #28 SP1a, inc 186). Queries NCBI **E-utilities** (esearch → esummary) and drops
into the discovery SourceRegistry with **no endpoint/UI change** (the registry's promise). Its own injectable fetcher
(hermetic tests) — separate from the assistant's PubMed MCP (this is the app's own client). Public metadata; the
polite-pool `tool` + `email` params (email from Settings → Metadata access). No egress gate (public-metadata search,
like Crossref) — NOT the Gemini gate. v1 has no abstract (esummary doesn't carry it; efetch is deferred)."""

from __future__ import annotations

import re
from typing import Any, Protocol

import httpx

from app.backend.app_settings import resolved_mailto
from app.backend.discovery.providers import Item

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "callosum"
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")


class SearchFetcher(Protocol):
    def __call__(self, query: str, retmax: int, *, email: str | None, timeout: float) -> list[dict[str, Any]]: ...


def _eutils_search(query: str, retmax: int, *, email: str | None, timeout: float) -> list[dict[str, Any]]:
    """esearch (query → PMIDs) then esummary (PMIDs → records). Constant host; the query is a bound *param*."""
    common: dict[str, Any] = {"db": "pubmed", "retmode": "json", "tool": TOOL}
    if email:
        common["email"] = email
    es = httpx.get(f"{EUTILS}/esearch.fcgi", params={**common, "term": query, "retmax": retmax}, timeout=timeout)
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
