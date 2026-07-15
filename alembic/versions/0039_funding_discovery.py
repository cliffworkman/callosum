"""funding_discovery — normalized funding discovery entities.

Revision ID: 0039_funding_discovery
Revises: 0038_reference_integrity
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

from alembic import op

revision = "0039_funding_discovery"
down_revision = "0038_reference_integrity"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "funding_organizations" not in tables:
        op.create_table(
            "funding_organizations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("display_name", sa.String(length=500), nullable=False),
            sa.Column("organization_type", sa.String(length=80)),
            sa.Column("identifiers_json", sqlite.JSON(), nullable=False),
            sa.Column("aliases_json", sqlite.JSON(), nullable=False),
            sa.Column("website", sa.String(length=1000)),
            sa.Column("geography_json", sqlite.JSON(), nullable=False),
            sa.Column("resolution_status", sa.String(length=40), nullable=False, server_default="unresolved"),
            sa.Column("provenance_json", sqlite.JSON(), nullable=False),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("display_name", name="uq_funding_org_display_name"),
        )
    if "funding_schemes" not in tables:
        op.create_table(
            "funding_schemes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("funding_organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=500), nullable=False),
            sa.Column("scheme_type", sa.String(length=80)),
            sa.Column("recurrence_json", sqlite.JSON(), nullable=False),
            sa.Column("official_url", sa.String(length=1000)),
            sa.Column("provenance_json", sqlite.JSON(), nullable=False),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("organization_id", "name", name="uq_funding_scheme_org_name"),
        )
    if "research_funding_profiles" not in tables:
        op.create_table(
            "research_funding_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_kind", sa.String(length=80), nullable=False),
            sa.Column("source_id", sa.String(length=200)),
            sa.Column("title", sa.String(length=1000)),
            sa.Column("facets_json", sqlite.JSON(), nullable=False),
            sa.Column("applicant_context_json", sqlite.JSON(), nullable=False),
            sa.Column("preferences_json", sqlite.JSON(), nullable=False),
            sa.Column("provenance_json", sqlite.JSON(), nullable=False),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
        )
    if "funding_search_runs" not in tables:
        op.create_table(
            "funding_search_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("research_funding_profiles.id", ondelete="SET NULL")),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="done"),
            sa.Column("provider_statuses_json", sqlite.JSON(), nullable=False),
            sa.Column("result_counts_json", sqlite.JSON(), nullable=False),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
        )
    if "funding_historical_awards" not in tables:
        op.create_table(
            "funding_historical_awards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("funding_organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("funding_schemes.id", ondelete="SET NULL")),
            sa.Column(
                "recipient_organization_id",
                sa.Integer(),
                sa.ForeignKey("funding_organizations.id", ondelete="SET NULL"),
            ),
            sa.Column("recipient_name_raw", sa.String(length=500)),
            sa.Column("recipient_is_individual", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("award_number", sa.String(length=200)),
            sa.Column("title", sa.String(length=1000)),
            sa.Column("purpose_text", sa.Text()),
            sa.Column("amount_json", sqlite.JSON(), nullable=False),
            sa.Column("start_date", sa.String(length=40)),
            sa.Column("end_date", sa.String(length=40)),
            sa.Column("tax_year", sa.Integer()),
            sa.Column("source_kind", sa.String(length=80), nullable=False),
            sa.Column("source_record_id", sa.String(length=500), nullable=False),
            sa.Column("provenance_json", sqlite.JSON(), nullable=False),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("source_kind", "source_record_id", name="uq_funding_award_source"),
        )
        op.create_index("ix_funding_awards_org", "funding_historical_awards", ["organization_id"])
    if "funding_prospects" not in tables:
        op.create_table(
            "funding_prospects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("funding_organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("funding_schemes.id", ondelete="SET NULL")),
            sa.Column("prospect_kind", sa.String(length=40), nullable=False),
            sa.Column("evidence_freshness", sa.String(length=40), nullable=False, server_default="unknown"),
            sa.Column("signals_json", sqlite.JSON(), nullable=False),
            sa.Column("identity_resolution_quality", sa.String(length=40), nullable=False, server_default="low"),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("funding_search_runs.id", ondelete="SET NULL")),
            sa.Column("surfaced_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.CheckConstraint(
                "prospect_kind IN ('organization', 'scheme')", name="ck_funding_prospects_funding_prospect_kind"
            ),
        )
        op.create_index("ix_funding_prospects_run", "funding_prospects", ["run_id"])
    if "funding_opportunities" not in tables:
        op.create_table(
            "funding_opportunities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("funding_organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("funding_schemes.id", ondelete="SET NULL")),
            sa.Column("provider_id", sa.String(length=120), nullable=False),
            sa.Column("provider_opportunity_id", sa.String(length=300), nullable=False),
            sa.Column("title", sa.String(length=1000), nullable=False),
            sa.Column("summary", sa.Text()),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="unknown"),
            sa.Column("opportunity_type", sa.String(length=200)),
            sa.Column("opens_at", sa.String(length=40)),
            sa.Column("deadlines_json", sqlite.JSON(), nullable=False),
            sa.Column("amount_json", sqlite.JSON(), nullable=False),
            sa.Column("expected_awards", sa.Integer()),
            sa.Column("eligibility_json", sqlite.JSON(), nullable=False),
            sa.Column("source_url", sa.String(length=1000)),
            sa.Column("source_updated_at", sa.String(length=80)),
            sa.Column("fetched_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("content_hash", sa.String(length=80)),
            sa.Column("provenance_json", sqlite.JSON(), nullable=False),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("funding_search_runs.id", ondelete="SET NULL")),
            sa.UniqueConstraint("provider_id", "provider_opportunity_id", name="uq_funding_opp_provider"),
        )
        op.create_index("ix_funding_opportunities_run", "funding_opportunities", ["run_id"])
    if "funding_application_surfaces" not in tables:
        op.create_table(
            "funding_application_surfaces",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("funding_organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("funding_schemes.id", ondelete="SET NULL")),
            sa.Column("surface_type", sa.String(length=80), nullable=False),
            sa.Column("access_mode", sa.String(length=80)),
            sa.Column("actionability", sa.String(length=80), nullable=False, server_default="unknown"),
            sa.Column("url", sa.String(length=1000)),
            sa.Column("details", sa.Text()),
            sa.Column("checked_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("provenance_json", sqlite.JSON(), nullable=False),
        )
    if "saved_funding_items" not in tables:
        op.create_table(
            "saved_funding_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("item_kind", sa.String(length=40), nullable=False),
            sa.Column("canonical_item_id", sa.Integer(), nullable=False),
            sa.Column("saved_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("notes", sa.Text()),
            sa.Column("workflow_state", sa.String(length=40), nullable=False, server_default="saved"),
            sa.Column("last_checked_at", sa.String()),
            sa.Column("last_known_status", sa.String(length=80)),
            sa.Column("last_known_deadline", sa.String(length=80)),
            sa.CheckConstraint(
                "item_kind IN ('opportunity', 'scheme', 'prospect')",
                name="ck_saved_funding_items_saved_funding_item_kind",
            ),
            sa.CheckConstraint(
                "workflow_state IN ('saved', 'reviewing', 'considering', 'planning', 'applying', 'submitted', 'archived')",
                name="ck_saved_funding_items_saved_funding_workflow_state",
            ),
            sa.UniqueConstraint("item_kind", "canonical_item_id", name="uq_saved_funding_item"),
        )
    if "funding_source_batches" not in tables:
        op.create_table(
            "funding_source_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider_id", sa.String(length=120), nullable=False),
            sa.Column("batch_key", sa.String(length=300), nullable=False),
            sa.Column("indexed_through", sa.String(length=120)),
            sa.Column("watermark_json", sqlite.JSON(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="indexed"),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("provider_id", "batch_key", name="uq_funding_source_batch"),
        )


def downgrade() -> None:
    pass
