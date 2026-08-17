"""Findings subsystem endpoints (inc 130): per-paper findings, the library overview, and the candidate review
workflow. Sync, local, no egress. Facts are not reviewable (review targets candidates only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.persistence.findings_repo import (
    findings_overview,
    get_finding_dict,
    get_paper_findings,
    set_review_state,
)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()


class FindingModel(BaseModel):
    id: int
    paper_id: int
    source: str
    kind: str
    tier: str | None = None
    payload: dict
    review_state: str | None = None
    review_reason: str | None = None


class PaperFindingsResponse(BaseModel):
    facts: list[FindingModel]
    candidates: list[FindingModel]


class FindingsOverviewItem(BaseModel):
    paper_id: int
    unreviewed_count: int
    has_facts: bool


class ReviewRequest(BaseModel):
    state: str
    reason: str | None = None


@router.get("/papers/{paper_id}/findings", response_model=PaperFindingsResponse)
def paper_findings_get(
    paper_id: int, source: str | None = None, conn: Connection = Depends(get_connection)
) -> PaperFindingsResponse:
    """``source`` is an optional query param scoping the result to one producer's findings (e.g.
    ``?source=analytic-flexibility``); omitted, it returns every source's findings exactly as before this
    parameter existed."""
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    data = get_paper_findings(conn, paper_id, source=source)
    return PaperFindingsResponse(
        facts=[FindingModel(**f) for f in data["facts"]],
        candidates=[FindingModel(**c) for c in data["candidates"]],
    )


@router.get("/findings/overview", response_model=list[FindingsOverviewItem])
def findings_overview_get(conn: Connection = Depends(get_connection)) -> list[FindingsOverviewItem]:
    return [FindingsOverviewItem(**o) for o in findings_overview(conn)]


@router.post("/findings/{finding_id}/review", response_model=FindingModel)
def finding_review(finding_id: int, payload: ReviewRequest, engine: Engine = Depends(get_engine)) -> FindingModel:
    def _do(conn: Connection) -> FindingModel:
        result = set_review_state(conn, finding_id, payload.state, payload.reason)
        errors = {
            "not-found": (404, "Finding not found"),
            "not-candidate": (422, "Facts are not reviewable"),
            "bad-state": (422, "state must be one of: confirmed, accepted, noted"),
            "needs-reason": (422, "Accepted requires a reason"),
        }
        if result in errors:
            raise HTTPException(status_code=errors[result][0], detail=errors[result][1])
        return FindingModel(**get_finding_dict(conn, finding_id))

    return run_write(engine, _do)  # transaction-level retry on a transient SQLite writer lock (inc 281)
