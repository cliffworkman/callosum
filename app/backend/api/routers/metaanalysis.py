"""Meta-analysis reporting auditor endpoint (backlog #36, inc 249).

GET /papers/{id}/meta-analysis — deterministic, local, read-only. Reads the paper's extracted text and returns a
presence/absence reporting checklist (never a verdict, never a score, never pools/models). No chunks → an honest
is_meta_analysis:false. Mirrors GET /papers/{id}/lmm and /bayes. See methods/metaanalysis.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.methods.metaanalysis import audit_meta_analysis
from app.backend.persistence.repository import get_chunks_for_paper, get_paper

router = APIRouter()


class MetaCheckOut(BaseModel):
    key: str
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None = None
    page: int | None = None
    note: str | None = None
    explainer: str
    basis: str


class MetaResponse(BaseModel):
    is_meta_analysis: bool
    checks: list[MetaCheckOut]


@router.get("/papers/{paper_id}/meta-analysis", response_model=MetaResponse)
def paper_meta_analysis(paper_id: int, conn: Connection = Depends(get_connection)) -> MetaResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    report = audit_meta_analysis(get_chunks_for_paper(conn, paper_id))
    return MetaResponse(
        is_meta_analysis=report.is_meta_analysis,
        checks=[
            MetaCheckOut(
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
