"""Full-text PDF search endpoint (inc 209, A3) — `GET /papers/fulltext`.

Verbatim lexical search over the extracted PDF chunk text (FTS5; see `persistence/fulltext_repo.py`) — the
exact-string complement to the semantic axes/synthesis. Per-occurrence hits, bm25-ranked, each carrying a snippet +
page so the UI can open the PDF at that page (region precision — page scroll, no fabricated exact rect). Entirely
local (no egress). Lives in its own router so it can be included **before** `papers.router` (so `/papers/fulltext`
isn't captured by `/papers/{paper_id}`), the duplicates.py precedent.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.persistence.fulltext_repo import FULLTEXT_MAX_RESULTS, search_chunks_fulltext

router = APIRouter()


class FulltextHit(BaseModel):
    paper_id: int
    title: str | None = None
    author: str | None = None  # first-author family name (for the "Author · year" meta)
    year: int | None = None
    chunk_id: int
    page_start: int
    page_end: int
    snippet: str  # matched terms wrapped in SNIPPET_OPEN/CLOSE markers (the frontend bolds them)
    coordinate_precision: str = "region"  # page-level scroll, never a fabricated exact rect (coordinate honesty)


@router.get("/papers/fulltext", response_model=list[FulltextHit])
def fulltext_search(
    q: str = Query(default=""),
    limit: int = Query(default=FULLTEXT_MAX_RESULTS, ge=1, le=FULLTEXT_MAX_RESULTS),
    conn: Connection = Depends(get_connection),
) -> list[FulltextHit]:
    # The query is sanitized + bound in the repo (rule #3/#4); a malformed/empty query → [] (never 500).
    return [
        FulltextHit(
            paper_id=int(r["paper_id"]),
            title=r["title"],
            author=r["first_author_family_name"],
            year=r["year"],
            chunk_id=int(r["chunk_id"]),
            page_start=int(r["page_start"]),
            page_end=int(r["page_end"]),
            snippet=r["snippet"],
        )
        for r in search_chunks_fulltext(conn, q, limit=limit)
    ]
