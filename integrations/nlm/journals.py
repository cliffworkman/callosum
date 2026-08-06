"""NLM/MEDLINE indexing status client for the PUBLISHERS "where to submit" tool (backlog #40).

A live per-ISSN lookup against NCBI's free, no-key **E-utilities** ``esearch`` endpoint
(``db=nlmcatalog``) -- mirrors ``integrations/scielo/journals.py``'s shape (ISSN validated
``^\\d{4}-\\d{3}[\\dX]$`` before any request; injectable ``fetcher``; cached via
``integrations.api_cache``; fail-closed, never raises), but returns a plain ``bool``: there are no
sub-fields worth carrying (unlike SciELO's collections/title/country), and a malformed ISSN, a
well-formed-but-unindexed ISSN, and a network error all legitimately collapse to "not (confirmed)
currently indexed" -- confirmed live against the real API, including a real journal that WAS indexed
2009-2013 and has since been "Deselected" (this client deliberately does not distinguish "never
indexed" from "no longer indexed" -- a simple binary signal, not a richer status like AJOL's).

**Checks MEDLINE specifically, not "PubMed" broadly -- a real distinction, caught live before ship.**
NLM's own catalog record treats "MEDLINE" and "PubMed" as separate ``IndexingSourceName`` values with
independent status: a journal can be "Currently-indexed" for PubMed while carrying no MEDLINE entry at
all (confirmed live for *World Psychiatry* -- a major, unambiguously legitimate journal -- whose real
NLM Catalog record has a "Currently-indexed" PubMed source and NO MEDLINE source whatsoever). The
``currentlyindexed[all]`` query term used here empirically tracks MEDLINE status specifically (verified
against three real journals: two MEDLINE-indexed hits, and World Psychiatry's confirmed miss) -- so this
client, its cache provider, and every caller name the signal **"MEDLINE indexing,"** never "PubMed,"
to avoid overclaiming a check this query does not actually perform. Broader raw-PubMed presence
(including PubMed-only, non-MEDLINE-curated content) is out of scope.

The ``currentlyindexed[all]`` search-field term does the indexing-status filtering server-side in one
call (``count > 0`` = yes), avoiding a second ``efetch`` per candidate and avoiding a real ambiguity
found live: some ISSNs resolve to more than one NLM catalog record (an old vs. current incarnation of
the same title), so picking the first ``esearch`` id blind can read a live journal as "ceased." The
combined ISSN+filter query sidesteps that by asking NCBI to resolve it, never picking a record id
ourselves.

Reuses the exact ``EUTILS``/``TOOL``/``CALLOSUM_CROSSREF_MAILTO`` convention already established by
``app/backend/discovery/pubmed_provider.py`` for the same NCBI E-utilities family, rather than
inventing a second one.

**Self-paced, not API-keyed.** Confirmed live: NCBI enforces ~3 requests/second without a key (real
429s reproduced after 4 rapid requests). A PUBLISHERS run makes one live call per candidate (bounded by
``MAX_CANDIDATES``) with no batching, same as SciELO -- a 429 tail would silently misreport "not
indexed" for real journals, which is a correctness problem, not just a slowdown. Rather than add a new
optional API-key env var (config surface most users would never set up, so it wouldn't protect the
default case), the client paces its own live calls to stay under the unauthenticated ceiling.
"""

from __future__ import annotations

import re
import time
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.app_settings import resolved_mailto
from integrations.api_cache import get_cached, put_cached

NLM_PROVIDER = "nlm-medline-index"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "callosum"
_MIN_REQUEST_INTERVAL = 0.35  # seconds; keeps live calls under NCBI's unauthenticated ~3 req/s ceiling

_ISSN_RE = re.compile(r"\d{4}-\d{3}[\dX]", re.IGNORECASE)


class NlmMedlineFetcher(Protocol):
    def __call__(self, issn: str, *, params: dict[str, str], timeout: float) -> tuple[int, Any]:
        """Return HTTP status + parsed JSON body for an NLM Catalog esearch MEDLINE-indexing lookup."""


class NlmJournalsClient:
    def __init__(self, *, fetcher: NlmMedlineFetcher | None = None, timeout: float = 10.0):
        self.fetcher = fetcher or _httpx_fetcher
        self.timeout = timeout
        self.email = resolved_mailto("CALLOSUM_CROSSREF_MAILTO")
        self._last_request_at: float | None = None

    def fetch_medline_indexed(self, conn: Connection, issn: str) -> bool:
        """Whether `issn` is currently MEDLINE-indexed per the NLM Catalog. Fail-closed -> False."""
        issn = (issn or "").strip().upper()
        if not _ISSN_RE.fullmatch(issn):
            return False
        cache_key = f"journal:{issn}"
        cached = get_cached(conn, NLM_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return _is_indexed(cached["response_json"]) if status == 200 else False
        self._pace()
        try:
            status, body = self.fetcher(issn, params=self._params(issn), timeout=self.timeout)
        except Exception as exc:  # fail closed
            put_cached(
                conn,
                NLM_PROVIDER,
                cache_key,
                request_json={"issn": issn},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return False
        put_cached(
            conn,
            NLM_PROVIDER,
            cache_key,
            request_json={"issn": issn},
            response_json=body if isinstance(body, dict) else None,
            status_code=status,
        )
        return _is_indexed(body) if status == 200 else False

    def _params(self, issn: str) -> dict[str, str]:
        params = {
            "db": "nlmcatalog",
            "term": f"{issn}[issn] AND currentlyindexed[all]",
            "retmode": "json",
            "tool": TOOL,
        }
        if self.email:
            params["email"] = self.email
        return params

    def _pace(self) -> None:
        """Sleep the remainder of `_MIN_REQUEST_INTERVAL` since the last live call, if any -- only called on a
        cache miss, right before firing a real request."""
        if self._last_request_at is not None:
            remaining = _MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()


def _is_indexed(body: Any) -> bool:
    try:
        return int(body["esearchresult"]["count"]) > 0
    except (TypeError, ValueError, KeyError):
        return False


def _httpx_fetcher(issn: str, *, params: dict[str, str], timeout: float) -> tuple[int, Any]:
    response = httpx.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
