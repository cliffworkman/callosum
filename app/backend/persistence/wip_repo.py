"""Transactional data access and reconciliation for WIP roots/manuscripts/files."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, case, delete, func, insert, or_, select, update

from app.backend.persistence.schema import wip_activity_events, wip_files, wip_manuscripts, wip_watch_roots
from app.backend.wip.discovery import ScanInspection


def create_watch_root(
    conn: Connection,
    *,
    path: str,
    path_key: str,
    discovery_mode: str,
    excluded_children: list[str],
) -> dict:
    existing = conn.execute(select(wip_watch_roots).where(wip_watch_roots.c.path_key == path_key)).mappings().first()
    if existing:
        return dict(existing)
    result = conn.execute(
        insert(wip_watch_roots).values(
            uid=str(uuid4()),
            path=path,
            path_key=path_key,
            discovery_mode=discovery_mode,
            excluded_children_json=excluded_children,
        )
    )
    return get_watch_root(conn, int(result.inserted_primary_key[0]))


def get_watch_root(conn: Connection, root_id: int) -> dict | None:
    row = conn.execute(select(wip_watch_roots).where(wip_watch_roots.c.id == root_id)).mappings().first()
    return dict(row) if row else None


def list_watch_roots(conn: Connection) -> list[dict]:
    return [dict(row) for row in conn.execute(select(wip_watch_roots).order_by(wip_watch_roots.c.path)).mappings()]


def update_watch_root(conn: Connection, root_id: int, values: dict[str, Any]) -> dict | None:
    allowed = {"path", "path_key", "discovery_mode", "enabled", "excluded_children_json"}
    clean = {key: value for key, value in values.items() if key in allowed}
    if clean:
        clean["updated_at"] = func.current_timestamp()
        conn.execute(update(wip_watch_roots).where(wip_watch_roots.c.id == root_id).values(**clean))
    return get_watch_root(conn, root_id)


def delete_watch_root(conn: Connection, root_id: int) -> bool:
    return bool(conn.execute(delete(wip_watch_roots).where(wip_watch_roots.c.id == root_id)).rowcount)


def reconcile_watch_root(conn: Connection, root: dict, inspection: ScanInspection) -> dict[str, int]:
    root_id = int(root["id"])
    current = {
        row["path_key"]: dict(row)
        for row in conn.execute(select(wip_manuscripts).where(wip_manuscripts.c.watch_root_id == root_id)).mappings()
    }
    discovered_keys: set[str] = set()
    counts = {
        "added": 0,
        "restored": 0,
        "missing": 0,
        "files_added": 0,
        "files_missing": 0,
        "errors": len(inspection.errors),
    }

    for item in inspection.manuscripts:
        discovered_keys.add(item.path_key)
        manuscript = (
            conn.execute(select(wip_manuscripts).where(wip_manuscripts.c.path_key == item.path_key)).mappings().first()
        )
        if manuscript is None:
            result = conn.execute(
                insert(wip_manuscripts).values(
                    uid=str(uuid4()),
                    watch_root_id=root_id,
                    root_path=item.root_path,
                    path_key=item.path_key,
                    derived_title=item.derived_title,
                    last_filesystem_activity_at=item.last_activity_at,
                )
            )
            manuscript_id = int(result.inserted_primary_key[0])
            from app.backend.persistence.wip_workflow_repo import seed_default_sections

            seed_default_sections(conn, manuscript_id)
            counts["added"] += 1
            add_activity(conn, manuscript_id, "manuscript-discovered", f"Discovered {item.derived_title}")
        else:
            manuscript_id = int(manuscript["id"])
            restored = manuscript["state"] == "missing"
            values: dict[str, Any] = {
                "watch_root_id": root_id,
                "root_path": item.root_path,
                "derived_title": item.derived_title,
                "last_filesystem_activity_at": item.last_activity_at,
                "missing_since": None,
                "updated_at": func.current_timestamp(),
            }
            if restored:
                values["state"] = "active"
            conn.execute(update(wip_manuscripts).where(wip_manuscripts.c.id == manuscript_id).values(**values))
            if restored:
                counts["restored"] += 1
                add_activity(conn, manuscript_id, "folder-restored", f"Restored {item.derived_title}")
        file_counts = _reconcile_files(conn, manuscript_id, item.files)
        counts["files_added"] += file_counts["added"]
        counts["files_missing"] += file_counts["missing"]

    can_mark_missing = not inspection.errors or not inspection.manuscripts
    for key, manuscript in current.items():
        if not can_mark_missing or key in discovered_keys or manuscript["state"] in {"archived", "missing"}:
            continue
        manuscript_id = int(manuscript["id"])
        conn.execute(
            update(wip_manuscripts)
            .where(wip_manuscripts.c.id == manuscript_id)
            .values(state="missing", missing_since=func.current_timestamp(), updated_at=func.current_timestamp())
        )
        counts["missing"] += 1
        add_activity(conn, manuscript_id, "folder-missing", f"Folder unavailable: {manuscript['root_path']}")

    detail = "\n".join(inspection.errors[:25]) or None
    status = "error" if inspection.errors and not inspection.manuscripts else "done"
    conn.execute(
        update(wip_watch_roots)
        .where(wip_watch_roots.c.id == root_id)
        .values(
            last_scanned_at=func.current_timestamp(),
            last_scan_status=status,
            last_scan_detail=detail,
            updated_at=func.current_timestamp(),
        )
    )
    return counts


def _reconcile_files(conn: Connection, manuscript_id: int, files) -> dict[str, int]:
    current = {
        row["path_key"]: dict(row)
        for row in conn.execute(select(wip_files).where(wip_files.c.manuscript_id == manuscript_id)).mappings()
    }
    seen: set[str] = set()
    added = missing = 0
    for item in files:
        seen.add(item.path_key)
        existing = current.get(item.path_key)
        if existing is None:
            result = conn.execute(
                insert(wip_files).values(
                    uid=str(uuid4()),
                    manuscript_id=manuscript_id,
                    relative_path=item.relative_path,
                    path_key=item.path_key,
                    role=item.role,
                    file_size=item.file_size,
                    modified_at=item.modified_at,
                    whole_file_hash=item.whole_file_hash,
                    last_scanned_at=func.current_timestamp(),
                )
            )
            file_id = int(result.inserted_primary_key[0])
            added += 1
            add_activity(
                conn,
                manuscript_id,
                "file-added",
                f"Found {item.relative_path}",
                related_entity_type="file",
                related_entity_id=str(file_id),
            )
            continue
        restored = existing["existence_state"] == "missing"
        conn.execute(
            update(wip_files)
            .where(wip_files.c.id == existing["id"])
            .values(
                relative_path=item.relative_path,
                role=existing["role"],
                existence_state="available",
                file_size=item.file_size,
                modified_at=item.modified_at,
                whole_file_hash=item.whole_file_hash,
                last_scanned_at=func.current_timestamp(),
            )
        )
        if restored:
            add_activity(
                conn,
                manuscript_id,
                "file-restored",
                f"Restored {item.relative_path}",
                related_entity_type="file",
                related_entity_id=str(existing["id"]),
            )
    for key, existing in current.items():
        if key in seen or existing["existence_state"] == "missing":
            continue
        conn.execute(
            update(wip_files)
            .where(wip_files.c.id == existing["id"])
            .values(existence_state="missing", last_scanned_at=func.current_timestamp())
        )
        missing += 1
        add_activity(
            conn,
            manuscript_id,
            "file-missing",
            f"File unavailable: {existing['relative_path']}",
            related_entity_type="file",
            related_entity_id=str(existing["id"]),
        )
    return {"added": added, "missing": missing}


def list_manuscripts(
    conn: Connection,
    *,
    query: str = "",
    state: str | None = None,
    stage: str | None = None,
    sort: str = "activity",
) -> list[dict]:
    file_counts = (
        select(
            wip_files.c.manuscript_id,
            func.count(wip_files.c.id).label("file_count"),
            func.sum(case((wip_files.c.existence_state == "missing", 1), else_=0)).label("missing_file_count"),
        )
        .group_by(wip_files.c.manuscript_id)
        .subquery()
    )
    stmt = select(
        wip_manuscripts,
        func.coalesce(file_counts.c.file_count, 0).label("file_count"),
        func.coalesce(file_counts.c.missing_file_count, 0).label("missing_file_count"),
    ).outerjoin(file_counts, file_counts.c.manuscript_id == wip_manuscripts.c.id)
    if query.strip():
        needle = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                wip_manuscripts.c.derived_title.ilike(needle),
                wip_manuscripts.c.title_override.ilike(needle),
                wip_manuscripts.c.target_journal.ilike(needle),
                wip_manuscripts.c.notes.ilike(needle),
            )
        )
    if state:
        stmt = stmt.where(wip_manuscripts.c.state == state)
    if stage:
        stmt = stmt.where(wip_manuscripts.c.stage == stage)
    order = {
        "title": func.coalesce(wip_manuscripts.c.title_override, wip_manuscripts.c.derived_title).asc(),
        "created": wip_manuscripts.c.created_at.desc(),
        "deadline": wip_manuscripts.c.deadline.asc().nullslast(),
        "stage": wip_manuscripts.c.stage.asc(),
    }.get(sort, wip_manuscripts.c.last_filesystem_activity_at.desc().nullslast())
    return [_manuscript_dict(row) for row in conn.execute(stmt.order_by(order, wip_manuscripts.c.id)).mappings()]


def get_manuscript(conn: Connection, manuscript_id: int) -> dict | None:
    row = conn.execute(select(wip_manuscripts).where(wip_manuscripts.c.id == manuscript_id)).mappings().first()
    return _manuscript_dict(row) if row else None


def update_manuscript(conn: Connection, manuscript_id: int, values: dict[str, Any]) -> dict | None:
    allowed = {"title_override", "state", "manuscript_type", "stage", "target_journal", "deadline", "notes"}
    clean = {key: value for key, value in values.items() if key in allowed}
    before = get_manuscript(conn, manuscript_id)
    if before is None:
        return None
    if clean:
        clean["updated_at"] = func.current_timestamp()
        conn.execute(update(wip_manuscripts).where(wip_manuscripts.c.id == manuscript_id).values(**clean))
        if "stage" in clean and clean["stage"] != before["stage"]:
            add_activity(conn, manuscript_id, "stage-changed", f"Stage changed to {clean['stage']}")
        if "title_override" in clean and clean["title_override"] != before["title_override"]:
            add_activity(conn, manuscript_id, "manuscript-renamed", "Display title changed")
    return get_manuscript(conn, manuscript_id)


def list_files(conn: Connection, manuscript_id: int) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            select(wip_files).where(wip_files.c.manuscript_id == manuscript_id).order_by(wip_files.c.relative_path)
        ).mappings()
    ]


def get_file(conn: Connection, manuscript_id: int, file_id: int) -> dict | None:
    row = (
        conn.execute(
            select(wip_files).where(
                wip_files.c.id == file_id,
                wip_files.c.manuscript_id == manuscript_id,
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def update_file(conn: Connection, manuscript_id: int, file_id: int, values: dict[str, Any]) -> dict | None:
    existing = get_file(conn, manuscript_id, file_id)
    if existing is None:
        return None
    clean = {key: value for key, value in values.items() if key in {"role", "is_primary"}}
    if clean.get("is_primary"):
        conn.execute(
            update(wip_files)
            .where(wip_files.c.manuscript_id == manuscript_id, wip_files.c.id != file_id)
            .values(is_primary=False)
        )
    if clean:
        conn.execute(update(wip_files).where(wip_files.c.id == file_id).values(**clean))
        if clean.get("is_primary"):
            add_activity(
                conn,
                manuscript_id,
                "primary-file-changed",
                f"Primary manuscript: {existing['relative_path']}",
                related_entity_type="file",
                related_entity_id=str(file_id),
            )
    return get_file(conn, manuscript_id, file_id)


def list_activity(conn: Connection, manuscript_id: int, *, limit: int = 100) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            select(wip_activity_events)
            .where(wip_activity_events.c.manuscript_id == manuscript_id)
            .order_by(wip_activity_events.c.created_at.desc(), wip_activity_events.c.id.desc())
            .limit(limit)
        ).mappings()
    ]


def add_activity(
    conn: Connection,
    manuscript_id: int,
    event_type: str,
    summary: str,
    *,
    metadata: dict | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
) -> None:
    conn.execute(
        insert(wip_activity_events).values(
            manuscript_id=manuscript_id,
            event_type=event_type,
            summary=summary,
            metadata_json=metadata,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
    )


def _manuscript_dict(row) -> dict:
    data = dict(row)
    data["display_title"] = data.get("title_override") or data.get("derived_title")
    for key, value in list(data.items()):
        if isinstance(value, (datetime, date)):
            data[key] = value.isoformat()
    return data
