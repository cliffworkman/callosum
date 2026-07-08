"""Data access for the critical-review candidate store (backlog #12).

All bound-param (rule #3). Candidates are Tier-2 (AI-proposed) critiques a human accepts/rejects; a rejected
candidate's ``signature`` is remembered so ``generate`` never re-proposes it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, insert, select, update

from app.backend.persistence.schema import critical_review_candidates as cands


def insert_candidates(conn: Connection, paper_id: int, candidates: list[dict[str, Any]]) -> list[int]:
    """Insert verified candidates (status defaults to 'pending'); returns the new ids in order."""
    ids: list[int] = []
    for cand in candidates:
        result = conn.execute(
            insert(cands).values(
                paper_id=paper_id,
                concern=cand["concern"],
                anchor_quote=cand["anchor_quote"],
                page=cand.get("page"),
                stance=cand.get("stance"),
                confidence=cand.get("confidence"),
                signature=cand["signature"],
            )
        )
        ids.append(int(result.inserted_primary_key[0]))
    return ids


def list_candidates(conn: Connection, paper_id: int, *, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    """Candidates for a paper (optionally filtered by status), oldest first."""
    query = select(cands).where(cands.c.paper_id == paper_id)
    if statuses is not None:
        query = query.where(cands.c.status.in_(statuses))
    query = query.order_by(cands.c.id)
    return [dict(row._mapping) for row in conn.execute(query)]


def set_status(conn: Connection, candidate_id: int, status: str) -> bool:
    """Set a candidate's status ('accepted' / 'rejected'); False if the id is unknown."""
    result = conn.execute(update(cands).where(cands.c.id == candidate_id).values(status=status))
    return result.rowcount > 0


def rejected_signatures(conn: Connection, paper_id: int) -> set[str]:
    """The signatures of this paper's rejected candidates — never re-proposed."""
    query = select(cands.c.signature).where(cands.c.paper_id == paper_id, cands.c.status == "rejected")
    return {row[0] for row in conn.execute(query)}
