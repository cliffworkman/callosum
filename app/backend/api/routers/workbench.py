"""Meta-analysis extraction workspace endpoints (workbench SP2a-1, inc 253).

A stateful "Extract" workspace: projects (a dataset + a template) -> rows (one effect each, optionally linked to a
library paper) -> cells (a value + its exact source provenance). A row's role-tagged cells feed the SP1 effect-size
converter (``POST …/convert``); the dataset exports to a metafor/JASP-ready CSV + a provenance audit JSON.

The load-bearing boundary (extends SP1): extract / structure / convert / export — NEVER pool / model / adjudicate.
No endpoint combines two rows; export carries data + provenance, never a synthesized estimate; a value is only ever
set by a human. Fully local — no LLM, no egress. Bound-param SQL; typed/validated bodies (rule #3/#4).
"""

from __future__ import annotations

import csv
import io
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.methods.effectsize import convert
from app.backend.persistence import workbench_repo as wr

router = APIRouter()

_KEY_RE = re.compile(r"^[A-Za-z0-9_]{1,80}$")
_FIELD_TYPES = {"number", "text", "choice"}


# --- models --------------------------------------------------------------------------------------------------------
class ProjectSummary(BaseModel):
    id: int
    name: str
    design: str
    row_count: int


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=300)
    design: str


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=300)
    protocol_note: str | None = Field(default=None, max_length=8000)
    template: list[dict] | None = None


class RowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_id: int | None = None
    label: str | None = Field(default=None, max_length=500)


class RowPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = Field(default=None, max_length=500)
    paper_id: int | None = None
    position: int | None = Field(default=None, ge=0)


class CellPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | None = Field(default=None, max_length=500)
    page: int | None = Field(default=None, ge=0)
    quote: str | None = Field(default=None, max_length=4000)
    bbox_json: str | None = Field(default=None, max_length=2000)


# --- helpers -------------------------------------------------------------------------------------------------------
def _validate_template(design: str, submitted: list[dict]) -> None:
    """A submitted template must keep every role column of the design (key/role/type) and only add/edit non-role
    columns. Prevents removing the converter spine or injecting a fake role that would hijack the convert hook."""
    spine = wr.role_columns(wr.seed_template(design))  # {key: field}
    seen: set[str] = set()
    present_roles: set[str] = set()
    for f in submitted:
        if not isinstance(f, dict):
            raise HTTPException(status_code=422, detail="Each template field must be an object.")
        key, typ, role = f.get("key"), f.get("type"), f.get("role")
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise HTTPException(status_code=422, detail="Invalid field key.")
        if key in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate field key: {key}")
        seen.add(key)
        if typ not in _FIELD_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid field type: {typ}")
        if typ == "choice" and not f.get("options"):
            raise HTTPException(status_code=422, detail="A choice field needs options.")
        if role:
            if role != key or key not in spine or typ != spine[key]["type"]:
                raise HTTPException(status_code=422, detail=f"Field '{key}' cannot claim a role.")
            present_roles.add(key)
    if set(spine) - present_roles:
        raise HTTPException(status_code=422, detail="A design's required (role) columns cannot be removed.")


