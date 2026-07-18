"""Reading-queue endpoints (inc 219) — a personal, ordered to-read list surfaced as the left-pane "Queue" tab.

A queue is NOT an axis (no semantic scoring): a small local table of papers, manually ordered (drag-to-reorder).
``GET`` lists it (joined to papers, trashed excluded); ``POST`` appends a paper (idempotent); ``DELETE`` removes one
(the × and ✓ Done both call it, idempotent); ``PUT …/order`` writes the manual order (the inc-211/212 reorder
contract — 422 on a foreign id set). Entirely local (no egress). Reuses ``papers._authors_from_csl`` for row display.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.routers.papers import _authors_from_csl
from app.backend.persistence.reading_queue_repo import (
    add_to_queue,
    list_reading_queue,
    remove_from_queue,
    set_queue_order,
)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()


class ReadingQueueItem(BaseModel):
    id: int
    title: str
    authors: list[str]
    year: int | None = None
    priority: str | None = None  # the user's hand-set triage label (high/normal/low or null) — drives queue grouping


class AddToQueueRequest(BaseModel):
    paper_id: int


class AddToQueueResponse(BaseModel):
    added: bool  # False if the paper was already in the queue (idempotent)


class QueueOrderRequest(BaseModel):
    paper_ids: list[int]


@router.get("/reading-queue", response_model=list[ReadingQueueItem])
def get_reading_queue(conn: Connection = Depends(get_connection)) -> list[ReadingQueueItem]:
    return [
        ReadingQueueItem(
            id=int(r["id"]),
            title=r["title"],
            authors=_authors_from_csl(r["csl_json"], fallback=r["first_author_family_name"]),
            year=r["year"],
            priority=r["priority"],
        )
        for r in list_reading_queue(conn)
    ]


@router.post("/reading-queue", response_model=AddToQueueResponse)
def add_paper_to_queue(payload: AddToQueueRequest, request: Request) -> AddToQueueResponse:
    def op(c: Connection):
        try:
            get_paper(c, payload.paper_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Paper not found") from None
        return add_to_queue(c, payload.paper_id)

    return AddToQueueResponse(added=run_write(request.app.state.engine, op))


@router.put("/reading-queue/order", status_code=http_status.HTTP_204_NO_CONTENT)
def set_reading_queue_order(payload: QueueOrderRequest, request: Request) -> Response:
    def op(c: Connection):
        try:
            set_queue_order(c, payload.paper_ids)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    run_write(request.app.state.engine, op)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.delete("/reading-queue/{paper_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_paper_from_queue(paper_id: int, request: Request) -> Response:
    run_write(request.app.state.engine, lambda c: remove_from_queue(c, paper_id))  # idempotent → always 204
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
