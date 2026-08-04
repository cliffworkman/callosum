"""Citation concentration for a WIP manuscript's linked Library references (backlog #48).

Reuses `audit_reference_list` (the Library-paper citation-concentration pure function) completely unmodified.
Unlike a Library paper, a WIP manuscript has no DOI and no OpenAlex record of its own, so there is no
`referenced_works` graph traversal and no focal-paper metadata to draw a field-topic comparison from -- the
reference list is already known locally via `wip_references` ("cited" rows), and `focal_author_families`/
`field`/`field_topic` are passed as their honest empty/absent values, which `audit_reference_list` already
degrades gracefully for (no fabricated author identity or field-topic proxy -- Principles #6). Fully
ephemeral, like the Library-paper version: no dedicated table, no migration.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select

from app.backend.acquisition.registry import PaperRef
from app.backend.api.job_store import JobStore
from app.backend.api.routers.citation_equity import EquityProgress, EquityReportModel
from app.backend.api.wip_security import require_local_wip
from app.backend.methods.citation_equity import audit_reference_list
from app.backend.persistence.schema import papers
from app.backend.persistence.schema_wip_workflow import wip_references
from app.backend.persistence.wip_repo import get_manuscript
from integrations.openalex.adapter import OpenAlexClient

router = APIRouter(prefix="/wip", dependencies=[Depends(require_local_wip)])


class WipCitationEquityResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: EquityReportModel | None = None
    progress: EquityProgress | None = None


@router.post(
    "/manuscripts/{manuscript_id}/citation-equity/run",
    response_model=WipCitationEquityResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def wip_citation_equity_run(
    manuscript_id: int, background_tasks: BackgroundTasks, request: Request
) -> WipCitationEquityResponse:
    with request.app.state.engine.begin() as conn:
        if get_manuscript(conn, manuscript_id) is None:
            raise HTTPException(status_code=404, detail="WIP manuscript not found")
    job_id = request.app.state.wip_citation_equity_jobs.create(nav={"manuscript_id": manuscript_id})
    background_tasks.add_task(_run_wip_citation_equity_job, request.app, job_id, manuscript_id)
    return WipCitationEquityResponse(job_id=job_id, status="pending")


@router.get("/citation-equity/run/{job_id}", response_model=WipCitationEquityResponse)
def wip_citation_equity_status(job_id: str, request: Request) -> WipCitationEquityResponse:
    job = request.app.state.wip_citation_equity_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="WIP citation-equity job not found")
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
    return WipCitationEquityResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


def _run_wip_citation_equity_job(app: FastAPI, job_id: str, manuscript_id: int) -> None:
    jobs: JobStore[WipCitationEquityResponse] = app.state.wip_citation_equity_jobs
    jobs.mark_running(job_id)
    client = app.state.openalex_client or OpenAlexClient()
    try:
        with app.state.engine.begin() as conn:
            cited_rows = list(
                conn.execute(
                    select(papers.c.id, papers.c.doi, papers.c.title)
                    .select_from(wip_references.join(papers, papers.c.id == wip_references.c.paper_id))
                    .where(
                        wip_references.c.manuscript_id == manuscript_id,
                        wip_references.c.relationship_state == "cited",
                    )
                ).mappings()
            )
            total = len(cited_rows)
            refs: list[dict] = []
            for i, row in enumerate(cited_rows):
                ref = PaperRef(doi=row["doi"]) if row["doi"] else PaperRef(title=row["title"])
                meta = client.fetch_work_meta_for(conn, ref)  # per-reference errors skipped, never fatal
                if meta:
                    refs.append(meta)
                jobs.mark_progress(job_id, i + 1, total, "Fetching reference metadata")
            report = audit_reference_list(
                refs=refs,
                focal_author_families=set(),  # WIP manuscripts have no stored author identity -- honest empty
                field=[],  # no manuscript-of-its-own OpenAlex record to draw a field comparison from
                field_topic=None,
                references_total=total,
            )
        jobs.mark_done(
            job_id,
            WipCitationEquityResponse(job_id=job_id, status="done", report=EquityReportModel(**report.to_dict())),
        )
    except Exception as exc:  # noqa: BLE001
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
