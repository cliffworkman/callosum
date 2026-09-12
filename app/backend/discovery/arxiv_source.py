"""arXiv preprint-by-category Feed source (backlog #40, inc 592).

Like bioRxiv, arXiv's feed is category-based (not keyword), so it belongs in the Feed, not Search. Contract
probed live against the real API (2026-09-12):

* Endpoint ``https://export.arxiv.org/api/query`` (Atom XML). Params: ``search_query=cat:<category>``,
  ``sortBy=submittedDate``, ``sortOrder=descending``, ``start``, ``max_results``.
* Per ``<entry>``: ``<id>`` = the canonical abs URL (``http://arxiv.org/abs/<id>vN``, also the arXiv identifier),
  ``<title>``, ``<published>`` (ISO-8601 Z), one ``<author><name>`` per author, ``<summary>`` (abstract),
  ``<arxiv:primary_category term=...>``, and ``<arxiv:doi>`` **only** if the author linked a published DOI
  (usually absent for a preprint → dedup by the arXiv id, not a DOI).
* Rate limit: arXiv asks for ≤ 1 request / 3 s; a Feed refresh issues one request per subscription, so a single
  poll is well within that. Constant host; only the category (a short token) enters the query → no SSRF.

XML is parsed with ElementTree behind a DOCTYPE/ENTITY guard (the same XXE/entity-expansion defense the GROBID
TEI parser uses), and the body is size-capped via ``bounded_get``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Protocol

from app.backend.discovery.feed import FeedEntry
from app.backend.discovery.providers import normalized_title
from integrations.http_bounds import bounded_get

ARXIV = "https://export.arxiv.org/api/query"
_MAX_BYTES = 4_000_000  # arXiv Atom pages are small; a generous cap that still bounds a pathological response.
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# A datalist of common arXiv categories surfaced to the Follow UI. The value is free text (an arXiv category id
# such as ``cs.AI`` or a top-level archive such as ``q-bio``); these are only suggestions.
ARXIV_CATEGORIES = [
    "cs.AI",
    "cs.LG",
    "cs.CL",
    "cs.CV",
    "cs.NE",
    "stat.ML",
    "q-bio.NC",
    "q-bio.QM",
    "physics.med-ph",
    "eess.SP",
    "math.ST",
    "econ.EM",
]


class ArxivFetcher(Protocol):
    def __call__(self, category: str, max_results: int, *, timeout: float) -> str: ...


def _arxiv_fetch(category: str, max_results: int, *, timeout: float) -> str:
    """Fetch the raw Atom XML for the most recently submitted preprints in ``category``. Constant host; the
    category is sent as the ``search_query`` value (``cat:<category>``), never interpolated into the host/path."""
    params = {
        "search_query": f"cat:{category}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max_results,
    }
    resp = bounded_get(ARXIV, max_bytes=_MAX_BYTES, params=params, timeout=timeout, follow_redirects=True)
    if resp.status_code != 200:
        return ""
    return resp.text


def _safe_parse(xml_text: str) -> ET.Element | None:
    """Parse Atom XML, refusing a DOCTYPE / internal ENTITY before handing it to ElementTree (XXE /
    billion-laughs defense; ElementTree already blocks external entities but not internal expansion). Mirrors
    the GROBID TEI guard: we check the DECODED text (bounded_get returns httpx-decoded ``.text``, which already
    collapses a UTF-16 NUL-interleaved ``<!DOCTYPE`` bypass back to a literal substring) and also reject a NUL,
    which never appears in legitimate Atom. Returns the root element, or None on malformed/rejected input."""
    if not xml_text or "\x00" in xml_text:
        return None
    head = xml_text[:2048].lower()
    if "<!doctype" in head or "<!entity" in head:
        return None
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError:
        return None


def _text(entry: ET.Element, tag: str) -> str:
    node = entry.find(tag)
    return (node.text or "").strip() if node is not None and node.text else ""


def entry_to_feed(entry: ET.Element) -> FeedEntry | None:
    """Map one arXiv Atom ``<entry>`` → a FeedEntry. Drops an entry with no title and no id."""
    abs_url = _text(entry, f"{_ATOM}id")  # e.g. http://arxiv.org/abs/2609.11923v1 — canonical abs URL + id
    title = " ".join(_text(entry, f"{_ATOM}title").split())  # arXiv wraps long titles across lines
    if not title and not abs_url:
        return None
    authors = tuple(
        (name.text or "").strip()
        for author in entry.findall(f"{_ATOM}author")
        for name in author.findall(f"{_ATOM}name")
        if name.text and name.text.strip()
    )
    published = _text(entry, f"{_ATOM}published")  # 2026-09-10T17:58:14Z
    year = int(published[:4]) if published[:4].isdigit() else None
    doi = _text(entry, f"{_ARXIV_NS}doi").lower() or None  # usually absent for a preprint
    # A preprint rarely has a DOI, so dedup by the stable arXiv id (strip the version suffix) when there's none.
    arxiv_id = abs_url.rsplit("/abs/", 1)[-1] if "/abs/" in abs_url else abs_url
    arxiv_id_base = arxiv_id.split("v")[0] if arxiv_id else ""
    dedup_key = (
        f"doi:{doi}" if doi else (f"arxiv:{arxiv_id_base}" if arxiv_id_base else f"title:{normalized_title(title)}")
    )
    abstract = " ".join(_text(entry, f"{_ATOM}summary").split()) or None
    return FeedEntry(
        dedup_key=dedup_key,
        title=title or arxiv_id,
        doi=doi,
        authors=authors,
        journal="arXiv",
        year=year,
        url=abs_url.replace("http://arxiv.org", "https://arxiv.org") or None,
        abstract=abstract,
        posted_date=published or None,
    )


class ArxivFeedSource:
    kind = "arxiv_category"
    label = "arXiv category"
    placeholder = "e.g. cs.AI"
    suggestions = ARXIV_CATEGORIES
    user_addable = True

    def __init__(self, fetcher: ArxivFetcher | None = None, max_results: int = 25, timeout: float = 25.0) -> None:
        # max_results is modest by design: arXiv is markedly slower for large result sets and 429s on bursts, so
        # a Feed poll asks for the newest ~25 in the category (the Feed's own per-source cap is 40). A single
        # per-refresh request stays within arXiv's ~1-req/3s guidance; a 429/timeout returns [] (honest miss),
        # so one throttled arXiv poll never aborts the refresh — the items reappear next refresh.
        self.fetcher = fetcher or _arxiv_fetch
        self.max_results = max_results
        self.timeout = timeout

    def fetch(self, value: str, *, limit: int) -> list[FeedEntry]:
        category = (value or "").strip()
        if not category:
            return []
        root = _safe_parse(self.fetcher(category, self.max_results, timeout=self.timeout) or "")
        if root is None:
            return []
        seen: set[str] = set()
        out: list[FeedEntry] = []
        for entry in root.findall(f"{_ATOM}entry"):
            fe = entry_to_feed(entry)
            if fe is None or fe.dedup_key in seen:
                continue
            seen.add(fe.dedup_key)
            out.append(fe)
        return out[:limit]
