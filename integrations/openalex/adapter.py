"""OpenAlex open-access location resolver with database-backed caching (mirrors the Crossref adapter).

OpenAlex aggregates rights-holder-authorized OA locations (gold/green/bronze) across publishers and
repositories. We read *its* OA judgment — `open_access.oa_status` + the OA-location records — and never
make our own. Returns an `OaLocation` (the acquisition seam's only currency) or None; never raises.
Polite-pool `mailto` comes from `CALLOSUM_OPENALEX_MAILTO` (env / gitignored `.env`).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import Connection, insert, select, update

from app.backend.acquisition.registry import OaColor, OaLocation, OaVersion, PaperRef
from app.backend.app_settings import resolved_mailto
from app.backend.persistence.schema import external_api_cache

OPENALEX_PROVIDER = "openalex"
OPENALEX_BASE_URL = "https://api.openalex.org/works"
MAX_REFERENCED = 500  # cap on referenced-work ids read per paper (inc 135; bound the gap-finder fetches)
MAX_CITING = 200  # cap on citing works read per paper (inc 137 forward gap; bound + a documented coverage limit)
MAX_RELATED = 50  # cap on related-work ids read per paper (inc 228 overlooked-work; OpenAlex returns ~10–25)
MAX_BYIDS = 50  # cap on ids fetched in one batch `?filter=openalex_id:` call (inc 228; OpenAlex's OR-filter limit)

# OpenAlex `oa_status` → our OA color. "closed" (and anything unknown) → None = no authorized OA copy.
_OA_STATUS_TO_COLOR: dict[str, OaColor] = {
    "gold": "gold",
    "hybrid": "gold",
    "diamond": "gold",
    "green": "green",
    "bronze": "bronze",
}
# OpenAlex location `version` → our version label.
_VERSION_MAP: dict[str, OaVersion] = {
    "publishedVersion": "vor",
    "acceptedVersion": "am",
    "submittedVersion": "preprint",
}
# When a location omits `version`, infer an honest default from the OA color.
_DEFAULT_VERSION_BY_COLOR: dict[OaColor, OaVersion] = {"gold": "vor", "bronze": "vor", "green": "am"}


class OpenAlexFetcher(Protocol):
    def __call__(
        self, path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status + parsed JSON for a GET to OPENALEX_BASE_URL + path."""


