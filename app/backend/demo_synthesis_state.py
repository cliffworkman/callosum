"""Strict saved-state contract for demo Synthesize surfaces.

Every rendered payload uses the production response model consumed by the shared frontend. The wrapper only
indexes immutable responses by paper/run id and records the public-registration license boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.backend.api.routers.critical_review import CandidateListResponse, CriticalReadJobResponse
from app.backend.api.routers.registration_acquisition import RegistrationVersionOut
from app.backend.api.routers.registration_comparisons import ComparisonRunDetail, ComparisonRunSummary
from app.backend.api.routers.registration_discovery import RegistrationLinkOut


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoRegistrationLicenseAudit(_StrictModel):
    provider: str
    external_id: str
    canonical_url: str
    license_name: str
    redistribution: str
    verified_via: str
    verified_on: str
    bundled_full_registration: bool = False
    notice: str


class DemoSynthesisState(_StrictModel):
    critical_reads: dict[str, CriticalReadJobResponse]
    critical_candidates: dict[str, CandidateListResponse]
    registration_links: dict[str, list[RegistrationLinkOut]]
    registration_versions: dict[str, list[RegistrationVersionOut]]
    registration_comparison_runs: dict[str, list[ComparisonRunSummary]]
    registration_comparison_details: dict[str, ComparisonRunDetail]
    registration_license_audits: list[DemoRegistrationLicenseAudit] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_indexes(self) -> "DemoSynthesisState":
        paper_ids = set(self.critical_reads)
        for name, mapping in (
            ("critical candidates", self.critical_candidates),
            ("registration links", self.registration_links),
            ("registration versions", self.registration_versions),
            ("registration comparison runs", self.registration_comparison_runs),
        ):
            if set(mapping) != paper_ids:
                raise ValueError(f"{name} must cover the same papers as critical reads")
        for paper_id, runs in self.registration_comparison_runs.items():
            for run in runs:
                detail = self.registration_comparison_details.get(str(run.id))
                if detail is None or detail.paper_id != int(paper_id) or detail.id != run.id:
                    raise ValueError("registration comparison detail/index mismatch")
        return self
