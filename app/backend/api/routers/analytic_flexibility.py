"""Analytic-flexibility surfacing endpoint (backlog #37).

A single per-paper action wiring app/backend/analytic_flexibility.py's orchestration to the API: draft
candidate analytic-decision points from a paper's methods-section text and persist them as reviewable
``paper_findings``. Egress is refused BEFORE any paper lookup or network call (mirrors
``routers/grobid.py``'s exact ordering -- the gate wins even over a 404 for a nonexistent paper). The LLM
call and its local write share ONE plain connection (mirrors ``routers/workbench.py``'s ``propose_row``)
rather than ``run_write``'s retry wrapper, so a transient SQLite-lock retry can never re-issue the network
call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.analytic_flexibility import propose_analytic_flexibility
from app.backend.api.dependencies import get_connection, resolve_llm_config
from app.backend.llm.egress import DataEgressDisabledError
from app.backend.llm.managed_local import ManagedLocalTargetError
from app.backend.llm.providers import ProviderError, requires_egress
from app.backend.persistence.repository import get_paper

router = APIRouter()

_EGRESS_REFUSED_DETAIL = (
    "Analytic-flexibility surfacing requires explicit data-egress consent (Settings -> AI features)."
)


@router.post("/papers/{paper_id}/analytic-flexibility")
def run_analytic_flexibility(paper_id: int, request: Request, conn: Connection = Depends(get_connection)) -> dict:
    try:
        config = resolve_llm_config(request.app)
    except ManagedLocalTargetError as exc:
        raise HTTPException(
            status_code=422, detail=f"Local AI is not ready ({exc.code}). Check Settings → AI features."
        ) from None
    if requires_egress(config) and not config.data_egress_enabled:
        raise HTTPException(status_code=403, detail=_EGRESS_REFUSED_DETAIL)
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    try:
        result = propose_analytic_flexibility(conn, paper_id, config)
    except DataEgressDisabledError as exc:  # defense in depth -- the pre-check above should already catch this
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {exc}") from None
    conn.commit()
    return result
