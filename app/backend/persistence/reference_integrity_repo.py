"""Persistence helpers for the Meta Reference List.

The current warning state is derived from active signals plus the review row for the active signal-set
fingerprint. Older reviews remain as provenance but do not suppress changed signals.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from sqlalchemy import Connection, delete, func, insert, select, update
from sqlalchemy.engine import RowMapping

from app.backend.methods.reference_integrity import entity_key, signal_set_fingerprint
from app.backend.persistence.schema import papers
from app.backend.persistence.schema_reference_integrity import (
    REFERENCE_REVIEW_STATES,
    reference_entities,
    reference_instances,
    reference_reviews,
    reference_signals,
)
from app.backend.persistence.sqlite_retry import retry_sqlite_locked


def upsert_reference_entity(conn: Connection, metadata: Mapping[str, Any]) -> int:
    key = entity_key(metadata)
    row = conn.execute(select(reference_entities).where(reference_entities.c.normalized_key == key)).mappings().first()
    values = {
        "doi": metadata.get("doi"),
        "openalex_work_id": metadata.get("openalex_work_id"),
        "semantic_scholar_paper_id": metadata.get("semantic_scholar_paper_id"),
        "title": metadata.get("title"),
        "authors_json": list(metadata.get("authors") or []),
        "year": metadata.get("year"),
        "updated_at": func.current_timestamp(),
    }
    if row is None:
        result = _write(conn, insert(reference_entities).values(normalized_key=key, **values))
        return int(result.inserted_primary_key[0])
    _write(conn, update(reference_entities).where(reference_entities.c.id == row["id"]).values(**values))
    return int(row["id"])


def upsert_reference_instance(
    conn: Connection,
    *,
    citing_paper_id: int,
    entity_id: int | None,
    instance_key: str,
    source: str,
    source_ordinal: int,
    raw_text: str,
    title: str | None,
    authors: list[str],
    year: int | None,
    doi: str | None,
    context: dict[str, Any],
) -> int:
    row = (
        conn.execute(
            select(reference_instances).where(
                reference_instances.c.citing_paper_id == citing_paper_id,
                reference_instances.c.instance_key == instance_key,
            )
        )
        .mappings()
        .first()
    )
    values = {
        "reference_entity_id": entity_id,
        "source": source,
        "source_ordinal": source_ordinal,
        "raw_text": raw_text,
        "title": title,
        "authors_json": authors,
        "year": year,
        "doi": doi,
        "context_json": context,
        "updated_at": func.current_timestamp(),
    }
    if row is None:
        result = _write(
            conn,
            insert(reference_instances).values(citing_paper_id=citing_paper_id, instance_key=instance_key, **values),
        )
        return int(result.inserted_primary_key[0])
    _write(conn, update(reference_instances).where(reference_instances.c.id == row["id"]).values(**values))
    return int(row["id"])


def replace_instance_signals(conn: Connection, instance_id: int, signals: list[Mapping[str, Any]]) -> None:
    _write(conn, delete(reference_signals).where(reference_signals.c.citation_instance_id == instance_id))
    for signal in signals:
        _write(
            conn,
            insert(reference_signals).values(
                citation_instance_id=instance_id,
                detector_kind=signal["detector_kind"],
                detector_status=signal["detector_status"],
                evidence_json=signal["evidence_json"],
                source=signal["source"],
                snapshot_marker=signal["snapshot_marker"],
                signal_key=signal["signal_key"],
            ),
        )
    ensure_current_review(conn, instance_id)


def ensure_current_review(conn: Connection, instance_id: int) -> str | None:
    signals = active_signals_for_instance(conn, instance_id)
    if not signals:
        return None
    fingerprint = signal_set_fingerprint(signals)
    existing = (
        conn.execute(
            select(reference_reviews).where(
                reference_reviews.c.citation_instance_id == instance_id,
                reference_reviews.c.signal_fingerprint == fingerprint,
            )
        )
        .mappings()
        .first()
    )
    if existing is None:
        entity_id = conn.execute(
            select(reference_instances.c.reference_entity_id).where(reference_instances.c.id == instance_id)
        ).scalar()
        _write(
            conn,
            insert(reference_reviews).values(
                citation_instance_id=instance_id,
                signal_fingerprint=fingerprint,
                state="unreviewed",
                reference_entity_id=entity_id,
                review_snapshot_json={"signals": [_signal_snapshot(s) for s in signals]},
            ),
        )
    return fingerprint


def active_signals_for_instance(conn: Connection, instance_id: int) -> list[RowMapping]:
    return list(
        conn.execute(
            select(reference_signals)
            .where(reference_signals.c.citation_instance_id == instance_id)
            .order_by(reference_signals.c.detector_kind, reference_signals.c.id)
        ).mappings()
    )


def set_reference_review_state(conn: Connection, instance_id: int, state: str) -> str:
    if state not in REFERENCE_REVIEW_STATES:
        return "bad-state"
    if state == "unreviewed":
        return "bad-state"
    signals = active_signals_for_instance(conn, instance_id)
    if not signals:
        return "no-active-signals"
    fingerprint = signal_set_fingerprint(signals)
    ensure_current_review(conn, instance_id)
    result = _write(
        conn,
        update(reference_reviews)
        .where(
            reference_reviews.c.citation_instance_id == instance_id,
            reference_reviews.c.signal_fingerprint == fingerprint,
        )
        .values(
            state=state,
            reviewed_at=func.current_timestamp(),
            review_snapshot_json={"signals": [_signal_snapshot(s) for s in signals]},
        ),
    )
    return "ok" if result.rowcount else "not-found"


def paper_reference_report(conn: Connection, paper_id: int) -> dict[str, Any]:
    rows = _current_rows(conn, paper_id=paper_id)
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        iid = int(row["instance_id"])
        item = grouped.setdefault(iid, _instance_payload(row))
        if row["signal_id"] is not None:
            item["signals"].append(_signal_payload(row))
    items = list(grouped.values())
    items.sort(key=lambda item: (item["review_state"] == "dismissed", item["source_ordinal"], item["id"]))
    return {
        "paper_id": paper_id,
        "checked_count": len(items),
        "last_checked_at": _latest_checked_at(items),
        "items": [item for item in items if item["signals"]],
        "active_count": sum(1 for item in items if item["signals"] and item["review_state"] != "dismissed"),
    }


def reference_overview(conn: Connection) -> list[dict[str, Any]]:
    rows = _current_rows(conn)
    by_paper: dict[int, dict[str, int]] = defaultdict(lambda: {"active": 0, "unreviewed": 0, "confirmed": 0})
    seen: set[int] = set()
    for row in rows:
        iid = int(row["instance_id"])
        if iid in seen or row["signal_id"] is None:
            continue
        seen.add(iid)
        state = row["review_state"] or "unreviewed"
        if state != "dismissed":
            by_paper[int(row["citing_paper_id"])]["active"] += 1
        if state == "unreviewed":
            by_paper[int(row["citing_paper_id"])]["unreviewed"] += 1
        elif state == "confirmed_problem":
            by_paper[int(row["citing_paper_id"])]["confirmed"] += 1
    return [
        {
            "paper_id": paper_id,
            "active_count": counts["active"],
            "unreviewed_count": counts["unreviewed"],
            "confirmed_count": counts["confirmed"],
        }
        for paper_id, counts in sorted(by_paper.items())
        if counts["active"] > 0
    ]


def flagged_sources_for_entity(conn: Connection, entity_id: int, *, exclude_paper_id: int) -> list[dict[str, Any]]:
    rows = _current_rows(conn, entity_id=entity_id)
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        if int(row["citing_paper_id"]) == exclude_paper_id:
            continue
        if row["signal_id"] is None or row["review_state"] == "dismissed":
            continue
        if row["detector_kind"] == "own_library_propagation":
            continue
        iid = int(row["instance_id"])
        item = grouped.setdefault(
            iid,
            {
                "citing_paper_id": int(row["citing_paper_id"]),
                "citation_instance_id": iid,
                "review_state": row["review_state"] or "unreviewed",
                "detector_kinds": [],
                "title": row["paper_title"],
            },
        )
        if row["detector_kind"] not in item["detector_kinds"]:
            item["detector_kinds"].append(row["detector_kind"])
    return list(grouped.values())


def _current_rows(
    conn: Connection, *, paper_id: int | None = None, entity_id: int | None = None
) -> list[dict[str, Any]]:
    sig_cols = [
        reference_signals.c.id.label("signal_id"),
        reference_signals.c.detector_kind,
        reference_signals.c.detector_status,
        reference_signals.c.evidence_json,
        reference_signals.c.source.label("signal_source"),
        reference_signals.c.snapshot_marker,
        reference_signals.c.signal_key,
        reference_signals.c.detected_at,
    ]
    stmt = (
        select(
            reference_instances.c.id.label("instance_id"),
            reference_instances.c.citing_paper_id,
            reference_instances.c.reference_entity_id,
            reference_instances.c.source.label("instance_source"),
            reference_instances.c.source_ordinal,
            reference_instances.c.raw_text,
            reference_instances.c.title,
            reference_instances.c.authors_json,
            reference_instances.c.year,
            reference_instances.c.doi,
            reference_instances.c.context_json,
            reference_instances.c.updated_at.label("instance_updated_at"),
            papers.c.title.label("paper_title"),
            *sig_cols,
        )
        .select_from(
            reference_instances.join(papers, papers.c.id == reference_instances.c.citing_paper_id).outerjoin(
                reference_signals, reference_signals.c.citation_instance_id == reference_instances.c.id
            )
        )
        .order_by(reference_instances.c.source_ordinal, reference_signals.c.id)
    )
    if paper_id is not None:
        stmt = stmt.where(reference_instances.c.citing_paper_id == paper_id)
    if entity_id is not None:
        stmt = stmt.where(reference_instances.c.reference_entity_id == entity_id)
    rows = [dict(row) for row in conn.execute(stmt).mappings()]
    if not rows:
        return []
    signals_by_instance: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["signal_id"] is not None:
            signals_by_instance[int(row["instance_id"])].append(
                {
                    "detector_kind": row["detector_kind"],
                    "detector_status": row["detector_status"],
                    "signal_key": row["signal_key"],
                    "snapshot_marker": row["snapshot_marker"],
                }
            )
    fingerprints = {
        instance_id: signal_set_fingerprint(signals) for instance_id, signals in signals_by_instance.items() if signals
    }
    reviews: dict[tuple[int, str], RowMapping] = {}
    prior_human_reviews: dict[int, set[str]] = defaultdict(set)
    if fingerprints:
        review_rows = conn.execute(
            select(reference_reviews).where(reference_reviews.c.citation_instance_id.in_(list(fingerprints)))
        ).mappings()
        for row in review_rows:
            instance_id = int(row["citation_instance_id"])
            reviews[(instance_id, row["signal_fingerprint"])] = row
            if row["state"] != "unreviewed":
                prior_human_reviews[instance_id].add(row["signal_fingerprint"])
    for row in rows:
        instance_id = int(row["instance_id"])
        fingerprint = fingerprints.get(instance_id)
        review = reviews.get((instance_id, fingerprint)) if fingerprint else None
        row["signal_fingerprint"] = fingerprint
        row["review_state"] = review["state"] if review else "unreviewed"
        row["reviewed_at"] = review["reviewed_at"] if review else None
        row["reopened"] = bool(
            fingerprint and row["review_state"] == "unreviewed" and (prior_human_reviews[instance_id] - {fingerprint})
        )
    return rows


def _instance_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["instance_id"]),
        "citing_paper_id": int(row["citing_paper_id"]),
        "reference_entity_id": row["reference_entity_id"],
        "source": row["instance_source"],
        "source_ordinal": row["source_ordinal"],
        "raw_text": row["raw_text"],
        "title": row["title"],
        "authors": row["authors_json"] or [],
        "year": row["year"],
        "doi": row["doi"],
        "context": row["context_json"] or {},
        "review_state": row["review_state"] or "unreviewed",
        "reviewed_at": str(row["reviewed_at"]) if row["reviewed_at"] else None,
        "updated_at": str(row["instance_updated_at"]) if row.get("instance_updated_at") else None,
        "signal_fingerprint": row["signal_fingerprint"],
        "reopened": bool(row.get("reopened")),
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
