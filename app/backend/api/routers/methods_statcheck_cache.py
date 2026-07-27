"""Per-paper statcheck result cache — cache-then-explicit-rescan (inc 400).

Split from `methods.py` (rule #1 — that file was at 524/600) rather than grow it further. Imports its
private compute/payload helpers directly, the `paper_enrich.py`/`_detail_for` precedent — `methods.py`
never imports this module, so there's no cycle. The existing `GET /papers/{paper_id}/statcheck` (a fused
compute-and-return endpoint) is untouched; this adds a genuine cache alongside it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.routers.methods import (
    StatcheckCoverage,
    StatcheckResult,
    _run_statcheck_for_paper,
    _statcheck_result_payload,
)
from app.backend.api.routers.papers import _iso_or_none
from app.backend.methods.evidence_anchors import pdf_attachment_ids
from app.backend.persistence.repository import get_paper
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.statcheck_cache_repo import (
    compute_content_fingerprint,
    get_statcheck_cache,
    store_statcheck_cache,
)

router = APIRouter()


class StatcheckCacheResponse(BaseModel):
    cached: bool
    checked: int = 0
    inconsistent: int = 0
    decision_errors: int = 0
    results: list[StatcheckResult] = []
    coverage: StatcheckCoverage | None = None
    computed_at: str | None = None  # ISO — the frontend's verbatim "as of" attribution
    stale: bool = False  # a passive hint only; the cached result above is never withheld or replaced by this


def _cache_response(conn: Connection, paper_id: int) -> StatcheckCacheResponse:
    row = get_statcheck_cache(conn, paper_id)
    if row is None:
        return StatcheckCacheResponse(cached=False)
    return StatcheckCacheResponse(
        cached=True,
        checked=row["checked"],
        inconsistent=row["inconsistent"],
        decision_errors=row["decision_errors"],
        results=[StatcheckResult(**r) for r in row["results_json"]],
        coverage=StatcheckCoverage(**row["coverage_json"]),
        computed_at=_iso_or_none(row["computed_at"]),
        stale=compute_content_fingerprint(conn, paper_id) != row["content_fingerprint"],
    )


@router.get("/papers/{paper_id}/statcheck/cached", response_model=StatcheckCacheResponse)
def paper_statcheck_cached(paper_id: int, conn: Connection = Depends(get_connection)) -> StatcheckCacheResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    return _cache_response(conn, paper_id)


@router.post("/papers/{paper_id}/statcheck/rescan", response_model=StatcheckCacheResponse)
def paper_statcheck_rescan(paper_id: int, engine: Engine = Depends(get_engine)) -> StatcheckCacheResponse:
    def _do(conn: Connection) -> StatcheckCacheResponse:
        try:
            get_paper(conn, paper_id)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Paper not found") from None
        report, coverage = _run_statcheck_for_paper(conn, paper_id)
        pdf_ids = pdf_attachment_ids(conn, (r.attachment_id for r in report.results))
        results = [_statcheck_result_payload(conn, r, pdf_ids) for r in report.results]
        fingerprint = compute_content_fingerprint(conn, paper_id)
        store_statcheck_cache(
            conn,
            paper_id,
            checked=report.checked,
            inconsistent=report.inconsistent,
            decision_errors=report.decision_errors,
            results_json=results,
            coverage_json=coverage,
            content_fingerprint=fingerprint,
        )
        return _cache_response(conn, paper_id)

    return run_write(engine, _do)
