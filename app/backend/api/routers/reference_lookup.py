"""Reader "Find referenced paper…" — resolve a selected reference string to scholarly candidate(s).

Composes the read-only ``resolve_reference`` primitive; this router CREATES NOTHING. The add + OA steps reuse
the existing canonical endpoints (``POST /discovery/save`` then ``POST /papers/{id}/acquire-oa``). The request
itself IS the explicit user action authorizing the public, bibliographic Crossref lookup — selecting or
highlighting text never triggers it. A reference string is bibliographic metadata (the same posture as
Discover → Search), NOT gated library text, so it is not on the Gemini egress gate.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.metadata.reference_resolver import MAX_REFERENCE_LEN, ReferenceCandidate, resolve_reference
from integrations.crossref import CrossrefClient

router = APIRouter()


class ResolveReferenceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_REFERENCE_LEN)


class ReferenceCandidateModel(BaseModel):
    title: str
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    in_library: bool = False
    existing_paper_id: int | None = None


class ResolveReferenceResponse(BaseModel):
    # Four inspectable states, not a confidence score (see reference_resolver). `error` (separate from
    # `none`) means the lookup could not complete (Crossref unreachable), distinct from "nothing plausible".
    classification: Literal["identifier_match", "one_candidate", "multiple_candidates", "none"]
    candidates: list[ReferenceCandidateModel] = []
    normalized_text: str = ""
    error: str | None = None


def _to_model(c: ReferenceCandidate) -> ReferenceCandidateModel:
    return ReferenceCandidateModel(
        title=c.title,
        authors=list(c.authors),
        year=c.year,
        venue=c.venue,
        doi=c.doi,
        url=c.url,
        in_library=c.in_library,
        existing_paper_id=c.existing_paper_id,
    )


@router.post("/references/resolve", response_model=ResolveReferenceResponse)
def resolve_reference_endpoint(
    body: ResolveReferenceRequest, request: Request, conn: Connection = Depends(get_connection)
) -> ResolveReferenceResponse:
    """Resolve the selected text → candidate(s). Read-only; the browser makes the add + OA calls on confirm."""
    crossref_client = request.app.state.crossref_client or CrossrefClient()
    result = resolve_reference(conn, body.text, crossref_client=crossref_client)
    return ResolveReferenceResponse(
        classification=result.classification,
        candidates=[_to_model(c) for c in result.candidates],
        normalized_text=result.normalized_text,
        error=result.error,
    )
