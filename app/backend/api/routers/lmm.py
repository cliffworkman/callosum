"""LMM-reporting completeness auditor endpoint (backlog #23, inc 247; #23 F1/F4 chip + persistence, inc 336).

GET /papers/{id}/lmm — deterministic, local, read-only READ, with a persistence SIDE EFFECT (F4): every call
also upserts the #23 signal + (when incomplete) a review-queue candidate, via `methods.lmm.apply_lmm` — so simply
viewing a paper's LMM panel keeps the library-wide chip/filter current without requiring the batch below first.
No chunks → an honest is_lmm:false, and nothing persisted (not a mixed-model paper by construction). Mirrors
GET /papers/{id}/bayes and /statcheck.

POST /methods/lmm/run (async) batch-checks the whole live library — the same `apply_lmm` shared with the
ad-hoc path — so the count is complete even for papers nobody has opened yet. `GET /methods/lmm/summary` backs
the library header chip; `GET /papers?signal=lmm-incomplete` filters to flagged papers. See methods/lmm.py.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.engine import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.methods.evidence_anchors import anchor_evidence, pdf_attachment_ids_for_chunks
from app.backend.methods.lmm import apply_lmm, audit_lmm
from app.backend.persistence.repository import get_chunks_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.signals_repo import count_lmm_flagged
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()
_log = logging.getLogger("callosum.methods")


class LmmCheckOut(BaseModel):
    key: str
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None = None
    page: int | None = None
    page_end: int | None = None
    coordinate_precision: str | None = None
    bbox_json: Any | None = None
    attachment_id: int | None = None
    note: str | None = None
    explainer: str
    basis: str


class LmmResponse(BaseModel):
    is_lmm: bool  # the checklist runs only on a paper that detectably uses a mixed model
    checks: list[LmmCheckOut]


@router.get("/papers/{paper_id}/lmm", response_model=LmmResponse)
def paper_lmm(paper_id: int, request: Request, conn: Connection = Depends(get_connection)) -> LmmResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    chunks = get_chunks_for_paper(conn, paper_id)
    pdf_attachment_ids = pdf_attachment_ids_for_chunks(conn, chunks)
    report = audit_lmm(chunks)
    response = LmmResponse(
        is_lmm=report.is_lmm,
        checks=[
            LmmCheckOut(
                key=c.key,
                label=c.label,
                status=c.status,
                evidence=c.evidence,
                page=c.page,
                **anchor_evidence(conn, chunks, c.evidence, c.page, pdf_attachment_ids=pdf_attachment_ids),
                note=c.note,
                explainer=c.explainer,
                basis=c.basis,
            )
            for c in report.checks
        ],
    )
    run_write(request.app.state.engine, lambda c: apply_lmm(c, paper_id, report))
    return response


# ── library-wide batch (backlog #23 F1): persist a per-paper summary so the library can be filtered/chip-counted ──


class LmmRunSummary(BaseModel):
    total: int = 0  # live papers
    detected: int = 0  # papers detectably using a mixed model
    incomplete: int = 0  # detected papers with ≥1 reporting gap


class LmmRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: LmmRunSummary | None = None


@router.post("/methods/lmm/run", response_model=LmmRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def lmm_run(background_tasks: BackgroundTasks, request: Request) -> LmmRunResponse:
    job_id = request.app.state.lmm_jobs.create()
    background_tasks.add_task(_run_lmm_all_job, request.app, job_id)
    return LmmRunResponse(job_id=job_id, status="pending")


class LmmLibrarySummary(BaseModel):
    incomplete: int = 0  # papers a batch run (or an ad-hoc view) flagged — drives the library "N incomplete" chip


@router.get("/methods/lmm/summary", response_model=LmmLibrarySummary)
def lmm_library_summary(conn: Connection = Depends(get_connection)) -> LmmLibrarySummary:
    return LmmLibrarySummary(incomplete=count_lmm_flagged(conn))


@router.get("/methods/lmm/run/{job_id}", response_model=LmmRunResponse)
def lmm_run_status(job_id: str, request: Request) -> LmmRunResponse:
    job = request.app.state.lmm_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="LMM job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return LmmRunResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_lmm_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[LmmRunResponse] = app.state.lmm_jobs
    jobs.mark_running(job_id)
    try:
        total = detected = incomplete = 0
        engine = app.state.engine
        with engine.connect() as conn:
            ids = list_live_paper_ids(conn)

        def process(conn, paper_id):  # one committed transaction per paper — lock released between papers
            report = audit_lmm(get_chunks_for_paper(conn, paper_id))
            apply_lmm(conn, paper_id, report)
            return report

        for paper_id in ids:
            total += 1
            try:
                report = run_write(engine, lambda conn, pid=paper_id: process(conn, pid))
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("lmm batch: skipped paper %s: %s", paper_id, exc)
                continue
            if report.is_lmm:
                detected += 1
                if any(c.status == "not-found" for c in report.checks):
                    incomplete += 1
        jobs.mark_done(
            job_id,
            LmmRunResponse(
                job_id=job_id,
                status="done",
                summary=LmmRunSummary(total=total, detected=detected, incomplete=incomplete),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
