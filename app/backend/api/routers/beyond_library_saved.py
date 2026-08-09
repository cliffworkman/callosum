"""Persistent, dismissible beyond-library suggestion queue (backlog #30's last open piece, inc 465).

`app/backend/citations/beyond_library.py` is a live, per-sentence, ephemeral search — a suggestion you don't
act on immediately (add or insert) is gone the moment you clear the sentence or close the dialog. This gives an
explicit "Save for later" action (never automatic accumulation — matches how nothing else in this codebase
silently persists data from passive activity) a place to land: a flat, add-or-dismiss review queue, mirroring
`gaps.py`'s own "persist candidates, read-time-filter dismissed/now-in-library, Add imports metadata-only,
Dismiss hides for good" shape. Unlike gap-finder (a whole-library scan cached per scope), there is no
"recompute" concept here — only "remember this one candidate I explicitly flagged."

The full suggestion payload (title/authors/abstract/doi/url/reason/evidence/relationship) is persisted verbatim
so a saved card looks identical to the one shown when it was flagged — no re-fetch, no drift, no new judgment
about the literature (Principles #9): `status` is pure user-driven bookkeeping, not a new signal.

No egress in this router — the suggestion was already fetched by `POST /citations/suggest`; save/list/add/
dismiss here is local DB read/write only, the same posture as `gaps.py`'s own add/dismiss endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine, insert, select, update

from app.backend.api.dependencies import get_engine
from app.backend.discovery.search import save_item
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.schema import saved_beyond_library_suggestions
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()

MAX_TITLE = 2000
MAX_TEXT = 4000


class SaveBeyondLibraryRequest(BaseModel):
    dedup_key: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    sources: list[str] = Field(default_factory=list)
    doi: str | None = None
    pmid: str | None = None
    abstract: str | None = Field(default=None, max_length=8000)
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    url: str | None = None
    reason: str | None = Field(default=None, max_length=MAX_TEXT)
    evidence_text: str | None = Field(default=None, max_length=MAX_TEXT)
    evidence_kind: str | None = None
    relationship_kind: str | None = None
    relationship_label: str | None = None
    anchor_paper_id: int | None = None
    anchor_title: str | None = None
    source_query: str | None = Field(default=None, max_length=MAX_TEXT)


class SavedBeyondLibraryItem(BaseModel):
    dedup_key: str
    title: str
    sources: list[str] = []
    doi: str | None = None
    pmid: str | None = None
    abstract: str | None = None
    authors: list[str] = []
    journal: str | None = None
    year: int | None = None
    url: str | None = None
    reason: str | None = None
    evidence_text: str | None = None
    evidence_kind: str | None = None
    relationship_kind: str | None = None
    relationship_label: str | None = None
    anchor_paper_id: int | None = None
    anchor_title: str | None = None
    source_query: str | None = None
    saved_at: str


class SavedBeyondLibraryListResponse(BaseModel):
    items: list[SavedBeyondLibraryItem] = []


def _row_to_item(row: Any) -> SavedBeyondLibraryItem:
    return SavedBeyondLibraryItem(
        dedup_key=row["dedup_key"],
        title=row["title"],
        sources=row["sources"] or [],
        doi=row["doi"],
        pmid=row["pmid"],
        abstract=row["abstract"],
        authors=row["authors"] or [],
        journal=row["journal"],
        year=row["year"],
        url=row["url"],
        reason=row["reason"],
        evidence_text=row["evidence_text"],
        evidence_kind=row["evidence_kind"],
        relationship_kind=row["relationship_kind"],
        relationship_label=row["relationship_label"],
        anchor_paper_id=row["anchor_paper_id"],
        anchor_title=row["anchor_title"],
        source_query=row["source_query"],
        saved_at=row["saved_at"],
    )


@router.post("/citations/beyond-library/save", response_model=SavedBeyondLibraryItem)
def save_beyond_library_suggestion(
    payload: SaveBeyondLibraryRequest, engine: Engine = Depends(get_engine)
) -> SavedBeyondLibraryItem:
    def _do(conn: Connection) -> SavedBeyondLibraryItem:
        values = {
            "dedup_key": payload.dedup_key,
            "title": payload.title,
            "sources": payload.sources,
            "doi": payload.doi,
            "pmid": payload.pmid,
            "abstract": payload.abstract,
            "authors": payload.authors,
            "journal": payload.journal,
            "year": payload.year,
            "url": payload.url,
            "reason": payload.reason,
            "evidence_text": payload.evidence_text,
            "evidence_kind": payload.evidence_kind,
            "relationship_kind": payload.relationship_kind,
            "relationship_label": payload.relationship_label,
            "anchor_paper_id": payload.anchor_paper_id,
            "anchor_title": payload.anchor_title,
            "source_query": payload.source_query,
            "status": "pending",  # an explicit re-save always lands (or re-lands) in the review queue
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        existing = conn.execute(
            select(saved_beyond_library_suggestions.c.id).where(
                saved_beyond_library_suggestions.c.dedup_key == payload.dedup_key
            )
        ).first()
        if existing is not None:
            conn.execute(
                update(saved_beyond_library_suggestions)
                .where(saved_beyond_library_suggestions.c.id == existing[0])
                .values(**values)
            )
        else:
            conn.execute(insert(saved_beyond_library_suggestions).values(**values))
        row = (
            conn.execute(
                select(saved_beyond_library_suggestions).where(
                    saved_beyond_library_suggestions.c.dedup_key == payload.dedup_key
                )
            )
            .mappings()
            .one()
        )
        return _row_to_item(row)

    return run_write(engine, _do)


@router.get("/citations/beyond-library/saved", response_model=SavedBeyondLibraryListResponse)
def list_saved_beyond_library_suggestions(engine: Engine = Depends(get_engine)) -> SavedBeyondLibraryListResponse:
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(saved_beyond_library_suggestions).where(saved_beyond_library_suggestions.c.status == "pending")
            )
            .mappings()
            .all()
        )
        items = []
        for row in rows:  # read-time filter, like gaps_list's own -- Add elsewhere makes a row vanish for free
            if row["doi"] and find_existing_paper_by_identity(conn, doi=row["doi"]) is not None:
                continue
            items.append(_row_to_item(row))
        return SavedBeyondLibraryListResponse(items=items)


class DedupKeyRequest(BaseModel):
    dedup_key: str = Field(min_length=1, max_length=512)


class AddSavedBeyondLibraryResponse(BaseModel):
    paper_id: int
    created: bool


@router.post("/citations/beyond-library/add", response_model=AddSavedBeyondLibraryResponse)
def add_saved_beyond_library_suggestion(
    payload: DedupKeyRequest, engine: Engine = Depends(get_engine)
) -> AddSavedBeyondLibraryResponse:
    def _do(conn: Connection) -> AddSavedBeyondLibraryResponse:
        row = (
            conn.execute(
                select(saved_beyond_library_suggestions).where(
                    saved_beyond_library_suggestions.c.dedup_key == payload.dedup_key
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="No saved suggestion with that identity.")
        result = save_item(
            conn,
            title=row["title"],
            doi=row["doi"],
            pmid=row["pmid"],
            abstract=row["abstract"],
            authors=row["authors"] or [],
            journal=row["journal"],
            year=row["year"],
            url=row["url"],
        )
        conn.execute(
            update(saved_beyond_library_suggestions)
            .where(saved_beyond_library_suggestions.c.id == row["id"])
            .values(status="added")
        )
        return AddSavedBeyondLibraryResponse(paper_id=int(result["paper_id"]), created=bool(result["created"]))

    return run_write(engine, _do)


@router.post("/citations/beyond-library/dismiss", status_code=204)
def dismiss_saved_beyond_library_suggestion(payload: DedupKeyRequest, engine: Engine = Depends(get_engine)) -> None:
    def _do(conn: Connection) -> None:
        result = conn.execute(
            update(saved_beyond_library_suggestions)
            .where(saved_beyond_library_suggestions.c.dedup_key == payload.dedup_key)
            .values(status="dismissed")
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="No saved suggestion with that identity.")

    run_write(engine, _do)
