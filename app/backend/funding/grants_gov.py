"""Grants.gov opportunity provider adapter for Funding Discovery."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.funding.domain import FundingOpportunity, ProvenanceRecord, ProviderStatus
from app.backend.funding.profile import ResearchFundingProfile
from integrations.api_cache import get_cached, put_cached

GRANTS_GOV_PROVIDER = "grants-gov"
GRANTS_GOV_SEARCH_URL = "https://api.grants.gov/v1/api/search2"
GRANTS_GOV_FETCH_URL = "https://api.grants.gov/v1/api/fetchOpportunity"


class JsonFetcher(Protocol):
    def __call__(
        self, url: str, *, json: dict[str, Any] | None, params: dict[str, str] | None, timeout: float
    ) -> tuple[int, dict[str, Any] | None]: ...


def httpx_fetcher(url: str, *, json: dict[str, Any] | None, params: dict[str, str] | None, timeout: float):
    response = httpx.post(url, json=json, params=params, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


class GrantsGovClient:
    id = GRANTS_GOV_PROVIDER
    capabilities = ["opportunity_index"]

    def __init__(self, *, fetcher: JsonFetcher | None = None, timeout: float = 15.0) -> None:
        self.fetcher = fetcher or httpx_fetcher
        self.timeout = timeout

    def search_opportunities(
        self, conn: Connection, profile: ResearchFundingProfile, *, rows: int = 25
    ) -> tuple[list[FundingOpportunity], ProviderStatus]:
        keyword = _keyword(profile)
        if not keyword:
            return [], ProviderStatus(self.id, "opportunity_index", "not_searched", warning="No query facets.")
        body = {"keyword": keyword, "rows": rows, "oppStatuses": "forecasted|posted"}
        cache_key = hashlib.sha256(str(body).encode("utf-8")).hexdigest()
        cached = get_cached(conn, self.id, cache_key)
        if cached is not None and cached["response_json"] is not None:
            payload = cached["response_json"] if cached["status_code"] == 200 else None
            return self._normalize(payload, keyword, cached["status_code"])
        try:
            status, payload = self.fetcher(GRANTS_GOV_SEARCH_URL, json=body, params=None, timeout=self.timeout)
        except Exception:
            put_cached(
                conn, self.id, cache_key, request_json=body, response_json={"error": "fetch failed"}, status_code=None
            )
            return [], ProviderStatus(self.id, "opportunity_index", "failed", error_code="fetch_failed")
        put_cached(conn, self.id, cache_key, request_json=body, response_json=payload, status_code=status)
        return self._normalize(payload, keyword, status)

    def fetch_opportunity(
        self, conn: Connection, opportunity_id: str | int, *, refresh: bool = False
    ) -> tuple[FundingOpportunity | None, ProviderStatus]:
        oid = str(opportunity_id or "").strip()
        if not oid:
            return None, ProviderStatus(self.id, "opportunity_index", "not_searched", warning="Missing opportunity id.")
        body = {"opportunityId": int(oid) if oid.isdigit() else oid}
        cache_key = "detail:" + hashlib.sha256(str(body).encode("utf-8")).hexdigest()
        cached = get_cached(conn, self.id, cache_key)
        if not refresh and cached is not None and cached["response_json"] is not None:
            return self._normalize_detail(cached["response_json"], cached["status_code"], oid)
        try:
            status, payload = self.fetcher(GRANTS_GOV_FETCH_URL, json=body, params=None, timeout=self.timeout)
        except Exception:
            put_cached(
                conn, self.id, cache_key, request_json=body, response_json={"error": "fetch failed"}, status_code=None
            )
            return None, ProviderStatus(self.id, "opportunity_index", "failed", error_code="fetch_failed")
        put_cached(conn, self.id, cache_key, request_json=body, response_json=payload, status_code=status)
        return self._normalize_detail(payload, status, oid)

    def _normalize(self, payload: dict[str, Any] | None, keyword: str, status: int | None):
        if status != 200 or not isinstance(payload, dict):
            return [], ProviderStatus(self.id, "opportunity_index", "failed", error_code=f"http_{status}")
        data = payload.get("data") or {}
        hits = data.get("oppHits") or []
        out: list[FundingOpportunity] = []
        now = datetime.now(UTC).isoformat()
        for h in hits:
            if not isinstance(h, dict):
                continue
            oid = str(h.get("id") or h.get("number") or "")
            if not oid:
                continue
            status_value = (
                "open"
                if str(h.get("oppStatus") or "").lower() == "posted"
                else str(h.get("oppStatus") or "unknown").lower()
            )
            close = h.get("closeDate")
            deadlines = [{"kind": "application", "date": close, "basis": "provider_native"}] if close else []
            out.append(
                FundingOpportunity(
                    organization_name=str(h.get("agencyName") or h.get("agencyCode") or "Grants.gov agency"),
                    provider_id=self.id,
                    provider_opportunity_id=oid,
                    title=str(h.get("title") or "Untitled opportunity"),
                    status=status_value if status_value in {"open", "forecasted", "closed"} else "unknown",
                    summary=f"Federal opportunity surfaced from Grants.gov search keyword: {keyword}",
                    deadlines=deadlines,
                    source_url=f"https://www.grants.gov/search-results-detail/{oid}",
                    provenance=[
                        ProvenanceRecord(
                            provider_id=self.id,
                            source_record_id=oid,
                            retrieved_at=now,
                            source_field="oppHits",
                            extraction_method="provider_native",
                        )
                    ],
                )
            )
        return out, ProviderStatus(self.id, "opportunity_index", "success", result_count=len(out))

    def _normalize_detail(self, payload: dict[str, Any] | None, status: int | None, fallback_id: str):
        if status != 200 or not isinstance(payload, dict):
            return None, ProviderStatus(self.id, "opportunity_index", "failed", error_code=f"http_{status}")
        data = payload.get("data") or {}
        if not isinstance(data, dict) or not data:
            return None, ProviderStatus(self.id, "opportunity_index", "success", result_count=0)
        synopsis = data.get("synopsis") if isinstance(data.get("synopsis"), dict) else {}
        forecast = data.get("forecast") if isinstance(data.get("forecast"), dict) else {}
        detail = synopsis or forecast
        oid = str(data.get("id") or detail.get("opportunityId") or fallback_id)
        title = str(data.get("opportunityTitle") or detail.get("opportunityTitle") or "Untitled opportunity")
        agency = (
            (data.get("agencyDetails") or {}).get("agencyName")
            or (detail.get("agencyDetails") or {}).get("agencyName")
            or detail.get("agencyName")
            or data.get("owningAgencyCode")
            or "Grants.gov agency"
        )
        doc_type = str(data.get("docType") or "").lower()
        due = detail.get("responseDateDesc") or data.get("originalDueDateDesc") or detail.get("originalDueDateDesc")
        deadlines = [{"kind": "application", "date": str(due), "basis": "provider_native"}] if due else []
        now = datetime.now(UTC).isoformat()
        return (
            FundingOpportunity(
                organization_name=str(agency),
                provider_id=self.id,
                provider_opportunity_id=oid,
                title=title,
                status=_detail_status(data, detail, doc_type),
                summary=detail.get("synopsisDesc") or f"Grants.gov opportunity detail for {oid}",
                deadlines=deadlines,
                amount=_detail_amount(detail),
                source_url=f"https://www.grants.gov/search-results-detail/{oid}",
                provenance=[
                    ProvenanceRecord(
                        provider_id=self.id,
                        source_record_id=oid,
                        retrieved_at=now,
                        source_field="fetchOpportunity",
                        extraction_method="provider_native",
                    )
                ],
            ),
            ProviderStatus(self.id, "opportunity_index", "success", result_count=1),
        )


def _detail_status(data: dict[str, Any], detail: dict[str, Any], doc_type: str) -> str:
    raw = str(
        data.get("opportunityStatus")
        or data.get("oppStatus")
        or detail.get("opportunityStatus")
        or detail.get("oppStatus")
        or ""
    ).lower()
    if raw in {"posted", "synopsis", "open"}:
        return "open"
    if raw in {"forecasted", "forecast"}:
        return "forecasted"
    if raw == "closed":
        return "closed"
    if doc_type == "synopsis":
        return "open"
    if doc_type == "forecast":
        return "forecasted"
    return "unknown"


def _detail_amount(detail: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"currency": "USD"}
    floor = _num(detail.get("awardFloor"))
    ceiling = _num(detail.get("awardCeiling"))
    if floor is not None:
        out["min"] = floor
    if ceiling is not None:
        out["max"] = ceiling
    return out if len(out) > 1 else {}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def _keyword(profile: ResearchFundingProfile) -> str:
    ordered = []
    for key in ("conditionsOrPhenomena", "methods", "supportStrategies", "subjects", "disciplines"):
        ordered.extend(f.normalized_value for f in profile.facets.get(key, []))
    return " ".join(dict.fromkeys(ordered).keys())[:200]
