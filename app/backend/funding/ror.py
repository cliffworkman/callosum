"""ROR organization identity adapter for Funding Discovery."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection

from app.backend.funding.domain import ProvenanceRecord, ProviderStatus
from integrations.api_cache import get_cached, put_cached

ROR_PROVIDER = "ror"
ROR_ORGS_URL = "https://api.ror.org/organizations"


class RorGetFetcher(Protocol):
    def __call__(
        self, url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> tuple[int, dict[str, Any] | None]: ...


def ror_httpx_fetcher(url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float):
    response = httpx.get(url, params=params, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


class RorIdentityProvider:
    id = ROR_PROVIDER
    capabilities = ["organization_identity"]

    def __init__(self, *, fetcher: RorGetFetcher | None = None, timeout: float = 10.0) -> None:
        self.fetcher = fetcher or ror_httpx_fetcher
        self.timeout = timeout

    def resolve(self, conn: Connection, name: str) -> tuple[dict[str, Any], ProviderStatus]:
        query = (name or "").strip()
        if not query:
            return _fallback_org(query), ProviderStatus(self.id, "organization_identity", "not_searched")
        params = {"query": query, "page": "1"}
        cache_key = hashlib.sha256(str(params).encode("utf-8")).hexdigest()
        cached = get_cached(conn, self.id, cache_key)
        if cached is not None and cached["response_json"] is not None:
            return self._normalize(query, cached["response_json"], cached["status_code"])
        try:
            status, payload = self.fetcher(ROR_ORGS_URL, params=params, headers=_headers(), timeout=self.timeout)
        except Exception:
            put_cached(
                conn, self.id, cache_key, request_json=params, response_json={"error": "fetch failed"}, status_code=None
            )
            return _fallback_org(query), ProviderStatus(
                self.id, "organization_identity", "failed", error_code="fetch_failed"
            )
        put_cached(conn, self.id, cache_key, request_json=params, response_json=payload, status_code=status)
        return self._normalize(query, payload, status)

    def _normalize(self, query: str, payload: dict[str, Any] | None, status: int | None):
        if status != 200 or not isinstance(payload, dict):
            return _fallback_org(query), ProviderStatus(
                self.id, "organization_identity", "failed", error_code=f"http_{status}"
            )
        candidates = [_ror_org_from_record(r) for r in (payload.get("items") or payload.get("results") or [])]
        candidates = [c for c in candidates if c]
        if not candidates:
            return _fallback_org(query), ProviderStatus(self.id, "organization_identity", "success", result_count=0)
        exact = [c for c in candidates if c["display_name"].lower() == query.lower()]
        chosen = exact[0] if len(exact) == 1 else candidates[0]
        if len(candidates) > 1 and not exact:
            chosen["resolution_status"] = "ambiguous"
        return chosen, ProviderStatus(self.id, "organization_identity", "success", result_count=len(candidates))


def _headers() -> dict[str, str]:
    return {"User-Agent": "Callosum/0.1 (local-first reference manager)", "Accept": "application/json"}


def _fallback_org(query: str) -> dict[str, Any]:
    name = query.strip() or "Unresolved funder"
    return {
        "display_name": name,
        "identifiers": {},
        "aliases": [],
        "resolution_status": "probable" if query.strip() else "unresolved",
        "provenance": [
            ProvenanceRecord(
                provider_id=ROR_PROVIDER,
                source_record_id=query.strip() or "unresolved",
                retrieved_at=datetime.now(UTC).isoformat(),
                extraction_method="deterministic_parse",
                confidence_basis="Name retained because ROR did not return a resolved identity.",
            ).to_dict()
        ],
    }


def _ror_org_from_record(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    ror_id = str(record.get("id") or "").strip()
    display_name = str(record.get("name") or record.get("display_name") or "").strip()
    aliases = _names(record.get("names") if isinstance(record.get("names"), list) else [], display_name)
    if not display_name and aliases:
        display_name = aliases[0]
    if not display_name:
        return None
    return {
        "display_name": display_name,
        "identifiers": _identifiers(record, ror_id),
        "aliases": [a for a in aliases if a != display_name],
        "website": _website(record),
        "geography": _geography(record),
        "resolution_status": "resolved",
        "provenance": [
            ProvenanceRecord(
                provider_id=ROR_PROVIDER,
                source_record_id=ror_id or display_name,
                retrieved_at=datetime.now(UTC).isoformat(),
                source_url=ror_id or None,
                extraction_method="provider_native",
            ).to_dict()
        ],
    }


def _names(names: list[Any], display_name: str) -> list[str]:
    out: list[str] = []
    for item in names:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or "").strip()
        if value and value not in out:
            out.append(value)
    return out or ([display_name] if display_name else [])


def _identifiers(record: dict[str, Any], ror_id: str) -> dict[str, Any]:
    identifiers: dict[str, Any] = {"ror": ror_id} if ror_id else {}
    for item in record.get("external_ids") or []:
        if not isinstance(item, dict):
            continue
        all_ids = item.get("all") if isinstance(item.get("all"), list) else []
        if str(item.get("type") or "").lower() == "fundref" and all_ids:
            identifiers["crossrefFunderId"] = all_ids[0]
    return identifiers


def _website(record: dict[str, Any]) -> str | None:
    links = record.get("links") if isinstance(record.get("links"), list) else []
    return links[0].get("value") if links and isinstance(links[0], dict) else None


def _geography(record: dict[str, Any]) -> dict[str, Any]:
    locations = record.get("locations") if isinstance(record.get("locations"), list) else []
    geo = (locations[0].get("geonames_details") or locations[0]) if locations and isinstance(locations[0], dict) else {}
    if not isinstance(geo, dict):
        return {}
    return {k: v for k, v in {"country": geo.get("country_name"), "city": geo.get("name")}.items() if v}
