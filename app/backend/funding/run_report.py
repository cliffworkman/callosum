"""Read model for persisted Funding Discovery runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, desc, func, select

from app.backend.funding.triage_repo import attach_llm_triage_annotations, load_llm_triage_annotations
from app.backend.persistence.schema import (
    funding_application_surfaces,
    funding_llm_triage_annotations,
    funding_opportunities,
    funding_organizations,
    funding_prospects,
    funding_schemes,
    funding_search_runs,
    research_funding_profiles,
)


def funding_run_summaries(conn: Connection, limit: int = 10) -> list[dict[str, Any]]:
    annotated = (
        select(
            funding_search_runs.c.id.label("run_id"),
            func.count(funding_llm_triage_annotations.c.id).label("llm_annotated_count"),
        )
        .select_from(
            funding_search_runs.outerjoin(
                funding_llm_triage_annotations,
                funding_search_runs.c.id == funding_llm_triage_annotations.c.run_id,
            )
        )
        .group_by(funding_search_runs.c.id)
        .subquery()
    )
    rows = (
        conn.execute(
            select(
                funding_search_runs.c.id,
                funding_search_runs.c.created_at,
                funding_search_runs.c.provider_statuses_json,
                funding_search_runs.c.result_counts_json,
                research_funding_profiles.c.source_kind,
                research_funding_profiles.c.source_id,
                research_funding_profiles.c.title,
                annotated.c.llm_annotated_count,
            )
            .outerjoin(research_funding_profiles, funding_search_runs.c.profile_id == research_funding_profiles.c.id)
            .outerjoin(annotated, funding_search_runs.c.id == annotated.c.run_id)
            .order_by(desc(funding_search_runs.c.id))
            .limit(max(1, min(int(limit), 25)))
        )
        .mappings()
        .all()
    )
    return [
        {
            "run_id": row["id"],
            "created_at": row["created_at"],
            "source_kind": row["source_kind"],
            "source_id": row["source_id"],
            "title": row["title"],
            "result_counts": row["result_counts_json"] or {},
            "provider_statuses": row["provider_statuses_json"] or [],
            "llm_annotated_count": int(row["llm_annotated_count"] or 0),
        }
        for row in rows
    ]


def funding_run_report(conn: Connection, run_id: int) -> dict[str, Any] | None:
    run = (
        conn.execute(
            select(
                funding_search_runs.c.id,
                funding_search_runs.c.profile_id,
                funding_search_runs.c.provider_statuses_json,
                funding_search_runs.c.result_counts_json,
                research_funding_profiles.c.source_kind,
                research_funding_profiles.c.source_id,
                research_funding_profiles.c.title,
                research_funding_profiles.c.facets_json,
                research_funding_profiles.c.applicant_context_json,
                research_funding_profiles.c.preferences_json,
                research_funding_profiles.c.provenance_json,
            )
            .outerjoin(research_funding_profiles, funding_search_runs.c.profile_id == research_funding_profiles.c.id)
            .where(funding_search_runs.c.id == run_id)
        )
        .mappings()
        .first()
    )
    if run is None:
        return None
    opportunities, org_ids = _opportunities(conn, run_id)
    recurring, prospects, prospect_org_ids = _prospects(conn, run_id)
    org_ids.update(prospect_org_ids)
    report = {
        "run_id": run_id,
        "profile": _profile(run),
        "provider_statuses": run["provider_statuses_json"] or [],
        "result_counts": run["result_counts_json"] or {},
        "open_opportunities": opportunities,
        "recurring_schemes": recurring,
        "funding_prospects": prospects,
        "application_surfaces": _surfaces(conn, org_ids),
    }
    annotations = load_llm_triage_annotations(conn, run_id)
    attach_llm_triage_annotations(report, annotations)
    report["llm_triage_status"] = _triage_status(annotations)
    return report


def _profile(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["profile_id"],
        "source_kind": row["source_kind"],
        "source_id": row["source_id"],
        "title": row["title"],
        "facets": row["facets_json"] or {},
        "applicant_context": row["applicant_context_json"] or {},
        "funding_preferences": row["preferences_json"] or {},
        "provenance": row["provenance_json"] or [],
    }


def _opportunities(conn: Connection, run_id: int) -> tuple[list[dict[str, Any]], set[int]]:
    records = (
        conn.execute(
            select(
                funding_opportunities,
                funding_organizations.c.display_name.label("organization_name"),
                funding_schemes.c.name.label("scheme_name"),
            )
            .select_from(
                funding_opportunities.join(
                    funding_organizations,
                    funding_opportunities.c.organization_id == funding_organizations.c.id,
                ).outerjoin(funding_schemes, funding_opportunities.c.scheme_id == funding_schemes.c.id)
            )
            .where(funding_opportunities.c.run_id == run_id)
        )
        .mappings()
        .all()
    )
    items = []
    org_ids: set[int] = set()
    for row in records:
        org_ids.add(int(row["organization_id"]))
        items.append(
            {
                "id": row["id"],
                "organization_name": row["organization_name"],
                "scheme_name": row["scheme_name"],
                "provider_id": row["provider_id"],
                "provider_opportunity_id": row["provider_opportunity_id"],
                "title": row["title"],
                "status": row["status"],
                "summary": row["summary"],
                "deadlines": row["deadlines_json"] or [],
                "amount": row["amount_json"] or {},
                "eligibility": row["eligibility_json"] or {"assessment": "not_assessed", "label": "Not assessed"},
                "source_url": row["source_url"],
                "provenance": row["provenance_json"] or [],
            }
        )
    return items, org_ids


def _prospects(conn: Connection, run_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[int]]:
    records = (
        conn.execute(
            select(
                funding_prospects,
                funding_organizations.c.display_name.label("organization_name"),
                funding_schemes.c.name.label("scheme_name"),
            )
            .select_from(
                funding_prospects.join(
                    funding_organizations,
                    funding_prospects.c.organization_id == funding_organizations.c.id,
                ).outerjoin(funding_schemes, funding_prospects.c.scheme_id == funding_schemes.c.id)
            )
            .where(funding_prospects.c.run_id == run_id)
        )
        .mappings()
        .all()
    )
    recurring: list[dict[str, Any]] = []
    prospects: list[dict[str, Any]] = []
    org_ids: set[int] = set()
    for row in records:
        org_ids.add(int(row["organization_id"]))
        item = {
            "id": row["id"],
            "organization_name": row["organization_name"],
            "scheme_name": row["scheme_name"],
            "prospect_kind": row["prospect_kind"],
            "evidence_freshness": row["evidence_freshness"],
            "identity_resolution_quality": row["identity_resolution_quality"],
            "signals": row["signals_json"] or [],
        }
        (recurring if row["prospect_kind"] == "scheme" else prospects).append(item)
    return recurring, prospects, org_ids


def _surfaces(conn: Connection, org_ids: set[int]) -> list[dict[str, Any]]:
    if not org_ids:
        return []
    records = (
        conn.execute(
            select(
                funding_application_surfaces,
                funding_organizations.c.display_name.label("organization_name"),
                funding_schemes.c.name.label("scheme_name"),
            )
            .select_from(
                funding_application_surfaces.join(
                    funding_organizations,
                    funding_application_surfaces.c.organization_id == funding_organizations.c.id,
                ).outerjoin(funding_schemes, funding_application_surfaces.c.scheme_id == funding_schemes.c.id)
            )
            .where(funding_application_surfaces.c.organization_id.in_(org_ids))
        )
        .mappings()
        .all()
    )
    return [
        {
            "id": row["id"],
            "organization_name": row["organization_name"],
            "scheme_name": row["scheme_name"],
            "surface_type": row["surface_type"],
            "access_mode": row["access_mode"],
            "actionability": row["actionability"],
            "url": row["url"],
            "details": row["details"],
            "provenance": row["provenance_json"] or [],
        }
        for row in records
    ]


def _triage_status(annotations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not annotations:
        return {
            "provider_id": "configured-llm",
            "status": "not_searched",
            "warning": "No persisted AI fit labels are available for this run.",
        }
    first = next(iter(annotations.values()))
    return {
        "provider_id": first.get("provider_id") or "configured-llm",
        "status": "success",
        "annotated_count": len(annotations),
        "prompt_version": first.get("prompt_version"),
    }
