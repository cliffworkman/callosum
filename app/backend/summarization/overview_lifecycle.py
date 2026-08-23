"""Persisted, retry-safe lifecycle for the supplementary synthesis Overview.

The verified synthesis is already durable before anything in this module runs. Model/provider
work therefore happens without an open database connection, and only short compare-and-swap
transactions change lifecycle state or persist the finished Overview.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Mapping

from sqlalchemy import Connection, Engine, and_, or_, select, update

from app.backend.persistence.schema import citation_mappings, summaries, summary_sentences
from app.backend.summarization.overview import OverviewGenerator

OverviewStatus = Literal["not_requested", "pending", "running", "complete", "failed"]
OVERVIEW_STALE_AFTER = timedelta(minutes=5)

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverviewInput:
    scope_ref: dict[str, object]
    verified_claims: list[str]
    verified_ordinals: list[int]


def overview_status_for_row(row: Mapping[str, object]) -> OverviewStatus:
    """Interpret explicit state, with a safe compatibility rule for pre-lifecycle rows."""
    status = row.get("overview_status")
    if status in {"not_requested", "pending", "running", "complete", "failed"}:
        return status  # type: ignore[return-value]
    return "complete" if row.get("overview_json") is not None else "not_requested"


def acquire_overview(
    conn: Connection,
    summary_id: int,
    *,
    allow_pending: bool,
    allow_failed: bool,
    now: datetime | None = None,
) -> bool:
    """Acquire one overview attempt. Complete/not-requested work is never overwritten.

    A stale ``running`` row is manually reclaimable after five minutes. Nothing calls this
    automatically at startup, so persisted state never causes unconsented provider egress.
    """
    attempted_at = _naive_utc(now)
    allowed = []
    if allow_pending:
        allowed.append(summaries.c.overview_status == "pending")
    if allow_failed:
        allowed.append(summaries.c.overview_status == "failed")
    allowed.append(
        and_(
            summaries.c.overview_status == "running",
            summaries.c.overview_updated_at <= attempted_at - OVERVIEW_STALE_AFTER,
        )
    )
    result = conn.execute(
        update(summaries)
        .where(summaries.c.id == summary_id, or_(*allowed))
        .values(overview_status="running", overview_updated_at=attempted_at)
    )
    return result.rowcount == 1


def load_overview_input(conn: Connection, summary_id: int) -> OverviewInput:
    """Reread only committed verified claims in their authoritative sentence order."""
    summary = conn.execute(select(summaries.c.scope_ref_json).where(summaries.c.id == summary_id)).mappings().one()
    rows = list(
        conn.execute(
            select(
                summary_sentences.c.id,
                summary_sentences.c.ordinal,
                summary_sentences.c.text,
                citation_mappings.c.status,
            )
            .select_from(
                summary_sentences.outerjoin(
                    citation_mappings,
                    citation_mappings.c.summary_sentence_id == summary_sentences.c.id,
                )
            )
            .where(summary_sentences.c.summary_id == summary_id)
            .order_by(summary_sentences.c.ordinal, summary_sentences.c.id, citation_mappings.c.id)
        ).mappings()
    )
    by_sentence: dict[int, tuple[int, str, list[str]]] = {}
    for row in rows:
        sentence_id = int(row["id"])
        entry = by_sentence.setdefault(sentence_id, (int(row["ordinal"]), str(row["text"]), []))
        if row["status"] is not None:
            entry[2].append(str(row["status"]))
    verified = [entry for entry in by_sentence.values() if entry[2] and all(s == "verified" for s in entry[2])]
    scope_ref = summary["scope_ref_json"] if isinstance(summary["scope_ref_json"], dict) else {}
    return OverviewInput(
        scope_ref=dict(scope_ref),
        verified_claims=[entry[1] for entry in verified],
        verified_ordinals=[entry[0] for entry in verified],
    )


def generate_overview(
    engine: Engine,
    *,
    summary_id: int,
    generator: OverviewGenerator,
    acquired: bool = False,
) -> OverviewStatus:
    """Run one supplementary attempt; every failure is isolated from the primary synthesis."""
    try:
        if not acquired:
            claimed = False
            with engine.begin() as conn:
                claimed = acquire_overview(conn, summary_id, allow_pending=True, allow_failed=False)
            if not claimed:
                return _read_status(engine, summary_id)

        # The connection closes before the remote call. SQLAlchemy's implicit read transaction
        # therefore cannot retain a SQLite connection or writer lock during provider latency.
        with engine.connect() as conn:
            overview_input = load_overview_input(conn, summary_id)
        if not overview_input.verified_claims:
            raise ValueError("overview has no committed verified claims")

        produced = generator.generate(
            verified_claims=overview_input.verified_claims,
            scope_ref=overview_input.scope_ref,
        )
        items = _validated_items(produced, overview_input.verified_ordinals)
        if not items:
            raise ValueError("overview provider returned no usable referenced sentences")

        with engine.begin() as conn:
            persisted = _persist_overview(conn, summary_id, items)
        return "complete" if persisted else _read_status(engine, summary_id)
    except Exception as exc:
        _LOG.warning("Supplementary overview failed for summary %s: %s", summary_id, type(exc).__name__)
        try:
            with engine.begin() as conn:
                conn.execute(
                    update(summaries)
                    .where(summaries.c.id == summary_id, summaries.c.overview_status == "running")
                    .values(overview_status="failed", overview_updated_at=_naive_utc())
                )
        except Exception:
            _LOG.exception("Could not persist failed overview state for summary %s", summary_id)
        try:
            return _read_status(engine, summary_id)
        except Exception:
            return "failed"


def _validated_items(produced: object, verified_ordinals: list[int]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for sentence in produced if isinstance(produced, list) else []:
        ordinals = sorted(
            {verified_ordinals[index] for index in sentence.claim_indices if 0 <= index < len(verified_ordinals)}
        )
        if sentence.text.strip() and ordinals:
            items.append({"text": sentence.text.strip(), "claim_ordinals": ordinals})
    return items


def _persist_overview(conn: Connection, summary_id: int, items: list[dict[str, object]]) -> bool:
    result = conn.execute(
        update(summaries)
        .where(
            summaries.c.id == summary_id,
            summaries.c.overview_status == "running",
            summaries.c.overview_json.is_(None),
        )
        .values(
            overview_json=items,
            overview_status="complete",
            overview_updated_at=_naive_utc(),
        )
    )
    return result.rowcount == 1


def _read_status(engine: Engine, summary_id: int) -> OverviewStatus:
    with engine.connect() as conn:
        row = conn.execute(select(summaries).where(summaries.c.id == summary_id)).mappings().one()
        return overview_status_for_row(row)


def _naive_utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    return current.astimezone(UTC).replace(tzinfo=None)
