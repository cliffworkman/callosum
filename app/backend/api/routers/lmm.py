"""LMM-reporting completeness auditor endpoint (backlog #23, inc 247).

GET /papers/{id}/lmm — deterministic, local, read-only. Reads the paper's extracted text and returns a
presence/absence reporting checklist (never a verdict, never a score, never runs a model). No chunks → an honest
is_lmm:false. Mirrors GET /papers/{id}/bayes and /statcheck. See methods/lmm.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.methods.lmm import audit_lmm
from app.backend.persistence.repository import get_chunks_for_paper, get_paper

router = APIRouter()


class LmmCheckOut(BaseModel):
    key: str
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None = None
    page: int | None = None
    note: str | None = None
    explainer: str
    basis: str


class LmmResponse(BaseModel):
    is_lmm: bool  # the checklist runs only on a paper that detectably uses a mixed model
    checks: list[LmmCheckOut]


@router.get("/papers/{paper_id}/lmm", response_model=LmmResponse)
def paper_lmm(paper_id: int, conn: Connection = Depends(get_connection)) -> LmmResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    report = audit_lmm(get_chunks_for_paper(conn, paper_id))
    return LmmResponse(
        is_lmm=report.is_lmm,
        checks=[
            LmmCheckOut(
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
