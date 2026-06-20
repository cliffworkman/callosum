"""OpenAlex open-access location resolver with database-backed caching (mirrors the Crossref adapter).

OpenAlex aggregates rights-holder-authorized OA locations (gold/green/bronze) across publishers and
repositories. We read *its* OA judgment — `open_access.oa_status` + the OA-location records — and never
make our own. Returns an `OaLocation` (the acquisition seam's only currency) or None; never raises.
Polite-pool `mailto` comes from `CALLOSUM_OPENALEX_MAILTO` (env / gitignored `.env`).
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import Connection, insert, select, update

from app.backend.acquisition.registry import OaColor, OaLocation, OaVersion, PaperRef
from app.backend.persistence.schema import external_api_cache

OPENALEX_PROVIDER = "openalex"
OPENALEX_BASE_URL = "https://api.openalex.org/works"

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
        self.mailto = mailto or os.environ.get("CALLOSUM_OPENALEX_MAILTO")
        self.timeout = timeout

    def lookup_best_oa(self, conn: Connection, ref: PaperRef) -> OaLocation | None:
        """Resolve a paper to the best authorized open-access PDF location OpenAlex knows, or None."""
        work = self._fetch_work(conn, ref)
        if work is None:
            return None
        return _best_oa_location_from_work(work)

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
