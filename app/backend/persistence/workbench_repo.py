"""Data access for the meta-analysis extraction workspace (workbench SP2a, inc 253).

Projects (dataset + template) -> rows (one effect each, optionally linked to a paper) -> cells (a value + its exact
source provenance). The role-tagged cells of a row map to the SP1 effect-size converter's inputs (``CONVERT_MAP``).
Bound-param SQL throughout (rule #3); the workspace is fully local (no egress).
"""

from __future__ import annotations

import json

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection

from app.backend.persistence.schema import ma_cells, ma_projects, ma_proposals, ma_rows, papers

# --- the preset templates (a project's `design` seeds template_json; the user may add non-role columns) ------------
# Each field: {key, label, type in {number,text,choice}, role (a converter input key, or None for a moderator/notes
# column), options? (for choice). A role column's key == its converter input key, so the convert hook is deterministic.
DESIGN_TEMPLATES: dict[str, list[dict]] = {
    "two_group_continuous": [
        {"key": "n1", "label": "N (group 1)", "type": "number", "role": "n1"},
        {"key": "m1", "label": "Mean (group 1)", "type": "number", "role": "m1"},
        {"key": "s1", "label": "SD (group 1)", "type": "number", "role": "s1"},
        {"key": "n2", "label": "N (group 2)", "type": "number", "role": "n2"},
        {"key": "m2", "label": "Mean (group 2)", "type": "number", "role": "m2"},
        {"key": "s2", "label": "SD (group 2)", "type": "number", "role": "s2"},
    ],
    "binary_2x2": [
        {"key": "a", "label": "Events (group 1)", "type": "number", "role": "a"},
        {"key": "b", "label": "Non-events (group 1)", "type": "number", "role": "b"},
        {"key": "c", "label": "Events (group 2)", "type": "number", "role": "c"},
        {"key": "d", "label": "Non-events (group 2)", "type": "number", "role": "d"},
        {"key": "measure", "label": "Measure", "type": "choice", "role": "measure", "options": ["or", "rr", "rd"]},
    ],
    "correlation": [
        {"key": "r", "label": "Correlation r", "type": "number", "role": "r"},
        {"key": "n", "label": "N", "type": "number", "role": "n"},
    ],
}
DESIGNS = set(DESIGN_TEMPLATES)


def seed_template(design: str) -> list[dict]:
    return [dict(f) for f in DESIGN_TEMPLATES[design]]


def role_columns(template: list[dict]) -> dict[str, dict]:
    """The design's spine — {key: field} for fields carrying a role (converter inputs; not user-removable)."""
    return {f["key"]: f for f in template if f.get("role")}


# --- the convert hook: a design + a row's cell values -> (family, inputs) for methods.effectsize.convert -----------
# Cell values pass through as-is (strings); convert coerces + fails closed on blank/None (-> the router's 422).
def _two_group(cells: dict) -> tuple[str, dict]:
    keys = ("m1", "s1", "n1", "m2", "s2", "n2")
    return "smd", {"method": "means", **{k: cells.get(k) for k in keys}}


def _binary(cells: dict) -> tuple[str, dict]:
    inp = {k: cells.get(k) for k in ("a", "b", "c", "d")}
    inp["measure"] = cells.get("measure") or "or"
    return "binary", inp


def _correlation(cells: dict) -> tuple[str, dict]:
    return "correlation", {k: cells.get(k) for k in ("r", "n")}


CONVERT_MAP = {
    "two_group_continuous": _two_group,
    "binary_2x2": _binary,
    "correlation": _correlation,
}


