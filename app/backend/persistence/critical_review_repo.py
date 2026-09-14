"""Data access for the critical-review candidate store (backlog #12).

All bound-param (rule #3). Candidates are Tier-2 (AI-proposed) critiques a human accepts/rejects; a rejected
candidate's ``signature`` is remembered so ``generate`` never re-proposes it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select, update

from app.backend.persistence.schema import critical_read_snapshots as snapshots
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
                related_paper_ids_json=cand.get(
                    "related_paper_ids"
                ),  # set critical review (#12); None for single-paper
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


def list_candidates_by_ids(conn: Connection, candidate_ids: list[int]) -> list[dict[str, Any]]:
    """Candidates by an explicit id set, oldest first — the set-critique triage path spans several paper_ids."""
    if not candidate_ids:
        return []
    query = select(cands).where(cands.c.id.in_(candidate_ids)).order_by(cands.c.id)
    return [dict(row._mapping) for row in conn.execute(query)]


def rejected_signatures(conn: Connection, paper_id: int) -> set[str]:
    """The signatures of this paper's rejected candidates — never re-proposed."""
    query = select(cands.c.signature).where(cands.c.paper_id == paper_id, cands.c.status == "rejected")
    return {row[0] for row in conn.execute(query)}


# --- inc 601: one durable latest Tier-1 backbone snapshot per paper (current-only; Refresh replaces) ----------


def read_backbone_snapshot(conn: Connection, paper_id: int) -> dict[str, Any] | None:
    """The paper's latest persisted critique backbone, or None. Raw row — the caller validates the payload
    through ScrutinyBackboneResponse and applies the version/fingerprint checks (fail into 'refresh required')."""
    row = conn.execute(select(snapshots).where(snapshots.c.paper_id == paper_id)).mappings().first()
    return dict(row) if row is not None else None


def save_backbone_snapshot(
    conn: Connection,
    paper_id: int,
    backbone: dict[str, Any],
    *,
    requested_at: str,
    critical_review_version: str,
    content_fingerprint: str | None,
    snapshot_schema_version: int = 1,
) -> bool:
    """Replace the paper's snapshot with this run's result — but ONLY if this run is not older than the stored
    one (`requested_at` monotonic guard, c2): a Refresh that overlapped and completed out of order must never
    clobber a newer result. Returns True if written, False if a newer snapshot already exists. Current-only:
    exactly one row per paper (delete-then-insert keeps the UNIQUE(paper_id) invariant trivially)."""
    existing = conn.execute(select(snapshots.c.requested_at).where(snapshots.c.paper_id == paper_id)).first()
    if existing is not None and str(existing[0]) > requested_at:
        return False  # a newer run already persisted; do not regress
    conn.execute(delete(snapshots).where(snapshots.c.paper_id == paper_id))
    conn.execute(
        insert(snapshots).values(
            paper_id=paper_id,
            backbone_json=backbone,
            snapshot_schema_version=snapshot_schema_version,
            critical_review_version=critical_review_version,
            content_fingerprint=content_fingerprint,
            requested_at=requested_at,
        )
    )
    return True
