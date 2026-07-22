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

import logging
from copy import deepcopy
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.methods.effectsize import convert as convert_effect_size
from app.backend.methods.grim import grim_test, grimmer_test
from app.backend.methods.pcurve import PcurveResult, run_pcurve
from app.backend.methods.statcheck import run_statcheck
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.persistence.findings_repo import upsert_findings
from app.backend.persistence.repository import get_chunks_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.signals_repo import count_statcheck_flagged, store_statcheck
from app.backend.persistence.sqlite_retry import run_write

MAX_PCURVE_PAPERS = 1000  # bound the selection a p-curve runs over (rule #4)

router = APIRouter()
_log = logging.getLogger("callosum.methods")


class StatcheckResult(BaseModel):
    raw: str
    context: str | None = None
    test_type: str
    reported_p: str
    computed_p: float
    consistency: str  # consistent | inconsistent | decision-error
    page: int | None = None
    page_end: int | None = None
    section: str | None = None
    coordinate_precision: str | None = None
    bbox_json: Any | None = None


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
        results=[StatcheckResult(**_statcheck_result_payload(conn, r)) for r in report.results],
    )


def _stamp_coordinate_precision(bbox_json: Any | None, precision: str) -> Any | None:
    if bbox_json is None:
        return None
    copied = deepcopy(bbox_json)
    if isinstance(copied, list):
        return [{**item, "coordinate_precision": precision} if isinstance(item, dict) else item for item in copied]
    if isinstance(copied, dict):
        return {**copied, "coordinate_precision": precision}
    return copied


def _statcheck_result_payload(conn: Connection, result) -> dict[str, Any]:
    page = result.page
    page_end = result.page_end or result.page
    precision = "region" if page is not None else None
    bbox_json = _stamp_coordinate_precision(result.chunk_bbox_json, "region") if precision == "region" else None
    if result.attachment_id is not None and page is not None:
        try:
            match = locate_quote_for_attachment(conn, int(result.attachment_id), result.raw)
        except Exception:
            match = None
        if match and match.found and match.rectangles:
            located_pages = {
                int(rect["page"]) for rect in match.rectangles if isinstance(rect, dict) and rect.get("page")
            }
            expected_pages = set(range(int(page), int(page_end or page) + 1))
            if located_pages & expected_pages:
                precision = "exact"
                page = match.page_start or page
                page_end = match.page_end or page_end
                bbox_json = _stamp_coordinate_precision(list(match.rectangles), "exact")
    return {
        "raw": result.raw,
        "context": result.context,
        "test_type": result.test_type,
        "reported_p": result.reported_p,
        "computed_p": result.computed_p,
        "consistency": result.consistency,
        "page": page,
        "page_end": page_end,
        "section": result.section,
        "coordinate_precision": precision,
        "bbox_json": bbox_json,
    }


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


# ── effect-size converter (inc 252, meta-analysis workbench SP1): convert ONE study's stats → a common metric ──


class EffectSizeRequest(BaseModel):
    # family ∈ smd / sd_derivation / correlation / binary / cross; inputs is family-specific (validated in the module).
    family: Literal["smd", "sd_derivation", "correlation", "binary", "cross"]
    inputs: dict


class EffectSizeResponse(BaseModel):
    metric: str
    value: float
    variance: float
    se: float
    ci_low: float
    ci_high: float
    path: list[str]
    formula_source: str
    caveats: list[str]
    choices: list[str]


@router.post("/methods/effect-size", response_model=EffectSizeResponse)
def effect_size_convert(payload: EffectSizeRequest) -> EffectSizeResponse:
    # Deterministic, stateless, local — no DB, no egress, no LLM. Converts one study at a time (never pools/models).
    try:
        result = convert_effect_size(payload.family, payload.inputs)
    except (ValueError, KeyError, TypeError, ArithmeticError):
        raise HTTPException(
            status_code=422,
            detail="Invalid effect-size inputs for this family (check the required numeric fields).",
        ) from None
    return EffectSizeResponse(**result.to_dict())


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
        engine = app.state.engine
        with engine.connect() as conn:
            ids = list_live_paper_ids(conn)

        def process(conn, paper_id):  # inc C: one committed transaction per paper — lock released between papers
            report = run_statcheck(get_chunks_for_paper(conn, paper_id))
            store_statcheck(
                conn,
                paper_id,
                checked=report.checked,
                inconsistent=report.inconsistent,
                decision_errors=report.decision_errors,
            )
            # inc 133: also emit a CANDIDATE finding for the unified review queue (a prompt to look, reviewable —
            # coexists with the signal above, which is the persistent fact). Clean → supersede any prior one.
            flagged_n = report.inconsistent + report.decision_errors
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
            return report

        for paper_id in ids:
            total += 1
            try:
                report = run_write(engine, lambda conn, pid=paper_id: process(conn, pid))
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("statcheck batch: skipped paper %s: %s", paper_id, exc)
                continue
            if report.checked > 0:
                checked += 1
            if report.inconsistent + report.decision_errors > 0:
                flagged += 1
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
