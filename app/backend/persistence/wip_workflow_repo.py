"""Transactional workflow records for WIP manuscripts."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, delete, func, insert, select, update

from app.backend.persistence.schema import papers, wip_references, wip_sections, wip_tasks
from app.backend.persistence.wip_repo import add_activity

DEFAULT_SECTIONS = (
    "Title page",
    "Abstract",
    "Introduction",
    "Method",
    "Results",
    "Discussion",
    "References",
    "Tables",
    "Figures",
    "Supplement",
    "Open practices statement",
    "Author contributions",
    "Data availability statement",
)


def seed_default_sections(conn: Connection, manuscript_id: int) -> None:
    exists = conn.execute(
        select(wip_sections.c.id).where(wip_sections.c.manuscript_id == manuscript_id).limit(1)
    ).first()
    if exists:
        return
    conn.execute(
        insert(wip_sections),
        [
            {
                "uid": str(uuid4()),
                "manuscript_id": manuscript_id,
                "name": name,
                "position": position,
            }
            for position, name in enumerate(DEFAULT_SECTIONS)
        ],
    )


def list_sections(conn: Connection, manuscript_id: int) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            select(wip_sections).where(wip_sections.c.manuscript_id == manuscript_id).order_by(wip_sections.c.position)
        ).mappings()
    ]


def create_section(conn: Connection, manuscript_id: int, name: str) -> dict:
    position = (
        int(
            conn.execute(
                select(func.coalesce(func.max(wip_sections.c.position), -1)).where(
                    wip_sections.c.manuscript_id == manuscript_id
                )
            ).scalar_one()
        )
        + 1
    )
    result = conn.execute(
        insert(wip_sections).values(
            uid=str(uuid4()),
            manuscript_id=manuscript_id,
            name=name,
            position=position,
            is_custom=True,
        )
    )
    section_id = int(result.inserted_primary_key[0])
    add_activity(
        conn,
        manuscript_id,
        "section-added",
        f"Added section {name}",
        related_entity_type="section",
        related_entity_id=str(section_id),
    )
    return dict(conn.execute(select(wip_sections).where(wip_sections.c.id == section_id)).mappings().one())


def update_section(conn: Connection, manuscript_id: int, section_id: int, values: dict[str, Any]) -> dict | None:
    before = (
        conn.execute(
            select(wip_sections).where(
                wip_sections.c.id == section_id,
                wip_sections.c.manuscript_id == manuscript_id,
            )
        )
        .mappings()
        .first()
    )
    if before is None:
        return None
    allowed = {"name", "status", "notes"}
    clean = {key: value for key, value in values.items() if key in allowed}
    if clean:
        clean["updated_at"] = func.current_timestamp()
        conn.execute(update(wip_sections).where(wip_sections.c.id == section_id).values(**clean))
        if "status" in clean and clean["status"] != before["status"]:
            add_activity(
                conn,
                manuscript_id,
                "section-status-changed",
                f"{before['name']}: {clean['status'].replace('-', ' ')}",
                related_entity_type="section",
                related_entity_id=str(section_id),
            )
    return dict(conn.execute(select(wip_sections).where(wip_sections.c.id == section_id)).mappings().one())


def reorder_sections(conn: Connection, manuscript_id: int, section_ids: list[int]) -> list[dict] | None:
    current = list_sections(conn, manuscript_id)
    if set(section_ids) != {int(row["id"]) for row in current} or len(section_ids) != len(current):
        return None
    for offset, section_id in enumerate(section_ids):
        conn.execute(update(wip_sections).where(wip_sections.c.id == section_id).values(position=-(offset + 1)))
    for position, section_id in enumerate(section_ids):
        conn.execute(update(wip_sections).where(wip_sections.c.id == section_id).values(position=position))
    add_activity(conn, manuscript_id, "sections-reordered", "Reordered manuscript sections")
    return list_sections(conn, manuscript_id)


def delete_section(conn: Connection, manuscript_id: int, section_id: int) -> bool:
    row = (
        conn.execute(
            select(wip_sections).where(
                wip_sections.c.id == section_id,
                wip_sections.c.manuscript_id == manuscript_id,
            )
        )
        .mappings()
        .first()
    )
    if row is None or not row["is_custom"]:
        return False
    conn.execute(delete(wip_sections).where(wip_sections.c.id == section_id))
    _compact_sections(conn, manuscript_id)
    add_activity(conn, manuscript_id, "section-deleted", f"Deleted custom section {row['name']}")
    return True


def _compact_sections(conn: Connection, manuscript_id: int) -> None:
    ids = [
        int(value)
        for value in conn.execute(
            select(wip_sections.c.id)
            .where(wip_sections.c.manuscript_id == manuscript_id)
            .order_by(wip_sections.c.position)
        ).scalars()
    ]
    for offset, section_id in enumerate(ids):
        conn.execute(update(wip_sections).where(wip_sections.c.id == section_id).values(position=-(offset + 1)))
    for position, section_id in enumerate(ids):
        conn.execute(update(wip_sections).where(wip_sections.c.id == section_id).values(position=position))


def list_tasks(conn: Connection, manuscript_id: int) -> list[dict]:
    return [
        _serializable(row)
        for row in conn.execute(
            select(wip_tasks)
            .where(wip_tasks.c.manuscript_id == manuscript_id)
            .order_by(wip_tasks.c.completed_at.is_not(None), wip_tasks.c.due_date, wip_tasks.c.created_at.desc())
        ).mappings()
    ]


def create_task(conn: Connection, manuscript_id: int, values: dict[str, Any]) -> dict:
    result = conn.execute(insert(wip_tasks).values(uid=str(uuid4()), manuscript_id=manuscript_id, **values))
    task_id = int(result.inserted_primary_key[0])
    add_activity(
        conn,
        manuscript_id,
        "task-created",
        f"Added task {values['title']}",
        related_entity_type="task",
        related_entity_id=str(task_id),
    )
    return _serializable(conn.execute(select(wip_tasks).where(wip_tasks.c.id == task_id)).mappings().one())


def update_task(conn: Connection, manuscript_id: int, task_id: int, values: dict[str, Any]) -> dict | None:
    before = (
        conn.execute(select(wip_tasks).where(wip_tasks.c.id == task_id, wip_tasks.c.manuscript_id == manuscript_id))
        .mappings()
        .first()
    )
    if before is None:
        return None
    allowed = {"title", "description", "status", "due_date", "section_id", "file_id", "paper_id", "finding_id"}
    clean = {key: value for key, value in values.items() if key in allowed}
    if "status" in clean:
        clean["completed_at"] = func.current_timestamp() if clean["status"] == "complete" else None
    clean["updated_at"] = func.current_timestamp()
    conn.execute(update(wip_tasks).where(wip_tasks.c.id == task_id).values(**clean))
    if "status" in clean and clean["status"] != before["status"]:
        event = "task-completed" if clean["status"] == "complete" else "task-status-changed"
        add_activity(conn, manuscript_id, event, f"{before['title']}: {clean['status'].replace('-', ' ')}")
    return _serializable(conn.execute(select(wip_tasks).where(wip_tasks.c.id == task_id)).mappings().one())


def delete_task(conn: Connection, manuscript_id: int, task_id: int) -> bool:
    return bool(
        conn.execute(
            delete(wip_tasks).where(wip_tasks.c.id == task_id, wip_tasks.c.manuscript_id == manuscript_id)
        ).rowcount
    )


def list_references(conn: Connection, manuscript_id: int) -> list[dict]:
    stmt = (
        select(
            wip_references,
            papers.c.title.label("paper_title"),
            papers.c.year.label("paper_year"),
        )
        .join(papers, papers.c.id == wip_references.c.paper_id)
        .where(wip_references.c.manuscript_id == manuscript_id)
        .order_by(papers.c.title)
    )
    return [dict(row) for row in conn.execute(stmt).mappings()]


def upsert_reference(conn: Connection, manuscript_id: int, paper_id: int, state: str, notes: str | None) -> dict | None:
    if conn.execute(select(papers.c.id).where(papers.c.id == paper_id)).first() is None:
        return None
    existing = (
        conn.execute(
            select(wip_references).where(
                wip_references.c.manuscript_id == manuscript_id,
                wip_references.c.paper_id == paper_id,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        conn.execute(
            update(wip_references)
            .where(wip_references.c.id == existing["id"])
            .values(relationship_state=state, notes=notes, updated_at=func.current_timestamp())
        )
    else:
        conn.execute(
            insert(wip_references).values(
                manuscript_id=manuscript_id,
                paper_id=paper_id,
                relationship_state=state,
                notes=notes,
            )
        )
        add_activity(conn, manuscript_id, "reference-linked", f"Linked Library paper {paper_id}")
    return next(row for row in list_references(conn, manuscript_id) if row["paper_id"] == paper_id)


def delete_reference(conn: Connection, manuscript_id: int, paper_id: int) -> bool:
    deleted = conn.execute(
        delete(wip_references).where(
            wip_references.c.manuscript_id == manuscript_id,
            wip_references.c.paper_id == paper_id,
        )
    ).rowcount
    if deleted:
        add_activity(conn, manuscript_id, "reference-unlinked", f"Unlinked Library paper {paper_id}")
    return bool(deleted)


def list_paper_wips(conn: Connection, paper_id: int) -> list[dict]:
    from app.backend.persistence.schema import wip_manuscripts

    stmt = (
        select(
            wip_manuscripts.c.id,
            wip_manuscripts.c.uid,
            func.coalesce(wip_manuscripts.c.title_override, wip_manuscripts.c.derived_title).label("display_title"),
            wip_references.c.relationship_state,
        )
        .join(wip_references, wip_references.c.manuscript_id == wip_manuscripts.c.id)
        .where(wip_references.c.paper_id == paper_id)
    )
    return [dict(row) for row in conn.execute(stmt).mappings()]


def _serializable(row) -> dict:
    data = dict(row)
    for key, value in list(data.items()):
        if isinstance(value, date):
            data[key] = value.isoformat()
    return data
