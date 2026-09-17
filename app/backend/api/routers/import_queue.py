"""Import Queue endpoints (#61 provisional ingestion): the minimal, read-only-plus-delete surface
that proves the capture -> queue -> (promote | stay queued) -> delete lifecycle end to end.

Deliberately narrow: a list + a permanent-delete action, no candidate-picker, no thumbnail. The full
review-card UX described in #61/#96 is explicit future work; this exists so the data model can be
exercised by a real UI without changing shape later (see `provisional.py`'s module docstring for the
artifact/encounter split this reads from).

Desktop-UI-only, same as the rest of `library.py`'s routes — never the capture-session bearer token,
which stays browser-extension-only (`api/routers/capture.py`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, Engine

from app.backend.acquisition.fetch import library_dir
from app.backend.api.dependencies import get_connection, get_engine
from app.backend.capture.provisional import permanently_delete_provisional_artifact
from app.backend.persistence import capture_events_repo, provisional_artifacts_repo

router = APIRouter()


class ImportQueueItem(BaseModel):
    artifact_id: str
    identity_state: str
    promotion_state: str
    resolved_paper_id: int | None = None
    encounter_count: int
    first_captured_at: str | None = None
    last_captured_at: str | None = None
    last_source_url: str | None = None
    last_original_filename: str | None = None


class ImportQueueListResponse(BaseModel):
    items: list[ImportQueueItem]


def _to_item(conn: Connection, row: dict[str, Any]) -> ImportQueueItem:
    events = capture_events_repo.list_for_artifact(conn, str(row["id"]))
    first = events[0] if events else None
    last = events[-1] if events else None
    return ImportQueueItem(
        artifact_id=str(row["id"]),
        identity_state=str(row["identity_state"]),
        promotion_state=str(row["promotion_state"]),
        resolved_paper_id=row["resolved_paper_id"],
        encounter_count=len(events),
        first_captured_at=str(first["received_at_server"]) if first else None,
        last_captured_at=str(last["received_at_server"]) if last else None,
        last_source_url=last["source_url"] if last else None,
        last_original_filename=last["original_filename"] if last else None,
    )


@router.get("/library/import-queue", response_model=ImportQueueListResponse)
def list_import_queue(conn: Connection = Depends(get_connection)) -> ImportQueueListResponse:
    """Every provisional artifact not yet fully promoted — one row per distinct captured PDF, not
    per encounter (a PDF captured twice shows once, with `encounter_count == 2`)."""
    rows = provisional_artifacts_repo.list_needing_review(conn)
    return ImportQueueListResponse(items=[_to_item(conn, row) for row in rows])


@router.delete("/library/import-queue/{artifact_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_import_queue_item(artifact_id: str, request: Request, engine: Engine = Depends(get_engine)) -> None:
    """Permanent deletion: the queue PDF (if not already promoted-and-moved-out), the provenance
    sidecar, and every DB row for this artifact (including its capture-encounter history)."""
    deleted = permanently_delete_provisional_artifact(engine, artifact_id, library_dir())
    if not deleted:
        raise HTTPException(status_code=404, detail="Unknown provisional capture.")
