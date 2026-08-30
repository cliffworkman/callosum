"""Explicitly turn imported reference-manager folder structure into ordinary axes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Connection, Engine

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.routers.axes import run_axis_score_job
from app.backend.importers.collection_axes import (
    ImportedCollectionAxisCandidate,
    create_imported_collection_axes,
    list_imported_axis_candidates,
)
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter(tags=["library"])
ImportSource = Literal["zotero", "mendeley", "endnote"]
AxisKind = Literal["curated", "standard"]


class ImportedCollectionOut(BaseModel):
    collection_id: int
    name: str
    import_source: str
    descendant_count: int
    paper_count: int
    axis_id: int | None = None
    axis_kind: str | None = None


class ImportedCollectionsOut(BaseModel):
    collections: list[ImportedCollectionOut]


class ImportedCollectionAxesRequest(BaseModel):
    import_source: ImportSource
    axis_kind: AxisKind = "curated"


class ImportedCollectionAxesOut(BaseModel):
    created_axis_ids: list[int]
    existing_axis_ids: list[int]
    skipped_empty_collection_ids: list[int]
    score_job_ids: list[str]


@router.get("/library/imported-collections/axes", response_model=ImportedCollectionsOut)
def imported_collection_axes_preview(
    import_source: ImportSource, conn: Connection = Depends(get_connection)
) -> ImportedCollectionsOut:
    try:
        candidates = list_imported_axis_candidates(conn, import_source=import_source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImportedCollectionsOut(collections=[_candidate_out(candidate) for candidate in candidates])


@router.post("/library/imported-collections/axes", response_model=ImportedCollectionAxesOut)
def imported_collection_axes_create(
    payload: ImportedCollectionAxesRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    engine: Engine = Depends(get_engine),
) -> ImportedCollectionAxesOut:
    try:
        result = run_write(
            engine,
            lambda conn: create_imported_collection_axes(
                conn, import_source=payload.import_source, axis_kind=payload.axis_kind
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    score_job_ids: list[str] = []
    if payload.axis_kind == "standard":
        for axis_id in result.created_axis_ids:
            job_id = request.app.state.axis_score_jobs.create(nav={"axis_id": axis_id})
            score_job_ids.append(job_id)
            # FastAPI runs BackgroundTasks in insertion order. Reuse the one authoritative scorer so imported
            # papers remain manual anchors and the remainder of the library receives ordinary similarity scores.
            background_tasks.add_task(run_axis_score_job, request.app, job_id, axis_id)
    return ImportedCollectionAxesOut(
        created_axis_ids=list(result.created_axis_ids),
        existing_axis_ids=list(result.existing_axis_ids),
        skipped_empty_collection_ids=list(result.skipped_empty_collection_ids),
        score_job_ids=score_job_ids,
    )


def _candidate_out(candidate: ImportedCollectionAxisCandidate) -> ImportedCollectionOut:
    return ImportedCollectionOut(
        collection_id=candidate.collection_id,
        name=candidate.name,
        import_source=candidate.import_source,
        descendant_count=candidate.descendant_count,
        paper_count=len(candidate.paper_ids),
        axis_id=candidate.axis_id,
        axis_kind=candidate.axis_kind,
    )
