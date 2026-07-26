"""Meta-analysis reporting auditor endpoint (backlog #36, inc 249; #23 F1/F4 chip + persistence, inc 337).

GET /papers/{id}/meta-analysis — deterministic, local, read-only READ, with a persistence SIDE EFFECT (F4):
every call also upserts the #23 signal + (when incomplete) a review-queue candidate, via
`methods.metaanalysis.apply_meta_analysis` — mirrors `routers/lmm.py`. No chunks → an honest
is_meta_analysis:false, nothing persisted. Mirrors GET /papers/{id}/lmm and /bayes.

POST /methods/meta-analysis/run (async) batch-checks the whole live library. `GET /methods/meta-analysis/summary`
backs the library header chip; `GET /papers?signal=meta-incomplete` filters to flagged papers.
See methods/metaanalysis.py.
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
from app.backend.methods.metaanalysis import apply_meta_analysis, audit_meta_analysis
from app.backend.persistence.repository import get_chunks_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.signals_repo import count_meta_flagged
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()
_log = logging.getLogger("callosum.methods")


class MetaCheckOut(BaseModel):
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


class MetaResponse(BaseModel):
    is_meta_analysis: bool
    checks: list[MetaCheckOut]


@router.get("/papers/{paper_id}/meta-analysis", response_model=MetaResponse)
def paper_meta_analysis(paper_id: int, request: Request, conn: Connection = Depends(get_connection)) -> MetaResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    chunks = get_chunks_for_paper(conn, paper_id)
    pdf_attachment_ids = pdf_attachment_ids_for_chunks(conn, chunks)
    report = audit_meta_analysis(chunks)
    response = MetaResponse(
        is_meta_analysis=report.is_meta_analysis,
        checks=[
            MetaCheckOut(
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
    run_write(request.app.state.engine, lambda c: apply_meta_analysis(c, paper_id, report))
    return response


# ── library-wide batch (backlog #23 F1): persist a per-paper summary so the library can be filtered/chip-counted ──


class MetaRunSummary(BaseModel):
    total: int = 0  # live papers
    detected: int = 0  # papers detectably a meta-analysis
    incomplete: int = 0  # detected papers with ≥1 reporting gap


class MetaRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: MetaRunSummary | None = None


@router.post("/methods/meta-analysis/run", response_model=MetaRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def meta_analysis_run(background_tasks: BackgroundTasks, request: Request) -> MetaRunResponse:
    job_id = request.app.state.meta_jobs.create()
    background_tasks.add_task(_run_meta_all_job, request.app, job_id)
    return MetaRunResponse(job_id=job_id, status="pending")


class MetaLibrarySummary(BaseModel):
    incomplete: int = 0  # papers a batch run (or an ad-hoc view) flagged — drives the library "N incomplete" chip


@router.get("/methods/meta-analysis/summary", response_model=MetaLibrarySummary)
def meta_analysis_library_summary(conn: Connection = Depends(get_connection)) -> MetaLibrarySummary:
    return MetaLibrarySummary(incomplete=count_meta_flagged(conn))


@router.get("/methods/meta-analysis/run/{job_id}", response_model=MetaRunResponse)
def meta_analysis_run_status(job_id: str, request: Request) -> MetaRunResponse:
    job = request.app.state.meta_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Meta-analysis job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return MetaRunResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_meta_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[MetaRunResponse] = app.state.meta_jobs
    jobs.mark_running(job_id)
    try:
        total = detected = incomplete = 0
        engine = app.state.engine
        with engine.connect() as conn:
            ids = list_live_paper_ids(conn)

        def process(conn, paper_id):  # one committed transaction per paper — lock released between papers
            report = audit_meta_analysis(get_chunks_for_paper(conn, paper_id))
            apply_meta_analysis(conn, paper_id, report)
            return report

        for paper_id in ids:
            total += 1
            try:
                report = run_write(engine, lambda conn, pid=paper_id: process(conn, pid))
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("meta-analysis batch: skipped paper %s: %s", paper_id, exc)
                continue
            if report.is_meta_analysis:
                detected += 1
                if any(c.status == "not-found" for c in report.checks):
                    incomplete += 1
        jobs.mark_done(
            job_id,
            MetaRunResponse(
                job_id=job_id,
                status="done",
                summary=MetaRunSummary(total=total, detected=detected, incomplete=incomplete),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
