"""Sections, tasks, and Library-reference links for local WIP manuscripts."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.backend.api.wip_security import require_local_wip
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.wip_repo import get_manuscript
from app.backend.persistence.wip_workflow_repo import (
    create_section,
    create_task,
    delete_reference,
    delete_section,
    delete_task,
    list_paper_wips,
    list_references,
    list_sections,
    list_tasks,
    reorder_sections,
    update_section,
    update_task,
    upsert_reference,
)

router = APIRouter(prefix="/wip", dependencies=[Depends(require_local_wip)])

SectionStatus = Literal[
    "not-started",
    "outlined",
    "drafting",
    "complete",
    "needs-revision",
    "under-review",
    "approved",
    "not-applicable",
]
TaskStatus = Literal["open", "in-progress", "blocked", "complete", "deferred", "cancelled"]
ReferenceState = Literal[
    "cited",
    "possibly-cited",
    "background-reading",
    "to-cite",
    "rejected-for-use",
    "needs-verification",
]


class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SectionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: SectionStatus | None = None
    notes: str | None = Field(default=None, max_length=10_000)


class SectionOrder(BaseModel):
    section_ids: list[int] = Field(min_length=1, max_length=100)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10_000)
    status: TaskStatus = "open"
    due_date: date | None = None
    section_id: int | None = None
    file_id: int | None = None
    paper_id: int | None = None
    finding_id: int | None = None


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10_000)
    status: TaskStatus | None = None
    due_date: date | None = None
    section_id: int | None = None
    file_id: int | None = None
    paper_id: int | None = None
    finding_id: int | None = None


class ReferenceUpsert(BaseModel):
    paper_id: int
    relationship_state: ReferenceState = "possibly-cited"
    notes: str | None = Field(default=None, max_length=10_000)


def _require_manuscript(request: Request, manuscript_id: int) -> None:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")


@router.get("/manuscripts/{manuscript_id}/sections")
def sections_list(manuscript_id: int, request: Request) -> list[dict]:
    _require_manuscript(request, manuscript_id)
    with request.app.state.engine.connect() as conn:
        return list_sections(conn, manuscript_id)


@router.post("/manuscripts/{manuscript_id}/sections", status_code=201)
def sections_create(manuscript_id: int, payload: SectionCreate, request: Request) -> dict:
    _require_manuscript(request, manuscript_id)
    return run_write(
        request.app.state.engine,
        lambda conn: create_section(conn, manuscript_id, payload.name.strip()),
    )


@router.patch("/manuscripts/{manuscript_id}/sections/{section_id}")
def sections_patch(manuscript_id: int, section_id: int, payload: SectionPatch, request: Request) -> dict:
    result = run_write(
        request.app.state.engine,
        lambda conn: update_section(conn, manuscript_id, section_id, payload.model_dump(exclude_unset=True)),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="WIP section not found")
    return result


@router.put("/manuscripts/{manuscript_id}/sections/order")
def sections_order(manuscript_id: int, payload: SectionOrder, request: Request) -> list[dict]:
    result = run_write(
        request.app.state.engine,
        lambda conn: reorder_sections(conn, manuscript_id, payload.section_ids),
    )
    if result is None:
        raise HTTPException(status_code=422, detail="Section order must contain every section exactly once")
    return result


@router.delete("/manuscripts/{manuscript_id}/sections/{section_id}", status_code=204)
def sections_delete(manuscript_id: int, section_id: int, request: Request) -> Response:
    deleted = run_write(
        request.app.state.engine,
        lambda conn: delete_section(conn, manuscript_id, section_id),
    )
    if not deleted:
        raise HTTPException(status_code=422, detail="Only custom WIP sections can be deleted")
    return Response(status_code=204)


@router.get("/manuscripts/{manuscript_id}/tasks")
def tasks_list(manuscript_id: int, request: Request) -> list[dict]:
    _require_manuscript(request, manuscript_id)
    with request.app.state.engine.connect() as conn:
        return list_tasks(conn, manuscript_id)


@router.post("/manuscripts/{manuscript_id}/tasks", status_code=201)
def tasks_create(manuscript_id: int, payload: TaskCreate, request: Request) -> dict:
    _require_manuscript(request, manuscript_id)
    values = payload.model_dump()
    values["title"] = values["title"].strip()
    return run_write(request.app.state.engine, lambda conn: create_task(conn, manuscript_id, values))


@router.patch("/manuscripts/{manuscript_id}/tasks/{task_id}")
def tasks_patch(manuscript_id: int, task_id: int, payload: TaskPatch, request: Request) -> dict:
    result = run_write(
        request.app.state.engine,
        lambda conn: update_task(conn, manuscript_id, task_id, payload.model_dump(exclude_unset=True)),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="WIP task not found")
    return result


@router.delete("/manuscripts/{manuscript_id}/tasks/{task_id}", status_code=204)
def tasks_delete(manuscript_id: int, task_id: int, request: Request) -> Response:
    deleted = run_write(
        request.app.state.engine,
        lambda conn: delete_task(conn, manuscript_id, task_id),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="WIP task not found")
    return Response(status_code=204)


@router.get("/manuscripts/{manuscript_id}/references")
def references_list(manuscript_id: int, request: Request) -> list[dict]:
    _require_manuscript(request, manuscript_id)
    with request.app.state.engine.connect() as conn:
        return list_references(conn, manuscript_id)


@router.post("/manuscripts/{manuscript_id}/references")
def references_upsert(manuscript_id: int, payload: ReferenceUpsert, request: Request) -> dict:
    _require_manuscript(request, manuscript_id)
    result = run_write(
        request.app.state.engine,
        lambda conn: upsert_reference(
            conn,
            manuscript_id,
            payload.paper_id,
            payload.relationship_state,
            payload.notes,
        ),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Library paper not found")
    return result


@router.delete("/manuscripts/{manuscript_id}/references/{paper_id}", status_code=204)
def references_delete(manuscript_id: int, paper_id: int, request: Request) -> Response:
    deleted = run_write(
        request.app.state.engine,
        lambda conn: delete_reference(conn, manuscript_id, paper_id),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="WIP reference link not found")
    return Response(status_code=204)


@router.get("/papers/{paper_id}")
def paper_wips(paper_id: int, request: Request) -> list[dict]:
    with request.app.state.engine.connect() as conn:
        return list_paper_wips(conn, paper_id)
