"""Gated, audited, reversible WRITE endpoints for the MCP agent (B1 SP2).

Every write here is **additive + reversible**, gated behind the `agent_writes_enabled` opt-in (403 when off),
stamped with agent provenance (`papers.imported_source="ai-agent"`; `tags.import_source="agent:mcp"` — the
formal tag-vocabulary namespace, backlog #9), and recorded in `agent_writes` for the Settings review/revert surface.
**No destructive route exists** — delete/overwrite/merge/scan stay human-only (the structural A4 guarantee, like
SP1's read-only allowlist). The MCP write tools call only these endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine, insert, select
from sqlalchemy.exc import NoResultFound

from app.backend import app_settings
from app.backend.api.dependencies import get_connection, get_engine
from app.backend.clustering.axis_assignments import add_manual_assignment, remove_assignment
from app.backend.clustering.my_publications import MY_PUBLICATIONS_KIND
from app.backend.metadata.doi_add import add_paper_by_doi
from app.backend.metadata.enrichment import AI_AGENT_SOURCE, AI_AGENT_TAG_SOURCE
from app.backend.persistence.agent_repo import (
    delete_note,
    get_agent_write,
    list_agent_writes,
    mark_reverted,
    record_agent_write,
)
from app.backend.persistence.repository import (
    get_paper,
    soft_delete_paper,
)
from app.backend.persistence.schema import axes, notes, papers
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.tags_repo import add_tag_to_paper, remove_tag_from_paper
from integrations.crossref import CrossrefClient

router = APIRouter()


def _require_writes() -> None:
    if not app_settings.stored_agent_writes():
        raise HTTPException(
            status_code=403,
            detail="AI-agent writes are disabled — enable them in callosum Settings → AI agent.",
        )


def _paper_or_404(conn: Connection, paper_id: int) -> None:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None


@router.get("/agent/status")
def agent_status() -> dict[str, bool]:
    return {"writes_enabled": app_settings.stored_agent_writes()}


class TagBody(BaseModel):
    tag: str = Field(min_length=1, max_length=200)


@router.post("/agent/papers/{paper_id}/tags", dependencies=[Depends(_require_writes)])
def agent_add_tag(paper_id: int, body: TagBody, engine: Engine = Depends(get_engine)) -> dict[str, Any]:
    def _do(conn: Connection) -> dict[str, Any]:
        _paper_or_404(conn, paper_id)
        tag = add_tag_to_paper(conn, paper_id, body.tag, import_source=AI_AGENT_TAG_SOURCE)
        write_id = record_agent_write(
            conn,
            action="tag",
            target_paper_id=paper_id,
            detail={"tag_id": int(tag["id"]), "name": tag["name"]},
            tool="add_tag",
        )
        return {"write_id": write_id, "tag_id": int(tag["id"]), "name": tag["name"]}

    return run_write(engine, _do)


class AxisBody(BaseModel):
    paper_id: int


@router.post("/agent/axes/{axis_id}/papers", dependencies=[Depends(_require_writes)])
def agent_add_to_axis(axis_id: int, body: AxisBody, engine: Engine = Depends(get_engine)) -> dict[str, Any]:
    def _do(conn: Connection) -> dict[str, Any]:
        _paper_or_404(conn, body.paper_id)
        kind = conn.execute(select(axes.c.kind).where(axes.c.id == axis_id)).scalar_one_or_none()
        if kind is None:
            raise HTTPException(status_code=404, detail="Axis not found")
        if kind == MY_PUBLICATIONS_KIND:
            raise HTTPException(
                status_code=422, detail="Agents can't add to My Publications — authorship is yours to assert."
            )
        add_manual_assignment(conn, axis_id=axis_id, paper_id=body.paper_id)
        write_id = record_agent_write(
            conn, action="axis", target_paper_id=body.paper_id, detail={"axis_id": axis_id}, tool="add_to_axis"
        )
        return {"write_id": write_id, "axis_id": axis_id, "paper_id": body.paper_id}

    return run_write(engine, _do)


class RefBody(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)  # a DOI in v1


@router.post("/agent/references", dependencies=[Depends(_require_writes)])
def agent_save_reference(body: RefBody, request: Request, conn: Connection = Depends(get_connection)) -> dict[str, Any]:
    # Shared DOI-add primitive (backlog #58) — the same resolve → dedup → create logic the Library
    # "Add with DOI…" endpoint uses, so there is no second DOI silo. Metadata-only (no PDF fetch), exactly
    # as before: the agent surface does not acquire full text.
    # Fall back to a default CrossrefClient when app.state has none (only set when injected — e.g. tests);
    # mirrors paper_enrich._crossref, so the agent resolves DOIs in a running app too (backlog #58/#59 wave).
    crossref_client = request.app.state.crossref_client or CrossrefClient()
    result = add_paper_by_doi(conn, body.identifier, crossref_client=crossref_client, imported_source=AI_AGENT_SOURCE)
    if result.status == "invalid":
        raise HTTPException(status_code=422, detail="An identifier (DOI) is required.")
    if result.status == "unresolved":
        raise HTTPException(status_code=422, detail=f"Could not resolve '{result.doi}' to a real record — not saved.")
    created = result.status == "created"
    write_id = record_agent_write(
        conn,
        action="reference",
        target_paper_id=result.paper_id,
        detail={"doi": result.doi, "created": created},
        tool="save_reference",
    )
    conn.commit()
    return {"write_id": write_id, "paper_id": result.paper_id, "created": created}


class NoteBody(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


@router.post("/agent/papers/{paper_id}/notes", dependencies=[Depends(_require_writes)])
def agent_annotate(paper_id: int, body: NoteBody, engine: Engine = Depends(get_engine)) -> dict[str, Any]:
    def _do(conn: Connection) -> dict[str, Any]:
        _paper_or_404(conn, paper_id)
        note_id = int(
            conn.execute(
                insert(notes).values(paper_id=paper_id, body=body.text, import_source=AI_AGENT_SOURCE)
            ).inserted_primary_key[0]
        )
        write_id = record_agent_write(
            conn, action="note", target_paper_id=paper_id, detail={"note_id": note_id}, tool="annotate"
        )
        return {"write_id": write_id, "note_id": note_id}

    return run_write(engine, _do)


@router.get("/agent/writes")
def agent_writes_list(conn: Connection = Depends(get_connection)) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for w in list_agent_writes(conn):
        title = (
            conn.execute(select(papers.c.title).where(papers.c.id == w["target_paper_id"])).scalar_one_or_none()
            if w["target_paper_id"] is not None
            else None
        )
        out.append(
            {
                "id": w["id"],
                "created_at": str(w["created_at"]),
                "action": w["action"],
                "target_paper_id": w["target_paper_id"],
                "target_title": title,
                "detail": w["detail_json"],
                "reverted_at": str(w["reverted_at"]) if w["reverted_at"] else None,
            }
        )
    return out


@router.post("/agent/writes/{write_id}/revert", dependencies=[Depends(_require_writes)])
def agent_revert(write_id: int, engine: Engine = Depends(get_engine)) -> dict[str, bool]:
    def _do(conn: Connection) -> dict[str, bool]:
        w = get_agent_write(conn, write_id)
        if w is None:
            raise HTTPException(status_code=404, detail="Agent write not found")
        if w["reverted_at"] is not None:
            return {"reverted": True}  # idempotent
        action = w["action"]
        detail = w["detail_json"] or {}
        paper_id = w["target_paper_id"]
        if action == "tag":
            remove_tag_from_paper(conn, int(paper_id), int(detail["tag_id"]))
        elif action == "axis":
            remove_assignment(conn, axis_id=int(detail["axis_id"]), paper_id=int(paper_id))
        elif action == "reference":
            if detail.get("created") and paper_id is not None:
                soft_delete_paper(conn, int(paper_id))  # Trash (reversible); a re-found paper is left alone
        elif action == "note":
            delete_note(conn, int(detail["note_id"]))
        mark_reverted(conn, write_id)
        return {"reverted": True}

    return run_write(engine, _do)
