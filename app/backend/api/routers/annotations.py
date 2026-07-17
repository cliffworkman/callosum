"""User + synthesis annotation endpoints (the API's only mutating routes besides summaries)."""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.persistence.annotations_repo import (
    NATIVE_ANNOTATION_SOURCES,
    create_annotation,
    delete_annotation,
    get_annotation,
    list_annotations_for_paper,
    update_annotation,
)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()

# Preset highlight colors the UI offers and the API accepts. Kept server-side so a
# malformed/arbitrary color can't be persisted (matches the frontend swatch set).
ANNOTATION_COLORS = frozenset({"#ffd54a", "#7bc67e", "#6aa9ff", "#f48fb1", "#ff8a65"})

# Cap a note's length (a few KB). The one public-hardening item worth doing now —
# enforced on both create and update so a note can't grow unbounded on disk.
ANNOTATION_NOTE_MAX_LEN = 4000


class AnnotationBbox(BaseModel):
    page: int | None = None
    x0: float
    y0: float
    x1: float
    y1: float


class AnnotationCreateRequest(BaseModel):
    page: int = Field(ge=1)
    color: str
    bboxes: list[AnnotationBbox] = Field(min_length=1)
    anchor_text: str = Field(min_length=1)
    prefix: str | None = None
    suffix: str | None = None
    attachment_id: int | None = None
    note: str | None = None
    # Origin of the annotation. Omitted/None means a hand-made user highlight; a
    # client may set "synthesis" to save a verified, exact-coordinate citation
    # passage. Validated against an allowlist server-side (no forged sources).
    source: str | None = None


class AnnotationUpdateRequest(BaseModel):
    # Partial update of an existing highlight's note and/or color. Fields that are
    # omitted are left unchanged; an explicit note=null clears the note. Which fields
    # were supplied is read via Pydantic's model_fields_set in the handler.
    note: str | None = None
    color: str | None = None


class AnnotationResponse(BaseModel):
    id: int
    paper_id: int
    attachment_id: int | None = None
    page: int | None = None
    color: str | None = None
    bboxes_json: Any | None = None
    anchor_text: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    source: str | None = None
    note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@router.get("/papers/{paper_id}/annotations", response_model=list[AnnotationResponse])
def paper_annotations(paper_id: int, conn: Connection = Depends(get_connection)) -> list[AnnotationResponse]:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return [_annotation_response(row) for row in list_annotations_for_paper(conn, paper_id)]


@router.post(
    "/papers/{paper_id}/annotations",
    response_model=AnnotationResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_paper_annotation(
    paper_id: int,
    request: AnnotationCreateRequest,
    engine: Engine = Depends(get_engine),
) -> AnnotationResponse:
    def _do(conn: Connection) -> AnnotationResponse:
        try:
            get_paper(conn, paper_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Paper not found") from None
        _validate_annotation_request(request)
        annotation_id = create_annotation(
            conn,
            paper_id=paper_id,
            attachment_id=request.attachment_id,
            page=request.page,
            color=request.color,
            bboxes_json=_annotation_bboxes_payload(request),
            anchor_text=request.anchor_text,
            prefix=request.prefix,
            suffix=request.suffix,
            source=request.source or "user",
            note=request.note,
        )
        return _annotation_response(get_annotation(conn, annotation_id))

    return run_write(engine, _do)


@router.patch("/annotations/{annotation_id}", response_model=AnnotationResponse)
def update_paper_annotation(
    annotation_id: int,
    request: AnnotationUpdateRequest,
    engine: Engine = Depends(get_engine),
) -> AnnotationResponse:
    def _do(conn: Connection) -> AnnotationResponse:
        if get_annotation(conn, annotation_id) is None:
            raise HTTPException(status_code=404, detail="Annotation not found")
        fields = request.model_fields_set
        if not ({"note", "color"} & fields):
            raise HTTPException(status_code=422, detail="No updatable fields provided")
        kwargs: dict[str, Any] = {}
        if "color" in fields:
            if request.color not in ANNOTATION_COLORS:
                raise HTTPException(status_code=422, detail="Unsupported highlight color")
            kwargs["color"] = request.color
        if "note" in fields:
            _validate_annotation_note(request.note)
            kwargs["note"] = request.note
        update_annotation(conn, annotation_id, **kwargs)
        return _annotation_response(get_annotation(conn, annotation_id))

    return run_write(engine, _do)


@router.delete("/annotations/{annotation_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_paper_annotation(annotation_id: int, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        if get_annotation(conn, annotation_id) is None:
            raise HTTPException(status_code=404, detail="Annotation not found")
        delete_annotation(conn, annotation_id)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


def _validate_annotation_note(note: str | None) -> None:
    if note is not None and len(note) > ANNOTATION_NOTE_MAX_LEN:
        raise HTTPException(status_code=422, detail="Note exceeds the maximum length")


def _validate_annotation_request(request: AnnotationCreateRequest) -> None:
    if request.color not in ANNOTATION_COLORS:
        raise HTTPException(status_code=422, detail="Unsupported highlight color")
    if request.source is not None and request.source not in NATIVE_ANNOTATION_SOURCES:
        raise HTTPException(status_code=422, detail="Unsupported annotation source")
    _validate_annotation_note(request.note)
    for box in request.bboxes:
        if not (math.isfinite(box.x0) and math.isfinite(box.y0) and math.isfinite(box.x1) and math.isfinite(box.y1)):
            raise HTTPException(status_code=422, detail="Bounding box has non-finite coordinates")
        if box.x1 <= box.x0 or box.y1 <= box.y0:
            raise HTTPException(status_code=422, detail="Bounding box must have positive area")


def _annotation_bboxes_payload(request: AnnotationCreateRequest) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for box in request.bboxes:
        rect: dict[str, Any] = {"x0": box.x0, "y0": box.y0, "x1": box.x1, "y1": box.y1}
        if box.page is not None:
            rect["page"] = box.page
        payload.append(rect)
    return payload


def _annotation_response(row: Any) -> AnnotationResponse:
    return AnnotationResponse(
        id=row["id"],
        paper_id=row["paper_id"],
        attachment_id=row["attachment_id"],
        page=row["page"],
        color=row["color"],
        bboxes_json=row["bboxes_json"],
        anchor_text=row["anchor_text"],
        prefix=row["prefix"],
        suffix=row["suffix"],
        source=row["source"],
        note=row["note"],
        created_at=str(row["created_at"]) if row["created_at"] is not None else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] is not None else None,
    )
