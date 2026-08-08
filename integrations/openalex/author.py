"""OpenAlex author resolution + works fetch for My Publications (inc 78), with DB-backed caching.

Mirrors the inc-74 OA-location adapter + the Crossref pattern (injectable fetcher Protocol, `external_api_cache`,
fail-closed, frozen dataclasses, polite-pool `CALLOSUM_OPENALEX_MAILTO`). This is **metadata egress** (public
identifiers — name/ORCID/DOIs — like the Crossref DOI lookup), NOT the Gemini library-text egress gate, and it
is **LLM-free**. Returns dataclasses or None; never raises to the caller.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection, Engine

from app.backend.app_settings import resolved_mailto
from integrations.api_cache import get_cached, put_cached, put_cached_committing

OPENALEX_ROOT = "https://api.openalex.org"
OPENALEX_AUTHOR_PROVIDER = "openalex_author"
OPENALEX_WORKS_PROVIDER = "openalex_works"
_WORKS_PER_PAGE = 200
_MAX_WORKS_PAGES = 5  # cap a prolific author at ~1000 works
_MAX_CITING = 100  # inc 119 (SP3): cap the citing-works list (a highly-cited paper can have thousands of citers)


@dataclass(frozen=True)
class ResolvedAuthor:
    author_id: str  # the bare OpenAlex id, e.g. "A5023888391"
    display_name: str
    orcid: str | None
    works_count: int
    matched_by: str  # "orcid" (high confidence) or "name" (lower confidence)
    # inc 81 — the dashboard's headline metrics (parsed from the same author object; defaults keep existing
    # construction sites + test fixtures valid). These are OpenAlex's authoritative figures, shown verbatim.
    cited_by_count: int = 0
    h_index: int = 0
    i10_index: int = 0
    counts_by_year: tuple[dict[str, int], ...] = ()  # [{"year", "works_count", "cited_by_count"}, …]
    # inc 117 (My-Pubs SP1) — extra OpenAlex facts for the dashboard's OpenAlex card, shown verbatim + attributed.
    two_year_mean_citedness: float = 0.0  # summary_stats["2yr_mean_citedness"]
    affiliation: str | None = None  # last-known institution display name


@dataclass(frozen=True)
class AuthorWork:
    doi: str | None  # normalized: "10.xxxx/yyyy" lower-case (no https://doi.org/ prefix)
    title: str | None
    year: int | None
    cited_by_count: int = (
        0  # inc 83 — per-work OpenAlex citations, for impact-by-domain (default keeps old caches valid)
    )
    openalex_work_id: str | None = None  # inc 119 (SP3): the bare OpenAlex work id (e.g. "W9"), for the cited-by fetch
    publication_date: str | None = None  # inc 458 (backlog #28): OpenAlex's real "YYYY-MM-DD" when available --
    # day-level precision for Feed sorting, beyond the bare `year`. Default keeps old caches (pre-458) valid.


@dataclass(frozen=True)
class CitingWork:
    """inc 119 (SP3): a work that CITES one of the user's papers (a discovery candidate, per OpenAlex)."""

    doi: str | None
    title: str | None
    year: int | None
    cited_by_count: int = 0
    authors: tuple[str, ...] = ()


