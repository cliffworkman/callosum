"""Transparency-signals auditor endpoint (backlog #44, inc 250).

GET /papers/{id}/transparency — deterministic, local, read-only. Reads the paper's extracted text and returns 7
open-science-disclosure detectors (present / not-found / not-applicable). No score, no verdict; "not-found" ≠ "absent"
(silence≠certificate). No chunks → all detectors run over empty text (the frontend gates the "process a PDF first"
state). Mirrors GET /papers/{id}/meta-analysis. See methods/transparency.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.methods.transparency import detect_transparency
from app.backend.persistence.repository import get_chunks_for_paper, get_paper

router = APIRouter()


class TransparencyCheckOut(BaseModel):
    key: str
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None = None
    page: int | None = None
    note: str | None = None
    explainer: str
    basis: str


class TransparencyResponse(BaseModel):
    checks: list[TransparencyCheckOut]


@router.get("/papers/{paper_id}/transparency", response_model=TransparencyResponse)
def paper_transparency(paper_id: int, conn: Connection = Depends(get_connection)) -> TransparencyResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    report = detect_transparency(get_chunks_for_paper(conn, paper_id))
    return TransparencyResponse(
        checks=[
            TransparencyCheckOut(
                key=c.key,
                label=c.label,
                status=c.status,
                evidence=c.evidence,
                page=c.page,
                note=c.note,
                explainer=c.explainer,
                basis=c.basis,
            )
            for c in report.checks
        ],
    )
