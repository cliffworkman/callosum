"""The findings contract every METHODS check emits into (inc 130).

A Finding is a FACT (an established truth — a persistent mark, NOT resolvable, review_state NULL) or a CANDIDATE
(a possible concern for the user to check — reviewable, with an optional tier + payload anchors). Producers call
``upsert_findings``, which is IDEMPOTENT and REVIEW-STATE-PRESERVING: re-running a producer must never wipe the
user's reviews on unchanged findings. Badges describe the user's WORK STATE ("N to review"), never paper quality.
State lives in this table, not localStorage.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import Connection, and_, case, delete, func, insert, select, update
from sqlalchemy.engine import RowMapping

from app.backend.persistence.schema import paper_findings

REVIEW_STATES = ("confirmed", "accepted", "noted")  # settable candidate states (plus the 'unreviewed' default)


def _content_key(source: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(f"{source}\x00{canonical}".encode()).hexdigest()


def upsert_findings(conn: Connection, paper_id: int, source: str, findings: list[dict]) -> None:
    """Replace a (paper_id, source)'s findings, PRESERVING reviews on unchanged ones. Each finding is
    {kind: 'fact'|'candidate', tier?: str|None, payload: dict}. Idempotent: re-running with the same payloads
    touches nothing (same content_key); a changed payload is a new finding and supersedes the old."""
    keyed = [(_content_key(source, f["payload"]), f) for f in findings]
    new_keys = {ck for ck, _ in keyed}
    existing = {
        row.content_key
        for row in conn.execute(
            select(paper_findings.c.content_key).where(
                paper_findings.c.paper_id == paper_id, paper_findings.c.source == source
            )
        )
    }
    superseded = existing - new_keys
    if superseded:
        conn.execute(
            delete(paper_findings).where(
                paper_findings.c.paper_id == paper_id,
                paper_findings.c.source == source,
                paper_findings.c.content_key.in_(superseded),
            )
        )
    for content_key, f in keyed:
        if content_key in existing:
            continue  # unchanged → leave it (review_state preserved)
        kind = f["kind"]
        conn.execute(
            insert(paper_findings).values(
                paper_id=paper_id,
                source=source,
                kind=kind,
                tier=f.get("tier"),
                payload=f["payload"],
                content_key=content_key,
                review_state="unreviewed" if kind == "candidate" else None,
            )
        )


def _finding_dict(row: RowMapping) -> dict:
    return {
        "id": int(row["id"]),
        "paper_id": int(row["paper_id"]),
        "source": row["source"],
        "kind": row["kind"],
        "tier": row["tier"],
        "payload": row["payload"],
        "review_state": row["review_state"],
        "review_reason": row["review_reason"],
    }


def get_paper_findings(conn: Connection, paper_id: int) -> dict:
    rows = list(
        conn.execute(
            select(paper_findings).where(paper_findings.c.paper_id == paper_id).order_by(paper_findings.c.id)
        ).mappings()
    )
    facts = [_finding_dict(r) for r in rows if r["kind"] == "fact"]
    candidates = [_finding_dict(r) for r in rows if r["kind"] == "candidate"]
    tier_rank = {"primary": 0, "speculative": 1}
    candidates.sort(key=lambda c: (tier_rank.get(c["tier"], 0), c["review_state"] != "unreviewed", c["id"]))
    return {"facts": facts, "candidates": candidates}


def findings_overview(conn: Connection) -> list[dict]:
    rows = conn.execute(
        select(
            paper_findings.c.paper_id,
            func.sum(
                case(
                    (and_(paper_findings.c.kind == "candidate", paper_findings.c.review_state == "unreviewed"), 1),
                    else_=0,
                )
            ).label("unreviewed_count"),
            func.max(case((paper_findings.c.kind == "fact", 1), else_=0)).label("has_facts"),
        ).group_by(paper_findings.c.paper_id)
    )
    return [
        {
            "paper_id": int(r.paper_id),
            "unreviewed_count": int(r.unreviewed_count or 0),
            "has_facts": bool(r.has_facts),
        }
        for r in rows
    ]


def get_finding_dict(conn: Connection, finding_id: int) -> dict | None:
    row = conn.execute(select(paper_findings).where(paper_findings.c.id == finding_id)).mappings().first()
    return _finding_dict(row) if row is not None else None


def set_review_state(conn: Connection, finding_id: int, state: str, reason: str | None = None) -> str:
    """Returns 'ok' | 'not-found' | 'not-candidate' | 'bad-state' | 'needs-reason'. Candidates only; 'accepted'
    requires a non-empty reason."""
    row = conn.execute(select(paper_findings).where(paper_findings.c.id == finding_id)).mappings().first()
    if row is None:
        return "not-found"
    if row["kind"] != "candidate":
        return "not-candidate"
    if state not in REVIEW_STATES:
        return "bad-state"
    if state == "accepted" and not (reason and reason.strip()):
        return "needs-reason"
    conn.execute(
        update(paper_findings)
        .where(paper_findings.c.id == finding_id)
        .values(
            review_state=state,
            review_reason=(reason.strip() if reason else None),
            reviewed_at=func.current_timestamp(),
        )
    )
    return "ok"
