"""WIP checkpoint capture, deduplication, and content-identity status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, insert, select, update

from app.backend.persistence.schema import wip_files, wip_manuscripts, wip_snapshots
from app.backend.persistence.wip_repo import add_activity
from app.backend.wip.content import ContentIdentity, ContentIdentityError, extract_content_identity
from app.backend.wip.paths import trusted_child


@dataclass(frozen=True)
class PreparedSnapshot:
    manuscript_id: int
    file_id: int
    relative_path: str
    identity: ContentIdentity


def prepare_snapshot(conn: Connection, manuscript_id: int, *, file_id: int | None = None) -> PreparedSnapshot:
    manuscript = conn.execute(select(wip_manuscripts).where(wip_manuscripts.c.id == manuscript_id)).mappings().first()
    if manuscript is None:
        raise LookupError("WIP manuscript not found")
    file_stmt = select(wip_files).where(
        wip_files.c.manuscript_id == manuscript_id,
        wip_files.c.is_primary.is_(True) if file_id is None else wip_files.c.id == file_id,
    )
    file = conn.execute(file_stmt).mappings().first()
    if file is None:
        raise ContentIdentityError("Select a primary manuscript file before creating a checkpoint", status="not-run")
    if file["existence_state"] != "available":
        raise ContentIdentityError("The primary manuscript file is unavailable", status="error")
    path = trusted_child(manuscript["root_path"], file["relative_path"])
    if not path.is_file():
        raise ContentIdentityError("The primary manuscript file is unavailable", status="error")
    return PreparedSnapshot(
        manuscript_id=manuscript_id,
        file_id=int(file["id"]),
        relative_path=str(file["relative_path"]),
        identity=extract_content_identity(path),
    )


def record_snapshot(
    conn: Connection,
    prepared: PreparedSnapshot,
    *,
    reason: str,
    reason_detail: str = "",
) -> tuple[dict, bool]:
    identity = prepared.identity
    conn.execute(
        update(wip_files)
        .where(wip_files.c.id == prepared.file_id)
        .values(
            whole_file_hash=identity.whole_file_hash,
            extracted_text_hash=identity.extracted_text_hash,
            extracted_from_whole_hash=identity.whole_file_hash,
            extraction_status="complete",
            extraction_error=None,
            extraction_provider=identity.extraction_provider,
            extraction_version=identity.extraction_version,
        )
    )
    identity_clause = (
        wip_snapshots.c.manuscript_id == prepared.manuscript_id,
        wip_snapshots.c.file_id == prepared.file_id,
        wip_snapshots.c.whole_file_hash == identity.whole_file_hash,
        wip_snapshots.c.extracted_text_hash == identity.extracted_text_hash,
        wip_snapshots.c.reason == reason,
        wip_snapshots.c.reason_detail == reason_detail,
    )
    existing = conn.execute(select(wip_snapshots).where(*identity_clause)).mappings().first()
    if existing:
        return _snapshot_dict(existing), False
    result = conn.execute(
        insert(wip_snapshots).values(
            uid=str(uuid4()),
            manuscript_id=prepared.manuscript_id,
            file_id=prepared.file_id,
            whole_file_hash=identity.whole_file_hash,
            extracted_text_hash=identity.extracted_text_hash,
            section_hashes_json=identity.section_hashes or None,
            evidence_context_json=list(identity.evidence_contexts),
            extracted_char_count=identity.extracted_char_count,
            extraction_provider=identity.extraction_provider,
            extraction_version=identity.extraction_version,
            reason=reason,
            reason_detail=reason_detail,
        )
    )
    snapshot_id = int(result.inserted_primary_key[0])
    row = conn.execute(select(wip_snapshots).where(wip_snapshots.c.id == snapshot_id)).mappings().one()
    add_activity(
        conn,
        prepared.manuscript_id,
        "checkpoint-created",
        f"Created {reason.replace('-', ' ')} checkpoint for {prepared.relative_path}",
        metadata={"reason": reason, "reason_detail": reason_detail},
        related_entity_type="snapshot",
        related_entity_id=str(snapshot_id),
    )
    return _snapshot_dict(row), True


def mark_extraction_failure(
    conn: Connection,
    manuscript_id: int,
    file_id: int,
    error: ContentIdentityError,
    *,
    reason: str,
) -> None:
    conn.execute(
        update(wip_files)
        .where(wip_files.c.id == file_id, wip_files.c.manuscript_id == manuscript_id)
        .values(extraction_status=error.status, extraction_error=str(error)[:2000])
    )
    add_activity(
        conn,
        manuscript_id,
        "checkpoint-skipped",
        f"Could not create {reason.replace('-', ' ')} checkpoint: {error}",
        related_entity_type="file",
        related_entity_id=str(file_id),
    )


def list_snapshots(conn: Connection, manuscript_id: int) -> list[dict]:
    primary = (
        conn.execute(
            select(wip_files).where(
                wip_files.c.manuscript_id == manuscript_id,
                wip_files.c.is_primary.is_(True),
            )
        )
        .mappings()
        .first()
    )
    rows = conn.execute(
        select(wip_snapshots)
        .where(wip_snapshots.c.manuscript_id == manuscript_id)
        .order_by(wip_snapshots.c.created_at.desc(), wip_snapshots.c.id.desc())
    ).mappings()
    result = []
    for row in rows:
        item = _snapshot_dict(row)
        item["identity_status"], item["status_detail"] = _identity_status(item, primary)
        result.append(item)
    return result


def _identity_status(snapshot: dict[str, Any], primary) -> tuple[str, str]:
    if primary is None or int(primary["id"]) != int(snapshot["file_id"]):
        return "stale", "The primary manuscript file was replaced."
    if primary["existence_state"] != "available":
        return "stale", "The primary manuscript file is unavailable."
    current_whole = primary["whole_file_hash"]
    extracted_from = primary["extracted_from_whole_hash"]
    if current_whole == snapshot["whole_file_hash"]:
        return "current", "The primary file matches this checkpoint."
    if extracted_from != current_whole:
        return "potentially-stale", "The file changed and its current text has not been extracted yet."
    if primary["extracted_text_hash"] == snapshot["extracted_text_hash"]:
        return "current", "The file changed, but its normalized extracted text still matches."
    return "stale", "The normalized extracted manuscript text changed."


def _snapshot_dict(row) -> dict:
    data = dict(row)
    if isinstance(data.get("created_at"), datetime):
        data["created_at"] = data["created_at"].isoformat()
    return data
