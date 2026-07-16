"""Multi-pass, gap-filling metadata enrichment across the library (inc 217).

Fills each live paper's EMPTY bibliographic fields from a source cascade (Crossref-by-DOI → OpenAlex; SP2 adds
Europe PMC + PubMed), recovering a missing DOI first — never overwriting a value the user typed. Public
bibliographic-metadata egress (the inc-87/183/210 posture), NOT the Gemini library-text gate.

Split out of ``routers/library.py`` (rule #1, 600-line cap) as a sibling router mounted beside ``library.router``
in ``app.py`` — the inc-226 ``paper_enrich.py`` pattern. Reuses ``library``'s shared job-progress helpers
(``JobProgressOut`` / ``_progress_out``) via a one-way import (``library`` does not import this module → no cycle).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select

from app.backend.api.job_store import JobStore
from app.backend.api.routers.library import JobProgressOut, _progress_out
from app.backend.metadata.enrich_sources import build_default_enrich_registry
from app.backend.metadata.enrichment import enrich_paper_metadata_multi
from app.backend.persistence.repository import list_live_paper_ids
from app.backend.persistence.schema import papers
from app.backend.persistence.sqlite_retry import run_write

_log = logging.getLogger("callosum.library_enrich")

router = APIRouter()

_ENRICH_TITLE_MAX = 60


class MetadataEnrichSummary(BaseModel):
    papers: int = 0  # live papers processed
    dois_recovered: int = 0  # papers that had no DOI and gained one (PDF scan / Crossref title-search)
    fields_filled: int = 0  # total empty fields filled across all papers
    still_missing_doi: int = 0  # papers still without a DOI after the pass


class MetadataEnrichResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: MetadataEnrichSummary | None = None
    progress: JobProgressOut | None = None


@router.post(
    "/library/enrich/refresh", response_model=MetadataEnrichResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def enrich_library(background_tasks: BackgroundTasks, request: Request) -> MetadataEnrichResponse:
    job_id = request.app.state.metadata_enrich_jobs.create()
    background_tasks.add_task(_run_metadata_enrich_job, request.app, job_id)
    return MetadataEnrichResponse(job_id=job_id, status="pending")


@router.get("/library/enrich/refresh/{job_id}", response_model=MetadataEnrichResponse)
def enrich_library_status(job_id: str, request: Request) -> MetadataEnrichResponse:
    job = request.app.state.metadata_enrich_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Enrich job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return MetadataEnrichResponse(job_id=job_id, status=job.status, detail=job.detail, progress=_progress_out(job))


def _enrich_progress_label(title: str | None) -> str:
    """Per-item progress label for the metadata-enrich job (#4): show the paper being enriched — like the scan
    job shows each filename — falling back to the generic phase label when a paper has no title yet."""
    text = (title or "").strip()
    if not text:
        return "Enriching metadata"
    if len(text) > _ENRICH_TITLE_MAX:
        text = text[: _ENRICH_TITLE_MAX - 1].rstrip() + "…"
    return f"Enriching {text}"


def _run_metadata_enrich_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[MetadataEnrichResponse] = app.state.metadata_enrich_jobs
    jobs.mark_running(job_id)
    try:
        registry = app.state.enrich_registry or build_default_enrich_registry(
            crossref_client=app.state.crossref_client, openalex_client=app.state.openalex_client
        )
        search_provider = getattr(app.state, "enrich_search_provider", None)
        recovered = filled = missing = 0
        engine = app.state.engine
        with engine.connect() as conn:
            ids = list_live_paper_ids(conn)
            titles = {
                int(row[0]): row[1]
                for row in conn.execute(select(papers.c.id, papers.c.title).where(papers.c.id.in_(ids)))
            }
        total = len(ids)
        # inc B: enrich each paper (external metadata fetch + write) in its OWN committed transaction, so the write
        # lock is released between papers; one paper's hard failure is skipped, never aborting the batch.
        for index, paper_id in enumerate(ids, start=1):
            try:
                result = run_write(
                    engine,
                    lambda conn, pid=paper_id: enrich_paper_metadata_multi(
                        conn, pid, registry=registry, search_provider=search_provider
                    ),
                )
                recovered += 1 if result.doi_recovered else 0
                filled += len(result.filled_fields)
                missing += 1 if result.still_missing_doi else 0
            except Exception as exc:  # noqa: BLE001 — one bad paper never aborts the batch
                _log.warning("metadata enrich: skipped paper %s: %s", paper_id, exc)
            jobs.mark_progress(job_id, index, total, _enrich_progress_label(titles.get(paper_id)))
        jobs.mark_done(
            job_id,
            MetadataEnrichResponse(
                job_id=job_id,
                status="done",
                summary=MetadataEnrichSummary(
                    papers=total, dois_recovered=recovered, fields_filled=filled, still_missing_doi=missing
                ),
            ),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