class OpenAlexClient:
    def __init__(
        self,
        *,
        fetcher: OpenAlexFetcher | None = None,
        mailto: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.mailto = mailto or resolved_mailto("CALLOSUM_OPENALEX_MAILTO")  # UI contact email overlays the env var
        self.timeout = timeout

    def lookup_best_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        """Resolve a paper to the best authorized open-access PDF location OpenAlex knows, or None."""
        work = self._fetch_work(conn, ref)
        if work is None:
            return None
        return _best_oa_location_from_work(work)

    def fetch_referenced_works(self, conn: Connection, ref: PaperRef) -> list[str]:
        """The OpenAlex work ids a paper CITES (inc 135 gap-finder) — `referenced_works`, bare `W…` ids, capped.
        Reuses the cached DOI→work fetch; fail-closed (no work / no field → [])."""
        work = self._fetch_work(conn, ref)
        if not isinstance(work, dict):
            return []
        out: list[str] = []
        for url in work.get("referenced_works") or []:
            if not isinstance(url, str):
                continue
            wid = url.rsplit("/", 1)[-1]
            if re.fullmatch(r"W\d+", wid):
                out.append(wid)
            if len(out) >= MAX_REFERENCED:
                break
        return out

    def fetch_work_meta(self, conn: Connection, work_id: str) -> dict[str, Any] | None:
        """Metadata for one OpenAlex work by its `W…` id (inc 135) — for a gap candidate's title/DOI/authors.
        Validated, cached (`work:<id>`), fail-closed → None."""
        if not re.fullmatch(r"W\d+", work_id or ""):
            return None
        cache_key = f"work:{work_id}"
        cached = _cached_response(conn, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return _meta_from_work(cached["response_json"]) if status == 200 else None
        try:
            status, body = self.fetcher(
                f"/{work_id}", params=self._polite_params(), headers=self._headers(), timeout=self.timeout
            )
        except Exception:
            _store_cache(
                conn,
                cache_key,
                request_json={"work_id": work_id},
                response_json={"error": "fetch failed"},
                status_code=None,
            )
            return None
        _store_cache(conn, cache_key, request_json={"work_id": work_id}, response_json=body, status_code=status)
        if status != 200 or not isinstance(body, dict):
            return None
        return _meta_from_work(body)

    def fetch_work_meta_for(self, conn: Connection, ref: PaperRef) -> dict[str, Any] | None:
        """Full `_meta_from_work` for a paper by DOI/PMID/title (inc 227) — reuses the cached by-ref work fetch,
        so when `fetch_referenced_works`/`fetch_cited_by_count` already populated it there is **no extra HTTP**.
        Gives the focal paper's `primary_topic` (the field baseline) + authors. Fail-closed → None."""
        return _meta_from_work(self._fetch_work(conn, ref))

    def fetch_work_csl(self, conn: Connection, ref: PaperRef) -> dict[str, Any] | None:
        """A CSL-fragment (title/author/issued/container-title/type/abstract/DOI/PMID) for a work by DOI/PMID/
        title — the multi-pass metadata enricher's OpenAlex source (inc 217). Notably fills venue / abstract /
        type that Crossref may lack. Reuses the cached `_fetch_work`; fail-closed → None."""
        return _csl_from_work(self._fetch_work(conn, ref))

    def fetch_work_id(self, conn: Connection, ref: PaperRef) -> str | None:
        """The OpenAlex `W…` id for a paper (inc 137 forward gap) — read from the cached DOI→work fetch."""
        work = self._fetch_work(conn, ref)
        raw = work.get("id") if isinstance(work, dict) else None
        wid = str(raw).rsplit("/", 1)[-1] if raw else None
        return wid if wid and re.fullmatch(r"W\d+", wid) else None

    def fetch_citing_works(self, conn: Connection, work_id: str) -> list[dict[str, Any]]:
        """Works that CITE a given work (inc 137 forward gap) — `?filter=cites:<W…>`, capped, cached, fail-closed.
        Returns meta dicts (openalex_work_id/doi/title/authors/year)."""
        if not re.fullmatch(r"W\d+", work_id or ""):
            return []
        cache_key = f"citing:{work_id}"
        cached = _cached_response(conn, cache_key)
        if cached is not None:
            body = cached["response_json"] if cached["status_code"] == 200 else None
        else:
            try:
                status, body = self.fetcher(
                    "",
                    params={"filter": f"cites:{work_id}", "per-page": "200", **self._polite_params()},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except Exception:
                _store_cache(
                    conn,
                    cache_key,
                    request_json={"work_id": work_id},
                    response_json={"error": "fetch failed"},
                    status_code=None,
                )
                return []
            _store_cache(conn, cache_key, request_json={"work_id": work_id}, response_json=body, status_code=status)
            if status != 200:
                body = None
        if not isinstance(body, dict):
            return []
        out: list[dict[str, Any]] = []
        for work in (body.get("results") or [])[:MAX_CITING]:
            meta = _meta_from_work(work)
            if meta and meta.get("openalex_work_id"):
                out.append(meta)
        return out

    def _field_sample_body(self, conn: Connection, topic_id: str, size: int) -> dict[str, Any] | None:
        """Raw OpenAlex listing body for a topic sample (cached `field:<id>`) — shared by `fetch_field_sample`
        (inc 227) + `fetch_topic_candidates` (inc 228), so the audit's sample + the overlooked candidates reuse one
        cached call. `topic_id` validated `^T\\d+$` **before** any request (no SSRF). Fail-closed → None."""
        if not re.fullmatch(r"T\d+", topic_id or ""):
            return None
        size = max(1, min(int(size), 200))
        cache_key = f"field:{topic_id}"
        cached = _cached_response(conn, cache_key)
        if cached is not None:
            return cached["response_json"] if cached["status_code"] == 200 else None
        try:
            status, body = self.fetcher(
                "",
                params={
                    "filter": f"primary_topic.id:{topic_id}",
                    "sample": str(size),
                    "seed": "42",  # fixed → a reproducible sample (re-runs hit the cache anyway)
                    "per-page": str(size),
                    **self._polite_params(),
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
        except Exception:
            _store_cache(
                conn,
                cache_key,
                request_json={"topic_id": topic_id},
                response_json={"error": "fetch failed"},
                status_code=None,
            )
            return None
        _store_cache(conn, cache_key, request_json={"topic_id": topic_id}, response_json=body, status_code=status)
        return body if status == 200 else None

    def fetch_field_sample(self, conn: Connection, topic_id: str, *, size: int = 200) -> list[dict[str, Any]]:
        """A random sample of recent works in an OpenAlex topic (inc 227 citation-equity) — the descriptive
        "field" a paper's reference list is shown against. Returns `_meta_from_work` dicts."""
        body = self._field_sample_body(conn, topic_id, size)
        if not isinstance(body, dict):
            return []
        return [m for work in (body.get("results") or [])[:size] if (m := _meta_from_work(work))]

    def fetch_topic_candidates(self, conn: Connection, topic_id: str, *, size: int = 200) -> list[dict[str, Any]]:
        """Topic-sample works WITH the reconstructed abstract (inc 228 overlooked-work) — candidates from the field,
        ranked by local embedding similarity to the focal paper. Shares the `field:<id>` cache with
        `fetch_field_sample` (no extra HTTP if the audit already ran). Returns `_meta_with_abstract` dicts."""
        body = self._field_sample_body(conn, topic_id, size)
        if not isinstance(body, dict):
            return []
        return [m for work in (body.get("results") or [])[:size] if (m := _meta_with_abstract(work))]

    def fetch_works_by_ids(
        self, conn: Connection, ids: list[str], *, with_abstract: bool = True
    ) -> list[dict[str, Any]]:
        """Batch-fetch OpenAlex works by their `W…` ids (inc 228 overlooked-work) — one
        `?filter=openalex_id:W1|W2|…` call (≤MAX_BYIDS ids, each validated `^W\\d+$` **before** the request → no
        SSRF), cached per id-set. Returns `_meta_with_abstract` dicts (title+abstract+concepts for ranking).
        Fail-closed → []."""
        valid = [w for w in (ids or []) if re.fullmatch(r"W\d+", w or "")][:MAX_BYIDS]
        if not valid:
            return []
        cache_key = "byids:" + hashlib.sha256("|".join(sorted(valid)).encode("utf-8")).hexdigest()[:24]
        cached = _cached_response(conn, cache_key)
        if cached is not None:
            body = cached["response_json"] if cached["status_code"] == 200 else None
        else:
            try:
                status, body = self.fetcher(
                    "",
                    params={
                        "filter": "openalex_id:" + "|".join(valid),
                        "per-page": str(len(valid)),
                        **self._polite_params(),
                    },
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except Exception:
                _store_cache(
                    conn,
                    cache_key,
                    request_json={"ids": valid},
                    response_json={"error": "fetch failed"},
                    status_code=None,
                )
                return []
            _store_cache(conn, cache_key, request_json={"ids": valid}, response_json=body, status_code=status)
            if status != 200:
                body = None
        if not isinstance(body, dict):
            return []
        out: list[dict[str, Any]] = []
        for work in body.get("results") or []:
            meta = _meta_with_abstract(work) if with_abstract else _meta_from_work(work)
            if meta and meta.get("openalex_work_id"):
                out.append(meta)
        return out

    def fetch_cited_by_count(self, conn: Connection, ref: PaperRef) -> int | None:
        """OpenAlex's `cited_by_count` for a paper (inc 210, A2) — read from the cached DOI→work fetch.
        Returns the verbatim count (0 is a real value, kept), or None if the work/field is absent. Fail-closed."""
        work = self._fetch_work(conn, ref)
        if not isinstance(work, dict):
            return None
        count = work.get("cited_by_count")
        return int(count) if isinstance(count, int) else None

    def lookup_retraction(self, conn: Connection, ref: PaperRef) -> dict[str, Any] | None:
        """Read OpenAlex's `is_retracted` boolean for a work (inc 131). Thin (a boolean, no notice detail) —
        corroboration + coverage alongside Crossref. Returns `{"status": "retracted"}` or None; never raises."""
        work = self._fetch_work(conn, ref)
        if isinstance(work, dict) and work.get("is_retracted") is True:
            return {"status": "retracted"}
        return None

    def _fetch_work(self, conn: Connection, ref: PaperRef) -> dict[str, Any] | None:
        path, params, cache_key = _endpoint_for(ref)
        if path is None:
            return None
        cached = _cached_response(conn, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            return _work_from_body(cached["response_json"]) if status == 200 else None
        try:
            status, body = self.fetcher(
                path, params={**params, **self._polite_params()}, headers=self._headers(), timeout=self.timeout
            )
        except Exception as exc:  # fail closed — never raise to the caller
            _store_cache(
                conn,
                cache_key,
                request_json={"path": path, "params": params},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return None
        _store_cache(
            conn, cache_key, request_json={"path": path, "params": params}, response_json=body, status_code=status
        )
        if status != 200 or not isinstance(body, dict):
            return None
        return _work_from_body(body)

    def _polite_params(self) -> dict[str, str]:
        return {"mailto": self.mailto} if self.mailto else {}

    def _headers(self) -> dict[str, str]:
        user_agent = "Callosum/0.1 (local-first reference manager)"
        if self.mailto:
            user_agent = f"{user_agent}; mailto:{self.mailto}"
        return {"User-Agent": user_agent, "Accept": "application/json"}


def _endpoint_for(ref: PaperRef) -> tuple[str | None, dict[str, str], str]:
    """(path, query params, cache_key) for the highest-precedence identifier on the ref."""
    if ref.doi:
        doi = ref.doi.strip().lower()
        return (f"/doi:{quote(doi, safe='/')}", {}, f"doi:{doi}")
    if ref.pmid:
        pmid = str(ref.pmid).strip()
        return (f"/pmid:{quote(pmid, safe='')}", {}, f"pmid:{pmid}")
    if ref.title:
        title = ref.title.strip()
        cache_key = "title:" + hashlib.sha256(title.lower().encode("utf-8")).hexdigest()[:24]
        return ("", {"filter": f"title.search:{title}", "per_page": "1"}, cache_key)
    return (None, {}, "")


def _httpx_fetcher(
    path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, Any] | None]:
    response = httpx.get(OPENALEX_BASE_URL + path, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _meta_from_work(work: Any) -> dict[str, Any] | None:
    """Map an OpenAlex work object → a meta dict (inc 135 gap-finder; extended inc 227 citation-equity). DOI
    normalized lower, prefix stripped. The inc-227 keys (venue/issn/institutions/country_codes/primary_topic) are
    purely additive — gap-finder/citation-count callers read only their own keys."""
    if not isinstance(work, dict):
        return None
    raw_id = str(work.get("id") or "")
    raw_doi = work.get("doi") or (work.get("ids") or {}).get("doi")
    doi = raw_doi.strip().lower().replace("https://doi.org/", "") if isinstance(raw_doi, str) and raw_doi else None
    title = work.get("title") or work.get("display_name")
    year = work.get("publication_year")
    authorships = [a for a in (work.get("authorships") or []) if isinstance(a, dict)]
    authors = [str((a.get("author") or {}).get("display_name") or "").strip() for a in authorships]
    # inc 227 (citation-equity): venue + ISSN for the venue-concentration signal.
    venue_src = (work.get("primary_location") or {}).get("source") or work.get("host_venue") or {}
    venue = venue_src.get("display_name") if isinstance(venue_src, dict) else None
    issn = venue_src.get("issn_l") if isinstance(venue_src, dict) else None
    # inc 227: institutions + affiliation countries from the authorships, for the institutional + geographic signals.
    # OpenAlex affiliation coverage is uneven (esp. older works) — a missing country is recorded as absent, NEVER
    # assumed domestic (silence ≠ certificate); the analyzer reports its coverage.
    institutions: list[str] = []
    country_codes: set[str] = set()
    for a in authorships:
        for inst in a.get("institutions") or []:
            if not isinstance(inst, dict):
                continue
            name = inst.get("display_name")
            if name and str(name) not in institutions and len(institutions) < 20:
                institutions.append(str(name))
            cc = inst.get("country_code")
            if isinstance(cc, str) and cc.strip():
                country_codes.add(cc.strip().upper())
    # inc 227: the focal paper's primary_topic = the "field" the reference list is shown against (id validated).
    raw_topic = work.get("primary_topic")
    primary_topic = None
    if isinstance(raw_topic, dict):
        tid = str(raw_topic.get("id") or "").rsplit("/", 1)[-1]
        if re.fullmatch(r"T\d+", tid):
            primary_topic = {"id": tid, "display_name": str(raw_topic.get("display_name") or "")}
    # inc 228 (overlooked-work SP2): related_works (OpenAlex's relatedness to this paper, bare ids) + concepts
    # (top concept names — the shared-topic "why" for a candidate). Small lists; existing callers ignore them.
    related: list[str] = []
    for url in (work.get("related_works") or [])[:MAX_RELATED]:
        if isinstance(url, str):
            wid = url.rsplit("/", 1)[-1]
            if re.fullmatch(r"W\d+", wid):
                related.append(wid)
    concepts = [
        str(c.get("display_name"))
        for c in (work.get("concepts") or [])[:8]
        if isinstance(c, dict) and c.get("display_name")
    ]
    return {
        "openalex_work_id": raw_id.rsplit("/", 1)[-1] if raw_id else None,
        "doi": doi,
        "title": str(title) if title else None,
        "year": int(year) if isinstance(year, int) else None,
        "authors": [a for a in authors if a][:8],
        "cited_by_count": int(work.get("cited_by_count") or 0),
        "venue": str(venue) if venue else None,
        "issn": str(issn) if issn else None,
        "institutions": institutions,
        "country_codes": sorted(country_codes),
        "primary_topic": primary_topic,
        "related_works": related,
        "concepts": concepts,
    }


def _meta_with_abstract(work: Any) -> dict[str, Any] | None:
    """`_meta_from_work` + the reconstructed `abstract` (inc 228) — for an overlooked-work *candidate* whose
    title+abstract we embed to rank topical relevance. Abstract is kept out of `_meta_from_work` (too large to add
    to every reference/field meta); only candidates carry it."""
    meta = _meta_from_work(work)
    if meta is None:
        return None
    meta["abstract"] = _reconstruct_abstract(work.get("abstract_inverted_index"))
    return meta


# OpenAlex `type` → CSL type (only the common ones; unknown → omitted, never a guessed type — inc 217).
_OA_TYPE_TO_CSL = {
    "article": "article-journal",
    "journal-article": "article-journal",
    "book-chapter": "chapter",
    "book": "book",
    "dataset": "dataset",
    "proceedings-article": "paper-conference",
    "preprint": "article-journal",
    "posted-content": "article-journal",
}


def _reconstruct_abstract(inverted_index: Any) -> str | None:
    """Rebuild plain-text from OpenAlex's `abstract_inverted_index` ({word: [positions]}). Capped; None if absent."""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        if not isinstance(idxs, list):
            continue
        for i in idxs:
            if isinstance(i, int):
                positions.append((i, str(word)))
    if not positions:
        return None
    positions.sort()
    text = " ".join(word for _, word in positions).strip()
    return text[:20000] or None


def _csl_from_work(work: Any) -> dict[str, Any] | None:
    """Map an OpenAlex work object → a CSL-fragment for gap-fill enrichment (inc 217). Only includes keys it can
    supply; authors are stored as CSL `{literal}` (OpenAlex doesn't split family/given reliably)."""
    if not isinstance(work, dict):
        return None
    fragment: dict[str, Any] = {}
    title = work.get("title") or work.get("display_name")
    if title:
        fragment["title"] = str(title)
    year = work.get("publication_year")
    if isinstance(year, int):
        fragment["issued"] = {"date-parts": [[year]]}
    authors = [
        {"literal": str(name)}
        for a in (work.get("authorships") or [])
        if isinstance(a, dict)
        for name in [(a.get("author") or {}).get("display_name") or a.get("raw_author_name")]
        if name
    ]
    if authors:
        fragment["author"] = authors
    venue = (work.get("primary_location") or {}).get("source") or work.get("host_venue") or {}
    venue_name = venue.get("display_name") if isinstance(venue, dict) else None
    if venue_name:
        fragment["container-title"] = str(venue_name)
    csl_type = _OA_TYPE_TO_CSL.get(str(work.get("type") or "").lower())
    if csl_type:
        fragment["type"] = csl_type
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
    if abstract:
        fragment["abstract"] = abstract
    raw_doi = work.get("doi") or (work.get("ids") or {}).get("doi")
    if isinstance(raw_doi, str) and raw_doi:
        fragment["DOI"] = raw_doi.strip().lower().replace("https://doi.org/", "")
    raw_pmid = (work.get("ids") or {}).get("pmid")
    if isinstance(raw_pmid, str) and raw_pmid:
        digits = "".join(ch for ch in raw_pmid if ch.isdigit())
        if digits:
            fragment["PMID"] = digits
    return fragment or None


def _work_from_body(body: Any) -> dict[str, Any] | None:
    """A by-id lookup returns the work object; a title search returns {"results": [...]}."""
    if isinstance(body, dict) and isinstance(body.get("results"), list):
        return body["results"][0] if body["results"] else None
    return body if isinstance(body, dict) else None


def _best_oa_location_from_work(work: dict[str, Any]) -> OaLocation | None:
    color = _OA_STATUS_TO_COLOR.get(str((work.get("open_access") or {}).get("oa_status") or "").lower())
    if color is None:  # closed / unknown → no authorized OA copy
        return None
    location = _pick_pdf_location(work)
    if location is None:
        return None
    pdf_url = location.get("pdf_url")
    if not isinstance(pdf_url, str) or not pdf_url.startswith("https://"):
        return None
    version = _VERSION_MAP.get(str(location.get("version") or "")) or _DEFAULT_VERSION_BY_COLOR.get(color, "vor")
    landing = location.get("landing_page_url")
    lic = location.get("license")
    try:
        return OaLocation(
            pdf_url=pdf_url,
            oa_color=color,
            version=version,
            source=OPENALEX_PROVIDER,
            landing_page_url=landing if isinstance(landing, str) else None,
            license=str(lic) if lic else None,
        )
    except ValueError:
        return None  # OaLocation rejected the url (non-https / IP host) — treat as no usable OA copy


def _pick_pdf_location(work: dict[str, Any]) -> dict[str, Any] | None:
    """First location (best_oa first, then oa_locations, then locations) that has an https pdf_url."""
    candidates: list[dict[str, Any]] = []
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        candidates.append(best)
    for key in ("oa_locations", "locations"):
        for loc in work.get(key) or []:
            if isinstance(loc, dict):
                candidates.append(loc)
    for loc in candidates:
        pdf_url = loc.get("pdf_url")
        if isinstance(pdf_url, str) and pdf_url.startswith("https://"):
            return loc
    return None


def _cached_response(conn: Connection, cache_key: str):
    return (
        conn.execute(
            select(external_api_cache).where(
                external_api_cache.c.provider == OPENALEX_PROVIDER,
                external_api_cache.c.cache_key == cache_key,
            )
        )
        .mappings()
        .first()
    )


def _store_cache(
    conn: Connection,
    cache_key: str,
    *,
    request_json: dict[str, Any],
    response_json: dict[str, Any] | None,
    status_code: int | None,
) -> None:
    existing = _cached_response(conn, cache_key)
    values = {"request_json": request_json, "response_json": response_json, "status_code": status_code}
    if existing is None:
        conn.execute(insert(external_api_cache).values(provider=OPENALEX_PROVIDER, cache_key=cache_key, **values))
    else:
        conn.execute(update(external_api_cache).where(external_api_cache.c.id == int(existing["id"])).values(**values))
