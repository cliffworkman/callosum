"""Per-paper extra URL endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.routers.paper_models import PaperUrlRef
from app.backend.persistence.paper_urls_repo import add_paper_url, delete_paper_url, list_paper_urls

router = APIRouter()


class PaperUrlCreateRequest(BaseModel):
    url: str = Field(max_length=2000)
    label: str | None = Field(default=None, max_length=120)


@router.post("/papers/{paper_id}/urls", response_model=PaperUrlRef, status_code=http_status.HTTP_201_CREATED)
def add_url(paper_id: int, payload: PaperUrlCreateRequest, conn: Connection = Depends(get_connection)) -> PaperUrlRef:
    try:
        url_id = add_paper_url(conn, paper_id, payload.url, payload.label)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if url_id is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    conn.commit()
    row = next(row for row in list_paper_urls(conn, paper_id) if int(row["id"]) == url_id)
    return PaperUrlRef(id=int(row["id"]), url=row["url"], label=row["label"], source=row["source"])


@router.delete("/papers/{paper_id}/urls/{url_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_url(paper_id: int, url_id: int, conn: Connection = Depends(get_connection)) -> Response:
    if not delete_paper_url(conn, paper_id, url_id):
        raise HTTPException(status_code=404, detail="URL not found")
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
