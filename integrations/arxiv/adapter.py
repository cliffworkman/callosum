"""arXiv preprint resolver, with DB-backed caching.

Derives the arXiv id from the paper's DOI (``10.48550/arXiv.*``), else a title search, then returns
``https://arxiv.org/pdf/{id}`` as a green/preprint ``OaLocation``. arXiv hosts author-deposited preprints
(green OA by construction). The single id we need is read from the Atom feed with a targeted regex — NOT a
stdlib XML parser, which is exposed to XXE / entity-expansion on this untrusted response (rule #4). Returns
``OaLocation`` or None; never raises.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import httpx
from sqlalchemy import Connection

from app.backend.acquisition.registry import OaLocation, PaperRef
from integrations.api_cache import get_cached, put_cached

ARXIV_PROVIDER = "arxiv"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(.+)$", re.IGNORECASE)
# The entry's <id> is an /abs/ URL; the feed's own <id> is an /api/ URL, so matching /abs/ targets the entry.
_ENTRY_ID_RE = re.compile(r"<id>\s*https?://arxiv\.org/abs/([^<\s]+)", re.IGNORECASE)


class ArxivFetcher(Protocol):
    def __call__(self, params: dict[str, str], *, timeout: float) -> tuple[int, str | None]:
        """Return HTTP status + the raw Atom XML body text for an arXiv API query."""


class ArxivClient:
    def __init__(self, *, fetcher: ArxivFetcher | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout

    def lookup_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        direct = _arxiv_id_from_doi(ref.doi)
        if direct:
            return self._location(direct)  # arXiv DOI carries the id — no network call needed
        if not ref.title:
            return None
        arxiv_id = self._fetch_id_by_title(conn, ref.title.strip())
        return self._location(arxiv_id) if arxiv_id else None

    def _location(self, arxiv_id: str) -> OaLocation | None:
        try:
            return OaLocation(
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}", oa_color="green", version="preprint", source=ARXIV_PROVIDER
            )
        except ValueError:
            return None

    def _fetch_id_by_title(self, conn: Connection, title: str) -> str | None:
        cache_key = "title:" + hashlib.sha256(title.lower().encode("utf-8")).hexdigest()[:24]
        params = {"search_query": f'ti:"{title}"', "max_results": "1"}
        cached = get_cached(conn, ARXIV_PROVIDER, cache_key)
        if cached is not None:
            body = cached["response_json"]
            return body.get("arxiv_id") if isinstance(body, dict) else None
        try:
            status, text = self.fetcher(params, timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(conn, ARXIV_PROVIDER, cache_key, request_json=params, response_json={"error": str(exc)}, status_code=None)
            return None
        arxiv_id = _parse_first_id(text) if status == 200 and text else None
        put_cached(conn, ARXIV_PROVIDER, cache_key, request_json=params, response_json={"arxiv_id": arxiv_id}, status_code=status)
        return arxiv_id


def _arxiv_id_from_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    match = _ARXIV_DOI_RE.match(doi.strip())
    return match.group(1) if match else None


def _httpx_fetcher(params: dict[str, str], *, timeout: float) -> tuple[int, str | None]:
    response = httpx.get(
        ARXIV_API_URL, params=params, headers={"User-Agent": "Callosum/0.1 (local-first reference manager)"}, timeout=timeout
    )
    return response.status_code, response.text


def _parse_first_id(text: str) -> str | None:
    """Extract the first entry's arXiv id from the Atom feed WITHOUT an XML parser — we need only this one
    field, so a targeted regex avoids the stdlib XML XXE / entity-expansion surface on this untrusted response."""
    match = _ENTRY_ID_RE.search(text)
    return match.group(1).strip() if match else None
