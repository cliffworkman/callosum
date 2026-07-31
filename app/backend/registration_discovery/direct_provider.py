from __future__ import annotations

from app.backend.registration_discovery.domain import (
    DiscoveryRequest,
    ProviderReport,
    RegistrationCandidate,
)


class DirectReferenceProvider:
    """Candidate rows for already-known non-OSF references. No network request."""

    id = "direct-reference"

    def discover(self, request: DiscoveryRequest) -> ProviderReport:
        candidates: list[RegistrationCandidate] = []
        for ref in request.references:
            if ref.provider in {"osf", "doi"}:
                continue
            evidence = (
                {"kind": "paper-reference", "snippet": ref.evidence_snippet, "printed": ref.explicitly_printed},
            )
            candidates.append(
                RegistrationCandidate(
                    provider=ref.provider,
                    external_id=ref.external_id,
                    registration_doi=None,
                    canonical_url=ref.canonical_url,
                    title=None,
                    contributors=(),
                    registered_at=None,
                    registration_status="public-reference" if ref.canonical_url else "identifier-only",
                    schema_name=None,
                    linkage_class="explicit-linkage",
                    match_method="manual-reference" if ref.extraction_method == "manual" else "paper-printed-reference",
                    match_evidence=evidence,
                    source_metadata={"network_request": False},
                )
            )
        return ProviderReport(provider=self.id, status="ok", candidates=tuple(candidates))
