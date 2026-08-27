"""Optional, reversible LLM triage for critical-review items (backlog: critique triage).

Split out of `critical_review.py` (over the 600-line cap once triage landed there). The bounded
evaluator itself lives in `app/backend/methods/critical_review_triage.py`; this module wires it
into the two shapes critique produces — ephemeral Tier-1 contested claims (single-paper as
pydantic objects, set as plain dicts) and persisted Tier-2 candidates — plus the one standalone,
paper-agnostic endpoint that lets either surface re-triage already-persisted candidates on demand.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection, resolve_llm_config
from app.backend.persistence import critical_review_repo as repo

router = APIRouter()


def triage_evaluator(app: FastAPI):
    """(evaluator, refusal_status) — mirrors ``_run_set_tier2``'s own egress-gate shape exactly. ``evaluator`` is
    None whenever ``refusal_status`` is set (egress refused, or no resolved API key with no test-seam evaluator)."""
    from app.backend.llm.providers import requires_egress
    from app.backend.methods.critical_review_triage import CriticalReviewTriageEvaluator

    config = resolve_llm_config(app)
    if requires_egress(config) and not config.data_egress_enabled:
        return None, {
            "status": "unavailable",
            "detail": "AI triage needs data-egress consent (Settings → AI features).",
        }
    evaluator = getattr(app.state, "critical_review_triage_evaluator", None)
    if evaluator is None:
        if requires_egress(config) and not config.resolved_api_key():
            return None, {"status": "unavailable", "detail": "AI triage needs an API key (Settings → AI features)."}
        evaluator = CriticalReviewTriageEvaluator(config=config)
    return evaluator, None


def triage_contested(app: FastAPI, contested: list[Any]) -> dict:
    """Ephemeral, in-job triage over single-paper ``ContestedClaimResponse`` objects: annotates each item's
    ``llm_triage`` in place. Never persisted — contested claims themselves live only inside this job's cached
    result. Duck-typed on ``.claim``/``.passage``/``.stance``/``.confidence``/``.llm_triage`` to avoid importing
    the pydantic model back from ``critical_review.py`` (would create a circular import)."""
    evaluator, refusal = triage_evaluator(app)
    if refusal:
        return refusal
    if not contested:
        return {"status": "not_searched", "detail": "No contested claims were available to triage."}
    items = [
        {"item_id": i, "claim": c.claim, "evidence": c.passage, "stance": c.stance, "confidence": c.confidence}
        for i, c in enumerate(contested)
    ]
    result = evaluator.evaluate(items=items)
    annotations = result.get("annotations", {})
    for i, c in enumerate(contested):
        if i in annotations:
            c.llm_triage = annotations[i]
    return result.get("status", {"status": "success"})


def triage_contested_dicts(app: FastAPI, contested: list[dict]) -> dict:
    """Same as ``triage_contested`` but for the set path's plain-dict contested-claim shape (``set_aggregate``
    builds ``report`` straight from these dicts, never through ``ContestedClaimResponse``)."""
    evaluator, refusal = triage_evaluator(app)
    if refusal:
        return refusal
    if not contested:
        return {"status": "not_searched", "detail": "No contested claims were available to triage."}
    items = [
        {
            "item_id": i,
            "claim": c.get("claim"),
            "evidence": c.get("passage"),
            "stance": c.get("stance"),
            "confidence": c.get("confidence"),
        }
        for i, c in enumerate(contested)
    ]
    result = evaluator.evaluate(items=items)
    annotations = result.get("annotations", {})
    for i, c in enumerate(contested):
        if i in annotations:
            c["llm_triage"] = annotations[i]
    return result.get("status", {"status": "success"})


def triage_and_persist_candidates(app: FastAPI, conn: Connection, candidates: list[dict]) -> dict:
    """Triage newly (or previously) persisted candidate rows and store the annotations, keyed by candidate id."""
    from app.backend.persistence import critical_review_triage_repo as triage_repo

    evaluator, refusal = triage_evaluator(app)
    if refusal:
        return refusal
    if not candidates:
        return {"status": "not_searched", "detail": "No candidates were available to triage."}
    items = [
        {
            "item_id": c["id"],
            "claim": c.get("concern"),
            "evidence": c.get("anchor_quote"),
            "stance": c.get("stance"),
            "confidence": c.get("confidence"),
        }
        for c in candidates
    ]
    result = evaluator.evaluate(items=items)
    triage_repo.persist_candidate_triage(conn, candidates=candidates, result=result)
    return result.get("status", {"status": "success"})


class CandidateTriageRequest(BaseModel):
    candidate_ids: list[int]


class CandidateTriageResponse(BaseModel):
    candidates: list[dict] = []
    status: dict


@router.post("/critical-read/candidates/triage", response_model=CandidateTriageResponse)
def triage_candidates(
    body: CandidateTriageRequest, request: Request, conn: Connection = Depends(get_connection)
) -> CandidateTriageResponse:
    # Paper-agnostic by design, mirroring accept/reject's own shape — a set critique's candidates span several
    # paper_ids at once. Re-triageable on demand (e.g. candidates generated before this feature existed).
    from app.backend.methods.critical_review_triage import TRIAGE_PROMPT_VERSION
    from app.backend.persistence import critical_review_triage_repo as triage_repo

    rows = repo.list_candidates_by_ids(conn, body.candidate_ids)
    status = triage_and_persist_candidates(request.app, conn, rows)
    conn.commit()
    stored = triage_repo.load_candidate_triage(conn, [r["id"] for r in rows])
    attached = triage_repo.attach_candidate_triage(rows, stored, current_prompt_version=TRIAGE_PROMPT_VERSION)
    return CandidateTriageResponse(
        candidates=[
            {
                "id": r["id"],
                "paper_id": r["paper_id"],
                "concern": r["concern"],
                "anchor_quote": r["anchor_quote"],
                "page": r["page"],
                "stance": r["stance"],
                "confidence": r["confidence"],
                "status": r["status"],
                "llm_triage": attached.get(r["id"]),
            }
            for r in rows
        ],
        status=status,
    )
