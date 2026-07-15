"""Persistence helpers for Funding Discovery."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import Connection, insert, select, update

from app.backend.funding.domain import (
    ApplicationSurface,
    FundingOpportunity,
    FundingProspect,
    HistoricalAward,
    ProviderStatus,
    ResearchFundingProfile,
)
from app.backend.persistence.schema import (
    funding_application_surfaces,
    funding_historical_awards,
    funding_opportunities,
    funding_organizations,
    funding_prospects,
    funding_schemes,
    funding_search_runs,
    research_funding_profiles,
)
from app.backend.persistence.sqlite_retry import retry_sqlite_locked


def persist_search_result(
    conn: Connection,
    *,
    profile: ResearchFundingProfile,
    awards: list[HistoricalAward],
    opportunities: list[FundingOpportunity],
    recurring_schemes: list[FundingProspect],
    prospects: list[FundingProspect],
    surfaces: list[ApplicationSurface],
    statuses: list[ProviderStatus],
) -> dict[str, Any]:
    profile_id = _insert_profile(conn, profile)
    counts = {
        "opportunities": len(opportunities),
        "recurring_schemes": len(recurring_schemes),
        "prospects": len(prospects),
        "historical_awards": len(awards),
    }
    run_id = _write(
        conn,
        insert(funding_search_runs).values(
            profile_id=profile_id,
            status="done",
            provider_statuses_json=[s.to_dict() for s in statuses],
            result_counts_json=counts,
        ),
    ).inserted_primary_key[0]
    for award in awards:
        _insert_award(conn, award)
    opportunity_rows = [_insert_opportunity(conn, run_id, o) for o in opportunities]
    scheme_rows = [_insert_prospect(conn, run_id, s) for s in recurring_schemes]
    prospect_rows = [_insert_prospect(conn, run_id, p) for p in prospects]
    surface_rows = [_insert_surface(conn, s) for s in surfaces]
    return {
        "run_id": run_id,
        "profile": profile.to_dict(),
        "provider_statuses": [s.to_dict() for s in statuses],
        "open_opportunities": opportunity_rows,
        "recurring_schemes": scheme_rows,
        "funding_prospects": prospect_rows,
        "application_surfaces": surface_rows,
        "result_counts": counts,
    }


def _insert_profile(conn: Connection, profile: ResearchFundingProfile) -> int:
    return _write(
        conn,
        insert(research_funding_profiles).values(
            source_kind=profile.source_kind,
            source_id=profile.source_id,
            title=profile.title,
            facets_json={k: [f.to_dict() for f in v] for k, v in profile.facets.items()},
            applicant_context_json=profile.applicant_context,
            preferences_json=profile.funding_preferences,
            provenance_json=[p.to_dict() for p in profile.provenance],
        ),
    ).inserted_primary_key[0]


def _org_id(conn: Connection, name: str) -> int:
    display = (name or "Unresolved funder").strip()
    row = conn.execute(
        select(funding_organizations.c.id).where(funding_organizations.c.display_name == display)
    ).first()
    if row:
        return int(row[0])
    return _write(
        conn,
        insert(funding_organizations).values(
            display_name=display,
            organization_type=None,
            identifiers_json={},
            aliases_json=[],
            geography_json={},
            resolution_status="probable" if display != "Unresolved funder" else "unresolved",
            provenance_json=[],
        ),
    ).inserted_primary_key[0]


def _scheme_id(conn: Connection, org_id: int, name: str | None, recurrence: dict[str, Any] | None = None) -> int | None:
    if not name:
        return None
    row = conn.execute(
        select(funding_schemes.c.id).where(funding_schemes.c.organization_id == org_id, funding_schemes.c.name == name)
    ).first()
    if row:
        return int(row[0])
    return _write(
        conn,
        insert(funding_schemes).values(
            organization_id=org_id,
            name=name,
            recurrence_json=recurrence or {},
            provenance_json=[],
        ),
    ).inserted_primary_key[0]


def _insert_award(conn: Connection, award: HistoricalAward) -> int:
    existing = (
        conn.execute(
            select(funding_historical_awards.c.id).where(
                funding_historical_awards.c.source_kind == award.source_kind,
                funding_historical_awards.c.source_record_id == award.source_record_id,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        return int(existing)
    org_id = _org_id(conn, award.organization_name)
    scheme_id = _scheme_id(conn, org_id, award.scheme_name)
    return _write(
        conn,
        insert(funding_historical_awards).values(
            organization_id=org_id,
            scheme_id=scheme_id,
            recipient_name_raw=award.recipient_name_raw if not award.recipient_is_individual else None,
            recipient_is_individual=1 if award.recipient_is_individual else 0,
            award_number=award.award_number,
            title=award.title,
            purpose_text=award.purpose_text,
            amount_json=award.amount,
            tax_year=award.tax_year,
            source_kind=award.source_kind,
            source_record_id=award.source_record_id,
            provenance_json=[p.to_dict() for p in award.provenance],
        ),
    ).inserted_primary_key[0]


def _insert_prospect(conn: Connection, run_id: int, prospect: FundingProspect) -> dict[str, Any]:
    org_id = _org_id(conn, prospect.organization_name)
    scheme_id = _scheme_id(conn, org_id, prospect.scheme_name)
    row_id = _write(
        conn,
        insert(funding_prospects).values(
            organization_id=org_id,
            scheme_id=scheme_id,
            prospect_kind=prospect.prospect_kind,
            evidence_freshness=prospect.evidence_freshness,
            signals_json=[s.to_dict() for s in prospect.signals],
            identity_resolution_quality=prospect.identity_resolution_quality,
            run_id=run_id,
        ),
    ).inserted_primary_key[0]
    return {
        "id": row_id,
        "organization_name": prospect.organization_name,
        "scheme_name": prospect.scheme_name,
        "prospect_kind": prospect.prospect_kind,
        "evidence_freshness": prospect.evidence_freshness,
        "identity_resolution_quality": prospect.identity_resolution_quality,
        "signals": [s.to_dict() for s in prospect.signals],
    }


def _insert_opportunity(
    conn: Connection, run_id: int | None, opp: FundingOpportunity, *, scheme_id: int | None = None
) -> dict[str, Any]:
    org_id = _org_id(conn, opp.organization_name)
    existing = (
        conn.execute(
            select(funding_opportunities.c.id).where(
                funding_opportunities.c.provider_id == opp.provider_id,
                funding_opportunities.c.provider_opportunity_id == opp.provider_opportunity_id,
            )
        )
        .scalars()
        .first()
    )
    values = dict(
        organization_id=org_id,
        provider_id=opp.provider_id,
        provider_opportunity_id=opp.provider_opportunity_id,
        title=opp.title,
        summary=opp.summary,
        status=opp.status,
        deadlines_json=opp.deadlines,
        amount_json=opp.amount,
        eligibility_json=opp.eligibility or {"assessment": "not_assessed", "label": "Not assessed"},
        source_url=opp.source_url,
        content_hash=_hash({"title": opp.title, "status": opp.status, "deadlines": opp.deadlines}),
        provenance_json=[p.to_dict() for p in opp.provenance],
    )
    if run_id is not None:
        values["run_id"] = run_id
    if scheme_id is not None:
        values["scheme_id"] = scheme_id
    if existing:
        _write(conn, update(funding_opportunities).where(funding_opportunities.c.id == existing).values(**values))
        row_id = int(existing)
    else:
        row_id = _write(conn, insert(funding_opportunities).values(**values)).inserted_primary_key[0]
    return {"id": row_id, "organization_name": opp.organization_name, **_opp_dict(opp)}


def _insert_surface(conn: Connection, surface: ApplicationSurface) -> dict[str, Any]:
    org_id = _org_id(conn, surface.organization_name)
    scheme_id = _scheme_id(conn, org_id, surface.scheme_name)
    row_id = _write(
        conn,
        insert(funding_application_surfaces).values(
            organization_id=org_id,
            scheme_id=scheme_id,
            surface_type=surface.surface_type,
            access_mode=surface.access_mode,
            actionability=surface.actionability,
            url=surface.url,
            details=surface.details,
            provenance_json=[p.to_dict() for p in surface.provenance],
        ),
    ).inserted_primary_key[0]
    return {"id": row_id, **surface.__dict__, "provenance": [p.to_dict() for p in surface.provenance]}


def _opp_dict(opp: FundingOpportunity) -> dict[str, Any]:
    return {
        "provider_id": opp.provider_id,
        "provider_opportunity_id": opp.provider_opportunity_id,
        "title": opp.title,
        "status": opp.status,
        "summary": opp.summary,
        "deadlines": opp.deadlines,
        "amount": opp.amount,
        "eligibility": opp.eligibility or {"assessment": "not_assessed", "label": "Not assessed"},
        "source_url": opp.source_url,
        "provenance": [p.to_dict() for p in opp.provenance],
    }


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _write(conn: Connection, statement):
    return retry_sqlite_locked(lambda: conn.execute(statement))