class AuthorFetcher(Protocol):
    def __call__(
        self, url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a GET to an absolute OpenAlex URL."""


class OpenAlexAuthorClient:
    def __init__(
        self,
        *,
        fetcher: AuthorFetcher | None = None,
        mailto: str | None = None,
        timeout: float = 10.0,
        cache_engine: Engine | None = None,
    ) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.mailto = mailto or resolved_mailto("CALLOSUM_OPENALEX_MAILTO")  # UI contact email overlays the env var
        self.timeout = timeout
        self.cache_engine = cache_engine  # inc D: when set, cache writes self-commit (fetch-outside-lock jobs)

    def with_cache_engine(self, engine: Engine) -> OpenAlexAuthorClient:
        """A copy whose cache writes self-commit in their own transaction (inc D) — for a fetch-outside-lock job."""
        return OpenAlexAuthorClient(fetcher=self.fetcher, mailto=self.mailto, timeout=self.timeout, cache_engine=engine)

    def _put(self, conn: Connection, provider: str, key: str, **cache_fields: Any) -> None:
        """Cache a response — self-committing (own txn) when cache_engine is set, else via the caller's conn."""
        if self.cache_engine is not None:
            put_cached_committing(self.cache_engine, provider, key, **cache_fields)
        else:
            put_cached(conn, provider, key, **cache_fields)

    def resolve_author(
        self, conn: Connection, *, orcid: str | None = None, name: str | None = None
    ) -> ResolvedAuthor | None:
        """ORCID-first (exact match, ``matched_by="orcid"``). If OpenAlex has no ORCID-linked record for it — a
        real, common gap when an author's OpenAlex profile predates or was never linked to their ORCID iD, not
        a Callosum bug — falls back to a name search rather than reporting no match, as long as a name is also
        on file. The fallback is honestly lower-confidence (``matched_by="name"``): never silently equated with
        an exact ORCID match (see ``ResolvedAuthor.matched_by``, surfaced to the user)."""
        if orcid and orcid.strip():
            author = self._fetch_by_orcid(conn, orcid)
            if author is not None:
                return author
        if name and name.strip():
            return self._fetch_by_name(conn, name)
        return None

    def _fetch_by_orcid(self, conn: Connection, orcid: str) -> ResolvedAuthor | None:
        key = _orcid_cache_key(orcid)
        body = self._fetch(conn, OPENALEX_AUTHOR_PROVIDER, key, f"{OPENALEX_ROOT}/authors/orcid:{orcid.strip()}", {})
        return _author_from_obj(_pick_author(body), matched_by="orcid") if body is not None else None

    def _fetch_by_name(self, conn: Connection, name: str) -> ResolvedAuthor | None:
        key = _name_cache_key(name)
        url = f"{OPENALEX_ROOT}/authors"
        params = {"filter": f"display_name.search:{name.strip()}", "per-page": "1"}
        body = self._fetch(conn, OPENALEX_AUTHOR_PROVIDER, key, url, params)
        return _author_from_obj(_pick_author(body), matched_by="name") if body is not None else None

    def cached_author(
        self, conn: Connection, *, orcid: str | None = None, name: str | None = None
    ) -> ResolvedAuthor | None:
        """Cache-only author lookup (inc 81) — return the enriched author from cache, or None; NEVER fetches.
        The dashboard uses this so opening it makes ZERO egress (the resolve that set ``openalex_author_id``
        already warmed this cache under the same key). Mirrors ``resolve_author``'s ORCID-first-then-name-
        fallback order so a name-fallback match resolved earlier is still found on a later cache-only read."""
        if orcid and orcid.strip():
            author = self._cached_by_key(conn, _orcid_cache_key(orcid), matched_by="orcid")
            if author is not None:
                return author
        if name and name.strip():
            return self._cached_by_key(conn, _name_cache_key(name), matched_by="name")
        return None

    def _cached_by_key(self, conn: Connection, key: str, *, matched_by: str) -> ResolvedAuthor | None:
        cached = get_cached(conn, OPENALEX_AUTHOR_PROVIDER, key)
        if cached is None or int(cached["status_code"] or 0) != 200 or not isinstance(cached["response_json"], dict):
            return None
        return _author_from_obj(_pick_author(cached["response_json"]), matched_by=matched_by)

    def fetch_author_works(self, conn: Connection, author_id: str, *, refresh: bool = False) -> list[AuthorWork]:
        if not refresh:  # refresh=True bypasses + re-caches, so an old cache (no cited_by_count) upgrades (inc 83)
            cached = get_cached(conn, OPENALEX_WORKS_PROVIDER, author_id)
            if cached is not None and isinstance(cached["response_json"], dict):
                works = cached["response_json"].get("works")
                if isinstance(works, list):
                    return [
                        AuthorWork(
                            doi=w.get("doi"),
                            title=w.get("title"),
                            year=w.get("year"),
                            cited_by_count=int(w.get("cited_by_count") or 0),
                            openalex_work_id=w.get("openalex_work_id"),  # inc 119: carry the id from a refreshed cache
                            publication_date=w.get("publication_date"),  # inc 458: absent on pre-458 caches -> None
                        )
                        for w in works
                    ]
        works, ok = self._fetch_all_works(author_id)
        if ok:  # only cache a real result — never cache a transient total failure
            self._put(
                conn,
                OPENALEX_WORKS_PROVIDER,
                author_id,
                request_json={"author_id": author_id},
                response_json={"works": [asdict(w) for w in works]},
                status_code=200,
            )
        return works

    def _fetch(self, conn, provider, key, url, params) -> dict[str, Any] | None:
        cached = get_cached(conn, provider, key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return cached["response_json"] if status == 200 and isinstance(cached["response_json"], dict) else None
        try:
            status, body = self.fetcher(
                url, params={**params, **self._polite()}, headers=self._headers(), timeout=self.timeout
            )
        except Exception as exc:  # fail closed
            self._put(
                conn, provider, key, request_json={"url": url}, response_json={"error": str(exc)}, status_code=None
            )
            return None
        self._put(conn, provider, key, request_json={"url": url}, response_json=body, status_code=status)
        return body if status == 200 and isinstance(body, dict) else None

    def _fetch_all_works(self, author_id: str) -> tuple[list[AuthorWork], bool]:
        works: list[AuthorWork] = []
        any_ok = False
        cursor: str | None = "*"
        for _ in range(_MAX_WORKS_PAGES):
            params = {
                "filter": f"author.id:{author_id}",
                "per-page": str(_WORKS_PER_PAGE),
                "cursor": cursor or "*",
                "select": "id,doi,title,publication_year,publication_date,cited_by_count",
            }
            try:
                status, body = self.fetcher(
                    f"{OPENALEX_ROOT}/works",
                    params={**params, **self._polite()},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except Exception:
                break
            if status != 200 or not isinstance(body, dict):
                break
            any_ok = True
            for work in body.get("results") or []:
                parsed = _work_from_obj(work)
                if parsed is not None:
                    works.append(parsed)
            cursor = (body.get("meta") or {}).get("next_cursor")
            if not cursor:
                break
        return works, any_ok

    def fetch_citing_works(self, conn: Connection, work_id: str) -> tuple[list[CitingWork], bool]:
        """inc 119 (SP3): works that CITE the given OpenAlex work, cached under ``citing:<work_id>`` and capped at
        ``_MAX_CITING``. Returns (works, capped). Fail-closed; validates the work id; on-demand (caller-gated)."""
        if not re.fullmatch(r"W\d+", work_id or ""):
            return [], False
        cache_key = f"citing:{work_id}"
        cached = get_cached(conn, OPENALEX_WORKS_PROVIDER, cache_key)
        if cached is not None and isinstance(cached["response_json"], dict):
            raw = cached["response_json"].get("works")
            if isinstance(raw, list):
                return [_citing_from_dict(w) for w in raw], bool(cached["response_json"].get("capped"))
        works, capped, ok = self._fetch_citing(work_id)
        if ok:  # only cache a real result
            self._put(
                conn,
                OPENALEX_WORKS_PROVIDER,
                cache_key,
                request_json={"cites": work_id},
                response_json={"works": [asdict(w) for w in works], "capped": capped},
                status_code=200,
            )
        return works, capped

    def _fetch_citing(self, work_id: str) -> tuple[list[CitingWork], bool, bool]:
        works: list[CitingWork] = []
        any_ok = False
        capped = False
        cursor: str | None = "*"
        for _ in range(_MAX_WORKS_PAGES):
            params = {
                "filter": f"cites:{work_id}",
                "per-page": str(_WORKS_PER_PAGE),
                "cursor": cursor or "*",
                "select": "id,doi,title,publication_year,cited_by_count,authorships",
            }
            try:
                status, body = self.fetcher(
                    f"{OPENALEX_ROOT}/works",
                    params={**params, **self._polite()},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except Exception:
                break
            if status != 200 or not isinstance(body, dict):
                break
            any_ok = True
            for work in body.get("results") or []:
                works.append(_citing_from_obj(work))
                if len(works) >= _MAX_CITING:
                    capped = True
                    break
            if capped:
                break
            cursor = (body.get("meta") or {}).get("next_cursor")
            if not cursor:
                break
        return works[:_MAX_CITING], capped, any_ok

    def _polite(self) -> dict[str, str]:
        return {"mailto": self.mailto} if self.mailto else {}

    def _headers(self) -> dict[str, str]:
        ua = "Callosum/0.1 (local-first reference manager)"
        if self.mailto:
            ua = f"{ua}; mailto:{self.mailto}"
        return {"User-Agent": ua, "Accept": "application/json"}


def _httpx_fetcher(
    url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, Any] | None]:
    response = httpx.get(url, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _orcid_cache_key(orcid: str) -> str:
    return "orcid:" + orcid.strip().lower()


def _name_cache_key(name: str) -> str:
    return "name:" + hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()[:24]


def _pick_author(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    if isinstance(body.get("results"), list):  # the name-filter endpoint
        return body["results"][0] if body["results"] else None
    return body if body.get("id") else None  # the by-id (orcid) endpoint returns the author object


def _author_from_obj(obj: dict[str, Any] | None, *, matched_by: str) -> ResolvedAuthor | None:
    if not isinstance(obj, dict):
        return None
    raw_id = str(obj.get("id") or "")
    author_id = raw_id.rsplit("/", 1)[-1] if raw_id else ""
    if not author_id:
        return None
    stats = obj.get("summary_stats") if isinstance(obj.get("summary_stats"), dict) else {}
    counts = []
    for row in obj.get("counts_by_year") or []:
        if isinstance(row, dict) and isinstance(row.get("year"), int):
            counts.append(
                {
                    "year": int(row["year"]),
                    "works_count": int(row.get("works_count") or 0),
                    "cited_by_count": int(row.get("cited_by_count") or 0),
                }
            )
    return ResolvedAuthor(
        author_id=author_id,
        display_name=str(obj.get("display_name") or ""),
        orcid=_normalize_orcid(obj.get("orcid")),
        works_count=int(obj.get("works_count") or 0),
        matched_by=matched_by,
        cited_by_count=int(obj.get("cited_by_count") or 0),
        h_index=int(stats.get("h_index") or 0),
        i10_index=int(stats.get("i10_index") or 0),
        counts_by_year=tuple(sorted(counts, key=lambda c: c["year"])),
        two_year_mean_citedness=float(stats.get("2yr_mean_citedness") or 0.0),
        affiliation=(
            (obj.get("last_known_institutions") or [{}])[0].get("display_name")
            if obj.get("last_known_institutions")
            else None
        ),
    )


def _work_from_obj(work: dict[str, Any]) -> AuthorWork | None:
    if not isinstance(work, dict):
        return None
    doi = _normalize_doi(work.get("doi") or (work.get("ids") or {}).get("doi"))
    title = work.get("title") or work.get("display_name")
    year = work.get("publication_year")
    raw_id = str(work.get("id") or "")
    return AuthorWork(
        doi=doi,
        title=str(title) if title else None,
        year=int(year) if isinstance(year, int) else None,
        cited_by_count=int(work.get("cited_by_count") or 0),
        openalex_work_id=(raw_id.rsplit("/", 1)[-1] if raw_id else None),
        publication_date=_normalize_publication_date(work.get("publication_date")),
    )


def _citing_from_obj(work: dict[str, Any]) -> CitingWork:
    """inc 119 (SP3): parse an OpenAlex /works result into a CitingWork (≤8 author names from authorships)."""
    authors = tuple(
        str((a.get("author") or {}).get("display_name") or "").strip()
        for a in (work.get("authorships") or [])
        if isinstance(a, dict) and (a.get("author") or {}).get("display_name")
    )[:8]
    year = work.get("publication_year")
    title = work.get("title") or work.get("display_name")
    return CitingWork(
        doi=_normalize_doi(work.get("doi") or (work.get("ids") or {}).get("doi")),
        title=str(title) if title else None,
        year=int(year) if isinstance(year, int) else None,
        cited_by_count=int(work.get("cited_by_count") or 0),
        authors=authors,
    )


def _citing_from_dict(w: dict[str, Any]) -> CitingWork:
    """Reconstruct a CitingWork from its cached ``asdict`` form."""
    return CitingWork(
        doi=w.get("doi"),
        title=w.get("title"),
        year=w.get("year"),
        cited_by_count=int(w.get("cited_by_count") or 0),
        authors=tuple(w.get("authors") or ()),
    )


def _normalize_doi(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi or None


def _normalize_publication_date(value: Any) -> str | None:
    """inc 458: OpenAlex's `publication_date` is normally a real "YYYY-MM-DD" -- validated at this untrusted-input
    boundary (rule #4) rather than trusted verbatim, so a malformed value never reaches Feed's `posted_date`
    ordering as an unvalidated string."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    return value.strip()


def _normalize_orcid(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    orcid = value.strip()
    for prefix in ("https://orcid.org/", "http://orcid.org/"):
        if orcid.startswith(prefix):
            orcid = orcid[len(prefix) :]
    return orcid or None
