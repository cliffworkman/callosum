"""Deterministic Methods producers (inc 95–97).

`GET /papers/{paper_id}/statcheck` recomputes reported NHST p-values from the paper's extracted text — sync,
read-only, **local, no egress, no LLM**. A signal, not a verdict (see `methods/statcheck.py`).

`POST /methods/statcheck/run` (async, inc 97) batch-checks the whole live library and persists one summary row
per paper into `open_science_signals`, so the library can be **filtered** to papers with reporting
inconsistencies (`GET /papers?signal=statcheck-inconsistent`). A *filter to review*, never a rank or score.

The concern lives in its own router (like tags.py's suggested-tags) to keep papers.py lean; the per-paper path is
3 segments so it never collides with `/papers/{paper_id}`.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.methods.bayes import DEFAULT_R, run_bayes
from app.backend.methods.grim import grim_test, grimmer_test
from app.backend.methods.pcurve import PcurveResult, run_pcurve
from app.backend.methods.retraction import apply_retraction, detect_retraction
from app.backend.methods.statcheck import run_statcheck
from app.backend.persistence.findings_repo import upsert_findings
from app.backend.persistence.repository import get_chunks_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.retraction_repo import retraction_db_status
from app.backend.persistence.signals_repo import (
    count_retraction_flagged,
    count_statcheck_flagged,
    get_retraction_status,
    store_statcheck,
)
from integrations.retraction_watch.adapter import RetractionWatchUnavailable, download_retraction_database

MAX_PCURVE_PAPERS = 1000  # bound the selection a p-curve runs over (rule #4)

router = APIRouter()
_log = logging.getLogger("callosum.methods")


class StatcheckResult(BaseModel):
    raw: str
    test_type: str
    reported_p: str
    computed_p: float
    consistency: str  # consistent | inconsistent | decision-error
    page: int | None = None


class StatcheckResponse(BaseModel):
    checked: int
    inconsistent: int
    decision_errors: int
    results: list[StatcheckResult]


@router.get("/papers/{paper_id}/statcheck", response_model=StatcheckResponse)
def paper_statcheck(paper_id: int, conn: Connection = Depends(get_connection)) -> StatcheckResponse:
    # Deterministic, local recomputation over the paper's extracted text. No chunks (a metadata-only paper) →
    # checked: 0, an honest "no extractable text" — never an error.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    report = run_statcheck(get_chunks_for_paper(conn, paper_id))
    return StatcheckResponse(
        checked=report.checked,
        inconsistent=report.inconsistent,
        decision_errors=report.decision_errors,
        results=[
            StatcheckResult(
                raw=r.raw,
                test_type=r.test_type,
                reported_p=r.reported_p,
                computed_p=r.computed_p,
                consistency=r.consistency,
                page=r.page,
            )
            for r in report.results
        ],
    )


# ── Bayesian auditor (inc 241): recompute reported default (JZS) Bayes factors for inline t-test BFs (sync,
# read-only, local, no egress, no LLM). A signal, not a verdict — see `methods/bayes.py`. ──


class BayesResult(BaseModel):
    raw: str
    reported_bf10: float
    computed_paired: float | None = None
    computed_two_sample: float | None = None
    consistency: str  # reproduced | not-reproduced
    matched_design: str | None = None
    page: int | None = None


class BayesResponse(BaseModel):
    checked: int
    not_reproduced: int
    prior_scale: float  # the assumed default JZS prior scale (r ≈ 0.707), shown for inspectability
    results: list[BayesResult]


@router.get("/papers/{paper_id}/bayes", response_model=BayesResponse)
def paper_bayes(paper_id: int, conn: Connection = Depends(get_connection)) -> BayesResponse:
    # Deterministic, local recompute of default JZS Bayes factors over the paper's extracted text. No chunks →
    # checked: 0, an honest "no extractable text" — never an error.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    report = run_bayes(get_chunks_for_paper(conn, paper_id))
    return BayesResponse(
        checked=report.checked,
        not_reproduced=report.not_reproduced,
        prior_scale=round(DEFAULT_R, 4),
        results=[
            BayesResult(
                raw=r.raw,
                reported_bf10=r.reported_bf10,
                computed_paired=r.computed_paired,
                computed_two_sample=r.computed_two_sample,
                consistency=r.consistency,
                matched_design=r.matched_design,
                page=r.page,
            )
            for r in report.results
        ],
    )


# ── GRIM + GRIMMER (inc 127): an assisted, per-value data-consistency calculator (sync, stateless, no DB/egress).
# The user enters one reported value to check — inherently non-accusatory; a prompt to look, never a verdict. ──


class GrimRequest(BaseModel):
    mean: str
    sd: str | None = None
    n: int
    items: int = 1


class GrimResultModel(BaseModel):
    consistent: bool
    reported_mean: str
    n: int
    items: int
    decimals: int
    granularity: float
    nearest: list[str]
    no_power: bool
    note: str


class GrimmerResultModel(BaseModel):
    consistent: bool
    reported_sd: str
    decimals: int
    supported: bool
    note: str


class GrimComputeResponse(BaseModel):
    grim: GrimResultModel
    grimmer: GrimmerResultModel | None = None


@router.post("/methods/grim", response_model=GrimComputeResponse)
def grim_compute(payload: GrimRequest) -> GrimComputeResponse:
    try:
        grim = grim_test(payload.mean, payload.n, payload.items)
        grimmer = grimmer_test(payload.mean, payload.sd, payload.n, payload.items) if payload.sd else None
    except (ValueError, ArithmeticError):
        raise HTTPException(
            status_code=422,
            detail="Invalid GRIM inputs: mean/SD must be numbers; n and items must be positive.",
        ) from None
    return GrimComputeResponse(
        grim=GrimResultModel(**vars(grim)),
        grimmer=GrimmerResultModel(**vars(grimmer)) if grimmer else None,
    )


# ── library-wide batch (inc 97): persist a per-paper summary so the library can be filtered to inconsistencies ──


class StatcheckRunSummary(BaseModel):
    total: int = 0  # live papers
    checked: int = 0  # papers with ≥1 detected APA test
    flagged: int = 0  # papers with ≥1 inconsistency or decision error


class StatcheckRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: StatcheckRunSummary | None = None


@router.post("/methods/statcheck/run", response_model=StatcheckRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def statcheck_run(background_tasks: BackgroundTasks, request: Request) -> StatcheckRunResponse:
    # Batch-check every live paper (async — bounded by paper count + the per-paper MAX_RESULTS). Persists one
    # summary row per paper into open_science_signals; re-running overwrites. Local, no egress, no LLM.
    job_id = request.app.state.statcheck_jobs.create()
    background_tasks.add_task(_run_statcheck_all_job, request.app, job_id)
    return StatcheckRunResponse(job_id=job_id, status="pending")


class StatcheckLibrarySummary(BaseModel):
    flagged: int = 0  # papers a batch run flagged (status='inconsistent') — drives the library "N flagged" chip


@router.get("/methods/statcheck/summary", response_model=StatcheckLibrarySummary)
def statcheck_library_summary(conn: Connection = Depends(get_connection)) -> StatcheckLibrarySummary:
    return StatcheckLibrarySummary(flagged=count_statcheck_flagged(conn))


@router.get("/methods/statcheck/run/{job_id}", response_model=StatcheckRunResponse)
def statcheck_run_status(job_id: str, request: Request) -> StatcheckRunResponse:
    job = request.app.state.statcheck_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Statcheck job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return StatcheckRunResponse(job_id=job_id, status=job.status, detail=job.detail)


# ── p-curve (inc 126): collection-level evidential-value check over a USER-SELECTED set of papers ──
# Ephemeral (no persistence): runs over an ad-hoc selection and returns the result. Reuses the statcheck
# extractor for the exact p-values. Collection-level only — never per-paper, never "p-hacked" (the no-accusation
# boundary). The interpretation (evidential value vs concern) is the user's.


class PcurveIncludedTest(BaseModel):
    paper_id: int
    page: int | None = None
    p: float
    raw: str


class PcurveResultModel(BaseModel):
    n_papers: int
    k_total_extracted: int
    k_significant: int
    right_skew_z: float | None = None
    right_skew_p: float | None = None
    binomial_p: float | None = None
    bins: list[float] = []
    included_tests: list[PcurveIncludedTest] = []
    low_power: bool = False
    note: str = ""


class PcurveRunRequest(BaseModel):
    paper_ids: list[int]


class PcurveRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: PcurveResultModel | None = None


@router.post("/methods/pcurve/run", response_model=PcurveRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def pcurve_run(payload: PcurveRunRequest, background_tasks: BackgroundTasks, request: Request) -> PcurveRunResponse:
    ids = list(dict.fromkeys(payload.paper_ids))[:MAX_PCURVE_PAPERS]  # de-dup, preserve order, cap (rule #4)
    if not ids:
        raise HTTPException(status_code=422, detail="p-curve requires at least one paper_id")
    job_id = request.app.state.pcurve_jobs.create()
    background_tasks.add_task(_run_pcurve_job, request.app, job_id, ids)
    return PcurveRunResponse(job_id=job_id, status="pending")


@router.get("/methods/pcurve/run/{job_id}", response_model=PcurveRunResponse)
def pcurve_run_status(job_id: str, request: Request) -> PcurveRunResponse:
    job = request.app.state.pcurve_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="p-curve job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return PcurveRunResponse(job_id=job_id, status=job.status, detail=job.detail)


def _pcurve_to_model(result: PcurveResult) -> PcurveResultModel:
    return PcurveResultModel(
        n_papers=result.n_papers,
        k_total_extracted=result.k_total_extracted,
        k_significant=result.k_significant,
        right_skew_z=result.right_skew_z,
        right_skew_p=result.right_skew_p,
        binomial_p=result.binomial_p,
        bins=result.bins,
        included_tests=[
            PcurveIncludedTest(paper_id=t.paper_id, page=t.page, p=t.p, raw=t.raw) for t in result.included_tests
        ],
        low_power=result.low_power,
        note=result.note,
    )


def _run_pcurve_job(app: FastAPI, job_id: str, paper_ids: list[int]) -> None:
    jobs: JobStore[PcurveRunResponse] = app.state.pcurve_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.begin() as conn:
            live = set(list_live_paper_ids(conn))  # exclude trashed papers from the analysis
            per_paper = [
                (pid, run_statcheck(get_chunks_for_paper(conn, pid)).results) for pid in paper_ids if pid in live
            ]
            result = run_pcurve(per_paper)
        jobs.mark_done(job_id, PcurveRunResponse(job_id=job_id, status="done", result=_pcurve_to_model(result)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _run_statcheck_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[StatcheckRunResponse] = app.state.statcheck_jobs
    jobs.mark_running(job_id)
    try:
        total = checked = flagged = 0
        with app.state.engine.begin() as conn:
            for paper_id in list_live_paper_ids(conn):
                total += 1
                report = run_statcheck(get_chunks_for_paper(conn, paper_id))
                if report.checked > 0:
                    checked += 1
                flagged_n = report.inconsistent + report.decision_errors
                if flagged_n > 0:
                    flagged += 1
                store_statcheck(
                    conn,
                    paper_id,
                    checked=report.checked,
                    inconsistent=report.inconsistent,
                    decision_errors=report.decision_errors,
                )
                # inc 133: also emit a CANDIDATE finding for the unified review queue (a prompt to look, reviewable
                # — coexists with the signal above, which is the persistent fact). Clean → supersede any prior one.
                if flagged_n > 0:
                    page = next(
                        (r.page for r in report.results if r.consistency != "consistent" and r.page is not None), None
                    )
                    upsert_findings(
                        conn,
                        paper_id,
                        "statcheck",
                        [
                            {
                                "kind": "candidate",
                                "tier": "primary",
                                "payload": {
                                    "desc": f"{flagged_n} statistical reporting "
                                    f"inconsistenc{'y' if flagged_n == 1 else 'ies'} (statcheck) — review",
                                    "inconsistent": report.inconsistent,
                                    "decision_errors": report.decision_errors,
                                    "checked": report.checked,
                                    "page": page,
                                },
                            }
                        ],
                    )
                else:
                    upsert_findings(conn, paper_id, "statcheck", [])
        jobs.mark_done(
            job_id,
            StatcheckRunResponse(
                job_id=job_id,
                status="done",
                summary=StatcheckRunSummary(total=total, checked=checked, flagged=flagged),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


# ── retraction (inc 131): the first findings producer. Multi-source (Crossref + OpenAlex) per-DOI detection →
# a FACT in paper_findings + an honest per-paper check status in open_science_signals (silence != clean) + the
# library "Retracted" filter. A FACT relayed from a registry — never an author judgment (the no-accusation veto). ──


class RetractionStatusResponse(BaseModel):
    paper_id: int
    status: str  # retracted/correction/concern (flagged) | none (checked-clean) | unchecked (no DOI / not yet run)
    checked: bool  # was a check actually run for this paper? (distinguishes 'unchecked, no DOI' from 'never run')
    sources: list[str] = []
    checked_at: str | None = None


@router.get("/papers/{paper_id}/retraction", response_model=RetractionStatusResponse)
def paper_retraction_status(paper_id: int, conn: Connection = Depends(get_connection)) -> RetractionStatusResponse:
    # Read-only: returns the STORED status (no network). The library batch is the trigger; this is what the
    # Review pane reads to show "checked — none found" / "unchecked — no DOI" / (the FACT renders the retraction).
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    row = get_retraction_status(conn, paper_id)
    if row is None:
        return RetractionStatusResponse(paper_id=paper_id, status="unchecked", checked=False)
    snippet = json.loads(row["evidence_snippet"]) if row["evidence_snippet"] else {}
    return RetractionStatusResponse(
        paper_id=paper_id,
        status=row["status"],
        checked=True,
        sources=snippet.get("sources", []),
        checked_at=snippet.get("checked_at"),
    )


class RetractionRunSummary(BaseModel):
    total: int = 0  # live papers
    checked: int = 0  # papers that had a DOI to check
    flagged: int = 0  # papers a registry records as retracted


class RetractionRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: RetractionRunSummary | None = None


@router.post("/methods/retraction/run", response_model=RetractionRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def retraction_run(background_tasks: BackgroundTasks, request: Request) -> RetractionRunResponse:
    # Batch-check every live paper against the configured sources (async). Persists a FACT (when flagged) + a
    # per-paper check-status row; re-running overwrites. Metadata egress only (public DOI lookups), not the Gemini gate.
    job_id = request.app.state.retraction_jobs.create()
    background_tasks.add_task(_run_retraction_all_job, request.app, job_id)
    return RetractionRunResponse(job_id=job_id, status="pending")


class RetractionLibrarySummary(BaseModel):
    retracted: int = 0  # papers a registry records as retracted — drives the library "N retracted" chip


@router.get("/methods/retraction/summary", response_model=RetractionLibrarySummary)
def retraction_library_summary(conn: Connection = Depends(get_connection)) -> RetractionLibrarySummary:
    return RetractionLibrarySummary(retracted=count_retraction_flagged(conn))


@router.get("/methods/retraction/run/{job_id}", response_model=RetractionRunResponse)
def retraction_run_status(job_id: str, request: Request) -> RetractionRunResponse:
    job = request.app.state.retraction_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Retraction job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return RetractionRunResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_retraction_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[RetractionRunResponse] = app.state.retraction_jobs
    jobs.mark_running(job_id)
    try:
        checkers = app.state.retraction_checkers
        total = checked = flagged = 0
        with app.state.engine.begin() as conn:
            for paper_id in list_live_paper_ids(conn):
                total += 1
                outcome = detect_retraction(conn, get_paper(conn, paper_id), checkers=checkers)
                apply_retraction(conn, paper_id, outcome)
                if outcome.status_kind != "unchecked":
                    checked += 1
                if outcome.merged is not None and outcome.merged.status == "retracted":
                    flagged += 1
        jobs.mark_done(
            job_id,
            RetractionRunResponse(
                job_id=job_id,
                status="done",
                summary=RetractionRunSummary(total=total, checked=checked, flagged=flagged),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


# ── Retraction Watch DB (inc 132): the bulk third source — download the Crossref-hosted RW database (CC0) into a
# local mirror the producer matches DOIs against offline. Public bulk metadata (CALLOSUM_CROSSREF_MAILTO). ──


class RetractionDbStatus(BaseModel):
    count: int = 0
    retrieved_at: str | None = None


class RetractionDbRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    count: int | None = None


@router.get("/methods/retraction/database", response_model=RetractionDbStatus)
def retraction_database(conn: Connection = Depends(get_connection)) -> RetractionDbStatus:
    status = retraction_db_status(conn)
    return RetractionDbStatus(count=status["count"], retrieved_at=status["retrieved_at"])


@router.post(
    "/methods/retraction/database/refresh",
    response_model=RetractionDbRefreshResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def retraction_database_refresh(background_tasks: BackgroundTasks, request: Request) -> RetractionDbRefreshResponse:
    job_id = request.app.state.retraction_db_jobs.create()
    background_tasks.add_task(_run_retraction_db_refresh_job, request.app, job_id)
    return RetractionDbRefreshResponse(job_id=job_id, status="pending")


@router.get("/methods/retraction/database/refresh/{job_id}", response_model=RetractionDbRefreshResponse)
def retraction_database_refresh_status(job_id: str, request: Request) -> RetractionDbRefreshResponse:
    job = request.app.state.retraction_db_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Retraction database refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return RetractionDbRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_retraction_db_refresh_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[RetractionDbRefreshResponse] = app.state.retraction_db_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.begin() as conn:
            count = download_retraction_database(app.state.retraction_watch_client, conn)
        jobs.mark_done(job_id, RetractionDbRefreshResponse(job_id=job_id, status="done", count=count))
    except RetractionWatchUnavailable as exc:
        jobs.mark_error(job_id, str(exc))  # mailto absent / oversize / network — a clear, expected failure
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
