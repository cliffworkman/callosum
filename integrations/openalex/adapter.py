"""OpenAlex open-access location resolver with database-backed caching (mirrors the Crossref adapter).

OpenAlex aggregates rights-holder-authorized OA locations (gold/green/bronze) across publishers and
repositories. We read *its* OA judgment — `open_access.oa_status` + the OA-location records — and never
make our own. Returns an `OaLocation` (the acquisition seam's only currency) or None; never raises.
Polite-pool `mailto` comes from `CALLOSUM_OPENALEX_MAILTO` (env / gitignored `.env`).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Protocol
from urllib.parse import quote

from sqlalchemy import Connection, Engine

from app.backend.acquisition.registry import OaColor, OaLocation, OaVersion, PaperRef
from app.backend.app_settings import resolved_mailto
from integrations.api_cache import put_cached, put_cached_committing
from integrations.openalex.field_sample import FieldSampleMixin
from integrations.openalex.request import (
    OpenAlexResponseUnavailable,
    bounded_openalex_get,
    openalex_headers,
    openalex_params,
)
from integrations.openalex.work_keywords import keywords_from_work
from integrations.openalex.work_meta import (
    MAX_REFERENCED,
    OPENALEX_PROVIDER,
    _cached_response,
    _csl_from_work,
    _meta_from_work,
    _meta_with_abstract,  # noqa: F401 -- re-exported: beyond_library.py + tests still import it from here
)

OPENALEX_BASE_URL = "https://api.openalex.org/works"
MAX_CITING = 200  # cap on citing works read per paper (inc 137 forward gap; bound + a documented coverage limit)


class OpenAlexUnavailableError(OpenAlexResponseUnavailable):
    """The provider could not establish a complete answer for a requested OpenAlex lookup."""


@dataclass(frozen=True)
class _WorkFetchResult:
    work: dict[str, Any] | None
    state: str  # ok | not_found | unavailable


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


class OpenAlexClient(FieldSampleMixin):
    def __init__(
        self,
        *,
        fetcher: OpenAlexFetcher | None = None,
        mailto: str | None = None,
        timeout: float = 10.0,
        cache_engine: Engine | None = None,
    ) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.mailto = mailto or resolved_mailto("CALLOSUM_OPENALEX_MAILTO")  # UI contact email overlays the env var
        self.timeout = timeout
        # inc D: when set (fetch-outside-lock jobs — gap-finder / my-publications), cache writes self-commit in
        # their own short transaction instead of the caller's conn, so a long fetch phase never holds the write
        # lock. Default None → the usual conn-based cache (every per-item B/C caller is untouched).
        self.cache_engine = cache_engine

    def with_cache_engine(self, engine: Engine) -> OpenAlexClient:
        """A copy of this client whose cache writes self-commit in their own transaction (inc D) — for a
        fetch-outside-lock job that runs its fetch phase on a read connection."""
        return OpenAlexClient(fetcher=self.fetcher, mailto=self.mailto, timeout=self.timeout, cache_engine=engine)

    def _store(self, conn: Connection, cache_key: str, **cache_fields: Any) -> None:
        """Cache a provider response (``cache_fields`` = request_json / response_json / status_code). Self-commits
        in its own transaction when ``cache_engine`` is set (fetch-outside-lock jobs), else writes via ``conn``."""
        if self.cache_engine is not None:
            put_cached_committing(self.cache_engine, OPENALEX_PROVIDER, cache_key, **cache_fields)
        else:
            put_cached(conn, OPENALEX_PROVIDER, cache_key, **cache_fields)

    def lookup_best_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        """Resolve a paper to the best authorized open-access PDF location OpenAlex knows, or None."""
        work = self._fetch_work(conn, ref)
        if work is None:
            return None
        return _best_oa_location_from_work(work)

    def fetch_referenced_works(self, conn: Connection, ref: PaperRef) -> list[str]:
        """The OpenAlex work ids a paper CITES (inc 135 gap-finder) — `referenced_works`, bare `W…` ids, capped.
        Reuses the cached DOI→work fetch; fail-closed (no work / no field → [])."""
        try:
            return self.fetch_referenced_works_strict(conn, ref)
        except OpenAlexUnavailableError:
            return []

    def fetch_referenced_works_strict(self, conn: Connection, ref: PaperRef) -> list[str]:
        """Like ``fetch_referenced_works``, but distinguish provider failure from a complete empty result."""
        result = self._fetch_work_result(conn, ref)
        if result.state == "unavailable":
            raise OpenAlexUnavailableError("OpenAlex referenced-work lookup was unavailable")
        work = result.work
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
        try:
            return self.fetch_work_meta_strict(conn, work_id)
        except OpenAlexUnavailableError:
            return None

    def fetch_work_meta_strict(self, conn: Connection, work_id: str) -> dict[str, Any] | None:
        """Fetch one work while preserving unavailable versus complete-not-found semantics."""
        if not re.fullmatch(r"W\d+", work_id or ""):
            return None
        cache_key = f"work:{work_id}"
        cached = _cached_response(conn, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            if status == 200:
                return _meta_from_work(cached["response_json"])
            if status == 404:
                return None
            # A cached transient response is not an authoritative answer; retry below.
        try:
            status, body = self.fetcher(
                f"/{work_id}", params=self._polite_params(), headers=self._headers(), timeout=self.timeout
            )
        except Exception as exc:
            raise OpenAlexUnavailableError("OpenAlex work lookup failed") from exc
        if status == 404:
            return None
        if status != 200 or not isinstance(body, dict):
            raise OpenAlexUnavailableError(f"OpenAlex work lookup returned HTTP {status}")
        self._store(conn, cache_key, request_json={"work_id": work_id}, response_json=body, status_code=status)
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

    def fetch_work_id_strict(self, conn: Connection, ref: PaperRef) -> str | None:
        """Return a work id or a proven absence; raise when OpenAlex was unavailable."""
        result = self._fetch_work_result(conn, ref)
        if result.state == "unavailable":
            raise OpenAlexUnavailableError("OpenAlex work lookup was unavailable")
        raw = result.work.get("id") if isinstance(result.work, dict) else None
        work_id = str(raw).rsplit("/", 1)[-1] if raw else None
        return work_id if work_id and re.fullmatch(r"W\d+", work_id) else None

    def fetch_work_keywords(self, conn: Connection, ref: PaperRef) -> list[str]:
        """Curated keyword display-names (topics, else concepts) for a paper (inc 306 — the `keyword:openalex`
        tag source). Reads the cached work populated by the enrich cascade → zero extra egress in the normal path.
        Fail-closed → `[]`."""
        return keywords_from_work(self._fetch_work(conn, ref) or {})

    def fetch_citing_works(self, conn: Connection, work_id: str) -> list[dict[str, Any]]:
        """Works that CITE a given work (inc 137 forward gap) — `?filter=cites:<W…>`, capped, cached, fail-closed.
        Returns meta dicts (openalex_work_id/doi/title/authors/year)."""
        try:
            return self.fetch_citing_works_strict(conn, work_id)
        except OpenAlexResponseUnavailable:
            return []

    def fetch_citing_works_strict(self, conn: Connection, work_id: str) -> list[dict[str, Any]]:
        """Return a complete bounded citing-work page, raising when it cannot be established."""
        if not re.fullmatch(r"W\d+", work_id or ""):
            return []
        cache_key = f"citing:{work_id}"
        cached = _cached_response(conn, cache_key)
        body = (
            cached["response_json"]
            if cached is not None and cached["status_code"] == 200 and isinstance(cached["response_json"], dict)
            else None
        )
        if body is None:
            try:
                status, body = self.fetcher(
                    "",
                    params={"filter": f"cites:{work_id}", "per-page": "200", **self._polite_params()},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except Exception as exc:
                raise OpenAlexUnavailableError("OpenAlex citing-work lookup was unavailable") from exc
            if status != 200 or not isinstance(body, dict):
                raise OpenAlexUnavailableError(f"OpenAlex citing-work lookup returned HTTP {status}")
            self._store(conn, cache_key, request_json={"work_id": work_id}, response_json=body, status_code=status)
        if not isinstance(body, dict):
            raise OpenAlexUnavailableError("OpenAlex citing-work response was malformed")
        results = body.get("results")
        if not isinstance(results, list):
            raise OpenAlexUnavailableError("OpenAlex citing-work results were malformed")
        out: list[dict[str, Any]] = []
        for work in results[:MAX_CITING]:
            meta = _meta_from_work(work)
            if meta and meta.get("openalex_work_id"):
                out.append(meta)
        return out

    def fetch_cited_by_count(self, conn: Connection, ref: PaperRef, *, refresh: bool = False) -> int | None:
        """OpenAlex's `cited_by_count` for a paper (inc 210, A2) — read from the cached DOI→work fetch.
        Returns the verbatim count (0 is a real value, kept), or None if the work/field is absent. Fail-closed."""
        work = self._fetch_work_result(conn, ref, refresh=refresh).work
        if not isinstance(work, dict):
            return None
        count = work.get("cited_by_count")
        return int(count) if isinstance(count, int) else None

    def lookup_retraction(self, conn: Connection, ref: PaperRef) -> dict[str, Any] | None:
        """Read OpenAlex's `is_retracted` boolean for a work (inc 131). Thin (a boolean, no notice detail) —
        corroboration + coverage alongside Crossref. Returns `{"status": "retracted"}` or None; never raises."""
        result = self._fetch_work_result(conn, ref)
        if result.state == "unavailable":
            raise OpenAlexUnavailableError("OpenAlex retraction lookup was unavailable")
        work = result.work
        if isinstance(work, dict) and work.get("is_retracted") is True:
            return {"status": "retracted"}
        return None

    def _fetch_work(self, conn: Connection, ref: PaperRef) -> dict[str, Any] | None:
        return self._fetch_work_result(conn, ref).work

    def _fetch_work_result(self, conn: Connection, ref: PaperRef, *, refresh: bool = False) -> _WorkFetchResult:
        path, params, cache_key = _endpoint_for(ref)
        if path is None:
            return _WorkFetchResult(None, "not_found")
        cached = None if refresh else _cached_response(conn, cache_key)
        if cached is not None:
            status = int(cached["status_code"]) if cached["status_code"] is not None else None
            if status == 200:
                work = _validated_work(cached["response_json"], ref)
                return _WorkFetchResult(work, "ok" if work is not None else "not_found")
            if status == 404:
                return _WorkFetchResult(None, "not_found")
            # Retry cached transient/error statuses rather than replaying them indefinitely.
        try:
            status, body = self.fetcher(
                path, params={**params, **self._polite_params()}, headers=self._headers(), timeout=self.timeout
            )
        except Exception:
            return _WorkFetchResult(None, "unavailable")
        if status == 404:
            return _WorkFetchResult(None, "not_found")
        if status != 200 or not isinstance(body, dict):
            return _WorkFetchResult(None, "unavailable")
        work = _validated_work(body, ref)
        self._store(
            conn, cache_key, request_json={"path": path, "params": params}, response_json=body, status_code=status
        )
        return _WorkFetchResult(work, "ok" if work is not None else "not_found")

    def _polite_params(self) -> dict[str, str]:
        return openalex_params(self.mailto)

    def _headers(self) -> dict[str, str]:
        return openalex_headers(self.mailto)


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
    response = bounded_openalex_get(OPENALEX_BASE_URL + path, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _work_from_body(body: Any) -> dict[str, Any] | None:
    """A by-id lookup returns the work object; a title search returns {"results": [...]}."""
    if isinstance(body, dict) and isinstance(body.get("results"), list):
        return body["results"][0] if body["results"] else None
    return body if isinstance(body, dict) else None


def _validated_work(body: Any, ref: PaperRef) -> dict[str, Any] | None:
    work = _work_from_body(body)
    if work is None or not ref.title or ref.doi or ref.pmid:
        return work
    return work if _title_matches(ref.title, work.get("title")) else None


def _title_matches(requested: str, returned: Any) -> bool:
    """Reject an unrelated first search hit while tolerating minor punctuation/Unicode variation."""
    if not isinstance(returned, str):
        return False

    def normalized(value: str) -> str:
        folded = unicodedata.normalize("NFKC", value).casefold()
        return " ".join(re.findall(r"\w+", folded, flags=re.UNICODE))

    wanted, found = normalized(requested), normalized(returned)
    if not wanted or not found:
        return False
    if wanted == found:
        return True
    wanted_tokens, found_tokens = set(wanted.split()), set(found.split())
    overlap = len(wanted_tokens & found_tokens) / max(len(wanted_tokens | found_tokens), 1)
    return overlap >= 0.9 and SequenceMatcher(None, wanted, found).ratio() >= 0.92


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
