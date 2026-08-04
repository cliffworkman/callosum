"""Persistence helpers for WIP manuscript reference-integrity signals (backlog #48).

Mirrors `reference_integrity_repo.py`'s fingerprint-scoped review semantics -- a review applies to one active
signal-set fingerprint only; a materially changed signal set gets a fresh unreviewed row instead of inheriting
an older dismissal. Signals attach directly to a `wip_references` row (already the canonical, deduped
`(manuscript_id, paper_id)` identity), so there is no entity/instance dedup layer to maintain here.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from sqlalchemy import Connection, delete, func, insert, select, update
from sqlalchemy.engine import RowMapping

from app.backend.methods.reference_integrity import signal_set_fingerprint
from app.backend.persistence.schema_wip_reference_integrity import (
    WIP_REFERENCE_REVIEW_STATES,
    wip_reference_reviews,
    wip_reference_signals,
)
from app.backend.persistence.schema_wip_workflow import wip_references
from app.backend.persistence.sqlite_retry import retry_sqlite_locked


def replace_reference_signals(
    conn: Connection, manuscript_id: int, reference_id: int, signals: list[Mapping[str, Any]]
) -> None:
    _write(conn, delete(wip_reference_signals).where(wip_reference_signals.c.reference_id == reference_id))
    for signal in signals:
        _write(
            conn,
            insert(wip_reference_signals).values(
                manuscript_id=manuscript_id,
                reference_id=reference_id,
                detector_kind=signal["detector_kind"],
                detector_status=signal["detector_status"],
                evidence_json=signal["evidence_json"],
                source=signal["source"],
                snapshot_marker=signal["snapshot_marker"],
                signal_key=signal["signal_key"],
            ),
        )
    ensure_current_review(conn, reference_id)


def ensure_current_review(conn: Connection, reference_id: int) -> str | None:
    signals = active_signals_for_reference(conn, reference_id)
    if not signals:
        return None
    fingerprint = signal_set_fingerprint(signals)
    existing = (
        conn.execute(
            select(wip_reference_reviews).where(
                wip_reference_reviews.c.reference_id == reference_id,
                wip_reference_reviews.c.signal_fingerprint == fingerprint,
            )
        )
        .mappings()
        .first()
    )
    if existing is None:
        _write(
            conn,
            insert(wip_reference_reviews).values(
                reference_id=reference_id,
                signal_fingerprint=fingerprint,
                state="unreviewed",
                review_snapshot_json={"signals": [_signal_snapshot(s) for s in signals]},
            ),
        )
    return fingerprint


def active_signals_for_reference(conn: Connection, reference_id: int) -> list[RowMapping]:
    return list(
        conn.execute(
            select(wip_reference_signals)
            .where(wip_reference_signals.c.reference_id == reference_id)
            .order_by(wip_reference_signals.c.detector_kind, wip_reference_signals.c.id)
        ).mappings()
    )


def set_reference_review_state(conn: Connection, reference_id: int, state: str) -> str:
    if state not in WIP_REFERENCE_REVIEW_STATES or state == "unreviewed":
        return "bad-state"
    signals = active_signals_for_reference(conn, reference_id)
    if not signals:
        return "no-active-signals"
    fingerprint = signal_set_fingerprint(signals)
    ensure_current_review(conn, reference_id)
    result = _write(
        conn,
        update(wip_reference_reviews)
        .where(
            wip_reference_reviews.c.reference_id == reference_id,
            wip_reference_reviews.c.signal_fingerprint == fingerprint,
        )
        .values(
            state=state,
            reviewed_at=func.current_timestamp(),
            review_snapshot_json={"signals": [_signal_snapshot(s) for s in signals]},
        ),
    )
    return "ok" if result.rowcount else "not-found"


def manuscript_reference_report(conn: Connection, manuscript_id: int) -> dict[str, Any]:
    rows = _current_rows(conn, manuscript_id)
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        rid = int(row["reference_id"])
        item = grouped.setdefault(rid, _reference_payload(row))
        if row["signal_id"] is not None:
            item["signals"].append(_signal_payload(row))
    items = list(grouped.values())
    items.sort(key=lambda item: (item["review_state"] == "dismissed", item["paper_title"] or ""))
    return {
        "manuscript_id": manuscript_id,
        "checked_count": len(items),
        "last_checked_at": _latest_checked_at(items),
        "items": [item for item in items if item["signals"]],
        "active_count": sum(1 for item in items if item["signals"] and item["review_state"] != "dismissed"),
    }


def _current_rows(conn: Connection, manuscript_id: int) -> list[dict[str, Any]]:
    from app.backend.persistence.schema import papers

    sig_cols = [
        wip_reference_signals.c.id.label("signal_id"),
        wip_reference_signals.c.detector_kind,
        wip_reference_signals.c.detector_status,
        wip_reference_signals.c.evidence_json,
        wip_reference_signals.c.source.label("signal_source"),
        wip_reference_signals.c.snapshot_marker,
        wip_reference_signals.c.signal_key,
        wip_reference_signals.c.detected_at,
    ]
    stmt = (
        select(
            wip_references.c.id.label("reference_id"),
            wip_references.c.paper_id,
            wip_references.c.updated_at.label("reference_updated_at"),
            papers.c.title.label("paper_title"),
            papers.c.year.label("paper_year"),
            papers.c.doi,
            *sig_cols,
        )
        .select_from(
            wip_references.join(papers, papers.c.id == wip_references.c.paper_id).outerjoin(
                wip_reference_signals, wip_reference_signals.c.reference_id == wip_references.c.id
            )
        )
        .where(wip_references.c.manuscript_id == manuscript_id, wip_references.c.relationship_state == "cited")
        .order_by(papers.c.title, wip_reference_signals.c.id)
    )
    rows = [dict(row) for row in conn.execute(stmt).mappings()]
    if not rows:
        return []
    signals_by_reference: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["signal_id"] is not None:
            signals_by_reference[int(row["reference_id"])].append(
                {
                    "detector_kind": row["detector_kind"],
                    "detector_status": row["detector_status"],
                    "signal_key": row["signal_key"],
                    "snapshot_marker": row["snapshot_marker"],
                }
            )
    fingerprints = {
        reference_id: signal_set_fingerprint(signals)
        for reference_id, signals in signals_by_reference.items()
        if signals
    }
    reviews: dict[tuple[int, str], RowMapping] = {}
    if fingerprints:
        review_rows = conn.execute(
            select(wip_reference_reviews).where(wip_reference_reviews.c.reference_id.in_(list(fingerprints)))
        ).mappings()
        for row in review_rows:
            reviews[(int(row["reference_id"]), row["signal_fingerprint"])] = row
    for row in rows:
        reference_id = int(row["reference_id"])
        fingerprint = fingerprints.get(reference_id)
        review = reviews.get((reference_id, fingerprint)) if fingerprint else None
        row["signal_fingerprint"] = fingerprint
        row["review_state"] = review["state"] if review else "unreviewed"
        row["reviewed_at"] = review["reviewed_at"] if review else None
    return rows


def _reference_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["reference_id"]),
        "paper_id": int(row["paper_id"]),
        "paper_title": row["paper_title"],
        "paper_year": row["paper_year"],
        "doi": row["doi"],
        "review_state": row["review_state"] or "unreviewed",
        "reviewed_at": str(row["reviewed_at"]) if row["reviewed_at"] else None,
        "updated_at": str(row["reference_updated_at"]) if row.get("reference_updated_at") else None,
        "signal_fingerprint": row["signal_fingerprint"],
        "signals": [],
    }


def _latest_checked_at(items: list[dict[str, Any]]) -> str | None:
    values = [item.get("updated_at") for item in items if item.get("updated_at")]
    return max(values) if values else None


def _signal_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["signal_id"]),
        "detector_kind": row["detector_kind"],
        "detector_status": row["detector_status"],
        "evidence": row["evidence_json"],
        "source": row["signal_source"],
        "snapshot_marker": row["snapshot_marker"],
        "detected_at": str(row["detected_at"]) if row["detected_at"] else None,
    }


def _signal_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "detector_kind": row["detector_kind"],
        "detector_status": row["detector_status"],
        "signal_key": row["signal_key"],
        "snapshot_marker": row["snapshot_marker"],
    }


def _write(conn: Connection, statement):
    return retry_sqlite_locked(lambda: conn.execute(statement))
