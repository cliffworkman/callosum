"""Meta-analysis extraction workspace endpoints (workbench SP2a-1, inc 253).

A stateful "Extract" workspace: projects (a dataset + a template) -> rows (one effect each, optionally linked to a
library paper) -> cells (a value + its exact source provenance). A row's role-tagged cells feed the SP1 effect-size
converter (``POST …/convert``); the dataset exports to a metafor/JASP-ready CSV + a provenance audit JSON.

The load-bearing boundary (extends SP1): extract / structure / convert / export — NEVER pool / model / adjudicate.
No endpoint combines two rows; export carries data + provenance, never a synthesized estimate; a value is only ever
set by a human. SP2b (inc 259) adds an egress-gated assisted-extraction funnel (propose/accept/reject): the LLM only
PROPOSES candidates into the isolated ma_proposals table and a human must accept each one into ma_cells — the trusted
cells, converter, and exports remain human-only. Bound-param SQL; typed/validated bodies (rule #3/#4).
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, Engine

from app.backend import workbench_assist as wa
from app.backend.api.dependencies import get_connection, get_engine, resolve_llm_config
from app.backend.api.routers.library import _embedding_model, _vector_store
from app.backend.llm.egress import DataEgressDisabledError, EgressGatedExtractionAssistant
from app.backend.llm.managed_local import ManagedLocalTargetError
from app.backend.llm.providers import ProviderError
from app.backend.methods.effectsize import convert
from app.backend.persistence import workbench_export as wx
from app.backend.persistence import workbench_repo as wr
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import get_chunks_for_paper
from app.backend.persistence.sqlite_retry import run_write
from integrations.gemini.extraction_assistant import GeminiExtractionAssistant

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


class ProposalAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | None = Field(default=None, max_length=500)  # edit-before-accept override (drops exact → region)


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


def _extraction_assistant(app: FastAPI) -> EgressGatedExtractionAssistant:
    """Build the gated funnel assistant from the active provider (a test injects app.state.extraction_assistant).
    The gate raises DataEgressDisabledError on a non-loopback provider without consent — mirrors _summary_generator."""
    config = resolve_llm_config(app)
    inner = app.state.extraction_assistant or GeminiExtractionAssistant(config=config)
    return EgressGatedExtractionAssistant(
        inner=inner,
        data_egress_enabled=config.data_egress_enabled,
        provider=config.provider,
        wire_format=config.wire_format,
        base_url=config.base_url,
    )


# --- projects ------------------------------------------------------------------------------------------------------
@router.get("/workbench/projects", response_model=list[ProjectSummary])
def list_projects(conn: Connection = Depends(get_connection)) -> list[ProjectSummary]:
    return [ProjectSummary(**p) for p in wr.list_projects(conn)]


@router.post("/workbench/projects")
def create_project(payload: ProjectCreate, engine: Engine = Depends(get_engine)) -> dict:
    if payload.design not in wr.DESIGNS:
        raise HTTPException(status_code=422, detail=f"Unknown design: {payload.design}")

    def _do(conn: Connection) -> dict:
        pid = wr.create_project(conn, name=payload.name, design=payload.design)
        return _project_or_404(conn, pid)

    return run_write(engine, _do)


@router.get("/workbench/projects/{project_id}")
def get_project(project_id: int, conn: Connection = Depends(get_connection)) -> dict:
    return _project_or_404(conn, project_id)


@router.patch("/workbench/projects/{project_id}")
def patch_project(project_id: int, payload: ProjectPatch, engine: Engine = Depends(get_engine)) -> dict:
    def _do(conn: Connection) -> dict:
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
        return _project_or_404(conn, project_id)

    return run_write(engine, _do)


@router.delete("/workbench/projects/{project_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        if not wr.delete_project(conn, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


# --- rows ----------------------------------------------------------------------------------------------------------
@router.post("/workbench/projects/{project_id}/rows")
def add_row(project_id: int, payload: RowCreate, engine: Engine = Depends(get_engine)) -> dict:
    def _do(conn: Connection) -> dict:
        if wr.get_project(conn, project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if payload.paper_id is not None and not wr._paper_titles(conn, [payload.paper_id]):
            raise HTTPException(status_code=404, detail="Paper not found")
        wr.add_row(conn, project_id, paper_id=payload.paper_id, label=payload.label)
        return _project_or_404(conn, project_id)

    return run_write(engine, _do)


@router.patch("/workbench/rows/{row_id}")
def patch_row(row_id: int, payload: RowPatch, engine: Engine = Depends(get_engine)) -> dict:
    def _do(conn: Connection) -> dict:
        _row_or_404(conn, row_id)
        wr.update_row(conn, row_id, label=payload.label, paper_id=payload.paper_id, position=payload.position)
        return {"ok": True}

    return run_write(engine, _do)


@router.delete("/workbench/rows/{row_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_row(row_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        if not wr.delete_row(conn, row_id):
            raise HTTPException(status_code=404, detail="Row not found")
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


# --- cells ---------------------------------------------------------------------------------------------------------
@router.put("/workbench/rows/{row_id}/cells/{field_key}")
def put_cell(row_id: int, field_key: str, payload: CellPut, engine: Engine = Depends(get_engine)) -> dict:
    def _do(conn: Connection) -> dict:
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
        # A hand-entered value is a fact, not a candidate: drop any live proposal for this field so a stale candidate
        # can't later be accepted over the human's value (the funnel fills gaps, it never contests a human).
        wr.delete_proposals_for_field(conn, row_id, field_key)
        # A cell changed → the stored effect size is now stale; drop it so it's re-converted (never silently stale).
        wr.set_converted(conn, row_id, None)
        return {"ok": True}

    return run_write(engine, _do)


# --- convert (the SP1 hook) ----------------------------------------------------------------------------------------
@router.post("/workbench/rows/{row_id}/convert")
def convert_row(row_id: int, engine: Engine = Depends(get_engine)) -> dict:
    def _do(conn: Connection) -> dict:
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
        return conv

    return run_write(engine, _do)


@router.post("/workbench/projects/{project_id}/convert-all")
def convert_all(project_id: int, engine: Engine = Depends(get_engine)) -> dict:
    """Run the SP1 converter over every row (the dataset loop). A row with incomplete/invalid inputs is left
    honestly un-converted and reported in ``incomplete`` — never a fabricated result. Still per-study only:
    nothing is pooled, weighted, or aggregated across rows."""

    def _do(conn: Connection) -> dict:
        view = _project_or_404(conn, project_id)
        builder = wr.CONVERT_MAP.get(view["design"])
        if builder is None:
            raise HTTPException(status_code=422, detail="This design has no converter mapping.")
        converted = 0
        incomplete: list[dict] = []
        for row in view["rows"]:
            cell_vals = {k: (c or {}).get("value") for k, c in row["cells"].items()}
            family, inputs = builder(cell_vals)
            try:
                result = convert(family, inputs)
            except (ValueError, KeyError, TypeError, ArithmeticError):
                wr.set_converted(conn, row["id"], None)  # leave it honestly un-converted, don't invent a number
                incomplete.append({"row_id": row["id"], "label": row["label"] or row["paper_title"]})
                continue
            wr.set_converted(conn, row["id"], json.dumps(result.to_dict()))
            converted += 1
        return {"total": len(view["rows"]), "converted": converted, "incomplete": incomplete}

    return run_write(engine, _do)


# --- export --------------------------------------------------------------------------------------------------------
@router.get("/workbench/projects/{project_id}/export")
def export_project(project_id: int, format: str = "csv", conn: Connection = Depends(get_connection)) -> Response:
    if format not in ("csv", "metafor", "revman", "audit"):
        raise HTTPException(status_code=422, detail="format must be csv, metafor, revman, or audit")
    view = _project_or_404(conn, project_id)
    if format == "audit":
        return Response(
            content=json.dumps(view, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="extraction-{project_id}-provenance.json"'},
        )
    suffix = "" if format == "csv" else f"-{format}"
    return Response(
        content=wx.FORMATS[format](view),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="extraction-{project_id}{suffix}.csv"'},
    )


# --- assisted extraction (SP2b funnel): the LLM PROPOSES candidates; a human accepts each into ma_cells ------------
@router.post("/workbench/rows/{row_id}/propose")
def propose_row(row_id: int, request: Request, conn: Connection = Depends(get_connection)) -> dict:
    """Draft candidate values for a row's EMPTY STRUCTURED cells from its linked paper's PDF. Candidates land ONLY in
    ma_proposals (never ma_cells) — convert/export stay candidate-safe until a human accepts. Egress rides the gate."""
    row = _row_or_404(conn, row_id)
    if row["paper_id"] is None:
        raise HTTPException(status_code=422, detail="Link a library paper to this row before drafting.")
    view = _project_or_404(conn, row["project_id"])
    vrow = next((r for r in view["rows"] if r["id"] == row_id), None)
    fields = wa.proposable_fields(view["template"], (vrow or {}).get("cells", {}))
    if not fields:
        return {"proposals": [], "truncated": False}  # nothing empty+structured to draft — no egress
    pdf_path = wa.primary_pdf_path(conn, row["paper_id"])
    if pdf_path is None:
        raise HTTPException(status_code=422, detail="This paper has no processed local PDF to draft from.")
    try:
        text_cap_provider = resolve_llm_config(request.app).provider
    except ManagedLocalTargetError as exc:
        raise HTTPException(
            status_code=422, detail=f"Local AI is not ready ({exc.code}). Check Settings → AI features."
        ) from None
    text_cap = wa.MAX_TEXT_CHARS_MANAGED_LOCAL if text_cap_provider == "managed_local" else wa.MAX_TEXT_CHARS
    text, truncated = wa.relevant_page_tagged_text(
        conn,
        get_chunks_for_paper(conn, row["paper_id"], document_roles=ARTICLE_DOCUMENT_ROLES),
        fields=fields,
        model=_embedding_model(request.app),
        vector_store=_vector_store(request.app),
        cap=text_cap,
    )
    if not text.strip():
        raise HTTPException(status_code=422, detail="This paper has no extracted text to draft from.")
    try:
        assistant = _extraction_assistant(request.app)
        raw = assistant.propose(text=text, fields=fields)
    except ManagedLocalTargetError as exc:
        raise HTTPException(
            status_code=422, detail=f"Local AI is not ready ({exc.code}). Check Settings → AI features."
        ) from None
    except DataEgressDisabledError:
        raise HTTPException(
            status_code=403, detail="AI features are off. Enable data egress in Settings to draft from the PDF."
        ) from None
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {exc}") from None
    proposals = wa.assemble_proposals(pdf_path, raw, {f["key"] for f in fields})
    wr.replace_row_proposals(conn, row_id, proposals)
    conn.commit()
    return {"proposals": wr.proposals_for_row(conn, row_id), "truncated": truncated}


@router.post("/workbench/proposals/{proposal_id}/accept")
def accept_proposal(proposal_id: int, payload: ProposalAccept, engine: Engine = Depends(get_engine)) -> dict:
    """Promote a candidate into the trusted cell. Precision is derived from anchor_state (invariant #2): keep the
    exact bbox only when anchor_state == 'exact' AND the value wasn't overridden. Clears the stale g; deletes the
    proposal."""

    def _do(conn: Connection) -> dict:
        prop = wr.get_proposal(conn, proposal_id)
        if prop is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        row = _row_or_404(conn, prop["row_id"])
        edited = payload.value is not None
        final_value = payload.value if edited else prop["value"]
        keep_exact = prop["anchor_state"] == "exact" and not edited
        wr.upsert_cell(
            conn,
            prop["row_id"],
            prop["field_key"],
            value=final_value,
            page=prop["page"],
            quote=prop["quote"],
            bbox_json=prop["bbox_json"] if keep_exact else None,
            origin="assisted",
        )
        wr.set_converted(conn, prop["row_id"], None)  # a new value invalidates the stale effect size (inc-256/258)
        wr.delete_proposal(conn, proposal_id)
        return _project_or_404(conn, row["project_id"])

    return run_write(engine, _do)


@router.post("/workbench/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, engine: Engine = Depends(get_engine)) -> dict:
    def _do(conn: Connection) -> dict:
        prop = wr.get_proposal(conn, proposal_id)
        if prop is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        row = _row_or_404(conn, prop["row_id"])
        wr.delete_proposal(conn, proposal_id)
        return _project_or_404(conn, row["project_id"])

    return run_write(engine, _do)
