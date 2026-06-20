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
from app.backend.persistence.tags_repo import add_tag_to_paper, get_tags_for_paper, list_tags, remove_tag_from_paper

router = APIRouter()


class TagRef(BaseModel):
    id: int
    name: str


class TagSummary(BaseModel):
    id: int
    name: str
    paper_count: int


class AddTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SuggestedTagsResponse(BaseModel):
    suggestions: list[str]


@router.get("/tags", response_model=list[TagSummary])
def list_all_tags(conn: Connection = Depends(get_connection)) -> list[TagSummary]:
    return [TagSummary(id=int(r["id"]), name=r["name"], paper_count=int(r["paper_count"])) for r in list_tags(conn)]


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
    return TagRef(id=int(row["id"]), name=row["name"])


@router.delete("/papers/{paper_id}/tags/{tag_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_paper_tag(paper_id: int, tag_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if not remove_tag_from_paper(conn, paper_id, tag_id):
        raise HTTPException(status_code=404, detail="Tag not on this paper")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
