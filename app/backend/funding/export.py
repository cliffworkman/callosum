"""CSV export read model for Funding Discovery runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, select

from app.backend.funding.triage_repo import llm_triage_annotation_for_item, load_llm_triage_annotations
from app.backend.persistence.schema import (
    funding_application_surfaces,
    funding_opportunities,
    funding_organizations,
    funding_prospects,
    funding_schemes,
    funding_search_runs,
)


def export_run_rows(conn: Connection, run_id: int) -> list[dict[str, Any]] | None:
    if conn.execute(select(funding_search_runs.c.id).where(funding_search_runs.c.id == run_id)).first() is None:
        return None
    triage = load_llm_triage_annotations(conn, run_id)
    rows: list[dict[str, Any]] = []
    rows.extend(_export_opportunity_rows(conn, run_id, triage))
    rows.extend(_export_prospect_rows(conn, run_id, triage))
    return rows


def _export_opportunity_rows(conn: Connection, run_id: int, triage: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = (
        conn.execute(
            select(
                funding_opportunities.c.id,
                funding_opportunities.c.organization_id,
                funding_opportunities.c.scheme_id,
                funding_opportunities.c.provider_id,
                funding_opportunities.c.title,
                funding_opportunities.c.status,
                funding_opportunities.c.deadlines_json,
                funding_opportunities.c.amount_json,
                funding_opportunities.c.eligibility_json,
                funding_opportunities.c.source_url,
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
    rows = []
    for row in records:
        item = {
            "id": row["id"],
            "status": row["status"],
            "deadlines": row["deadlines_json"] or [],
            "organization_name": row["organization_name"],
            "scheme_name": row["scheme_name"],
            "source_url": row["source_url"],
        }
        rows.append(
            _with_triage(
                {
                    "item_kind": "open_opportunity",
                    "canonical_item_id": row["id"],
                    "title": row["title"],
                    "organization_name": row["organization_name"],
                    "scheme_name": row["scheme_name"],
                    "status": row["status"],
                    "next_deadline": _first_deadline(row["deadlines_json"]),
                    "deadlines": _deadline_summary(row["deadlines_json"]),
                    "amount": _amount_summary(row["amount_json"]),
                    "eligibility": (row["eligibility_json"] or {}).get("label") or "Not assessed",
                    "identity_resolution_quality": "",
                    "source_provider": row["provider_id"],
                    "source_url": row["source_url"],
                    "application_route": _surface_summary(conn, row["organization_id"], row["scheme_id"]),
                    "top_signals": "",
                    "matched_facets": "",
                    "interpretation_boundary": (
                        "Current opportunity status was provider-backed at run time; eligibility still requires review."
                    ),
                },
                llm_triage_annotation_for_item(triage, "opportunity", item),
            )
        )
    return rows


def _export_prospect_rows(conn: Connection, run_id: int, triage: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = (
        conn.execute(
            select(
                funding_prospects.c.id,
                funding_prospects.c.organization_id,
                funding_prospects.c.scheme_id,
                funding_prospects.c.prospect_kind,
                funding_prospects.c.signals_json,
                funding_prospects.c.identity_resolution_quality,
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
    rows: list[dict[str, Any]] = []
    for row in records:
        signals = row["signals_json"] or []
        item_kind = "recurring_scheme" if row["prospect_kind"] == "scheme" else "funding_prospect"
        triage_kind = "scheme" if item_kind == "recurring_scheme" else "prospect"
        item = {
            "id": row["id"],
            "signals": signals,
            "organization_name": row["organization_name"],
            "scheme_name": row["scheme_name"],
        }
        rows.append(
            _with_triage(
                {
                    "item_kind": item_kind,
                    "canonical_item_id": row["id"],
                    "title": row["scheme_name"] or row["organization_name"],
                    "organization_name": row["organization_name"],
                    "scheme_name": row["scheme_name"],
                    "status": "current window not verified" if item_kind == "recurring_scheme" else "prospect only",
                    "next_deadline": "",
                    "deadlines": "",
                    "amount": "",
                    "eligibility": "Not assessed",
                    "identity_resolution_quality": row["identity_resolution_quality"],
                    "source_provider": _signal_sources(signals),
                    "source_url": "",
                    "application_route": _surface_summary(conn, row["organization_id"], row["scheme_id"]),
                    "top_signals": _signal_summary(signals),
                    "matched_facets": _facet_summary(signals),
                    "interpretation_boundary": (
                        "Repetition was detected from prior cycles; a current funding window was not verified."
                        if item_kind == "recurring_scheme"
                        else "Portfolio alignment is inferred from observed records; this is not an explicit funder policy."
                    ),
                },
                llm_triage_annotation_for_item(triage, triage_kind, item),
            )
        )
    return rows


def _with_triage(row: dict[str, Any], triage: dict[str, Any] | None) -> dict[str, Any]:
    row["llm_triage_label"] = triage.get("label") if triage else ""
    row["llm_triage_status"] = triage.get("status") if triage else ""
    row["llm_triage_show_in_triage"] = str(bool(triage.get("show_in_triage"))).lower() if triage else ""
    row["llm_triage_rationale"] = triage.get("rationale") if triage else ""
    row["llm_triage_prompt_version"] = triage.get("prompt_version") if triage else ""
    return row


def _first_deadline(deadlines: Any) -> str | None:
    if not isinstance(deadlines, list):
        return None
    for deadline in deadlines:
        if isinstance(deadline, dict) and deadline.get("date"):
            return str(deadline["date"])
    return None


def _deadline_summary(deadlines: Any) -> str:
    if not isinstance(deadlines, list):
        return ""
    parts = []
    for deadline in deadlines:
        if isinstance(deadline, dict) and deadline.get("date"):
            kind = str(deadline.get("kind") or "deadline").replace("_", " ")
            parts.append(f"{kind}: {deadline['date']}")
    return "; ".join(parts)


def _amount_summary(amount: Any) -> str:
    if not isinstance(amount, dict) or not amount:
        return ""
    currency = amount.get("currency") or ""
    if amount.get("min") or amount.get("max"):
        return f"{currency} {amount.get('min') or ''}-{amount.get('max') or ''}".strip()
    if amount.get("totalProgramFunding"):
        return f"{currency} {amount['totalProgramFunding']}".strip()
    if amount.get("value"):
        return f"{currency} {amount['value']}".strip()
    return ""


def _surface_summary(conn: Connection, organization_id: int, scheme_id: int | None) -> str:
    query = select(
        funding_application_surfaces.c.actionability,
        funding_application_surfaces.c.access_mode,
        funding_application_surfaces.c.surface_type,
        funding_application_surfaces.c.details,
        funding_application_surfaces.c.url,
    ).where(funding_application_surfaces.c.organization_id == organization_id)
    if scheme_id is not None:
        query = query.where(
            (funding_application_surfaces.c.scheme_id == scheme_id)
            | (funding_application_surfaces.c.scheme_id.is_(None))
        )
    records = conn.execute(query).mappings().all()
    parts = []
    for row in records[:3]:
        bits = [
            str(row["actionability"] or "unknown").replace("_", " "),
            str(row["access_mode"] or row["surface_type"] or "unknown").replace("_", " "),
        ]
        if row["details"]:
            bits.append(str(row["details"]))
        if row["url"]:
            bits.append(str(row["url"]))
        parts.append(" - ".join(bits))
    return "; ".join(parts)


def _signal_summary(signals: Any) -> str:
    if not isinstance(signals, list):
        return ""
    parts = []
    for signal in signals[:5]:
        if not isinstance(signal, dict):
            continue
        label = str(signal.get("signal_type") or "signal").replace("_", " ")
        explanation = str(signal.get("explanation") or "").strip()
        parts.append(f"{label}: {explanation}" if explanation else label)
    return "; ".join(parts)


def _facet_summary(signals: Any) -> str:
    if not isinstance(signals, list):
        return ""
    seen: list[str] = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        for facet in signal.get("matched_profile_facets") or []:
            if not isinstance(facet, dict):
                continue
            value = f"{facet.get('facet')}: {facet.get('value')}"
            if value not in seen:
                seen.append(value)
    return "; ".join(seen[:12])


def _signal_sources(signals: Any) -> str:
    if not isinstance(signals, list):
        return ""
    sources: list[str] = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        for evidence in signal.get("matched_evidence") or []:
            if not isinstance(evidence, dict):
                continue
            source = evidence.get("source_kind")
            if source and source not in sources:
                sources.append(str(source))
    return "; ".join(sources)
