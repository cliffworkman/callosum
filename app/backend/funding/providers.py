"""Funding provider capability contracts and initial open-data adapters."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection, select

from app.backend.acquisition.registry import PaperRef
from app.backend.app_settings import resolved_mailto
from app.backend.funding.domain import (
    ApplicationSurface,
    HistoricalAward,
    ProvenanceRecord,
    ProviderStatus,
)
from app.backend.funding.grants_gov import GRANTS_GOV_PROVIDER, GrantsGovClient  # noqa: F401
from app.backend.funding.profile import ResearchFundingProfile, facet_values
from app.backend.funding.ror import RorIdentityProvider as RorIdentityProvider  # noqa: F401
from app.backend.persistence.schema import papers
from integrations.api_cache import get_cached, put_cached
from integrations.openalex import OpenAlexClient

OPENALEX_FUNDING_PROVIDER = "openalex-funding"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_FUNDING_PROVIDER = "crossref-funding"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"


class GetJsonFetcher(Protocol):
    def __call__(
        self, url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]: ...


def httpx_get_fetcher(url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float):
    response = httpx.get(url, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


class FixtureAwardHistoryProvider:
    """Deterministic local award-history provider used for open-data fixtures and tests.

    This is also the bounded ETL feed point for EO-BMF / 990-PF parsed records.
    """

    id = "local-funding-history"
    capabilities = ["award_history", "grantmaking_transaction"]

    def __init__(
        self,
        awards: list[HistoricalAward] | None = None,
        surfaces: list[ApplicationSurface] | None = None,
    ) -> None:
        self.awards = list(awards or [])
        self.surfaces = surfaces or []

    def search_awards(
        self, conn: Connection | None, profile: ResearchFundingProfile
    ) -> tuple[list[HistoricalAward], ProviderStatus]:
        values = facet_values(profile)
        out = [a for a in self.awards if _award_matches(a, values)]
        return out, ProviderStatus(
            self.id, "award_history", "success", result_count=len(out), indexed_through="fixture"
        )

    def application_surfaces(self, awards: list[HistoricalAward]) -> list[ApplicationSurface]:
        orgs = {a.organization_name for a in awards}
        schemes = {a.scheme_name for a in awards if a.scheme_name}
        return [
            s
            for s in self.surfaces
            if s.organization_name in orgs and (s.scheme_name is None or s.scheme_name in schemes)
        ]


class NullAwardHistoryProvider:
    """Production default when no historical-award feed is configured.

    Contributes ZERO awards so the latent-prospect engine draws only from real OpenAlex/Crossref funding
    lineage + grants.gov opportunities. A real EO-BMF / 990-PF feed can later be wired via
    ``app.state.funding_award_provider`` (``irs.py`` already parses those records); until then no
    fabricated award history is surfaced — never present fabricated data as real.
    """

    id = "no-award-feed"
    capabilities: list[str] = []

    def search_awards(
        self, conn: Connection | None, profile: ResearchFundingProfile
    ) -> tuple[list[HistoricalAward], ProviderStatus]:
        return [], ProviderStatus(
            self.id, "award_history", "not_searched", warning="No historical-award feed configured."
        )

    def application_surfaces(self, awards: list[HistoricalAward]) -> list[ApplicationSurface]:
        return []


class OpenAlexFundingProvider:
    id = OPENALEX_FUNDING_PROVIDER
    capabilities = ["award_history"]

    def __init__(
        self,
        *,
        fetcher: GetJsonFetcher | None = None,
        client: OpenAlexClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.fetcher = fetcher or httpx_get_fetcher
        self.client = client
        self.timeout = timeout
        self.mailto = resolved_mailto("CALLOSUM_OPENALEX_MAILTO")

    def search_awards(
        self, conn: Connection, profile: ResearchFundingProfile
    ) -> tuple[list[HistoricalAward], ProviderStatus]:
        lineage_awards = self._lineage_awards(conn, profile)
        keyword_awards, keyword_status = self._keyword_awards(conn, profile)
        combined = _dedupe_awards([*lineage_awards, *keyword_awards])
        if lineage_awards and keyword_status.status == "failed":
            return combined, ProviderStatus(
                self.id,
                "award_history",
                "partial",
                result_count=len(combined),
                warning="Related-work funding lineage succeeded; keyword funding search failed.",
            )
        if lineage_awards and keyword_status.status == "not_searched":
            return combined, ProviderStatus(self.id, "award_history", "success", result_count=len(combined))
        return combined, ProviderStatus(
            self.id,
            "award_history",
            keyword_status.status,
            result_count=len(combined),
            warning=keyword_status.warning,
            error_code=keyword_status.error_code,
        )

    def _keyword_awards(
        self, conn: Connection, profile: ResearchFundingProfile
    ) -> tuple[list[HistoricalAward], ProviderStatus]:
        query = _keyword(profile)
        if not query:
            return [], ProviderStatus(self.id, "award_history", "not_searched", warning="No query facets.")
        params = {
            "search": query,
            "filter": "has_funder:true",
            "per-page": "25",
            **({"mailto": self.mailto} if self.mailto else {}),
        }
        cache_key = hashlib.sha256(str(params).encode("utf-8")).hexdigest()
        cached = get_cached(conn, self.id, cache_key)
        if cached is not None and cached["response_json"] is not None:
            return self._normalize(cached["response_json"], cached["status_code"])
        try:
            status, payload = self.fetcher(
                OPENALEX_WORKS_URL, params=params, headers=_json_headers(self.mailto), timeout=self.timeout
            )
        except Exception:
            put_cached(
                conn, self.id, cache_key, request_json=params, response_json={"error": "fetch failed"}, status_code=None
            )
            return [], ProviderStatus(self.id, "award_history", "failed", error_code="fetch_failed")
        put_cached(conn, self.id, cache_key, request_json=params, response_json=payload, status_code=status)
        return self._normalize(payload, status)

    def _lineage_awards(self, conn: Connection, profile: ResearchFundingProfile) -> list[HistoricalAward]:
        if profile.source_kind != "paper" or not profile.source_id:
            return []
        try:
            paper_id = int(profile.source_id)
        except ValueError:
            return []
        row = conn.execute(select(papers.c.doi, papers.c.title).where(papers.c.id == paper_id)).mappings().first()
        if row is None or not row["doi"]:
            return []
        client = self.client or OpenAlexClient()
        focal = client.fetch_work_meta_for(conn, PaperRef(doi=row["doi"]))
        if not focal:
            return []
        related_ids = [rid for rid in focal.get("related_works") or [] if isinstance(rid, str)][:25]
        if not related_ids:
            return []
        works = client.fetch_works_by_ids(conn, related_ids, with_abstract=False)
        return _awards_from_openalex_works(works, source_field="related_works.grants", provider_id=self.id)

    def _normalize(self, payload: dict[str, Any] | None, status: int | None):
        if status != 200 or not isinstance(payload, dict):
            return [], ProviderStatus(self.id, "award_history", "failed", error_code=f"http_{status}")
        awards = _awards_from_openalex_works(payload.get("results") or [], source_field="grants", provider_id=self.id)
        return awards, ProviderStatus(self.id, "award_history", "success", result_count=len(awards))


class CrossrefFundingProvider:
    id = CROSSREF_FUNDING_PROVIDER
    capabilities = ["award_history"]

    def __init__(self, *, fetcher: GetJsonFetcher | None = None, timeout: float = 15.0) -> None:
        self.fetcher = fetcher or httpx_get_fetcher
        self.timeout = timeout
        self.mailto = resolved_mailto("CALLOSUM_CROSSREF_MAILTO")

    def search_awards(
        self, conn: Connection, profile: ResearchFundingProfile
    ) -> tuple[list[HistoricalAward], ProviderStatus]:
        query = _keyword(profile)
        if not query:
            return [], ProviderStatus(self.id, "award_history", "not_searched", warning="No query facets.")
        params = {"query": query, "rows": "25", "filter": "has-funder:true"}
        cache_key = hashlib.sha256(str(params).encode("utf-8")).hexdigest()
        cached = get_cached(conn, self.id, cache_key)
        if cached is not None and cached["response_json"] is not None:
            return self._normalize(cached["response_json"], cached["status_code"])
        try:
            status, payload = self.fetcher(
                CROSSREF_WORKS_URL, params=params, headers=_json_headers(self.mailto), timeout=self.timeout
            )
        except Exception:
            put_cached(
                conn, self.id, cache_key, request_json=params, response_json={"error": "fetch failed"}, status_code=None
            )
            return [], ProviderStatus(self.id, "award_history", "failed", error_code="fetch_failed")
        put_cached(conn, self.id, cache_key, request_json=params, response_json=payload, status_code=status)
        return self._normalize(payload, status)

    def _normalize(self, payload: dict[str, Any] | None, status: int | None):
        if status != 200 or not isinstance(payload, dict):
            return [], ProviderStatus(self.id, "award_history", "failed", error_code=f"http_{status}")
        message = payload.get("message") or {}
        items = message.get("items") if isinstance(message, dict) else []
        now = datetime.now(UTC).isoformat()
        awards: list[HistoricalAward] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            title = _first(item.get("title")) or item.get("DOI")
            year = _crossref_year(item)
            source_record = str(item.get("DOI") or title or "crossref-work")
            for idx, funder in enumerate(item.get("funder") or []):
                if not isinstance(funder, dict):
                    continue
                name = funder.get("name")
                if not name:
                    continue
                awards_raw = funder.get("award") if isinstance(funder.get("award"), list) else []
                for award_id in awards_raw or [f"{source_record}:{idx}"]:
                    awards.append(
                        HistoricalAward(
                            organization_name=str(name),
                            source_kind="crossref_grant",
                            source_record_id=str(award_id),
                            title=str(title) if title else None,
                            purpose_text=str(title) if title else None,
                            tax_year=year,
                            award_number=str(award_id),
                            provenance=[
                                ProvenanceRecord(
                                    self.id,
                                    source_record,
                                    now,
                                    source_url=item.get("URL"),
                                    source_field="funder",
                                    source_text=str(title) if title else None,
                                    extraction_method="provider_native",
                                )
                            ],
                        )
                    )
        return awards, ProviderStatus(self.id, "award_history", "success", result_count=len(awards))


def _award_matches(award: HistoricalAward, values: set[str]) -> bool:
    text = " ".join([award.title or "", award.purpose_text or "", award.scheme_name or ""]).lower()
    return any(v.lower() in text for v in values)


def _awards_from_openalex_works(works: list[Any], *, source_field: str, provider_id: str) -> list[HistoricalAward]:
    now = datetime.now(UTC).isoformat()
    awards: list[HistoricalAward] = []
    for work in works:
        if not isinstance(work, dict):
            continue
        title = work.get("title") or work.get("display_name")
        year = work.get("publication_year") if "publication_year" in work else work.get("year")
        work_id = str(work.get("id") or work.get("openalex_work_id") or work.get("doi") or title or "openalex-work")
        for idx, grant in enumerate(work.get("grants") or []):
            if not isinstance(grant, dict):
                continue
            funder = grant.get("funder_display_name") or grant.get("funder") or grant.get("funder_name")
            if not funder:
                continue
            award_id = grant.get("award_id") or grant.get("award") or f"{work_id}:{idx}"
            awards.append(
                HistoricalAward(
                    organization_name=str(funder),
                    source_kind="openalex_award",
                    source_record_id=str(award_id),
                    title=str(title) if title else None,
                    purpose_text=str(title) if title else None,
                    tax_year=int(year) if isinstance(year, int) else None,
                    award_number=str(award_id),
                    provenance=[
                        ProvenanceRecord(
                            provider_id,
                            str(work_id),
                            now,
                            source_url=str(work.get("id")) if work.get("id") else None,
                            source_field=source_field,
                            source_text=str(title) if title else None,
                            extraction_method="provider_native",
                        )
                    ],
                )
            )
    return awards


def _dedupe_awards(awards: list[HistoricalAward]) -> list[HistoricalAward]:
    seen: set[tuple[str, str]] = set()
    out: list[HistoricalAward] = []
    for award in awards:
        key = (award.source_kind, award.source_record_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(award)
    return out


def _json_headers(mailto: str | None = None) -> dict[str, str]:
    ua = "Callosum/0.1 (local-first reference manager)"
    if mailto:
        ua = f"{ua}; mailto:{mailto}"
    return {"User-Agent": ua, "Accept": "application/json"}


def _first(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    text = str(value).strip() if value else ""
    return text or None


def _crossref_year(item: dict[str, Any]) -> int | None:
    issued = item.get("issued") or item.get("published-print") or item.get("published-online") or {}
    try:
        return int(issued.get("date-parts", [[None]])[0][0])
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def _keyword(profile: ResearchFundingProfile) -> str:
    ordered = []
    for key in ("conditionsOrPhenomena", "methods", "supportStrategies", "subjects", "disciplines"):
        ordered.extend(f.normalized_value for f in profile.facets.get(key, []))
    return " ".join(dict.fromkeys(ordered).keys())[:200]
