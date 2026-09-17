"""Data access for ``capture_events`` — one row per encounter with a provisional artifact.

See ``schema_provisional_artifacts.py``. All bound-param (rule #3).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, insert, select

from app.backend.persistence.schema import capture_events


def create(
    conn: Connection,
    *,
    capture_event_id: str,
    artifact_id: str,
    source_url: str | None,
    captured_at_client: str | None,
    original_filename: str | None,
    producer_kind: str | None,
) -> None:
    conn.execute(
        insert(capture_events).values(
            id=capture_event_id,
            artifact_id=artifact_id,
            source_url=source_url,
            captured_at_client=captured_at_client,
            original_filename=original_filename,
            producer_kind=producer_kind,
        )
    )


def list_for_artifact(conn: Connection, artifact_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        select(capture_events)
        .where(capture_events.c.artifact_id == artifact_id)
        .order_by(capture_events.c.received_at_server)
    ).mappings()
    return [dict(r) for r in rows]


def delete_for_artifact(conn: Connection, artifact_id: str) -> int:
    return conn.execute(delete(capture_events).where(capture_events.c.artifact_id == artifact_id)).rowcount
