"""Local-only WIP content checkpoint API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.backend.api.wip_security import require_local_wip
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.wip_provenance_repo import (
    list_snapshots,
    mark_extraction_failure,
    prepare_snapshot,
    record_snapshot,
)
from app.backend.persistence.wip_repo import get_manuscript, list_files
from app.backend.wip.content import ContentIdentityError

router = APIRouter(prefix="/wip", dependencies=[Depends(require_local_wip)])


class CheckpointCreate(BaseModel):
    note: str = Field(default="", max_length=500)


@router.get("/manuscripts/{manuscript_id}/snapshots")
def snapshots_list(manuscript_id: int, request: Request) -> list[dict]:
    with request.app.state.engine.connect() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
        return list_snapshots(conn, manuscript_id)


@router.post("/manuscripts/{manuscript_id}/snapshots")
def snapshot_create(manuscript_id: int, payload: CheckpointCreate, request: Request) -> dict:
    primary_file_id = None
    try:
        with request.app.state.engine.connect() as conn:
            primary = next((file for file in list_files(conn, manuscript_id) if file["is_primary"]), None)
            primary_file_id = int(primary["id"]) if primary else None
            prepared = prepare_snapshot(conn, manuscript_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContentIdentityError as exc:
        failure = exc
        if primary_file_id is not None:
            run_write(
                request.app.state.engine,
                lambda conn: mark_extraction_failure(
                    conn,
                    manuscript_id,
                    primary_file_id,
                    failure,
                    reason="manual",
                ),
            )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    snapshot, created = run_write(
        request.app.state.engine,
        lambda conn: record_snapshot(conn, prepared, reason="manual", reason_detail=payload.note.strip()),
    )
    return {**snapshot, "created": created}
