"""Strict saved-result contracts for the public demo's remaining workspaces.

The frontend consumes the ordinary live response models.  This module only groups those
responses into an immutable, context-indexed bundle so demo mode can preload them without
pretending to execute a backend job.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.backend.api.routers.annotations import AnnotationResponse
from app.backend.api.routers.citation_context import CitationContextReportModel
from app.backend.api.routers.citation_equity import EquityReportModel, OverlookedReportModel
from app.backend.api.routers.citation_suggest import SuggestResponse
from app.backend.api.routers.followed_authors import FollowedAuthorOut
from app.backend.api.routers.my_publication_citing_authors import CitingAuthorListResponse
from app.backend.api.routers.my_publication_gaps import CitationGapListResponse
from app.backend.api.routers.my_publication_topics import EmergingTopicListResponse
from app.backend.api.routers.publishers import PublishersReportModel
from app.backend.api.routers.reference_integrity import ReferenceOverviewItem, ReferenceReportModel
from app.backend.api.routers.saved_searches import SavedSearch
from app.backend.api.routers.workbench import ProjectSummary

DEMO_EXTENDED_STATE_SCHEMA_VERSION = 2  # v2 (2026-08-27): dropped followed_author_candidates -- the Followed
# Authors tab's own gap-candidate view was retired when it consolidated into Discover -> Feed.


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoFeedSubscription(_StrictModel):
    id: int
    kind: str
    value: str
    label: str | None = None
    last_polled_at: str | None = None


class DemoFeedItem(_StrictModel):
    id: int
    subscription_id: int
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    posted_date: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    is_read: bool = False
    is_starred: bool = False
    in_library: bool = False


class DemoFeedState(_StrictModel):
    included: bool = False
    approved_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    subscriptions: list[DemoFeedSubscription] = Field(default_factory=list)
    items: list[DemoFeedItem] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)
    source_meta: list[dict[str, JsonValue]] = Field(default_factory=list)
    library_journals: list[dict[str, JsonValue]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_review_gate(self) -> "DemoFeedState":
        if self.included != bool(self.approved_digest):
            raise ValueError("a public Feed snapshot requires an approved review digest")
        if not self.included and (self.subscriptions or self.items):
            raise ValueError("unapproved Feed records cannot enter the public snapshot")
        known = {item.id for item in self.subscriptions}
        if any(item.subscription_id not in known for item in self.items):
            raise ValueError("Feed item references an unknown subscription")
        return self


class DemoDiscoveryItem(_StrictModel):
    dedup_key: str
    title: str
    sources: list[str] = Field(default_factory=list)
    doi: str | None = None
    pmid: str | None = None
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    url: str | None = None
    in_library: bool = False


class DemoSearchSnapshot(_StrictModel):
    query: str
    source: str = ""
    source_label: str = "All sources"
    sources: list[dict[str, JsonValue]]
    items: list[DemoDiscoveryItem]
    relevance: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)


class DemoFundingRunSummary(_StrictModel):
    run_id: int
    source_kind: str
    source_id: str | None = None
    title: str
    created_at: str
    result_counts: dict[str, int]
    provider_statuses: list[dict[str, JsonValue]]
    llm_annotated_count: int = 0


class DemoFundingReport(_StrictModel):
    run_id: int
    profile: dict[str, JsonValue]
    provider_statuses: list[dict[str, JsonValue]]
    result_counts: dict[str, int]
    open_opportunities: list[dict[str, JsonValue]]
    recurring_schemes: list[dict[str, JsonValue]]
    funding_prospects: list[dict[str, JsonValue]]
    application_surfaces: list[dict[str, JsonValue]]
    llm_triage_status: dict[str, JsonValue]


class DemoDiscoverState(_StrictModel):
    search: DemoSearchSnapshot
    journals: PublishersReportModel
    funding_runs: list[DemoFundingRunSummary]
    funding_reports: dict[str, DemoFundingReport]
    saved_funding: list[dict[str, JsonValue]] = Field(default_factory=list)
    followed_authors: list[FollowedAuthorOut] = Field(default_factory=list)
    citation_gaps: CitationGapListResponse
    emerging_topics: EmergingTopicListResponse
    citing_authors: CitingAuthorListResponse
    overlooked_by_axis: dict[str, OverlookedReportModel] = Field(default_factory=dict)


class DemoWorkbenchProject(_StrictModel):
    id: int
    name: str
    design: str
    protocol_note: str | None = None
    template: list[dict[str, JsonValue]]
    rows: list[dict[str, JsonValue]]


class DemoWorkState(_StrictModel):
    cite_claim: str
    cite: SuggestResponse
    reference_integrity: dict[str, ReferenceReportModel]
    reference_overview: list[ReferenceOverviewItem]
    citation_equity: dict[str, EquityReportModel]
    overlooked_work: dict[str, OverlookedReportModel]
    citation_context_incoming: dict[str, CitationContextReportModel]
    citation_context_outgoing: dict[str, CitationContextReportModel]
    workbench_projects: list[ProjectSummary]
    workbench_details: dict[str, DemoWorkbenchProject]
    credit_authors: list[dict[str, JsonValue]]
    credit_result: dict[str, JsonValue]
    statement_drafts: dict[str, str]
    credit_pending: dict[str, str]
    statements_pending: dict[str, str]
    citation_renderings: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    citation_bibtex: dict[str, str] = Field(default_factory=dict)
    workbench_exports: dict[str, dict[str, str]] = Field(default_factory=dict)


class DemoLibraryExtras(_StrictModel):
    annotations: dict[str, list[AnnotationResponse]]
    saved_searches: list[SavedSearch]
    grim_checks: dict[str, list[dict[str, JsonValue]]]
    debit_checks: dict[str, list[dict[str, JsonValue]]]
    duplicate_value_checks: dict[str, list[dict[str, JsonValue]]]


class DemoExtendedState(_StrictModel):
    schema_version: int = DEMO_EXTENDED_STATE_SCHEMA_VERSION
    generated_with: dict[str, str]
    feed: DemoFeedState = Field(default_factory=DemoFeedState)
    discover: DemoDiscoverState
    work: DemoWorkState
    library: DemoLibraryExtras

    @model_validator(mode="after")
    def validate_contract(self) -> "DemoExtendedState":
        if self.schema_version != DEMO_EXTENDED_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported extended demo state; regenerate it")
        paper_ids = {42, 67, 88}
        for mapping in (
            self.work.reference_integrity,
            self.work.citation_equity,
            self.work.overlooked_work,
            self.work.citation_context_incoming,
            self.work.citation_context_outgoing,
            self.library.annotations,
            self.library.grim_checks,
            self.library.debit_checks,
            self.library.duplicate_value_checks,
        ):
            if set(map(int, mapping)) != paper_ids:
                raise ValueError("extended per-paper state must cover all three curated papers")
        if set(map(int, self.work.workbench_details)) != {item.id for item in self.work.workbench_projects}:
            raise ValueError("workbench summary/detail indexes do not agree")
        if self.work.workbench_exports and set(map(int, self.work.workbench_exports)) != {
            item.id for item in self.work.workbench_projects
        }:
            raise ValueError("workbench exports must cover every saved project")
        if set(map(int, self.discover.funding_reports)) != {item.run_id for item in self.discover.funding_runs}:
            raise ValueError("funding summary/detail indexes do not agree")
        return self
