"""Data access for `ajol_records` — the local mirror of a third-party AJOL (African Journals Online) journal
metadata snapshot (backlog #40, inc 451).

A downloaded snapshot the PUBLISHERS tool matches candidate journals against **offline** by ISSN/EISSN (no
usable live per-ISSN query API exists for AJOL — see `integrations/ajol/adapter.py`). Replace-all on download (a
fresh snapshot is authoritative). `ajol_db_status` mirrors `top_factor_repo.top_factor_db_status`'s exact
`{count, retrieved_at}` shape — `retrieved_at` is the LOCAL download timestamp, distinct from the data's own
fixed vintage (`integrations.ajol.adapter.AJOL_SNAPSHOT_DATE`, February 2024, never updated by a re-download).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, func, insert, or_, select

from app.backend.persistence.schema import ajol_records


def replace_ajol_records(conn: Connection, records: list[dict[str, Any]], *, retrieved_at: str) -> None:
    """Replace the whole local mirror with a fresh snapshot, in one transaction."""
    conn.execute(delete(ajol_records))
    if records:
        conn.execute(
            insert(ajol_records),
            [
                {
                    "issn": r.get("issn"),
                    "eissn": r.get("eissn"),
                    "journal": r.get("journal"),
                    "country": r.get("country"),
                    "jpps_status": r.get("jpps_status"),
                    "is_diamond": r.get("is_diamond"),
                    "source_url": r.get("source_url"),
                    "retrieved_at": retrieved_at,
                }
                for r in records
            ],
        )


def lookup_ajol_record(conn: Connection, issn: str) -> dict[str, Any] | None:
    """`{"country", "jpps_status", "is_diamond", "source_url"}` for an ISSN (matched against either the print or
    electronic ISSN column), or None if the mirror has no row for it (ambiguous with "never downloaded" in
    isolation — callers should also read `ajol_db_status`; see PublishersReport.ajol_coverage)."""
    normalized = (issn or "").strip().upper()
    if not normalized:
        return None
    row = (
        conn.execute(
            select(ajol_records).where(or_(ajol_records.c.issn == normalized, ajol_records.c.eissn == normalized))
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return {
        "country": row["country"],
        "jpps_status": row["jpps_status"],
        "is_diamond": row["is_diamond"],
        "source_url": row["source_url"],
    }


def ajol_db_status(conn: Connection) -> dict[str, Any]:
    """`{count, retrieved_at}` for the as-of line (retrieved_at is None when never downloaded)."""
    count = conn.execute(select(func.count()).select_from(ajol_records)).scalar()
    as_of = conn.execute(select(func.max(ajol_records.c.retrieved_at))).scalar()
    return {"count": int(count or 0), "retrieved_at": as_of}
