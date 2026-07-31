from __future__ import annotations

import re
from dataclasses import replace

from app.backend.registration_discovery.domain import (
    DiscoveryRequest,
    ProviderReport,
    RegistrationCandidate,
    contextual_class,
    contextual_evidence,
)
from app.backend.registration_discovery.http import JsonFetcher, RegistryHttpError, get_registry_json

_GUID = re.compile(r"^[a-z0-9]{4,12}$")
_BASE = "https://api.osf.io/v2"


class OsfRegistrationProvider:
    id = "osf"

    def __init__(self, fetch_json: JsonFetcher = get_registry_json) -> None:
        self._fetch = fetch_json

    def discover(self, request: DiscoveryRequest) -> ProviderReport:
        candidates: list[RegistrationCandidate] = []
        details: list[str] = []
        for ref in request.references:
            if ref.provider != "osf" or not _GUID.fullmatch(ref.external_id.casefold()):
                continue
            guid = ref.external_id.casefold()
            try:
                payload = self._fetch(f"{_BASE}/registrations/{guid}/")
                candidate = self._candidate(payload.get("data") or {}, request, direct=True, ref=ref)
                if candidate:
                    candidates.append(candidate)
                continue
            except RegistryHttpError as exc:
                if exc.status != 404:
                    details.append(f"{guid}: {exc}")
                    continue
            # A paper may print an OSF project rather than the immutable registration. The documented node
            # relationship is bounded to OSF's first page (max 10); every result remains confirmation-required.
            try:
                payload = self._fetch(f"{_BASE}/nodes/{guid}/registrations/")
            except RegistryHttpError as exc:
                details.append(f"{guid}: not a public registration or project ({exc})")
                continue
            rows = list(payload.get("data") or [])[:10]
            for row in rows:
                candidate = self._candidate(row, request, direct=False, ref=ref, one_on_node=len(rows) == 1)
                if candidate:
                    candidates.append(candidate)
        status = "error" if details else "ok"
        return ProviderReport(
            provider=self.id,
            status=status,
            candidates=tuple(candidates),
            detail="; ".join(details) or None,
        )

    def _candidate(self, row, request, *, direct, ref, one_on_node=False) -> RegistrationCandidate | None:
        guid = str(row.get("id") or "").casefold()
        if not _GUID.fullmatch(guid):
            return None
        attrs = row.get("attributes") or {}
        contributors = self._contributors(guid)
        registration_doi = self._registration_doi(guid)
        resource_relation = self._publication_resource_relation(guid, request.doi)
        status = _registration_status(attrs)
        base_evidence: list[dict] = []
        if direct:
            base_evidence.append(
                {
                    "kind": "paper-reference",
                    "snippet": ref.evidence_snippet,
                    "printed": ref.explicitly_printed,
                }
            )
        if resource_relation:
            base_evidence.append(resource_relation)
        candidate = RegistrationCandidate(
            provider="osf",
            external_id=guid,
            registration_doi=registration_doi,
            canonical_url=f"https://osf.io/{guid}/",
            title=attrs.get("title"),
            contributors=contributors,
            registered_at=attrs.get("date_registered") or attrs.get("date_created"),
            registration_status=status,
            schema_name=attrs.get("registration_supplement"),
            linkage_class="explicit-linkage" if direct or resource_relation else "similarity-candidate",
            match_method="paper-osf-reference" if direct else "osf-project-registration",
            match_evidence=tuple(base_evidence),
            source_metadata={
                "public": attrs.get("public"),
                "embargoed": attrs.get("embargoed"),
                "withdrawn": attrs.get("withdrawn"),
                "reviews_state": attrs.get("reviews_state"),
                "resource_publication_doi": resource_relation.get("doi") if resource_relation else None,
            },
        )
        if not direct and not resource_relation:
            evidence = contextual_evidence(request, candidate)
            candidate = replace(
                candidate,
                linkage_class=contextual_class(evidence, one_registration_on_node=one_on_node),
                match_evidence=tuple(base_evidence) + evidence,
            )
        return candidate

    def _contributors(self, guid: str) -> tuple[str, ...]:
        try:
            rows = self._fetch(f"{_BASE}/registrations/{guid}/contributors/?embed=users").get("data") or []
        except RegistryHttpError:
            return ()
        return tuple(
            name
            for row in rows[:50]
            if (
                name := (((row.get("embeds") or {}).get("users") or {}).get("data") or {})
                .get("attributes", {})
                .get("full_name")
            )
        )

    def _registration_doi(self, guid: str) -> str | None:
        try:
            rows = self._fetch(f"{_BASE}/registrations/{guid}/identifiers/").get("data") or []
        except RegistryHttpError:
            return None
        for row in rows:
            attrs = row.get("attributes") or {}
            if str(attrs.get("category") or "").casefold() == "doi":
                return str(attrs.get("value") or "").lower() or None
        return None

    def _publication_resource_relation(self, guid: str, publication_doi: str | None) -> dict | None:
        if not publication_doi:
            return None
        try:
            rows = self._fetch(f"{_BASE}/registrations/{guid}/resources/").get("data") or []
        except RegistryHttpError:
            return None
        wanted = publication_doi.casefold().removeprefix("https://doi.org/")
        for row in rows:
            attrs = row.get("attributes") or {}
            pid = str(attrs.get("pid") or "").casefold().removeprefix("https://doi.org/")
            if attrs.get("resource_type") == "papers" and pid == wanted:
                return {"kind": "osf-papers-resource", "doi": publication_doi, "exact": True}
        return None


def _registration_status(attrs: dict) -> str:
    if attrs.get("withdrawn"):
        return "withdrawn"
    if attrs.get("embargoed"):
        return "embargoed"
    if attrs.get("public") is False:
        return "unavailable"
    return "public"
