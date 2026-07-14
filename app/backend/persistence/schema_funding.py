"""Funding Discovery persistence schema.

The tables preserve the epistemic split: historical awards, prospects, schemes, current opportunities, and
application surfaces are different records, not one generic grant object with a status flag.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint, func
from sqlalchemy.dialects.sqlite import JSON

from app.backend.persistence.schema_base import enum_check, metadata

PROSPECT_KINDS = ("organization", "scheme")
FUNDING_ITEM_KINDS = ("opportunity", "scheme", "prospect")
FUNDING_WORKFLOW_STATES = ("saved", "reviewing", "considering", "planning", "applying", "submitted", "archived")

funding_organizations = Table(
    "funding_organizations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("display_name", String(500), nullable=False),
    Column("organization_type", String(80)),
    Column("identifiers_json", JSON, nullable=False, default=dict),
    Column("aliases_json", JSON, nullable=False, default=list),
    Column("website", String(1000)),
    Column("geography_json", JSON, nullable=False, default=dict),
    Column("resolution_status", String(40), nullable=False, default="unresolved"),
    Column("provenance_json", JSON, nullable=False, default=list),
    Column("created_at", String, server_default=func.current_timestamp()),
    Column("updated_at", String, server_default=func.current_timestamp()),
    UniqueConstraint("display_name", name="uq_funding_org_display_name"),
)

funding_schemes = Table(
    "funding_schemes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("organization_id", ForeignKey("funding_organizations.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(500), nullable=False),
    Column("scheme_type", String(80)),
    Column("recurrence_json", JSON, nullable=False, default=dict),
    Column("official_url", String(1000)),
    Column("provenance_json", JSON, nullable=False, default=list),
    Column("created_at", String, server_default=func.current_timestamp()),
    Column("updated_at", String, server_default=func.current_timestamp()),
    UniqueConstraint("organization_id", "name", name="uq_funding_scheme_org_name"),
)

funding_historical_awards = Table(
    "funding_historical_awards",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("organization_id", ForeignKey("funding_organizations.id", ondelete="CASCADE"), nullable=False),
    Column("scheme_id", ForeignKey("funding_schemes.id", ondelete="SET NULL")),
    Column("recipient_organization_id", ForeignKey("funding_organizations.id", ondelete="SET NULL")),
    Column("recipient_name_raw", String(500)),
    Column("recipient_is_individual", Integer, nullable=False, default=0),
    Column("award_number", String(200)),
    Column("title", String(1000)),
    Column("purpose_text", Text),
    Column("amount_json", JSON, nullable=False, default=dict),
    Column("start_date", String(40)),
    Column("end_date", String(40)),
    Column("tax_year", Integer),
    Column("source_kind", String(80), nullable=False),
    Column("source_record_id", String(500), nullable=False),
    Column("provenance_json", JSON, nullable=False, default=list),
    Column("created_at", String, server_default=func.current_timestamp()),
    UniqueConstraint("source_kind", "source_record_id", name="uq_funding_award_source"),
)

funding_prospects = Table(
    "funding_prospects",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("organization_id", ForeignKey("funding_organizations.id", ondelete="CASCADE"), nullable=False),
    Column("scheme_id", ForeignKey("funding_schemes.id", ondelete="SET NULL")),
    Column("prospect_kind", String(40), nullable=False),
    Column("evidence_freshness", String(40), nullable=False, default="unknown"),
    Column("signals_json", JSON, nullable=False, default=list),
    Column("identity_resolution_quality", String(40), nullable=False, default="low"),
    Column("run_id", ForeignKey("funding_search_runs.id", ondelete="SET NULL")),
    Column("surfaced_at", String, server_default=func.current_timestamp()),
    enum_check("prospect_kind", PROSPECT_KINDS, "funding_prospect_kind"),
)

funding_opportunities = Table(
    "funding_opportunities",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("organization_id", ForeignKey("funding_organizations.id", ondelete="CASCADE"), nullable=False),
    Column("scheme_id", ForeignKey("funding_schemes.id", ondelete="SET NULL")),
    Column("provider_id", String(120), nullable=False),
    Column("provider_opportunity_id", String(300), nullable=False),
    Column("title", String(1000), nullable=False),
    Column("summary", Text),
    Column("status", String(40), nullable=False, default="unknown"),
    Column("opportunity_type", String(200)),
    Column("opens_at", String(40)),
    Column("deadlines_json", JSON, nullable=False, default=list),
    Column("amount_json", JSON, nullable=False, default=dict),
    Column("expected_awards", Integer),
    Column("eligibility_json", JSON, nullable=False, default=dict),
    Column("source_url", String(1000)),
    Column("source_updated_at", String(80)),
    Column("fetched_at", String, server_default=func.current_timestamp()),
    Column("content_hash", String(80)),
    Column("provenance_json", JSON, nullable=False, default=list),
    Column("run_id", ForeignKey("funding_search_runs.id", ondelete="SET NULL")),
    UniqueConstraint("provider_id", "provider_opportunity_id", name="uq_funding_opp_provider"),
)

funding_application_surfaces = Table(
    "funding_application_surfaces",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("organization_id", ForeignKey("funding_organizations.id", ondelete="CASCADE"), nullable=False),
    Column("scheme_id", ForeignKey("funding_schemes.id", ondelete="SET NULL")),
    Column("surface_type", String(80), nullable=False),
    Column("access_mode", String(80)),
    Column("actionability", String(80), nullable=False, default="unknown"),
    Column("url", String(1000)),
    Column("details", Text),
    Column("checked_at", String, server_default=func.current_timestamp()),
    Column("provenance_json", JSON, nullable=False, default=list),
)

research_funding_profiles = Table(
    "research_funding_profiles",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_kind", String(80), nullable=False),
    Column("source_id", String(200)),
    Column("title", String(1000)),
    Column("facets_json", JSON, nullable=False, default=dict),
    Column("applicant_context_json", JSON, nullable=False, default=dict),
    Column("preferences_json", JSON, nullable=False, default=dict),
    Column("provenance_json", JSON, nullable=False, default=list),
    Column("created_at", String, server_default=func.current_timestamp()),
)

funding_search_runs = Table(
    "funding_search_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("profile_id", ForeignKey("research_funding_profiles.id", ondelete="SET NULL")),
    Column("status", String(40), nullable=False, default="done"),
    Column("provider_statuses_json", JSON, nullable=False, default=list),
    Column("result_counts_json", JSON, nullable=False, default=dict),
    Column("created_at", String, server_default=func.current_timestamp()),
)

funding_llm_triage_annotations = Table(
    "funding_llm_triage_annotations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", ForeignKey("funding_search_runs.id", ondelete="CASCADE"), nullable=False),
    Column("item_kind", String(40), nullable=False),
    Column("canonical_item_id", Integer, nullable=False),
    Column("label", String(80), nullable=False),
    Column("show_in_triage", Integer, nullable=False, default=0),
    Column("rationale", Text),
    Column("fit_dimensions_json", JSON, nullable=False, default=list),
    Column("concerns_json", JSON, nullable=False, default=list),
    Column("basis", Text),
    Column("provider_id", String(120), nullable=False, default="configured-llm"),
    Column("prompt_version", String(120)),
    Column("evidence_fingerprint", String(80)),
    Column("status", String(40), nullable=False, default="current"),
    Column("created_at", String, server_default=func.current_timestamp()),
    enum_check("item_kind", FUNDING_ITEM_KINDS, "funding_llm_triage_item_kind"),
    UniqueConstraint("run_id", "item_kind", "canonical_item_id", name="uq_funding_llm_triage_item"),
)

saved_funding_items = Table(
    "saved_funding_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("item_kind", String(40), nullable=False),
    Column("canonical_item_id", Integer, nullable=False),
    Column("saved_at", String, server_default=func.current_timestamp()),
    Column("notes", Text),
    Column("workflow_state", String(40), nullable=False, default="saved"),
    Column("last_checked_at", String),
    Column("last_known_status", String(80)),
    Column("last_known_deadline", String(80)),
    enum_check("item_kind", FUNDING_ITEM_KINDS, "saved_funding_item_kind"),
    enum_check("workflow_state", FUNDING_WORKFLOW_STATES, "saved_funding_workflow_state"),
    UniqueConstraint("item_kind", "canonical_item_id", name="uq_saved_funding_item"),
)

saved_funding_refresh_events = Table(
    "saved_funding_refresh_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("saved_item_id", ForeignKey("saved_funding_items.id", ondelete="CASCADE"), nullable=False),
    Column("item_kind", String(40), nullable=False),
    Column("canonical_item_id", Integer, nullable=False),
    Column("outcome", String(80), nullable=False),
    Column("provider_status", String(120)),
    Column("changes_json", JSON, nullable=False, default=list),
    Column("linked_opportunity_id", ForeignKey("funding_opportunities.id", ondelete="SET NULL")),
    Column("checked_at", String, server_default=func.current_timestamp()),
)

funding_source_batches = Table(
    "funding_source_batches",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("provider_id", String(120), nullable=False),
    Column("batch_key", String(300), nullable=False),
    Column("indexed_through", String(120)),
    Column("watermark_json", JSON, nullable=False, default=dict),
    Column("status", String(40), nullable=False, default="indexed"),
    Column("created_at", String, server_default=func.current_timestamp()),
    Column("updated_at", String, server_default=func.current_timestamp()),
    UniqueConstraint("provider_id", "batch_key", name="uq_funding_source_batch"),
)

Index("ix_funding_awards_org", funding_historical_awards.c.organization_id)
Index("ix_funding_llm_triage_run", funding_llm_triage_annotations.c.run_id)
Index("ix_funding_prospects_run", funding_prospects.c.run_id)
Index("ix_funding_opportunities_run", funding_opportunities.c.run_id)
Index("ix_saved_funding_refresh_events_saved_item", saved_funding_refresh_events.c.saved_item_id)