def _project_or_404(conn: Connection, project_id: int) -> dict:
    view = wr.project_view(conn, project_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return view


def _row_or_404(conn: Connection, row_id: int) -> dict:
    row = wr.get_row(conn, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return row


# --- projects ------------------------------------------------------------------------------------------------------
@router.get("/workbench/projects", response_model=list[ProjectSummary])
def list_projects(conn: Connection = Depends(get_connection)) -> list[ProjectSummary]:
    return [ProjectSummary(**p) for p in wr.list_projects(conn)]


@router.post("/workbench/projects")
def create_project(payload: ProjectCreate, conn: Connection = Depends(get_connection)) -> dict:
    if payload.design not in wr.DESIGNS:
        raise HTTPException(status_code=422, detail=f"Unknown design: {payload.design}")
    pid = wr.create_project(conn, name=payload.name, design=payload.design)
    conn.commit()
    return _project_or_404(conn, pid)


@router.get("/workbench/projects/{project_id}")
def get_project(project_id: int, conn: Connection = Depends(get_connection)) -> dict:
    return _project_or_404(conn, project_id)


@router.patch("/workbench/projects/{project_id}")
def patch_project(project_id: int, payload: ProjectPatch, conn: Connection = Depends(get_connection)) -> dict:
    project = wr.get_project(conn, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    template_json = None
    if payload.template is not None:
        _validate_template(project["design"], payload.template)
        template_json = json.dumps(payload.template)
    wr.update_project(
        conn, project_id, name=payload.name, protocol_note=payload.protocol_note, template_json=template_json
    )
    conn.commit()
    return _project_or_404(conn, project_id)


@router.delete("/workbench/projects/{project_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if not wr.delete_project(conn, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# --- rows ----------------------------------------------------------------------------------------------------------
@router.post("/workbench/projects/{project_id}/rows")
def add_row(project_id: int, payload: RowCreate, conn: Connection = Depends(get_connection)) -> dict:
    if wr.get_project(conn, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.paper_id is not None and not wr._paper_titles(conn, [payload.paper_id]):
        raise HTTPException(status_code=404, detail="Paper not found")
    wr.add_row(conn, project_id, paper_id=payload.paper_id, label=payload.label)
    conn.commit()
    return _project_or_404(conn, project_id)


@router.patch("/workbench/rows/{row_id}")
def patch_row(row_id: int, payload: RowPatch, conn: Connection = Depends(get_connection)) -> dict:
    _row_or_404(conn, row_id)
    wr.update_row(conn, row_id, label=payload.label, paper_id=payload.paper_id, position=payload.position)
    conn.commit()
    return {"ok": True}


@router.delete("/workbench/rows/{row_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_row(row_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if not wr.delete_row(conn, row_id):
        raise HTTPException(status_code=404, detail="Row not found")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# --- cells ---------------------------------------------------------------------------------------------------------
@router.put("/workbench/rows/{row_id}/cells/{field_key}")
def put_cell(row_id: int, field_key: str, payload: CellPut, conn: Connection = Depends(get_connection)) -> dict:
    row = _row_or_404(conn, row_id)
    project = wr.get_project(conn, row["project_id"])
    template = json.loads(project["template_json"])
    if field_key not in {f["key"] for f in template}:
        raise HTTPException(status_code=422, detail="Field is not in this project's template.")
    wr.upsert_cell(
        conn,
        row_id,
        field_key,
        value=payload.value,
        page=payload.page,
        quote=payload.quote,
        bbox_json=payload.bbox_json,
    )
    # A cell changed → the stored effect size is now stale; drop it so it must be re-converted (never silently stale).
    wr.set_converted(conn, row_id, None)
    conn.commit()
    return {"ok": True}


# --- convert (the SP1 hook) ----------------------------------------------------------------------------------------
@router.post("/workbench/rows/{row_id}/convert")
def convert_row(row_id: int, conn: Connection = Depends(get_connection)) -> dict:
    row = _row_or_404(conn, row_id)
    project = wr.get_project(conn, row["project_id"])
    builder = wr.CONVERT_MAP.get(project["design"])
    if builder is None:
        raise HTTPException(status_code=422, detail="This design has no converter mapping.")
    family, inputs = builder(wr.cell_values(conn, row_id))
    try:
        result = convert(family, inputs)
    except (ValueError, KeyError, TypeError, ArithmeticError):
        raise HTTPException(
            status_code=422, detail="Fill the required fields with valid numbers before converting."
        ) from None
    conv = result.to_dict()
    wr.set_converted(conn, row_id, json.dumps(conv))
    conn.commit()
    return conv


# --- export --------------------------------------------------------------------------------------------------------
def _csv_safe(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s and s[0] in ("=", "+", "-", "@") else s  # neutralize spreadsheet formula injection


@router.get("/workbench/projects/{project_id}/export")
def export_project(project_id: int, format: str = "csv", conn: Connection = Depends(get_connection)) -> Response:
    if format not in ("csv", "audit"):
        raise HTTPException(status_code=422, detail="format must be csv or audit")
    view = _project_or_404(conn, project_id)
    if format == "audit":
        body = json.dumps(view, indent=2)
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="extraction-{project_id}-provenance.json"'},
        )
    keys = [f["key"] for f in view["template"]]
    labels = [f["label"] for f in view["template"]]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row_label", *labels, "metric", "effect_size", "variance"])
    for row in view["rows"]:
        cells = row["cells"]
        conv = row["converted"] or {}
        w.writerow(
            [
                _csv_safe(row["label"]),
                *[_csv_safe(cells.get(k, {}).get("value")) for k in keys],
                _csv_safe(conv.get("metric")),
                _csv_safe(conv.get("value")),
                _csv_safe(conv.get("variance")),
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="extraction-{project_id}.csv"'},
    )
