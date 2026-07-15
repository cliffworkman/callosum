"""Saved Funding Discovery item persistence and refresh helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import Connection, delete, insert, or_, select, update

from app.backend.funding.domain import ApplicationSurface, FundingOpportunity
from app.backend.funding.repo import _hash, _insert_opportunity, _insert_surface, _org_id, _write
from app.backend.persistence.schema import (
    funding_opportunities,
    funding_organizations,
    funding_prospects,
    funding_schemes,
    saved_funding_items,
    saved_funding_refresh_events,
)
from app.backend.persistence.schema_funding import FUNDING_WORKFLOW_STATES


def save_item(conn: Connection, *, item_kind: str, canonical_item_id: int, notes: str | None = None) -> dict[str, Any]:
    snapshot = _saved_item_snapshot(conn, item_kind, canonical_item_id)
    if snapshot is None:
        raise ValueError("Funding item not found")
    existing = (
        conn.execute(
            select(saved_funding_items).where(
                saved_funding_items.c.item_kind == item_kind,
                saved_funding_items.c.canonical_item_id == canonical_item_id,
            )
        )
        .mappings()
        .first()
    )
    values = {"notes": notes, "workflow_state": "saved", **snapshot}
    if existing:
        _write(conn, update(saved_funding_items).where(saved_funding_items.c.id == existing["id"]).values(**values))
        item_id = existing["id"]
    else:
        item_id = _write(
            conn,
            insert(saved_funding_items).values(item_kind=item_kind, canonical_item_id=canonical_item_id, **values),
        ).inserted_primary_key[0]
    row = conn.execute(select(saved_funding_items).where(saved_funding_items.c.id == item_id)).mappings().one()
    return dict(row)


def list_saved_items(conn: Connection) -> list[dict[str, Any]]:
    rows = (
        conn.execute(
            select(saved_funding_items).order_by(saved_funding_items.c.saved_at.desc(), saved_funding_items.c.id.desc())
        )
        .mappings()
        .all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.update(_saved_item_display(conn, item["item_kind"], int(item["canonical_item_id"])))
        item["refresh_events"] = _recent_refresh_events(conn, int(item["id"]))
        items.append(item)
    return items


def unsave_item(conn: Connection, item_id: int) -> dict[str, Any]:
    row = conn.execute(select(saved_funding_items).where(saved_funding_items.c.id == item_id)).mappings().first()
    if row is None:
        raise ValueError("Saved funding item not found")
    _write(conn, delete(saved_funding_items).where(saved_funding_items.c.id == item_id))
    return {"id": item_id, "item_kind": row["item_kind"], "canonical_item_id": row["canonical_item_id"]}


def update_saved_item(
    conn: Connection, item_id: int, *, workflow_state: str | None = None, notes: str | None = None
) -> dict[str, Any]:
    row = conn.execute(select(saved_funding_items).where(saved_funding_items.c.id == item_id)).mappings().first()
    if row is None:
        raise ValueError("Saved funding item not found")
    values: dict[str, Any] = {}
    if workflow_state is not None:
        if workflow_state not in FUNDING_WORKFLOW_STATES:
            raise ValueError("Unknown saved funding workflow state")
        values["workflow_state"] = workflow_state
    if notes is not None:
        values["notes"] = notes
    if values:
        _write(conn, update(saved_funding_items).where(saved_funding_items.c.id == item_id).values(**values))
    updated = conn.execute(select(saved_funding_items).where(saved_funding_items.c.id == item_id)).mappings().one()
    item = dict(updated)
    item.update(_saved_item_display(conn, item["item_kind"], int(item["canonical_item_id"])))
    return item


RefreshLookupResult = tuple[FundingOpportunity | None, str]
OpportunityDetailLookup = Callable[[str, str], RefreshLookupResult]
ApplicationSurfaceLookup = Callable[[str, dict[str, Any]], RefreshLookupResult]


def refresh_saved_items(
    conn: Connection,
    opportunity_detail_lookup: OpportunityDetailLookup | None = None,
    application_surface_lookup: ApplicationSurfaceLookup | None = None,
) -> dict[str, Any]:
    rows = conn.execute(select(saved_funding_items)).mappings().all()
    changes: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()
    for row in rows:
        provider_status = None
        if row["item_kind"] == "opportunity" and opportunity_detail_lookup is not None:
            provider_status = _refresh_canonical_opportunity(conn, row, opportunity_detail_lookup)
        elif row["item_kind"] in {"prospect", "scheme"} and application_surface_lookup is not None:
            provider_status = _refresh_application_surface(conn, row, application_surface_lookup)
        current = _saved_item_snapshot(conn, row["item_kind"], int(row["canonical_item_id"]))
        if current is None:
            change = {
                "saved_item_id": row["id"],
                "item_kind": row["item_kind"],
                "canonical_item_id": row["canonical_item_id"],
                "status": "unavailable",
                "changes": [],
                "message": "Canonical funding record was not available during refresh.",
                "provider_status": provider_status,
            }
            _insert_refresh_event(conn, change, checked_at=now)
            changes.append(change)
            continue
        old_status = row["last_known_status"]
        old_deadline = row["last_known_deadline"]
        values = {
            "last_checked_at": now,
            "last_known_status": current["last_known_status"],
            "last_known_deadline": current["last_known_deadline"],
        }
        _write(conn, update(saved_funding_items).where(saved_funding_items.c.id == row["id"]).values(**values))
        item_changes: list[dict[str, Any]] = []
        if old_status != current["last_known_status"]:
            item_changes.append({"field": "status", "before": old_status, "after": current["last_known_status"]})
        if old_deadline != current["last_known_deadline"]:
            item_changes.append({"field": "deadline", "before": old_deadline, "after": current["last_known_deadline"]})
        change = {
            "saved_item_id": row["id"],
            "item_kind": row["item_kind"],
            "canonical_item_id": row["canonical_item_id"],
            "status": "changed" if item_changes else "unchanged",
            "changes": item_changes,
            "message": _refresh_message(row["item_kind"], item_changes),
            "provider_status": provider_status,
        }
        _insert_refresh_event(conn, change, checked_at=now)
        changes.append(change)
    return {"refreshed_at": now, "changes": changes, "items": list_saved_items(conn)}


def _refresh_application_surface(
    conn: Connection, saved_row: Any, application_surface_lookup: ApplicationSurfaceLookup
) -> str:
    context = _prospect_context(conn, int(saved_row["canonical_item_id"]))
    if context is None:
        return "canonical_unavailable"
    refreshed, status = application_surface_lookup(str(saved_row["item_kind"]), context)
    if refreshed is None:
        return status
    opportunity_row = _insert_opportunity(conn, None, refreshed, scheme_id=context.get("scheme_id"))
    _insert_surface(
        conn,
        ApplicationSurface(
            organization_name=refreshed.organization_name,
            scheme_name=context.get("scheme_name"),
            surface_type="official_api",
            access_mode="open_rfp" if refreshed.status in {"open", "forecasted"} else "unknown",
            actionability="open_opportunity" if refreshed.status in {"open", "forecasted"} else "unknown",
            url=refreshed.source_url,
            details=f"Saved {saved_row['item_kind']} refresh found current provider-backed opportunity evidence.",
            provenance=refreshed.provenance,
        ),
    )
    return f"application_surface_refreshed:{opportunity_row['id']}"


def _refresh_canonical_opportunity(
    conn: Connection, saved_row: Any, opportunity_detail_lookup: OpportunityDetailLookup
) -> str:
    row = (
        conn.execute(
            select(
                funding_opportunities.c.provider_id,
                funding_opportunities.c.provider_opportunity_id,
            ).where(funding_opportunities.c.id == int(saved_row["canonical_item_id"]))
        )
        .mappings()
        .first()
    )
    if row is None:
        return "canonical_unavailable"
    refreshed, status = opportunity_detail_lookup(str(row["provider_id"]), str(row["provider_opportunity_id"]))
    if refreshed is None:
        return status
    _update_canonical_opportunity(conn, int(saved_row["canonical_item_id"]), refreshed)
    return "refreshed"


def _update_canonical_opportunity(conn: Connection, opportunity_id: int, opp: FundingOpportunity) -> None:
    org_id = _org_id(conn, opp.organization_name)
    _write(
        conn,
        update(funding_opportunities)
        .where(funding_opportunities.c.id == opportunity_id)
        .values(
            organization_id=org_id,
            title=opp.title,
            summary=opp.summary,
            status=opp.status,
            deadlines_json=opp.deadlines,
            amount_json=opp.amount,
            eligibility_json=opp.eligibility or {"assessment": "not_assessed", "label": "Not assessed"},
            source_url=opp.source_url,
            fetched_at=datetime.now(UTC).isoformat(),
            content_hash=_hash({"title": opp.title, "status": opp.status, "deadlines": opp.deadlines}),
            provenance_json=[p.to_dict() for p in opp.provenance],
        ),
    )


def _refresh_message(item_kind: str, changes: list[dict[str, Any]]) -> str:
    if changes:
        return "Saved snapshot changed; review the updated status/deadline evidence."
    if item_kind in {"prospect", "scheme"}:
        return "No current application surface was verified by this saved-item snapshot refresh."
    return "No status or deadline change was detected in the current saved-item snapshot."


def _insert_refresh_event(conn: Connection, change: dict[str, Any], *, checked_at: str) -> None:
    _write(
        conn,
        insert(saved_funding_refresh_events).values(
            saved_item_id=change["saved_item_id"],
            item_kind=change["item_kind"],
            canonical_item_id=change["canonical_item_id"],
            outcome=_refresh_outcome(change),
            provider_status=change.get("provider_status"),
            changes_json=change.get("changes") or [],
            linked_opportunity_id=_linked_opportunity_id_from_status(change.get("provider_status")),
            checked_at=checked_at,
        ),
    )


def _recent_refresh_events(conn: Connection, saved_item_id: int, *, limit: int = 5) -> list[dict[str, Any]]:
    rows = (
        conn.execute(
            select(saved_funding_refresh_events)
            .where(saved_funding_refresh_events.c.saved_item_id == saved_item_id)
            .order_by(saved_funding_refresh_events.c.checked_at.desc(), saved_funding_refresh_events.c.id.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    return [
        {
            "id": int(row["id"]),
            "outcome": row["outcome"],
            "provider_status": row["provider_status"],
            "changes": row["changes_json"] or [],
            "linked_opportunity_id": row["linked_opportunity_id"],
            "checked_at": row["checked_at"],
        }
        for row in rows
    ]


def _refresh_outcome(change: dict[str, Any]) -> str:
    provider_status = str(change.get("provider_status") or "")
    if provider_status.startswith("application_surface_refreshed"):
        return "current_opportunity_found"
    if provider_status == "provider_unavailable":
        return "provider_unavailable"
    if provider_status == "no_current_application_window_verified":
        return "no_current_application_window_verified"
    if change.get("status") == "unavailable":
        return "saved_item_unavailable"
    fields = {c.get("field") for c in change.get("changes") or [] if isinstance(c, dict)}
    if "status" in fields:
        return "status_changed"
    if "deadline" in fields:
        return "deadline_changed"
    return "unchanged"


def _linked_opportunity_id_from_status(provider_status: Any) -> int | None:
    text = str(provider_status or "")
    if not text.startswith("application_surface_refreshed:"):
        return None
    try:
        return int(text.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _saved_item_snapshot(conn: Connection, item_kind: str, canonical_item_id: int) -> dict[str, Any] | None:
    if item_kind == "opportunity":
        row = (
            conn.execute(
                select(
                    funding_opportunities.c.status,
                    funding_opportunities.c.deadlines_json,
                    funding_opportunities.c.fetched_at,
                ).where(funding_opportunities.c.id == canonical_item_id)
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        return {
            "last_checked_at": row["fetched_at"],
            "last_known_status": row["status"],
            "last_known_deadline": _first_deadline(row["deadlines_json"]),
        }
    if item_kind in {"prospect", "scheme"}:
        context = _prospect_context(conn, canonical_item_id)
        if context is None:
            return None
        linked = _linked_current_opportunity(conn, context["organization_id"], context.get("scheme_id"))
        if linked is not None:
            label = "open_opportunity" if linked["status"] == "open" else "forecasted_opportunity"
            return {
                "last_checked_at": linked["fetched_at"],
                "last_known_status": label,
                "last_known_deadline": _first_deadline(linked["deadlines_json"]),
            }
        return {
            "last_checked_at": context["surfaced_at"],
            "last_known_status": "recurring_scheme" if item_kind == "scheme" else "prospect",
            "last_known_deadline": None,
        }
    return None


def _saved_item_display(conn: Connection, item_kind: str, canonical_item_id: int) -> dict[str, Any]:
    if item_kind == "opportunity":
        row = (
            conn.execute(
                select(
                    funding_opportunities.c.title,
                    funding_opportunities.c.status,
                    funding_opportunities.c.deadlines_json,
                    funding_opportunities.c.source_url,
                    funding_organizations.c.display_name.label("organization_name"),
                )
                .select_from(
                    funding_opportunities.join(
                        funding_organizations,
                        funding_opportunities.c.organization_id == funding_organizations.c.id,
                    )
                )
                .where(funding_opportunities.c.id == canonical_item_id)
            )
            .mappings()
            .first()
        )
        if not row:
            return {
                "title": "Unavailable saved opportunity",
                "organization_name": None,
                "display_status": "unavailable",
            }
        return {
            "title": row["title"],
            "organization_name": row["organization_name"],
            "display_status": row["status"],
            "next_deadline": _first_deadline(row["deadlines_json"]),
            "source_url": row["source_url"],
        }
    row = (
        conn.execute(
            select(
                funding_prospects.c.organization_id,
                funding_prospects.c.scheme_id,
                funding_prospects.c.prospect_kind,
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
            .where(funding_prospects.c.id == canonical_item_id)
        )
        .mappings()
        .first()
    )
    if not row:
        return {"title": "Unavailable saved funding item", "organization_name": None, "display_status": "unavailable"}
    linked = _linked_current_opportunity(conn, int(row["organization_id"]), row["scheme_id"])
    title = row["scheme_name"] if item_kind == "scheme" and row["scheme_name"] else row["organization_name"]
    return {
        "title": title,
        "organization_name": row["organization_name"],
        "scheme_name": row["scheme_name"],
        "display_status": (
            ("open_opportunity" if linked["status"] == "open" else "forecasted_opportunity")
            if linked is not None
            else ("recurring_scheme" if item_kind == "scheme" else "prospect")
        ),
        "linked_opportunity_id": int(linked["id"]) if linked is not None else None,
        "linked_opportunity_title": linked["title"] if linked is not None else None,
        "next_deadline": _first_deadline(linked["deadlines_json"]) if linked is not None else None,
        "source_url": linked["source_url"] if linked is not None else None,
        "identity_resolution_quality": row["identity_resolution_quality"],
    }


def _prospect_context(conn: Connection, prospect_id: int) -> dict[str, Any] | None:
    row = (
        conn.execute(
            select(
                funding_prospects.c.id,
                funding_prospects.c.organization_id,
                funding_prospects.c.scheme_id,
                funding_prospects.c.surfaced_at,
                funding_organizations.c.display_name.label("organization_name"),
                funding_schemes.c.name.label("scheme_name"),
            )
            .select_from(
                funding_prospects.join(
                    funding_organizations,
                    funding_prospects.c.organization_id == funding_organizations.c.id,
                ).outerjoin(funding_schemes, funding_prospects.c.scheme_id == funding_schemes.c.id)
            )
            .where(funding_prospects.c.id == prospect_id)
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _linked_current_opportunity(conn: Connection, organization_id: int, scheme_id: int | None):
    rows = (
        conn.execute(
            select(funding_opportunities)
            .where(
                funding_opportunities.c.organization_id == organization_id,
                funding_opportunities.c.status.in_(["open", "forecasted"]),
                or_(funding_opportunities.c.scheme_id == scheme_id, funding_opportunities.c.scheme_id.is_(None)),
            )
            .order_by(funding_opportunities.c.fetched_at.desc(), funding_opportunities.c.id.desc())
        )
        .mappings()
        .all()
    )
    if scheme_id is not None:
        exact = [row for row in rows if row["scheme_id"] == scheme_id]
        if exact:
            return exact[0]
    return rows[0] if rows else None


def _first_deadline(deadlines: Any) -> str | None:
    if not isinstance(deadlines, list):
        return None
    for deadline in deadlines:
        if isinstance(deadline, dict) and deadline.get("date"):
            return str(deadline["date"])
    return None
