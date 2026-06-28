"""Literature discovery endpoints (backlog #28, inc 183) — the Search tab's backend.

`GET /discovery/search?q=` fans out to the SourceProvider registry, dedups across sources, marks `in_library`, and
returns the **complete** list (no filtering — relevance highlight is SP1b). `POST /discovery/save` creates a
metadata-only library paper (deduped; no PDF fetch). Public-metadata search (Crossref now) — NOT the egress gate.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.discovery.search import run_search, save_item

router = APIRouter()


class SaveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    doi: str | None = Field(default=None, max_length=300)
    abstract: str | None = Field(default=None, max_length=20000)
    authors: list[str] = Field(default_factory=list, max_length=500)
    journal: str | None = Field(default=None, max_length=600)
    year: int | None = Field(default=None, ge=1000, le=2100)
    url: str | None = Field(default=None, max_length=2000)


@router.get("/discovery/search")
def discovery_search(
    request: Request,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=25, ge=1, le=50),
    conn: Connection = Depends(get_connection),
) -> dict[str, Any]:
    items = run_search(conn, request.app.state.discovery_registry, q.strip(), limit)
    return {"items": [item.to_dict() for item in items]}


@router.post("/discovery/save")
def discovery_save(payload: SaveRequest, conn: Connection = Depends(get_connection)) -> dict[str, Any]:
    result = save_item(
        conn,
        title=payload.title.strip(),
        doi=payload.doi,
        abstract=payload.abstract,
        authors=payload.authors,
        journal=payload.journal,
        year=payload.year,
        url=payload.url,
    )
    conn.commit()
    return result
