from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import quote, urlencode

from app.backend.registration_discovery.domain import (
    DiscoveryRequest,
    ProviderReport,
    RegistrationCandidate,
    contextual_class,
    contextual_evidence,
)
from app.backend.registration_discovery.http import JsonFetcher, RegistryHttpError, get_registry_json

_BASE = "https://api.datacite.org"
_OSF_DOI = re.compile(r"^10\.17605/osf\.io/([a-z0-9]{4,12})$", re.I)


class DataCiteRegistrationProvider:
    id = "datacite"

    def __init__(self, fetch_json: JsonFetcher = get_registry_json) -> None:
        self._fetch = fetch_json

    def discover(self, request: DiscoveryRequest) -> ProviderReport:
        rows: list[tuple[dict, str]] = []
        details: list[str] = []
        for ref in request.references:
            if ref.provider != "doi":
                continue
            try:
                payload = self._fetch(f"{_BASE}/dois/{quote(ref.external_id, safe='')}")
                rows.append((payload.get("data") or {}, "paper-registration-doi"))
            except RegistryHttpError as exc:
                details.append(f"registration DOI {ref.external_id}: {exc}")

        if request.doi:
            query = f'relatedIdentifiers.relatedIdentifier:"{_clean_query_value(request.doi)}"'
            try:
                rows.extend((row, "datacite-related-identifier") for row in self._query(query))
            except RegistryHttpError as exc:
                details.append(f"publication DOI lookup: {exc}")

        if request.title.strip():
            query = (
                f'types.resourceTypeGeneral:StudyRegistration AND titles.title:"{_clean_query_value(request.title)}"'
            )
            try:
                rows.extend((row, "datacite-title-search") for row in self._query(query))
            except RegistryHttpError as exc:
                details.append(f"title lookup: {exc}")

        candidates: list[RegistrationCandidate] = []
        for row, method in rows:
            candidate = self._candidate(row, request, method)
            if candidate:
                candidates.append(candidate)
        return ProviderReport(
            provider=self.id,
            status="error" if details else "ok",
            candidates=tuple(candidates),
            detail="; ".join(details) or None,
        )

    def _query(self, query: str) -> list[dict]:
        url = f"{_BASE}/dois?{urlencode({'query': query, 'page[size]': 10})}"
        return list(self._fetch(url).get("data") or [])[:10]

    def _candidate(self, row: dict, request: DiscoveryRequest, method: str) -> RegistrationCandidate | None:
        attrs = row.get("attributes") or {}
        doi = str(attrs.get("doi") or row.get("id") or "").casefold()
        if not doi or str((attrs.get("types") or {}).get("resourceTypeGeneral") or "") != "StudyRegistration":
            return None
        osf_match = _OSF_DOI.fullmatch(doi)
        provider = "osf" if osf_match else "datacite"
        external_id = osf_match.group(1).casefold() if osf_match else doi
        related = [item for item in attrs.get("relatedIdentifiers") or [] if isinstance(item, dict)]
        exact_relations = _exact_publication_relations(related, request.doi)
        direct = method == "paper-registration-doi"
        evidence: list[dict] = []
        if direct:
            evidence.append({"kind": "paper-registration-doi", "doi": doi})
        evidence.extend(
            {"kind": "datacite-related-identifier", "doi": request.doi, "relation_type": relation}
            for relation in exact_relations
        )
        title = _first_title(attrs)
        candidate = RegistrationCandidate(
            provider=provider,
            external_id=external_id,
            registration_doi=doi,
            canonical_url=attrs.get("url") or f"https://doi.org/{doi}",
            title=title,
            contributors=tuple(
                str(item.get("name"))
                for item in attrs.get("creators") or []
                if isinstance(item, dict) and item.get("name")
            ),
            registered_at=_created_date(attrs),
            registration_status=str(attrs.get("state") or "findable"),
            schema_name=(attrs.get("types") or {}).get("resourceType"),
            linkage_class="explicit-linkage" if direct or exact_relations else "similarity-candidate",
            match_method=method,
            match_evidence=tuple(evidence),
            source_metadata={
                "publisher": attrs.get("publisher"),
                "resource_type_general": (attrs.get("types") or {}).get("resourceTypeGeneral"),
                "related_identifiers": related,
                "datacite_relation_types": exact_relations,
            },
        )
        if not direct and not exact_relations:
            contextual = contextual_evidence(request, candidate)
            candidate = replace(
                candidate,
                linkage_class=contextual_class(contextual),
                match_evidence=contextual,
            )
        return candidate


def _exact_publication_relations(related: list[dict], publication_doi: str | None) -> list[str]:
    if not publication_doi:
        return []
    wanted = publication_doi.casefold().removeprefix("https://doi.org/")
    return [
        str(item.get("relationType"))
        for item in related
        if str(item.get("relatedIdentifierType") or "").casefold() == "doi"
        and str(item.get("relatedIdentifier") or "").casefold().removeprefix("https://doi.org/") == wanted
    ]


def _first_title(attrs: dict) -> str | None:
    for item in attrs.get("titles") or []:
        if isinstance(item, dict) and item.get("title"):
            return str(item["title"])
    return None


def _created_date(attrs: dict) -> str | None:
    for item in attrs.get("dates") or []:
        if isinstance(item, dict) and item.get("dateType") in {"Created", "Issued", "Submitted"}:
            return str(item.get("date"))
    return str(attrs.get("created") or attrs.get("registered") or "") or None


def _clean_query_value(value: str) -> str:
    return value.replace("\\", " ").replace('"', " ").strip()[:500]
