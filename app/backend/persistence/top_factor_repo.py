"""Data access for `top_factor_records` — the local mirror of the Center for Open Science's TOP Factor CSV
(backlog #40).

A downloaded snapshot the PUBLISHERS tool matches candidate journals against **offline** by ISSN/EISSN (no live
query API exists for TOP Factor — see `integrations/top_factor/adapter.py`). Replace-all on refresh (a fresh
snapshot is authoritative). `top_factor_db_status` mirrors `retraction_repo.retraction_db_status`'s exact
`{count, retrieved_at}` shape so the mirror's freshness reads the same way across both local mirrors.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, func, insert, or_, select

from app.backend.persistence.schema import top_factor_records


def replace_top_factor_records(conn: Connection, records: list[dict[str, Any]], *, retrieved_at: str) -> None:
    """Replace the whole local mirror with a fresh snapshot, in one transaction."""
    conn.execute(delete(top_factor_records))
    if records:
        conn.execute(
            insert(top_factor_records),
            [
                {
                    "issn": r.get("issn"),
                    "eissn": r.get("eissn"),
                    "journal": r.get("journal"),
                    "categories_json": r["categories"],
                    "total": r["total"],
                    "retrieved_at": retrieved_at,
                }
                for r in records
            ],
        )


def lookup_top_factor_record(conn: Connection, issn: str) -> dict[str, Any] | None:
    """`{"total", "categories"}` for an ISSN (matched against either the print or electronic ISSN column), or
    None if the mirror has no row for it (this is ambiguous with "never downloaded" in isolation — callers
    should also read `top_factor_db_status` to distinguish the two; see PublishersReport.top_factor_coverage)."""
    normalized = (issn or "").strip().upper()
    if not normalized:
        return None
    row = (
        conn.execute(
            select(top_factor_records).where(
                or_(top_factor_records.c.issn == normalized, top_factor_records.c.eissn == normalized)
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return {"total": row["total"], "categories": row["categories_json"]}


def top_factor_db_status(conn: Connection) -> dict[str, Any]:
    """`{count, retrieved_at}` for the as-of line (retrieved_at is None when never downloaded)."""
    count = conn.execute(select(func.count()).select_from(top_factor_records)).scalar()
    as_of = conn.execute(select(func.max(top_factor_records.c.retrieved_at))).scalar()
    return {"count": int(count or 0), "retrieved_at": as_of}