# --- projects ------------------------------------------------------------------------------------------------------
def list_projects(conn: Connection) -> list[dict]:
    row_count = select(func.count(ma_rows.c.id)).where(ma_rows.c.project_id == ma_projects.c.id).scalar_subquery()
    rows = (
        conn.execute(
            select(
                ma_projects.c.id,
                ma_projects.c.name,
                ma_projects.c.design,
                ma_projects.c.updated_at,
                row_count.label("row_count"),
            ).order_by(ma_projects.c.updated_at.desc(), ma_projects.c.id.desc())
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def create_project(conn: Connection, *, name: str, design: str) -> int:
    template = seed_template(design)
    res = conn.execute(insert(ma_projects).values(name=name, design=design, template_json=json.dumps(template)))
    return int(res.inserted_primary_key[0])


def get_project(conn: Connection, project_id: int) -> dict | None:
    row = conn.execute(select(ma_projects).where(ma_projects.c.id == project_id)).mappings().first()
    return dict(row) if row else None


def update_project(conn: Connection, project_id: int, *, name=None, protocol_note=None, template_json=None) -> None:
    values: dict = {"updated_at": func.current_timestamp()}
    if name is not None:
        values["name"] = name
    if protocol_note is not None:
        values["protocol_note"] = protocol_note
    if template_json is not None:
        values["template_json"] = template_json
    conn.execute(update(ma_projects).where(ma_projects.c.id == project_id).values(**values))


def delete_project(conn: Connection, project_id: int) -> bool:
    return conn.execute(delete(ma_projects).where(ma_projects.c.id == project_id)).rowcount > 0


def _touch(conn: Connection, project_id: int) -> None:
    conn.execute(update(ma_projects).where(ma_projects.c.id == project_id).values(updated_at=func.current_timestamp()))


# --- rows ----------------------------------------------------------------------------------------------------------
def add_row(conn: Connection, project_id: int, *, paper_id=None, label=None) -> int:
    nxt = conn.execute(
        select(func.coalesce(func.max(ma_rows.c.position), -1) + 1).where(ma_rows.c.project_id == project_id)
    ).scalar_one()
    res = conn.execute(insert(ma_rows).values(project_id=project_id, paper_id=paper_id, label=label, position=nxt))
    _touch(conn, project_id)
    return int(res.inserted_primary_key[0])


def get_row(conn: Connection, row_id: int) -> dict | None:
    row = conn.execute(select(ma_rows).where(ma_rows.c.id == row_id)).mappings().first()
    return dict(row) if row else None


def update_row(conn: Connection, row_id: int, *, label=None, paper_id=None, position=None) -> None:
    values: dict = {}
    if label is not None:
        values["label"] = label
    if paper_id is not None:
        values["paper_id"] = paper_id
    if position is not None:
        values["position"] = position
    if values:
        conn.execute(update(ma_rows).where(ma_rows.c.id == row_id).values(**values))


def delete_row(conn: Connection, row_id: int) -> bool:
    return conn.execute(delete(ma_rows).where(ma_rows.c.id == row_id)).rowcount > 0


def set_converted(conn: Connection, row_id: int, converted_json: str | None) -> None:
    conn.execute(update(ma_rows).where(ma_rows.c.id == row_id).values(converted_json=converted_json))


# --- cells ---------------------------------------------------------------------------------------------------------
def upsert_cell(
    conn: Connection, row_id: int, field_key: str, *, value=None, page=None, quote=None, bbox_json=None, origin=None
) -> None:
    existing = conn.execute(
        select(ma_cells.c.id).where(ma_cells.c.row_id == row_id, ma_cells.c.field_key == field_key)
    ).scalar()
    payload = {"value": value, "page": page, "quote": quote, "bbox_json": bbox_json, "origin": origin}
    if existing is not None:
        conn.execute(update(ma_cells).where(ma_cells.c.id == existing).values(**payload))
    else:
        conn.execute(insert(ma_cells).values(row_id=row_id, field_key=field_key, **payload))


def cell_values(conn: Connection, row_id: int) -> dict[str, str | None]:
    """{field_key: value} — the raw values fed to the convert hook."""
    rows = conn.execute(select(ma_cells.c.field_key, ma_cells.c.value).where(ma_cells.c.row_id == row_id)).all()
    return {k: v for k, v in rows}


def _cells_full(conn: Connection, row_ids: list[int]) -> dict[int, dict[str, dict]]:
    if not row_ids:
        return {}
    out: dict[int, dict[str, dict]] = {rid: {} for rid in row_ids}
    rows = conn.execute(select(ma_cells).where(ma_cells.c.row_id.in_(row_ids))).mappings().all()
    for c in rows:
        out.setdefault(c["row_id"], {})[c["field_key"]] = {
            "value": c["value"],
            "page": c["page"],
            "quote": c["quote"],
            "bbox_json": c["bbox_json"],
            "origin": c["origin"],
        }
    return out


# --- proposals (SP2b funnel: AI-drafted candidates, isolated from the trusted cells) -------------------------------
def _proposal_dict(p) -> dict:
    return {
        "id": p["id"],
        "row_id": p["row_id"],
        "field_key": p["field_key"],
        "value": p["value"],
        "quote": p["quote"],
        "page": p["page"],
        "bbox_json": p["bbox_json"],
        "anchor_state": p["anchor_state"],
        "reason": p["reason"],
    }


def replace_row_proposals(conn: Connection, row_id: int, proposals: list[dict]) -> None:
    """Replace the row's live candidates with `proposals` (a re-draft supersedes the prior set)."""
    conn.execute(delete(ma_proposals).where(ma_proposals.c.row_id == row_id))
    for p in proposals:
        conn.execute(
            insert(ma_proposals).values(
                row_id=row_id,
                field_key=p["field_key"],
                value=p.get("value"),
                quote=p.get("quote"),
                page=p.get("page"),
                bbox_json=p.get("bbox_json"),
                anchor_state=p["anchor_state"],
                reason=p.get("reason"),
            )
        )


def get_proposal(conn: Connection, proposal_id: int) -> dict | None:
    p = conn.execute(select(ma_proposals).where(ma_proposals.c.id == proposal_id)).mappings().first()
    return _proposal_dict(p) if p else None


def delete_proposal(conn: Connection, proposal_id: int) -> bool:
    return conn.execute(delete(ma_proposals).where(ma_proposals.c.id == proposal_id)).rowcount > 0


def proposals_for_row(conn: Connection, row_id: int) -> list[dict]:
    rows = (
        conn.execute(select(ma_proposals).where(ma_proposals.c.row_id == row_id).order_by(ma_proposals.c.id))
        .mappings()
        .all()
    )
    return [_proposal_dict(p) for p in rows]


def _proposals_for_rows(conn: Connection, row_ids: list[int]) -> dict[int, list[dict]]:
    if not row_ids:
        return {}
    out: dict[int, list[dict]] = {rid: [] for rid in row_ids}
    rows = (
        conn.execute(select(ma_proposals).where(ma_proposals.c.row_id.in_(row_ids)).order_by(ma_proposals.c.id))
        .mappings()
        .all()
    )
    for p in rows:
        out.setdefault(p["row_id"], []).append(_proposal_dict(p))
    return out


def _paper_titles(conn: Connection, paper_ids: list[int]) -> dict[int, str]:
    ids = [p for p in paper_ids if p is not None]
    if not ids:
        return {}
    rows = conn.execute(select(papers.c.id, papers.c.title).where(papers.c.id.in_(ids))).all()
    return {pid: title for pid, title in rows}


def project_view(conn: Connection, project_id: int) -> dict | None:
    proj = get_project(conn, project_id)
    if proj is None:
        return None
    rows = (
        conn.execute(
            select(ma_rows).where(ma_rows.c.project_id == project_id).order_by(ma_rows.c.position, ma_rows.c.id)
        )
        .mappings()
        .all()
    )
    row_ids = [r["id"] for r in rows]
    cells = _cells_full(conn, row_ids)
    proposals = _proposals_for_rows(conn, row_ids)
    titles = _paper_titles(conn, [r["paper_id"] for r in rows])
    view_rows = []
    for r in rows:
        view_rows.append(
            {
                "id": r["id"],
                "paper_id": r["paper_id"],
                "paper_title": titles.get(r["paper_id"]),
                "label": r["label"],
                "position": r["position"],
                "converted": json.loads(r["converted_json"]) if r["converted_json"] else None,
                "cells": cells.get(r["id"], {}),
                "proposals": proposals.get(r["id"], []),
            }
        )
    return {
        "id": proj["id"],
        "name": proj["name"],
        "protocol_note": proj["protocol_note"],
        "design": proj["design"],
        "template": json.loads(proj["template_json"]),
        "rows": view_rows,
    }
