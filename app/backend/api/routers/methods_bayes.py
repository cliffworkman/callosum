"""Bayesian auditor endpoint (inc 241-244; split from methods.py + #23 F1/F4 chip + persistence, inc 338).

GET /papers/{id}/bayes — deterministic, local, read-only READ, with a persistence SIDE EFFECT (F4): every call
also upserts the #23 signal + (when flagged) a review-queue candidate, via `methods.bayes.apply_bayes` — mirrors
`routers/lmm.py`/`routers/metaanalysis.py`. No chunks / not detectably Bayesian → nothing persisted.

Unlike LMM/meta-analysis, Bayes has TWO independent signal sources from one auditor: `not_reproduced` (a BF
recompute mismatch, statcheck-like) and the Tier-2 completeness checklist (`is_bayesian`/`items`, LMM-like).
`apply_bayes` combines them into ONE "flagged" status — see methods/bayes.py for the combination rule.

POST /methods/bayes/run (async) batch-checks the whole live library. `GET /methods/bayes/summary` backs the
library header chip; `GET /papers?signal=bayes-flagged` filters to flagged papers. See methods/bayes.py.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.methods.bayes import DEFAULT_R, apply_bayes, audit_completeness, run_bayes
from app.backend.methods.evidence_anchors import anchor_evidence, pdf_attachment_ids_for_chunks
from app.backend.persistence.document_roles import ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES
from app.backend.persistence.repository import get_chunks_for_paper, get_paper, list_live_paper_ids
from app.backend.persistence.signals_repo import count_bayes_flagged
from app.backend.persistence.sqlite_retry import run_write

router = APIRouter()
_log = logging.getLogger("callosum.methods")


class BayesResult(BaseModel):
    raw: str
    reported_bf10: float
    computed_paired: float | None = None
    computed_two_sample: float | None = None
    computed_correlation: float | None = None
    consistency: str  # reproduced | not-reproduced
    matched_design: str | None = None
    page: int | None = None
    page_end: int | None = None
    coordinate_precision: str | None = None
    bbox_json: Any | None = None
    attachment_id: int | None = None


class BayesCompletenessItem(BaseModel):
    key: str  # prior | convergence | sensitivity
    label: str
    status: str  # present | not-found | not-applicable | coherence-flag
    evidence: str | None = None
    page: int | None = None
    page_end: int | None = None
    coordinate_precision: str | None = None
    bbox_json: Any | None = None
    attachment_id: int | None = None
    note: str | None = None


class BayesAdvisoryNote(BaseModel):
    key: str  # credible-confidence | bf-direction
    label: str
    note: str
    evidence: str | None = None
    page: int | None = None
    page_end: int | None = None
    coordinate_precision: str | None = None
    bbox_json: Any | None = None
    attachment_id: int | None = None


class BayesCompletenessOut(BaseModel):
    is_bayesian: bool  # the checklist runs only on a paper that detectably does Bayesian analysis
    items: list[BayesCompletenessItem]
    advisories: list[BayesAdvisoryNote] = []  # SP4: Tier-3 advisory prompts (requires expert judgment)


class BayesResponse(BaseModel):
    checked: int
    not_reproduced: int
    prior_scale: float  # the assumed default JZS prior scale (r ≈ 0.707), shown for inspectability
    results: list[BayesResult]
    completeness: BayesCompletenessOut  # SP2: the Tier-2 BARG/WAMBS/JASP reporting checklist


@router.get("/papers/{paper_id}/bayes", response_model=BayesResponse)
def paper_bayes(paper_id: int, request: Request, conn: Connection = Depends(get_connection)) -> BayesResponse:
    # Deterministic, local recompute of default JZS Bayes factors + a Tier-2 completeness checklist over the paper's
    # extracted text. No chunks → checked: 0, an honest "no extractable text" — never an error.
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES)
    pdf_attachment_ids = pdf_attachment_ids_for_chunks(conn, chunks)
    report = run_bayes(chunks)
    completeness = audit_completeness(chunks)
    response = BayesResponse(
        checked=report.checked,
        not_reproduced=report.not_reproduced,
        prior_scale=round(DEFAULT_R, 4),
        results=[
            BayesResult(
                raw=r.raw,
                reported_bf10=r.reported_bf10,
                computed_paired=r.computed_paired,
                computed_two_sample=r.computed_two_sample,
                computed_correlation=r.computed_correlation,
                consistency=r.consistency,
                matched_design=r.matched_design,
                page=r.page,
                **anchor_evidence(conn, chunks, r.raw, r.page, pdf_attachment_ids=pdf_attachment_ids),
            )
            for r in report.results
        ],
        completeness=BayesCompletenessOut(
            is_bayesian=completeness.is_bayesian,
            items=[
                BayesCompletenessItem(
                    key=i.key,
                    label=i.label,
                    status=i.status,
                    evidence=i.evidence,
                    page=i.page,
                    note=i.note,
                    **anchor_evidence(conn, chunks, i.evidence, i.page, pdf_attachment_ids=pdf_attachment_ids),
                )
                for i in completeness.items
            ],
            advisories=[
                BayesAdvisoryNote(
                    key=a.key,
                    label=a.label,
                    note=a.note,
                    evidence=a.evidence,
                    page=a.page,
                    **anchor_evidence(conn, chunks, a.evidence, a.page, pdf_attachment_ids=pdf_attachment_ids),
                )
                for a in completeness.advisories
            ],
        ),
    )
    run_write(request.app.state.engine, lambda c: apply_bayes(c, paper_id, report, completeness))
    return response


# ── library-wide batch (backlog #23 F1): persist a per-paper summary so the library can be filtered/chip-counted ──


class BayesRunSummary(BaseModel):
    total: int = 0  # live papers
    detected: int = 0  # papers detectably doing Bayesian analysis
    flagged: int = 0  # detected papers with ≥1 BF mismatch or reporting gap


class BayesRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: BayesRunSummary | None = None


@router.post("/methods/bayes/run", response_model=BayesRunResponse, status_code=http_status.HTTP_202_ACCEPTED)
def bayes_run(background_tasks: BackgroundTasks, request: Request) -> BayesRunResponse:
    job_id = request.app.state.bayes_jobs.create()
    background_tasks.add_task(_run_bayes_all_job, request.app, job_id)
    return BayesRunResponse(job_id=job_id, status="pending")


class BayesLibrarySummary(BaseModel):
    flagged: int = 0  # papers a batch run (or an ad-hoc view) flagged — drives the library "N flagged" chip


@router.get("/methods/bayes/summary", response_model=BayesLibrarySummary)
def bayes_library_summary(conn: Connection = Depends(get_connection)) -> BayesLibrarySummary:
    return BayesLibrarySummary(flagged=count_bayes_flagged(conn))


@router.get("/methods/bayes/run/{job_id}", response_model=BayesRunResponse)
def bayes_run_status(job_id: str, request: Request) -> BayesRunResponse:
    job = request.app.state.bayes_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Bayes job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return BayesRunResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_bayes_all_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[BayesRunResponse] = app.state.bayes_jobs
    jobs.mark_running(job_id)
    try:
        total = detected = flagged = 0
        engine = app.state.engine
        with engine.connect() as conn:
            ids = list_live_paper_ids(conn)

        def process(conn, paper_id):  # one committed transaction per paper — lock released between papers
            chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES)
            report = run_bayes(chunks)
            completeness = audit_completeness(chunks)
            apply_bayes(conn, paper_id, report, completeness)
            return report, completeness

        for paper_id in ids:
            total += 1
            try:
                report, completeness = run_write(engine, lambda conn, pid=paper_id: process(conn, pid))
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("bayes batch: skipped paper %s: %s", paper_id, exc)
                continue
            if completeness.is_bayesian:
                detected += 1
                gap = any(i.status in ("not-found", "coherence-flag") for i in completeness.items)
                if report.not_reproduced > 0 or gap:
                    flagged += 1
        jobs.mark_done(
            job_id,
            BayesRunResponse(
                job_id=job_id,
                status="done",
                summary=BayesRunSummary(total=total, detected=detected, flagged=flagged),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
