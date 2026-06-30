"""Citation-equity audit (inc 227, backlog #25) — the identity-agnostic structural shape of a paper's reference list.

``POST /methods/citation-equity/run {paper_id}`` (async) resolves a library paper's OpenAlex ``referenced_works``,
fetches each reference's metadata, samples the paper's *field* (its OpenAlex primary topic), and computes 5
**descriptive** structural signals (self-citation, reliance on highly-cited work, venue + institutional
concentration, geographic / Global-South spread) — each shown against the field with an inspectable basis. It is a
*signal, never a verdict* (Principles #2/#7), **identity-agnostic** (no gender/race inference — the gender module is
deferred behind its own gate), and honest about coverage (#6). Egress is **public OpenAlex metadata**, NOT the
Gemini library-text gate; the per-reference + field fetches are cached, so re-runs are cheap.

Own router (3-segment ``/methods/citation-equity/*`` path) — the citation_counts.py precedent. The audit is
ephemeral (the job result), no table/migration: it is recomputable and the OpenAlex calls are cached.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select

from app.backend.acquisition.registry import PaperRef
from app.backend.api.job_store import JobStore
from app.backend.api.routers.papers import _authors_from_csl
from app.backend.methods.citation_equity import audit_reference_list
from app.backend.persistence.schema import papers
from integrations.openalex.adapter import OpenAlexClient

router = APIRouter(tags=["citation-equity"])


class SignalModel(BaseModel):
    key: str
    label: str
    summary: str
    list_pct: float | None = None
    field_pct: float | None = None
    basis: list[str] = []
    coverage: str = ""


class EquityReportModel(BaseModel):
    references_total: int
    references_resolved: int
    field_topic: dict | None = None
    field_sample_size: int = 0
    signals: list[SignalModel] = []


class EquityProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None


class CitationEquityResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: EquityReportModel | None = None
    progress: EquityProgress | None = None


class CitationEquityRequest(BaseModel):
    paper_id: int


def _family(name: str) -> str:
    parts = str(name).strip().split()
    return parts[-1].lower() if parts else ""


@router.post(
    "/methods/citation-equity/run",
    response_model=CitationEquityResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def citation_equity_run(
    body: CitationEquityRequest, background_tasks: BackgroundTasks, request: Request
) -> CitationEquityResponse:
    # Validate synchronously so the client gets a clean 404/422 without polling: the audit needs the paper's DOI
    # to resolve its OpenAlex references.
    with request.app.state.engine.begin() as conn:
        row = conn.execute(select(papers.c.id, papers.c.doi).where(papers.c.id == body.paper_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not row["doi"]:
        raise HTTPException(status_code=422, detail="This paper has no DOI, so OpenAlex can't resolve its references.")
    job_id = request.app.state.citation_equity_jobs.create()
    background_tasks.add_task(_run_citation_equity_job, request.app, job_id, body.paper_id)
    return CitationEquityResponse(job_id=job_id, status="pending")


@router.get("/methods/citation-equity/run/{job_id}", response_model=CitationEquityResponse)
def citation_equity_status(job_id: str, request: Request) -> CitationEquityResponse:
    job = request.app.state.citation_equity_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Citation-equity job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = (
        EquityProgress(
            current=job.progress.current,
            total=job.progress.total,
            label=job.progress.label,
            eta_seconds=job.eta_seconds(),
        )
        if job.progress is not None
        else None
    )
    return CitationEquityResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _run_citation_equity_job(app: FastAPI, job_id: str, paper_id: int) -> None:
    jobs: JobStore[CitationEquityResponse] = app.state.citation_equity_jobs
    jobs.mark_running(job_id)
    client = app.state.openalex_client or OpenAlexClient()
    try:
        with app.state.engine.begin() as conn:
            row = (
                conn.execute(
                    select(papers.c.doi, papers.c.csl_json, papers.c.first_author_family_name).where(
                        papers.c.id == paper_id
                    )
                )
                .mappings()
                .first()
            )
            if row is None or not row["doi"]:
                jobs.mark_error(job_id, "Paper not found or has no DOI.")
                return
            ref = PaperRef(doi=row["doi"])
            families = {
                _family(a) for a in _authors_from_csl(row["csl_json"], fallback=row["first_author_family_name"])
            }
            families = {f for f in families if f}
            ref_ids = client.fetch_referenced_works(conn, ref)
            total = len(ref_ids)
            # The focal paper's primary_topic = the field baseline (read from the now-cached by-DOI fetch, no extra HTTP).
            focal_meta = client.fetch_work_meta_for(conn, ref)
            field_topic = (focal_meta or {}).get("primary_topic")
            refs: list[dict] = []
            for i, wid in enumerate(ref_ids):
                meta = client.fetch_work_meta(
                    conn, wid
                )  # per-ref errors are skipped (counted in coverage), never fatal
                if meta:
                    refs.append(meta)
                jobs.mark_progress(job_id, i + 1, total, "Fetching reference metadata")
            field = client.fetch_field_sample(conn, field_topic["id"]) if field_topic else []
            report = audit_reference_list(
                refs=refs,
                focal_author_families=families,
                field=field,
                field_topic=field_topic,
                references_total=total,
            )
        jobs.mark_done(
            job_id,
            CitationEquityResponse(job_id=job_id, status="done", report=EquityReportModel(**report.to_dict())),
        )
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
