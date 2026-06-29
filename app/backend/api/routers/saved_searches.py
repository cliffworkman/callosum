"""Saved-search endpoints (inc 208, A1) — list / save / delete a named bundle of the existing library facets.

A saved search persists a metadata predicate over the existing GET /papers filters (q / search_field / item_type /
axis / tag / needs_review / signal / sort) — distinct from a semantic axis. The values are re-applied client-side and
re-validated by GET /papers when the search runs; here we validate the SHAPE at the boundary (rule #4) with a typed,
extra-forbidding model so only known facet keys are stored. Entirely local (no egress).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.persistence.saved_search_repo import (
    delete_saved_search,
    list_saved_searches,
    upsert_saved_search,
)

router = APIRouter()


class SavedAxisFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    label: str = ""
    hideUncertain: bool = False


class SavedTagFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str = ""


class SavedSearchParams(BaseModel):
    # Only these known facet keys are stored (extra keys → 422). Defaults mirror the unfiltered library.
    model_config = ConfigDict(extra="forbid")
    q: str = ""
    search_field: str = "all"
    item_type: str = ""
    axis: SavedAxisFilter | None = None
    tag: SavedTagFilter | None = None
    needs_review: bool = False
    signal: str | None = None
    sort: str = "added"


class SavedSearch(BaseModel):
    id: int
    name: str
    params: SavedSearchParams


class SaveSearchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    params: SavedSearchParams


@router.get("/saved-searches", response_model=list[SavedSearch])
def list_all_saved_searches(conn: Connection = Depends(get_connection)) -> list[SavedSearch]:
    return [
        SavedSearch(id=int(r["id"]), name=r["name"], params=SavedSearchParams.model_validate(r["params"] or {}))
        for r in list_saved_searches(conn)
    ]


@router.post("/saved-searches", response_model=SavedSearch, status_code=http_status.HTTP_201_CREATED)
def save_search(payload: SaveSearchRequest, conn: Connection = Depends(get_connection)) -> SavedSearch:
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be blank")
    row = upsert_saved_search(conn, payload.name, payload.params.model_dump())
    conn.commit()
    return SavedSearch(
        id=int(row["id"]), name=row["name"], params=SavedSearchParams.model_validate(row["params"] or {})
    )


@router.delete("/saved-searches/{search_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_saved_search(search_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if not delete_saved_search(conn, search_id):
        raise HTTPException(status_code=404, detail="Saved search not found")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
