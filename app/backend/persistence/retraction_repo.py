"""Data access for `retraction_records` — the local mirror of the Retraction Watch Database (inc 132).

A downloaded snapshot the retraction producer matches DOIs against **offline**. Replace-all on refresh (the RW DB
is authoritative — a record withdrawn upstream must disappear). `lookup_retraction_record` returns the
most-severe record for a DOI as a signal dict the `RetractionWatchChecker` wraps.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, func, insert, select

from app.backend.persistence.schema import retraction_records

_STATUS_RANK = {"concern": 0, "correction": 1, "retracted": 2}


def replace_retraction_records(conn: Connection, records: list[dict[str, Any]], *, retrieved_at: str) -> None:
    """Replace the whole local mirror with a fresh snapshot, in one transaction (authoritative → drop withdrawn)."""
    conn.execute(delete(retraction_records))
    if records:
        conn.execute(
            insert(retraction_records),
            [
                {
                    "original_doi": r["original_doi"],
                    "status": r["status"],
                    "nature": r.get("nature"),
                    "date": r.get("date"),
                    "reason": r.get("reason"),
                    "notice_doi": r.get("notice_doi"),
                    "notice_url": r.get("notice_url"),
                    "retrieved_at": retrieved_at,
                }
                for r in records
            ],
        )


def lookup_retraction_record(conn: Connection, doi: str) -> dict[str, Any] | None:
    """The most-severe stored record for a DOI (a paper may have several notices), or None."""
    normalized = (doi or "").strip().lower()
    if not normalized:
        return None
    rows = (
        conn.execute(select(retraction_records).where(retraction_records.c.original_doi == normalized)).mappings().all()
    )
    if not rows:
        return None
    best = max(rows, key=lambda r: _STATUS_RANK.get(r["status"], 0))
    return {
        "status": best["status"],
        "nature": best["nature"],
        "date": best["date"],
        "reason": best["reason"],
        "notice_doi": best["notice_doi"],
        "notice_url": best["notice_url"],
    }


def retraction_db_status(conn: Connection) -> dict[str, Any]:
    """`{count, retrieved_at}` for the as-of line (retrieved_at is None when never downloaded)."""
    count = conn.execute(select(func.count()).select_from(retraction_records)).scalar()
    as_of = conn.execute(select(func.max(retraction_records.c.retrieved_at))).scalar()
    return {"count": int(count or 0), "retrieved_at": as_of}
