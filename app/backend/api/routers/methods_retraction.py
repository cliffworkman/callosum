"""Retraction findings producers (inc 131–132).

Split out of ``methods.py`` (inc 261) to keep it under the 600-line cap (rule #1). The retraction concern is a
self-contained cluster: per-DOI detection (Crossref + OpenAlex) + the bulk Retraction Watch DB mirror. It shares
the app state set up in ``api/app.py`` (``retraction_jobs`` / ``retraction_db_jobs`` / ``retraction_checkers`` /
``retraction_watch_client``); the router is mounted there beside ``methods.router``.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.methods.retraction import (
    RetractionOutcome,
    apply_retraction,
    detect_retraction,
    is_evidence_linked_correction,
)
from app.backend.persistence.repository import get_paper, list_live_paper_ids
from app.backend.persistence.retraction_repo import retraction_db_status
from app.backend.persistence.signals_repo import count_retraction_flagged, get_retraction_status
from app.backend.persistence.sqlite_retry import run_write
from integrations.retraction_watch.adapter import RetractionWatchUnavailable, download_retraction_database

MAX_CHECK_SELECTED = 100  # bounds a synchronous request -- mirrors reference_integrity.py's 200-cap precedent,
# smaller here since this checks papers cited in ONE manuscript, not a user-chosen library batch

router = APIRouter()
_log = logging.getLogger("callosum.methods_retraction")


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


class RetractionCheckSelectedRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1, max_length=MAX_CHECK_SELECTED)


class RetractionCheckSelectedItem(BaseModel):
    paper_id: int
    status: str  # retracted/correction/concern (flagged) | none (checked-clean) | unchecked (no DOI)
    nature: str | None = None
    date: str | None = None
    notice_url: str | None = None
    sources: list[str] = []


class RetractionCheckSelectedResponse(BaseModel):
    requested_count: int
    checked: list[RetractionCheckSelectedItem] = []
    not_found: list[int] = []


@router.post("/methods/retraction/check-selected", response_model=RetractionCheckSelectedResponse)
def retraction_check_selected(
    body: RetractionCheckSelectedRequest, request: Request
) -> RetractionCheckSelectedResponse:
    # A scoped, synchronous, on-demand re-check for exactly the papers a caller names -- e.g. the LibreOffice
    # adapter's citation-integrity preflight, checking just the papers cited in the open manuscript, right now,
    # rather than waiting on (or forcing) a whole-library POST /methods/retraction/run pass. Reuses the exact
    # same two calls the whole-library batch job makes (detect_retraction + apply_retraction via run_write), so
    # a fresh check here also persists -- GET /papers/{paper_id}/retraction benefits from it too, for free.
    ids = _unique_positive_ids(body.paper_ids)[:MAX_CHECK_SELECTED]
    checkers = request.app.state.retraction_checkers
    engine = request.app.state.engine
    checked: list[RetractionCheckSelectedItem] = []
    not_found: list[int] = []
    for paper_id in ids:
        try:
            outcome = run_write(engine, lambda conn, pid=paper_id: _check_and_persist(conn, pid, checkers))
        except NoResultFound:
            not_found.append(paper_id)
            continue
        merged = outcome.merged
        checked.append(
            RetractionCheckSelectedItem(
                paper_id=paper_id,
                status=outcome.status_kind,
                nature=merged.nature if merged else None,
                date=merged.date if merged else None,
                notice_url=merged.notice_url if merged else None,
                sources=(merged.sources if merged else outcome.sources_checked),
            )
        )
    return RetractionCheckSelectedResponse(requested_count=len(body.paper_ids), checked=checked, not_found=not_found)


def _check_and_persist(conn: Connection, paper_id: int, checkers: list) -> RetractionOutcome:
    outcome = detect_retraction(conn, get_paper(conn, paper_id), checkers=checkers)
    apply_retraction(conn, paper_id, outcome)
    return outcome


def _unique_positive_ids(values: list[int]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for value in values or []:
        try:
            pid = int(value)
        except (TypeError, ValueError):
            continue
        if pid > 0 and pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


class RetractionRunSummary(BaseModel):
    total: int = 0  # live papers
    checked: int = 0  # papers that had a DOI to check
    flagged: int = 0  # papers a registry records as retracted
    corrections: int = 0  # papers carrying an explicit correction record (positive self-correction signal)
    database_records: int | None = None  # Retraction Watch rows refreshed before the run, when available
    database_refresh_error: str | None = None  # refresh failed; batch continued against the existing mirror


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
        total = checked = flagged = corrections = 0
        engine = app.state.engine
        database_records: int | None = None
        database_refresh_error: str | None = None
        try:
            with engine.begin() as conn:
                database_records = download_retraction_database(app.state.retraction_watch_client, conn)
        except RetractionWatchUnavailable as exc:
            database_refresh_error = str(exc)
            _log.info("retraction batch: Retraction Watch refresh unavailable; using existing mirror: %s", exc)
        except Exception as exc:  # noqa: BLE001 — a stale/offline mirror must not abort the DOI check
            database_refresh_error = f"{type(exc).__name__}: {exc}"
            _log.warning("retraction batch: Retraction Watch refresh failed; using existing mirror: %s", exc)

        with engine.connect() as conn:
            ids = list_live_paper_ids(conn)

        def process(conn, paper_id):  # inc C: per-paper committed txn — the external DOI check no longer holds a
            outcome = detect_retraction(conn, get_paper(conn, paper_id), checkers=checkers)  # batch-wide write lock
            apply_retraction(conn, paper_id, outcome)
            return outcome

        for paper_id in ids:
            total += 1
            try:
                outcome = run_write(engine, lambda conn, pid=paper_id: process(conn, pid))
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("retraction batch: skipped paper %s: %s", paper_id, exc)
                jobs.mark_progress(job_id, total, len(ids), "Checking retractions")
                continue
            jobs.mark_progress(job_id, total, len(ids), "Checking retractions")
            if outcome.status_kind != "unchecked":
                checked += 1
            if outcome.merged is not None and outcome.merged.status == "retracted":
                flagged += 1
            if is_evidence_linked_correction(outcome):
                corrections += 1
        jobs.mark_done(
            job_id,
            RetractionRunResponse(
                job_id=job_id,
                status="done",
                detail=(
                    f"Retraction Watch refresh failed; used existing mirror: {database_refresh_error}"
                    if database_refresh_error
                    else None
                ),
                summary=RetractionRunSummary(
                    total=total,
                    checked=checked,
                    flagged=flagged,
                    corrections=corrections,
                    database_records=database_records,
                    database_refresh_error=database_refresh_error,
                ),
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
