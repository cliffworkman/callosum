"""OpenAlex *sources* (journals) client for the PUBLISHERS "where to submit" tool (inc TBD, backlog #40).

Distinct from `adapter.py` (a DOI→work OA resolver): this reads OpenAlex **journal** metadata for candidate
journals, and derives a candidate pool from a *topic* — never from the abstract (the abstract is embedded locally
by the caller; only topic ids / a subject keyword / source ids leave the machine). Three read paths:

- ``fetch_topic_for_subject`` — resolve a user-typed subject keyword → an OpenAlex topic id (``/topics?search=``).
- ``fetch_candidate_sources`` — the journals a topic's recent works appear in, ranked by frequency (``/works``).
- ``fetch_source_details`` — per-journal facts (OA flags, APC, open impact, homepage) for a batch of source ids
  (``/sources?filter=openalex_id:``).
- ``fetch_topic_works`` — a topic's works with citation counts + reconstructed abstracts (the candidate pool for
  the OVERLOOKED-WORK lens, backlog #37); abstracts are embedded on-device by the caller, never transmitted.

Every id is validated (``^T\\d+$`` / ``^S\\d+$``) **before** any request (no SSRF); the subject is a bound query
param, never the host. Injectable ``fetcher`` (a fake in tests); cached via ``integrations.api_cache``; fail-closed
(any error → cached error row → None/[], never raises). Polite-pool ``mailto`` via ``resolved_mailto``.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import Connection, Engine

from app.backend.app_settings import resolved_mailto
from integrations.api_cache import get_cached, put_cached, put_cached_committing
from integrations.http_bounds import METADATA_RESPONSE_CAP, bounded_get

OPENALEX_SOURCES_PROVIDER = "openalex-sources"
OPENALEX_API_BASE = "https://api.openalex.org"  # root — this client hits /topics, /works, /sources
WORKS_SAMPLE = 200  # works read to rank a topic's journals by frequency
MAX_CANDIDATES = 60  # cap on distinct candidate journals profiled (rule #4)
MAX_BYIDS = 50  # OpenAlex OR-filter limit for one /sources?filter=openalex_id: batch

_TOPIC_RE = re.compile(r"T\d+")
_SOURCE_RE = re.compile(r"S\d+")
_WORK_RE = re.compile(r"W\d+")


@dataclass(frozen=True)
class SourceStub:
    """A candidate journal from a topic's works — id + display name + how often it appeared (the ranking key)."""

    source_id: str  # bare `S…`
    display_name: str | None
    issn_l: str | None
    count: int


@dataclass(frozen=True)
class TopicWork:
    """A work under a topic — id + metadata + a locally-reconstructed abstract (the overlooked-lens candidate).
    Identity-agnostic by construction: no author/identity field (the lens measures the *work's* attention vs.
    relevance, never who wrote it)."""

    openalex_work_id: str  # bare `W…`
    doi: str | None
    title: str | None
    year: int | None
    cited_by_count: int
    abstract: str | None


@dataclass(frozen=True)
class SourceMeta:
    """Per-journal facts from OpenAlex `/sources` (the profile inputs; DOAJ enriches the OA-specific fields)."""

    source_id: str
    display_name: str | None
    issns: list[str] = field(default_factory=list)
    issn_l: str | None = None
    is_oa: bool = False
    is_in_doaj: bool = False
    apc_usd: int | None = None
    two_year_mean_citedness: float | None = None
    h_index: int | None = None
    works_count: int | None = None
    homepage_url: str | None = None
    concepts: list[str] = field(default_factory=list)
    type: str | None = None


