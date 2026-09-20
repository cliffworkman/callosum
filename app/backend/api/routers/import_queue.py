"""Import Queue endpoints (#61 provisional ingestion): list, per-item detail + evidence, an on-demand
raw-PDF stream for client-side preview, the human review/resolution loop (confirm a candidate, supply a
DOI manually, retry a known-paper attach), and permanent deletion.

Deliberately narrow: no candidate-picker beyond "confirm the best one or type another," no thumbnail
caching (the frontend renders page 1 client-side via pdf.js from the raw-bytes route below, exactly the
same pattern `paper_files.py` already uses for ordinary attachments — nothing new to own or clean up).
The full #96 provenance/research-artifact-manifest architecture is explicit future work.

Desktop-UI-only, same as the rest of `library.py`'s routes — never the capture-session bearer token,
which stays browser-extension-only (`api/routers/capture.py`). No new trust boundary is introduced.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Connection, Engine

from app.backend.acquisition.fetch import library_dir
from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.routers.library import _embedding_model, _vector_store
from app.backend.capture.provisional import queue_dir
from app.backend.capture.provisional_recovery import permanently_delete_provisional_artifact
from app.backend.capture.provisional_review import (
    best_candidate,
    confirm_identity,
    explain_evidence,
    preview_doi,
    retry_promotion,
)
from app.backend.capture.trusted_paths import is_canonical_id, resolve_queued_pdf
from app.backend.persistence import capture_events_repo, provisional_artifacts_repo
from app.backend.persistence.paper_query_repo import titles_for_ids
from integrations.crossref import CrossrefClient

router = APIRouter()


def _artifact_row(conn: Connection, artifact_id: str):
    """Route id -> provisional-artifact row. The id is only a LOOKUP key: network string -> syntactically a Callosum
    id -> lookup -> server-owned row. A string that is not a Callosum id is answered exactly like an unknown one."""
    return provisional_artifacts_repo.get(conn, artifact_id) if is_canonical_id(artifact_id) else None


class BestCandidateOut(BaseModel):
    doi: str | None = None
    title: str | None = None
    disposition: str | None = None


class ImportQueueItem(BaseModel):
    artifact_id: str
    identity_state: str
    promotion_state: str
    resolved_paper_id: int | None = None
    resolved_paper_title: str | None = None
    encounter_count: int
    first_captured_at: str | None = None
    last_captured_at: str | None = None
    last_source_url: str | None = None
    last_original_filename: str | None = None
    best_candidate: BestCandidateOut | None = None
    explanation: str


class ImportQueueListResponse(BaseModel):
    items: list[ImportQueueItem]


class ImportQueueDetail(ImportQueueItem):
    evidence: dict[str, Any]


class PreviewDoiRequest(BaseModel):
    doi: str


class ConfirmRequest(BaseModel):
    doi: str
    source: str = "manual"  # "candidate" | "manual" — provenance label only, never trust-relevant


class QueueActionResult(BaseModel):
    identity_state: str
    promotion_state: str
    resolved_paper_id: int | None = None


def _crossref_client(request: Request) -> Any:
    # Same fallback every other capture/import path uses — app.state.crossref_client is only set
    # under test injection; production relies on this default.
    return request.app.state.crossref_client or CrossrefClient()


def _evidence_dict(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("evidence_json")
    if not raw:
        return {
            "candidates": [],
            "title_candidates": [],
            "resolutions": [],
            "decision": "",
            "decision_reason": "",
            "user_actions": [],
        }
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {
            "candidates": [],
            "title_candidates": [],
            "resolutions": [],
            "decision": "",
            "decision_reason": "",
            "user_actions": [],
        }


def _to_item(
    row: dict[str, Any], events: list[dict[str, Any]], paper_titles: dict[int, str]
) -> tuple[ImportQueueItem, dict[str, Any]]:
    first = events[0] if events else None
    last = events[-1] if events else None
    evidence = _evidence_dict(row)
    resolved_paper_id = row["resolved_paper_id"]
    candidate = best_candidate(evidence)
    item = ImportQueueItem(
        artifact_id=str(row["id"]),
        identity_state=str(row["identity_state"]),
        promotion_state=str(row["promotion_state"]),
        resolved_paper_id=resolved_paper_id,
        resolved_paper_title=paper_titles.get(int(resolved_paper_id)) if resolved_paper_id is not None else None,
        encounter_count=len(events),
        first_captured_at=str(first["received_at_server"]) if first else None,
        last_captured_at=str(last["received_at_server"]) if last else None,
        last_source_url=last["source_url"] if last else None,
        last_original_filename=last["original_filename"] if last else None,
        best_candidate=BestCandidateOut(**candidate) if candidate else None,
        explanation=explain_evidence(evidence),
    )
    return item, evidence


@router.get("/library/import-queue", response_model=ImportQueueListResponse)
def list_import_queue(conn: Connection = Depends(get_connection)) -> ImportQueueListResponse:
    """Every provisional artifact not yet fully promoted — one row per distinct captured PDF, not per
    encounter (a PDF captured twice shows once, with `encounter_count == 2`). Newest-first."""
    rows = provisional_artifacts_repo.list_needing_review(conn)
    paper_ids = [int(r["resolved_paper_id"]) for r in rows if r["resolved_paper_id"] is not None]
    paper_titles = titles_for_ids(conn, paper_ids)
    items = []
    for row in rows:
        events = capture_events_repo.list_for_artifact(conn, str(row["id"]))
        item, _ = _to_item(row, events, paper_titles)
        items.append(item)
    return ImportQueueListResponse(items=items)


@router.get("/library/import-queue/{artifact_id}", response_model=ImportQueueDetail)
def get_import_queue_item(artifact_id: str, conn: Connection = Depends(get_connection)) -> ImportQueueDetail:
    row = _artifact_row(conn, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown provisional capture.")
    events = capture_events_repo.list_for_artifact(conn, artifact_id)
    paper_titles = titles_for_ids(conn, [int(row["resolved_paper_id"])]) if row["resolved_paper_id"] is not None else {}
    item, evidence = _to_item(row, events, paper_titles)
    return ImportQueueDetail(**item.model_dump(), evidence=evidence)


@router.get("/library/import-queue/{artifact_id}/pdf", response_model=None)
def get_import_queue_pdf(artifact_id: str, conn: Connection = Depends(get_connection)) -> FileResponse:
    """Stream the queued PDF's raw bytes for client-side (pdf.js) preview rendering — the path is
    resolved ONLY from the trusted DB row, never from client input, mirroring `paper_files.py`. No
    server-side rasterization, no cache file: nothing new to own or delete."""
    row = _artifact_row(conn, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown provisional capture.")
    # Trust boundary (trusted_paths.resolve_queued_pdf): serve only a real file directly under the RESOLVED queue
    # directory. A stored path elsewhere, or a queue-local symlink pointing elsewhere, is refused.
    path = resolve_queued_pdf(row["pdf_path"], queue_dir(library_dir()))
    if path is None:
        raise HTTPException(status_code=404, detail="This capture's PDF is no longer in the Import Queue.")
    return FileResponse(path, media_type="application/pdf", content_disposition_type="inline", filename=path.name)


@router.post("/library/import-queue/{artifact_id}/preview-doi")
def preview_import_queue_doi(
    artifact_id: str, payload: PreviewDoiRequest, request: Request, conn: Connection = Depends(get_connection)
) -> dict[str, Any]:
    """Read-only: normalize + resolve a DOI candidate WITHOUT mutating anything, so the user can see what
    they're about to confirm first. `artifact_id` is only checked to exist; the preview itself never
    touches the artifact row."""
    if _artifact_row(conn, artifact_id) is None:
        raise HTTPException(status_code=404, detail="Unknown provisional capture.")
    return preview_doi(conn, payload.doi, _crossref_client(request))


@router.post("/library/import-queue/{artifact_id}/confirm", response_model=QueueActionResult)
def confirm_import_queue_item(
    artifact_id: str, payload: ConfirmRequest, request: Request, engine: Engine = Depends(get_engine)
) -> QueueActionResult:
    if not is_canonical_id(artifact_id):
        raise HTTPException(status_code=404, detail="Unknown or already-resolved provisional capture.")
    result = confirm_identity(
        engine,
        artifact_id,
        doi=payload.doi,
        source=payload.source,
        library_root=library_dir(),
        crossref_client=_crossref_client(request),
        vector_store=_vector_store(request.app),
        embedding_model=_embedding_model(request.app),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown or already-resolved provisional capture.")
    return QueueActionResult(
        identity_state=result.identity_state,
        promotion_state=result.promotion_state,
        resolved_paper_id=result.resolved_paper_id,
    )


@router.post("/library/import-queue/{artifact_id}/retry", response_model=QueueActionResult)
def retry_import_queue_item(
    artifact_id: str, request: Request, engine: Engine = Depends(get_engine)
) -> QueueActionResult:
    if not is_canonical_id(artifact_id):
        raise HTTPException(
            status_code=422, detail="Nothing to retry — this capture is not in a resolved, non-promoted state."
        )
    result = retry_promotion(
        engine,
        artifact_id,
        library_root=library_dir(),
        vector_store=_vector_store(request.app),
        embedding_model=_embedding_model(request.app),
    )
    if result is None:
        raise HTTPException(
            status_code=422, detail="Nothing to retry — this capture is not in a resolved, non-promoted state."
        )
    return QueueActionResult(
        identity_state=result.identity_state,
        promotion_state=result.promotion_state,
        resolved_paper_id=result.resolved_paper_id,
    )


@router.delete("/library/import-queue/{artifact_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_import_queue_item(artifact_id: str, request: Request, engine: Engine = Depends(get_engine)) -> None:
    """Permanent deletion. Deliberate policy for provisional state: removes the queue PDF (if not
    already promoted-and-moved-out), the provenance sidecar, the artifact row, AND every one of its
    capture_events rows (cascade) — a provisional artifact's entire encounter history goes with it.
    There is no separate per-encounter delete; a provisional artifact is pre-canonical, and once it is
    gone this increment retains nothing else about it."""
    deleted = is_canonical_id(artifact_id) and permanently_delete_provisional_artifact(
        engine, artifact_id, library_dir()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Unknown provisional capture.")
