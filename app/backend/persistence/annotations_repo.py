"""SQLAlchemy Core data-access for native annotations (user highlights + synthesis marks).

Split out of `repository.py` (inc 91) to keep that module under the 600-line cap (rule #1) — the
annotations table is a cohesive concern, like `dedup_repo` (inc 67) / `tags_repo` (inc 71). This is a
behavior-preserving move; imported (e.g. Zotero) annotation rows leave `source` NULL and are not listed here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, RowMapping, delete, func, insert, select, update

from app.backend.persistence.schema import annotations

# Native annotation sources stored in (and surfaced from) the shared annotations
# table. Imported rows (e.g. Zotero) leave `source` NULL and are not listed here.
NATIVE_ANNOTATION_SOURCES = ("user", "synthesis")

# Coordinate basis recorded for native annotation bboxes — the increment-29 overlay
# model (page-relative PDF points, top-left origin).
ANNOTATION_COORDINATE_SYSTEM = "pdf-points-top-left"


def create_annotation(
    conn: Connection,
    *,
    paper_id: int,
    page: int,
    color: str,
    bboxes_json: Any,
    anchor_text: str,
    prefix: str | None = None,
    suffix: str | None = None,
    attachment_id: int | None = None,
    source: str = "user",
    note: str | None = None,
) -> int:
    result = conn.execute(
        insert(annotations).values(
            paper_id=paper_id,
            attachment_id=attachment_id,
            page=page,
            color=color,
            bboxes_json=bboxes_json,
            anchor_text=anchor_text,
            prefix=prefix,
            suffix=suffix,
            source=source,
            note=note,
            coordinate_system=ANNOTATION_COORDINATE_SYSTEM,
        )
    )
    return int(result.inserted_primary_key[0])


def get_annotation(conn: Connection, annotation_id: int) -> RowMapping | None:
    return conn.execute(select(annotations).where(annotations.c.id == annotation_id)).mappings().one_or_none()


def list_annotations_for_paper(conn: Connection, paper_id: int) -> list[RowMapping]:
    stmt = (
        select(annotations)
        .where(
            annotations.c.paper_id == paper_id,
            annotations.c.source.in_(NATIVE_ANNOTATION_SOURCES),
        )
        .order_by(annotations.c.page, annotations.c.id)
    )
    return list(conn.execute(stmt).mappings())


def delete_annotation(conn: Connection, annotation_id: int) -> bool:
    result = conn.execute(delete(annotations).where(annotations.c.id == annotation_id))
    return bool(result.rowcount)


# Sentinel distinguishing "field not supplied" from an explicit None (clear) in a
# partial update — lets a PATCH set note=None (clear) without touching color, etc.
_UNSET: Any = object()


def update_annotation(
    conn: Connection,
    annotation_id: int,
    *,
    note: Any = _UNSET,
    color: Any = _UNSET,
) -> bool:
    values: dict[str, Any] = {}
    if note is not _UNSET:
        values["note"] = note
    if color is not _UNSET:
        values["color"] = color
    if not values:
        return False
    values["updated_at"] = func.current_timestamp()
    result = conn.execute(update(annotations).where(annotations.c.id == annotation_id).values(**values))
    return bool(result.rowcount)
