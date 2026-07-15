"""Funding Discovery domain records.

These dataclasses are transport shapes for the deterministic pipeline. They intentionally keep historical evidence,
prospects, recurring schemes, current opportunities, and application surfaces separate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FundingCapability = Literal[
    "organization_identity",
    "award_history",
    "grantmaking_transaction",
    "opportunity_index",
    "application_surface",
    "taxonomy",
    "news_signal",
]
EvidenceStrength = Literal["strong", "moderate", "weak", "conflict", "unresolved"]


@dataclass(frozen=True)
class ProvenanceRecord:
    provider_id: str
    source_record_id: str
    retrieved_at: str
    source_url: str | None = None
    source_field: str | None = None
    source_text: str | None = None
    extraction_method: str = "provider_native"
    confidence_basis: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class FundingFacet:
    normalized_value: str
    source_text: str | None
    basis: str
    confidence_basis: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class ResearchFundingProfile:
    source_kind: str
    title: str | None
    facets: dict[str, list[FundingFacet]]
    source_id: str | None = None
    applicant_context: dict[str, Any] = field(default_factory=dict)
    funding_preferences: dict[str, Any] = field(default_factory=dict)
    provenance: list[ProvenanceRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "title": self.title,
            "facets": {k: [f.to_dict() for f in v] for k, v in self.facets.items()},
            "applicant_context": self.applicant_context,
            "funding_preferences": self.funding_preferences,
            "provenance": [p.to_dict() for p in self.provenance],
        }


@dataclass(frozen=True)
class FundingOrganization:
    display_name: str
    organization_type: str | None = None
    identifiers: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    website: str | None = None
    geography: dict[str, Any] = field(default_factory=dict)
    resolution_status: str = "unresolved"
    provenance: list[ProvenanceRecord] = field(default_factory=list)


@dataclass(frozen=True)
class FundingScheme:
    organization_name: str
    name: str
    scheme_type: str | None = None
    recurrence: dict[str, Any] = field(default_factory=dict)
    official_url: str | None = None
    provenance: list[ProvenanceRecord] = field(default_factory=list)


@dataclass(frozen=True)
class HistoricalAward:
    organization_name: str
    source_kind: str
    source_record_id: str
    title: str | None = None
    purpose_text: str | None = None
    amount: dict[str, Any] = field(default_factory=dict)
    tax_year: int | None = None
    recipient_name_raw: str | None = None
    recipient_is_individual: bool = False
    scheme_name: str | None = None
    award_number: str | None = None
    provenance: list[ProvenanceRecord] = field(default_factory=list)

    def ui_recipient(self) -> str | None:
        return None if self.recipient_is_individual else self.recipient_name_raw


@dataclass(frozen=True)
class FundingMatchSignal:
    signal_type: str
    strength: EvidenceStrength
    explanation: str
    matched_profile_facets: list[dict[str, Any]] = field(default_factory=list)
    matched_evidence: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    ordering_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("ordering_value", None)
        return data


@dataclass(frozen=True)
class FundingProspect:
    organization_name: str
    prospect_kind: Literal["organization", "scheme"]
    signals: list[FundingMatchSignal]
    scheme_name: str | None = None
    evidence_freshness: str = "unknown"
    identity_resolution_quality: str = "medium"


@dataclass(frozen=True)
class FundingOpportunity:
    organization_name: str
    provider_id: str
    provider_opportunity_id: str
    title: str
    status: str
    summary: str | None = None
    deadlines: list[dict[str, Any]] = field(default_factory=list)
    amount: dict[str, Any] = field(default_factory=dict)
    eligibility: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    provenance: list[ProvenanceRecord] = field(default_factory=list)


@dataclass(frozen=True)
class ApplicationSurface:
    organization_name: str
    surface_type: str
    actionability: str
    scheme_name: str | None = None
    access_mode: str | None = None
    url: str | None = None
    details: str | None = None
    provenance: list[ProvenanceRecord] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderStatus:
    provider_id: str
    capability: FundingCapability
    status: str
    result_count: int | None = None
    indexed_through: str | None = None
    warning: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class FundingSearchResult:
    profile: ResearchFundingProfile
    opportunities: list[FundingOpportunity]
    recurring_schemes: list[FundingProspect]
    prospects: list[FundingProspect]
    provider_statuses: list[ProviderStatus]
