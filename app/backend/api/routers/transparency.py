"""Transparency-signals auditor endpoint (backlog #44, inc 250/251).

GET /papers/{id}/transparency — deterministic, local, read-only. Reads the paper's extracted text and returns 7
open-science-disclosure detectors (present / not-found / not-applicable). No score, no verdict; "not-found" ≠ "absent"
(silence≠certificate). No chunks → all detectors run over empty text (the frontend gates the "process a PDF first"
state). Mirrors GET /papers/{id}/meta-analysis.

inc 251 adds the library-wide **persistence** layer (the statcheck inc-97 pattern): POST /methods/transparency/run
batch-runs every live paper, persisting present-disclosure FACTs + per-disclosure check statuses (see
methods/transparency_findings.py); GET /methods/transparency/summary drives the review-queue chip. See
methods/transparency.py (the detector) + methods/transparency_findings.py (the producer).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.engine import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.methods.evidence_anchors import anchor_evidence, pdf_attachment_ids_for_chunks
from app.backend.methods.transparency import detect_transparency
from app.backend.methods.transparency_findings import persist_transparency
from app.backend.persistence.repository import get_chunks_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.signals_repo import count_transparency_review, count_transparency_status
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()
_log = logging.getLogger("callosum.transparency")


class TransparencyCheckOut(BaseModel):
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


class TransparencyResponse(BaseModel):
    checks: list[TransparencyCheckOut]


@router.get("/papers/{paper_id}/transparency", response_model=TransparencyResponse)
def paper_transparency(paper_id: int, conn: Connection = Depends(get_connection)) -> TransparencyResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    chunks = get_chunks_for_paper(conn, paper_id)
    pdf_attachment_ids = pdf_attachment_ids_for_chunks(conn, chunks)
    report = detect_transparency(chunks)
    return TransparencyResponse(
        checks=[
            TransparencyCheckOut(
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


# --- inc 251: the library-wide persistence batch + the review-queue chip -------------------------------------------


class TransparencyRunSummary(BaseModel):
    total: int = 0  # live papers checked
    with_disclosures: int = 0  # papers with ≥1 detected disclosure


class TransparencyRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: TransparencyRunSummary | None = None


class TransparencyLibrarySummary(BaseModel):
    data_detected: int  # papers where data-availability was detected — a positive, checkable evidence signal
    data_not_detected: int  # papers where data-availability wasn't detected — a REVIEW QUEUE count, not a verdict


def _run_transparency_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[TransparencyRunResponse] = app.state.transparency_jobs
    jobs.mark_running(job_id)
    try:
        total = with_disclosures = 0
        engine = app.state.engine
        with engine.connect() as conn:
            paper_ids = list_live_paper_ids(conn)
        # inc C: persist each paper's transparency signals in its own committed transaction — lock released between.
        for i, paper_id in enumerate(paper_ids):
            total += 1
            try:
                result = run_write(
                    engine,
                    lambda conn, pid=paper_id: persist_transparency(conn, pid, get_chunks_for_paper(conn, pid)),
                )
                if result["present"] > 0:
                    with_disclosures += 1
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("transparency batch: skipped paper %s: %s", paper_id, exc)
            jobs.mark_progress(job_id, i + 1, len(paper_ids), "Detecting transparency signals")
        jobs.mark_done(
            job_id,
            TransparencyRunResponse(
                job_id=job_id,
                status="done",
                summary=TransparencyRunSummary(total=total, with_disclosures=with_disclosures),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


@router.post("/methods/transparency/run", response_model=TransparencyRunResponse, status_code=202)
def transparency_run(background_tasks: BackgroundTasks, request: Request) -> TransparencyRunResponse:
    # Batch-detect transparency signals over every live paper (async) — persists present-disclosure FACTs +
    # per-disclosure check statuses; re-running overwrites. Local, no egress, no LLM. NEVER writes an absence as a FACT.
    job_id = request.app.state.transparency_jobs.create()
    background_tasks.add_task(_run_transparency_all_job, request.app, job_id)
    return TransparencyRunResponse(job_id=job_id, status="pending")


@router.get("/methods/transparency/run/{job_id}", response_model=TransparencyRunResponse)
def transparency_run_status(job_id: str, request: Request) -> TransparencyRunResponse:
    job = request.app.state.transparency_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Transparency run job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return TransparencyRunResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/methods/transparency/summary", response_model=TransparencyLibrarySummary)
def transparency_library_summary(conn: Connection = Depends(get_connection)) -> TransparencyLibrarySummary:
    # Drives the Library-header Open Data chip with the positive detected signal. Keep the not-detected review count
    # available for the transparency panel; it is still only a "go look" queue, never "papers that hide their data."
    return TransparencyLibrarySummary(
        data_detected=count_transparency_status(conn, "data_availability", "detected"),
        data_not_detected=count_transparency_review(conn, "data_availability"),
    )
