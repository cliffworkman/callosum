"""Tag endpoints — list all tags, add/remove a tag on a paper (inc 71).

Lightweight free-form labels (distinct from the semantic axes). Entirely local (no egress); non-destructive
to papers (manages `paper_tags` links only). The per-paper tag list is returned with the paper detail
(`routers/papers.py`); the library filters by tag via `GET /papers?tag_id=`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.clustering.tag_suggestion import suggest_tags_for_paper
from app.backend.persistence.repository import get_paper
from app.backend.persistence.tags_repo import (
    TAG_COLORS,
    add_tag_to_paper,
    get_tags_for_paper,
    is_paper_tag_locked,
    list_tags,
    remove_tag_from_paper,
    set_paper_tag_locked,
    set_tag_color,
)

router = APIRouter()


class TagRef(BaseModel):
    id: int
    name: str
    source: str | None = None  # tag provenance — the UI distinguishes imported keywords from tags you added
    color: str | None = None  # inc 207: optional user-chosen palette key (NULL = uncolored)
    locked: bool = False  # per-paper lock, not a global tag property


class TagSummary(BaseModel):
    id: int
    name: str
    paper_count: int
    source: str | None = None
    color: str | None = None


class AddTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SetTagColorRequest(BaseModel):
    color: str | None = None  # a key in TAG_COLORS, or null to clear


class SetPaperTagLockRequest(BaseModel):
    locked: bool


class SuggestedTagsResponse(BaseModel):
    suggestions: list[str]


@router.get("/tags", response_model=list[TagSummary])
def list_all_tags(conn: Connection = Depends(get_connection)) -> list[TagSummary]:
    return [
        TagSummary(
            id=int(r["id"]),
            name=r["name"],
            paper_count=int(r["paper_count"]),
            source=r["import_source"],
            color=r["color"],
        )
        for r in list_tags(conn)
    ]


@router.get("/tags/colors", response_model=list[str])
def list_tag_colors() -> list[str]:
    """The fixed tag-color palette keys (inc 207) — the frontend renders a swatch per key."""
    return list(TAG_COLORS)


@router.post("/tags/{tag_id}/color", response_model=TagSummary)
def set_paper_tag_color(
    tag_id: int, payload: SetTagColorRequest, conn: Connection = Depends(get_connection)
) -> TagSummary:
    # inc 207: set (or clear, color=null) a tag's palette color. The value must be an allowlisted key (rule #4).
    if payload.color is not None and payload.color not in TAG_COLORS:
        raise HTTPException(status_code=422, detail=f"color must be one of {list(TAG_COLORS)} or null")
    row = set_tag_color(conn, tag_id, payload.color)
    if row is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    conn.commit()
    count = next((t["paper_count"] for t in list_tags(conn) if int(t["id"]) == tag_id), 0)
    return TagSummary(
        id=int(row["id"]), name=row["name"], paper_count=int(count), source=row["import_source"], color=row["color"]
    )


@router.get("/papers/{paper_id}/suggested-tags", response_model=SuggestedTagsResponse)
def suggest_paper_tags(paper_id: int, conn: Connection = Depends(get_connection)) -> SuggestedTagsResponse:
    # Local c-TF-IDF over the library (no egress); candidates exclude the paper's current tags. Read-only.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    existing = [t["name"] for t in get_tags_for_paper(conn, paper_id)]
    return SuggestedTagsResponse(suggestions=suggest_tags_for_paper(conn, paper_id, existing_tag_names=existing))


@router.post("/papers/{paper_id}/tags", response_model=TagRef, status_code=http_status.HTTP_201_CREATED)
def add_paper_tag(paper_id: int, payload: AddTagRequest, conn: Connection = Depends(get_connection)) -> TagRef:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Tag name cannot be blank")
    row = add_tag_to_paper(conn, paper_id, payload.name)
    conn.commit()
    return TagRef(
        id=int(row["id"]), name=row["name"], source=row["import_source"], color=row["color"], locked=bool(row["locked"])
    )


@router.post("/papers/{paper_id}/tags/{tag_id}/lock", response_model=TagRef)
def set_paper_tag_lock(
    paper_id: int, tag_id: int, payload: SetPaperTagLockRequest, conn: Connection = Depends(get_connection)
) -> TagRef:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    row = set_paper_tag_locked(conn, paper_id, tag_id, payload.locked)
    if row is None:
        raise HTTPException(status_code=404, detail="Tag not on this paper")
    conn.commit()
    return TagRef(
        id=int(row["id"]),
        name=row["name"],
        source=row["import_source"],
        color=row["color"],
        locked=bool(row["locked"]),
    )


@router.delete("/papers/{paper_id}/tags/{tag_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_paper_tag(paper_id: int, tag_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if is_paper_tag_locked(conn, paper_id, tag_id):
        raise HTTPException(status_code=409, detail="Unlock this tag before removing it from this paper")
    if not remove_tag_from_paper(conn, paper_id, tag_id):
        raise HTTPException(status_code=404, detail="Tag not on this paper")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
