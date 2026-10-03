"""Data access for ``provisional_artifacts`` — one row per distinct captured-PDF object.

See ``schema_provisional_artifacts.py`` for why this is split from ``capture_events``. All bound-param
(rule #3).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Connection, delete, func, insert, select, update

from app.backend.persistence.schema import provisional_artifacts


def find_by_content_hash(conn: Connection, content_hash: str) -> dict[str, Any] | None:
    row = (
        conn.execute(select(provisional_artifacts).where(provisional_artifacts.c.content_hash == content_hash))
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def get(conn: Connection, artifact_id: str) -> dict[str, Any] | None:
    row = (
        conn.execute(select(provisional_artifacts).where(provisional_artifacts.c.id == artifact_id)).mappings().first()
    )
    return dict(row) if row is not None else None


def create(
    conn: Connection,
    *,
    artifact_id: str,
    content_hash: str,
    pdf_path: str,
    provenance_sidecar_state: str = "pending",
) -> None:
    """Insert the initial row: freshly captured, identity not yet attempted.

    ``identity_state``/``promotion_state`` take their server defaults (``unresolved`` /
    ``pending_review``) — the same values a crash-recovered row would legitimately hold, so there is
    no separate "processing" limbo state to model (see provisional.py's durability-sequence notes).
    """
    conn.execute(
        insert(provisional_artifacts).values(
            id=artifact_id,
            content_hash=content_hash,
            pdf_path=pdf_path,
            provenance_sidecar_state=provenance_sidecar_state,
        )
    )


def update_resolution(
    conn: Connection,
    artifact_id: str,
    *,
    identity_state: str,
    promotion_state: str,
    resolved_paper_id: int | None = None,
    pdf_path: str | None = None,
    evidence_json: str | None = None,
) -> None:
    values: dict[str, Any] = {
        "identity_state": identity_state,
        "promotion_state": promotion_state,
        "resolved_paper_id": resolved_paper_id,
        "updated_at": func.current_timestamp(),
    }
    if pdf_path is not None:
        values["pdf_path"] = pdf_path
    if evidence_json is not None:
        values["evidence_json"] = evidence_json
    conn.execute(update(provisional_artifacts).where(provisional_artifacts.c.id == artifact_id).values(**values))


def update_sidecar_state(conn: Connection, artifact_id: str, state: str) -> None:
    conn.execute(
        update(provisional_artifacts)
        .where(provisional_artifacts.c.id == artifact_id)
        .values(provenance_sidecar_state=state, updated_at=func.current_timestamp())
    )


def list_needing_review(conn: Connection) -> list[dict[str, Any]]:
    """Everything not yet fully promoted — the Import Queue's contents."""
    rows = conn.execute(
        select(provisional_artifacts)
        .where(provisional_artifacts.c.promotion_state != "promoted")
        .order_by(provisional_artifacts.c.created_at.desc())
    ).mappings()
    return [dict(r) for r in rows]


def all_ids(conn: Connection) -> set[str]:
    return {str(r) for r in conn.execute(select(provisional_artifacts.c.id)).scalars().all()}


def iter_active_ids(conn: Connection) -> Iterator[str]:
    """The identifiers of artifacts still ACTIVE in the Import Queue (not yet promoted), streamed from the cursor.

    This is the server-owned allowlist behind every queue operation (serve, confirm, retry, delete): promoted artifacts
    stay in the table as provenance but are outside the queue, so the scan grows with the queue, not with history. The
    query takes no request input -- a request string is only ever compared against what this yields.
    """
    result = conn.execute(
        select(provisional_artifacts.c.id).where(provisional_artifacts.c.promotion_state != "promoted")
    )
    try:
        for stored in result.scalars():
            yield str(stored)
    finally:
        result.close()


def delete_artifact(conn: Connection, artifact_id: str) -> bool:
    return conn.execute(delete(provisional_artifacts).where(provisional_artifacts.c.id == artifact_id)).rowcount > 0