class SourcesFetcher(Protocol):
    def __call__(
        self, path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a GET to OPENALEX_API_BASE + path."""


class OpenAlexSourcesClient:
    def __init__(
        self,
        *,
        fetcher: SourcesFetcher | None = None,
        mailto: str | None = None,
        timeout: float = 10.0,
        cache_engine: Engine | None = None,
    ):
        self.fetcher = fetcher or _httpx_fetcher
        self.mailto = mailto or resolved_mailto("CALLOSUM_OPENALEX_MAILTO")
        self.timeout = timeout
        self.cache_engine = cache_engine

    def with_cache_engine(self, engine: Engine) -> OpenAlexSourcesClient:
        """A copy that caches responses self-committingly (inc D fetch-outside-lock) — used by an async job so the
        write lock is not held across network I/O; reads stay conn-based."""
        return OpenAlexSourcesClient(
            fetcher=self.fetcher, mailto=self.mailto, timeout=self.timeout, cache_engine=engine
        )

    def fetch_topic_for_subject(self, conn: Connection, subject: str) -> str | None:
        """Resolve a user-typed subject keyword → the top-matching OpenAlex topic id. The subject is a bound query
        param (never the host). Fail-closed → None."""
        subject = (subject or "").strip()
        if not subject:
            return None
        cache_key = "topicsearch:" + subject.lower()
        body = self._get(conn, "/topics", {"search": subject, "per-page": "1"}, cache_key, {"subject": subject})
        results = (body or {}).get("results") if isinstance(body, dict) else None
        if not results:
            return None
        tid = str((results[0] or {}).get("id") or "").rsplit("/", 1)[-1]
        return tid if _TOPIC_RE.fullmatch(tid) else None

    def fetch_candidate_sources(
        self, conn: Connection, topic_id: str, *, cap: int = MAX_CANDIDATES
    ) -> list[SourceStub]:
        """The journals a topic's recent works appear in, ranked by frequency (the topic's dominant venues).
        `topic_id` validated `^T\\d+$` before any request. Fail-closed → []."""
        if not _TOPIC_RE.fullmatch(topic_id or ""):
            return []
        cap = max(1, min(int(cap), MAX_CANDIDATES))
        cache_key = f"srcpool:{topic_id}"
        body = self._get(
            conn,
            "/works",
            {"filter": f"primary_topic.id:{topic_id}", "per-page": str(WORKS_SAMPLE), "select": "primary_location"},
            cache_key,
            {"topic_id": topic_id},
        )
        works = (body or {}).get("results") if isinstance(body, dict) else None
        if not isinstance(works, list):
            return []
        counts: Counter[str] = Counter()
        meta: dict[str, tuple[str | None, str | None]] = {}
        for work in works:
            src = ((work or {}).get("primary_location") or {}).get("source") if isinstance(work, dict) else None
            if not isinstance(src, dict):
                continue
            sid = str(src.get("id") or "").rsplit("/", 1)[-1]
            if not _SOURCE_RE.fullmatch(sid):
                continue
            counts[sid] += 1
            meta.setdefault(sid, (src.get("display_name"), src.get("issn_l")))
        return [
            SourceStub(source_id=sid, display_name=meta[sid][0], issn_l=meta[sid][1], count=n)
            for sid, n in counts.most_common(cap)
        ]

    def fetch_topic_works(self, conn: Connection, topic_id: str, *, cap: int = WORKS_SAMPLE) -> list[TopicWork]:
        """Works whose primary topic is ``topic_id``, with citation counts + reconstructed abstracts — the candidate
        pool for the overlooked-work lens (backlog #37). ``topic_id`` validated ``^T\\d+$`` before any request;
        bounded (``cap`` ≤ WORKS_SAMPLE), cached, fail-closed → []. Only the topic id egresses; abstracts are
        reconstructed from the inverted index and embedded on-device by the caller."""
        if not _TOPIC_RE.fullmatch(topic_id or ""):
            return []
        cap = max(1, min(int(cap), WORKS_SAMPLE))
        body = self._get(
            conn,
            "/works",
            {
                "filter": f"primary_topic.id:{topic_id}",
                "per-page": str(cap),
                "select": "id,doi,title,publication_year,cited_by_count,abstract_inverted_index",
            },
            f"topicworks:{topic_id}",
            {"topic_id": topic_id},
        )
        results = (body or {}).get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            return []
        out: list[TopicWork] = []
        for work in results:
            if not isinstance(work, dict):
                continue
            wid = str(work.get("id") or "").rsplit("/", 1)[-1]
            if not _WORK_RE.fullmatch(wid):
                continue
            doi = work.get("doi")
            doi = str(doi).replace("https://doi.org/", "").lower() if doi else None
            year = work.get("publication_year")
            out.append(
                TopicWork(
                    openalex_work_id=wid,
                    doi=doi,
                    title=str(work.get("title")) if work.get("title") else None,
                    year=year if isinstance(year, int) else None,
                    cited_by_count=int(work.get("cited_by_count") or 0),
                    abstract=_abstract_from_inverted_index(work.get("abstract_inverted_index")),
                )
            )
        return out

    def fetch_source_details(self, conn: Connection, source_ids: list[str]) -> dict[str, SourceMeta]:
        """Per-journal facts for a batch of source ids (`/sources?filter=openalex_id:S1|S2|…`, ≤MAX_BYIDS/call).
        Each id validated `^S\\d+$` before the request. Returns {source_id: SourceMeta}; fail-closed → {}."""
        valid = [s for s in (source_ids or []) if _SOURCE_RE.fullmatch(s or "")]
        out: dict[str, SourceMeta] = {}
        for i in range(0, len(valid), MAX_BYIDS):
            chunk = valid[i : i + MAX_BYIDS]
            cache_key = "srcdetail:" + hashlib.sha256("|".join(sorted(chunk)).encode("utf-8")).hexdigest()[:24]
            body = self._get(
                conn,
                "/sources",
                {"filter": "openalex_id:" + "|".join(chunk), "per-page": str(len(chunk))},
                cache_key,
                {"ids": chunk},
            )
            for src in (body or {}).get("results") or [] if isinstance(body, dict) else []:
                m = _source_meta(src)
                if m is not None:
                    out[m.source_id] = m
        return out

    def _get(
        self, conn: Connection, path: str, params: dict[str, str], cache_key: str, request_json: dict[str, Any]
    ) -> dict[str, Any] | None:
        cached = get_cached(conn, OPENALEX_SOURCES_PROVIDER, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            body = cached["response_json"]
            return body if status == 200 and isinstance(body, dict) else None
        try:
            status, body = self.fetcher(
                path, params={**params, **self._polite_params()}, headers=self._headers(), timeout=self.timeout
            )
        except Exception as exc:  # fail closed — never raise to the caller
            self._store(conn, cache_key, request_json=request_json, response_json={"error": str(exc)}, status_code=None)
            return None
        self._store(conn, cache_key, request_json=request_json, response_json=body, status_code=status)
        return body if status == 200 and isinstance(body, dict) else None

    def _store(self, conn: Connection, cache_key: str, *, request_json: Any, response_json: Any, status_code) -> None:
        """Cache a response: self-committingly (its own transaction) when ``cache_engine`` is set — the inc-D
        fetch-outside-lock path — else via the caller's ``conn`` (the default, per-request path)."""
        fields = {"request_json": request_json, "response_json": response_json, "status_code": status_code}
        if self.cache_engine is not None:
            put_cached_committing(self.cache_engine, OPENALEX_SOURCES_PROVIDER, cache_key, **fields)
        else:
            put_cached(conn, OPENALEX_SOURCES_PROVIDER, cache_key, **fields)

    def _polite_params(self) -> dict[str, str]:
        return {"mailto": self.mailto} if self.mailto else {}

    def _headers(self) -> dict[str, str]:
        user_agent = "Callosum/0.1 (local-first reference manager)"
        if self.mailto:
            user_agent = f"{user_agent}; mailto:{self.mailto}"
        return {"User-Agent": user_agent, "Accept": "application/json"}


def _abstract_from_inverted_index(index: Any) -> str | None:
    """Reconstruct plain abstract text from OpenAlex's ``{word: [positions]}`` inverted index; None if absent/empty."""
    if not isinstance(index, dict) or not index:
        return None
    positions: list[tuple[int, str]] = []
    for word, where in index.items():
        if isinstance(where, list):
            positions.extend((p, str(word)) for p in where if isinstance(p, int))
    if not positions:
        return None
    return " ".join(word for _p, word in sorted(positions))


def _source_meta(src: Any) -> SourceMeta | None:
    if not isinstance(src, dict):
        return None
    sid = str(src.get("id") or "").rsplit("/", 1)[-1]
    if not _SOURCE_RE.fullmatch(sid):
        return None
    stats = src.get("summary_stats") if isinstance(src.get("summary_stats"), dict) else {}
    issns = [str(x) for x in (src.get("issn") or []) if isinstance(x, str)]
    concepts = [
        str(c.get("display_name"))
        for c in (src.get("x_concepts") or [])[:8]
        if isinstance(c, dict) and c.get("display_name")
    ]
    apc = src.get("apc_usd")
    two_yr = stats.get("2yr_mean_citedness")
    h_index = stats.get("h_index")
    return SourceMeta(
        source_id=sid,
        display_name=str(src.get("display_name")) if src.get("display_name") else None,
        issns=issns,
        issn_l=str(src.get("issn_l")) if src.get("issn_l") else None,
        is_oa=bool(src.get("is_oa")),
        is_in_doaj=bool(src.get("is_in_doaj")),
        apc_usd=int(apc) if isinstance(apc, int) else None,
        two_year_mean_citedness=float(two_yr) if isinstance(two_yr, (int, float)) else None,
        h_index=int(h_index) if isinstance(h_index, int) else None,
        works_count=int(src.get("works_count")) if isinstance(src.get("works_count"), int) else None,
        homepage_url=str(src.get("homepage_url")) if src.get("homepage_url") else None,
        concepts=concepts,
        type=str(src.get("type")) if src.get("type") else None,
    )


def _httpx_fetcher(
    path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, Any] | None]:
    response = bounded_get(
        OPENALEX_API_BASE + path, max_bytes=METADATA_RESPONSE_CAP, params=params, headers=headers, timeout=timeout
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body
