"""Resolve/import Zotero word-processor citations into callosum's library (inc 464, backlog #33/#34 P2 #22).

The LibreOffice and Word adapters' "Convert Zotero citations…" commands decode each Zotero-authored document
field's embedded CSL-JSON locally (nothing but the citation's own bibliographic metadata ever reaches this
endpoint's request body), then call this endpoint once with every DISTINCT cited work to resolve each to a callosum
`paper_id` — matching an existing library paper first (`find_existing_paper_by_identity`, the same identity
precedence the Zotero *library* importer already uses), or creating a new metadata-only paper straight from the
citation's own embedded CSL-JSON when no match exists (`normalize_zotero_csl_item`, `importers/zotero.py`) —
the same `imported_source="zotero"` / `processing_tier="metadata-only"` trust posture that importer already
uses, not a new judgment (Principles gate: a faithful format migration, not a claim about the literature).

No egress: every match/create here is a local DB read/write over data already embedded in the open document.
Bounded by `MAX_ZOTERO_DISTINCT_WORKS` — a ReferenceMark/Word Field is untrusted content pulled from an opened
document (rule #4), so this stays defensively bounded like every other adapter-facing endpoint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.backend.importers.zotero import normalize_zotero_csl_item
from app.backend.persistence.repository import create_paper, find_existing_paper_by_identity

router = APIRouter()

MAX_ZOTERO_DISTINCT_WORKS = 300


class ZoteroCitationItem(BaseModel):
    item_data: dict[str, Any]
    uris: list[str] = Field(default_factory=list)


class ZoteroResolveRequest(BaseModel):
    items: list[ZoteroCitationItem] = Field(min_length=1, max_length=MAX_ZOTERO_DISTINCT_WORKS)


class ZoteroResolveResult(BaseModel):
    paper_id: int
    created: bool


@router.post("/citations/zotero/resolve", response_model=list[ZoteroResolveResult])
def resolve_zotero_citations(payload: ZoteroResolveRequest, request: Request) -> list[ZoteroResolveResult]:
    results: list[ZoteroResolveResult] = []
    with request.app.state.engine.begin() as conn:
        for item in payload.items:
            canonical = normalize_zotero_csl_item(item.item_data, item.uris)
            existing = find_existing_paper_by_identity(
                conn,
                doi=canonical["doi"],
                zotero_library_id=canonical["zotero_library_id"],
                zotero_item_key=canonical["zotero_item_key"],
                title=canonical["title"],
                year=canonical["year"],
                first_author_family_name=canonical["first_author_family_name"],
            )
            if existing is not None:
                results.append(ZoteroResolveResult(paper_id=int(existing[1]["id"]), created=False))
                continue
            paper_id = create_paper(conn, **canonical)
            results.append(ZoteroResolveResult(paper_id=paper_id, created=True))
    return results
