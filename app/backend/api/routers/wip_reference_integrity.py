"""Reference-integrity signals for a WIP manuscript's linked Library references (backlog #48).

Reuses `inspect_reference` (the Library-paper Meta Reference List's pure detector) completely unmodified.
Unlike the Library-paper path, the reference list is not *discovered* via Semantic Scholar/OpenAlex from a
citing DOI -- it is already known locally via `wip_references` ("cited" rows, each already a real, DOI'd
Library `papers` row) -- so this never calls the reference-discovery clients, only the same verification/
retraction/propagation machinery Library reference-integrity already uses.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select

from app.backend.api.job_store import JobStore
from app.backend.api.routers.papers import _authors_from_csl
from app.backend.api.wip_security import require_local_wip
from app.backend.methods.reference_integrity import (
    ReferenceCandidate,
    entity_key,
    inspect_reference,
    propagation_signal,
)
from app.backend.persistence.reference_integrity_repo import flagged_sources_for_entity
from app.backend.persistence.retraction_repo import retraction_db_status
from app.backend.persistence.schema import papers
from app.backend.persistence.schema_reference_integrity import reference_entities
from app.backend.persistence.schema_wip_reference_integrity import wip_reference_signals
from app.backend.persistence.schema_wip_workflow import wip_references
from app.backend.persistence.sqlite_retry import run_write
from app.backend.persistence.wip_reference_integrity_repo import (
    manuscript_reference_report,
    replace_reference_signals,
    set_reference_review_state,
)
from app.backend.persistence.wip_repo import add_activity, get_manuscript
from app.backend.usage import record_event
from integrations.crossref.adapter import CrossrefClient
from integrations.openalex.adapter import OpenAlexClient

router = APIRouter(prefix="/wip", dependencies=[Depends(require_local_wip)])


class WipReferenceSignalModel(BaseModel):
    id: int
    detector_kind: str
    detector_status: str
    evidence: dict
    source: str
    snapshot_marker: str
    detected_at: str | None = None


class WipReferenceItemModel(BaseModel):
    id: int
    paper_id: int
    paper_title: str | None = None
    paper_year: int | None = None
    doi: str | None = None
    review_state: str
    reviewed_at: str | None = None
    signal_fingerprint: str | None = None
    signals: list[WipReferenceSignalModel] = []


class WipReferenceReportModel(BaseModel):
    manuscript_id: int
    active_count: int
    checked_count: int = 0
    last_checked_at: str | None = None
    provider_statuses: list[dict[str, Any]] = []
    items: list[WipReferenceItemModel] = []


class WipReferenceRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: WipReferenceReportModel | None = None


class WipReferenceReviewRequest(BaseModel):
    state: Literal["dismissed", "confirmed_problem"]


@router.get("/manuscripts/{manuscript_id}/reference-integrity", response_model=WipReferenceReportModel)
def wip_reference_integrity_get(manuscript_id: int, request: Request) -> WipReferenceReportModel:
    with request.app.state.engine.begin() as conn:
        _require_manuscript(conn, manuscript_id)
        return WipReferenceReportModel(**manuscript_reference_report(conn, manuscript_id))


@router.post(
    "/manuscripts/{manuscript_id}/reference-integrity/run",
    response_model=WipReferenceRunResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def wip_reference_integrity_run(
    manuscript_id: int, background_tasks: BackgroundTasks, request: Request
) -> WipReferenceRunResponse:
    with request.app.state.engine.begin() as conn:
        _require_manuscript(conn, manuscript_id)
    job_id = request.app.state.wip_reference_integrity_jobs.create(nav={"manuscript_id": manuscript_id})
    run_write(
        request.app.state.engine,
        lambda conn: add_activity(conn, manuscript_id, "tool-run-started", "Started WIP reference-integrity scan"),
    )
    background_tasks.add_task(_run_wip_reference_integrity_job, request.app, job_id, manuscript_id)
    return WipReferenceRunResponse(job_id=job_id, status="pending")


@router.get("/reference-integrity/run/{job_id}", response_model=WipReferenceRunResponse)
def wip_reference_integrity_run_status(job_id: str, request: Request) -> WipReferenceRunResponse:
    job = request.app.state.wip_reference_integrity_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="WIP reference-integrity job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return WipReferenceRunResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.post("/reference-integrity/{reference_id}/review", response_model=WipReferenceReportModel)
def wip_reference_integrity_review(
    reference_id: int, body: WipReferenceReviewRequest, request: Request
) -> WipReferenceReportModel:
    with request.app.state.engine.begin() as conn:
        row = conn.execute(select(wip_references).where(wip_references.c.id == reference_id)).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="WIP reference not found")
        result = set_reference_review_state(conn, reference_id, body.state)
        errors = {
            "bad-state": (422, "state must be dismissed or confirmed_problem"),
            "no-active-signals": (422, "This reference has no active signals to review"),
            "not-found": (404, "WIP reference not found"),
        }
        if result in errors:
            raise HTTPException(status_code=errors[result][0], detail=errors[result][1])
        record_event(conn, "flag_reviewed", count=1)
        return WipReferenceReportModel(**manuscript_reference_report(conn, int(row["manuscript_id"])))


def _run_wip_reference_integrity_job(app: FastAPI, job_id: str, manuscript_id: int) -> None:
    jobs: JobStore[WipReferenceRunResponse] = app.state.wip_reference_integrity_jobs
    jobs.mark_running(job_id)
    try:
        report = _check_wip_references(app, manuscript_id, jobs=jobs, job_id=job_id)
        run_write(
            app.state.engine,
            lambda conn: add_activity(
                conn, manuscript_id, "tool-run-completed", "Completed WIP reference-integrity scan"
            ),
        )
        jobs.mark_done(job_id, WipReferenceRunResponse(job_id=job_id, status="done", report=report))
    except Exception as exc:  # noqa: BLE001
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
        run_write(
            app.state.engine,
            lambda conn: add_activity(
                conn, manuscript_id, "tool-run-failed", "WIP reference-integrity scan could not complete"
            ),
        )


def _cited_reference_rows(conn, manuscript_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(
            wip_references.c.id.label("reference_id"),
            papers.c.id.label("paper_id"),
            papers.c.title,
            papers.c.doi,
            papers.c.year,
            papers.c.csl_json,
            papers.c.first_author_family_name,
        )
        .select_from(wip_references.join(papers, papers.c.id == wip_references.c.paper_id))
        .where(wip_references.c.manuscript_id == manuscript_id, wip_references.c.relationship_state == "cited")
        .order_by(papers.c.title)
    )
    return [dict(row) for row in conn.execute(stmt).mappings()]


def _check_wip_references(
    app: FastAPI,
    manuscript_id: int,
    *,
    jobs: JobStore[WipReferenceRunResponse] | None = None,
    job_id: str | None = None,
) -> WipReferenceReportModel:
    crossref_client: CrossrefClient | None = app.state.crossref_client
    openalex_client: OpenAlexClient = app.state.openalex_client or OpenAlexClient()
    with app.state.engine.begin() as conn:
        cited_rows = _cited_reference_rows(conn, manuscript_id)
        snapshot = retraction_db_status(conn)
    retraction_snapshot = f"rw:{snapshot['retrieved_at'] or 'not-downloaded'}:{snapshot['count']}"
    provider_statuses: list[dict[str, Any]] = [
        {
            "provider": "WIP linked references",
            "status": "success" if cited_rows else "empty",
            "detail": f"{len(cited_rows)} cited Library reference(s) linked to this manuscript"
            if cited_rows
            else "No Library references are marked 'cited' for this manuscript yet.",
            "result_count": len(cited_rows),
        },
        {
            "provider": "Retraction data",
            "status": "success" if snapshot["count"] else "unavailable",
            "detail": f"{snapshot['count']} local records; snapshot {snapshot['retrieved_at'] or 'not downloaded'}",
            "result_count": int(snapshot["count"] or 0),
        },
    ]
    total = max(1, len(cited_rows))
    flagged_count = 0
    skipped_count = 0
    with app.state.engine.begin() as conn:
        _require_manuscript(conn, manuscript_id)
        for index, row in enumerate(cited_rows, start=1):
            if jobs and job_id:
                jobs.mark_progress(job_id, index, total, "Checking reference signals")
            authors = _authors_from_csl(row["csl_json"], fallback=row["first_author_family_name"])
            bits = [
                ", ".join(authors[:3]) if authors else None,
                f"({row['year']})" if row["year"] else None,
                row["title"],
                row["doi"],
            ]
            candidate = ReferenceCandidate(
                source_ordinal=index - 1,
                title=row["title"],
                authors=authors,
                year=row["year"],
                doi=row["doi"],
                raw_text=" ".join(str(b) for b in bits if b).strip() or f"Reference {index}",
                context={"reference_source": "wip-library-reference", "wip_reference_id": row["reference_id"]},
            )
            try:
                result = inspect_reference(
                    conn,
                    candidate,
                    crossref_client=crossref_client,
                    openalex_client=openalex_client,
                    retraction_checkers=app.state.retraction_checkers,
                    retraction_snapshot=retraction_snapshot,
                )
            except Exception as exc:  # noqa: BLE001
                skipped_count += 1
                provider_statuses.append(
                    {
                        "provider": "Reference detectors",
                        "status": "partial",
                        "detail": f"Skipped reference {index}: {type(exc).__name__}: {exc}",
                        "result_count": 0,
                    }
                )
                continue
            signals = [_signal_row(s) for s in result.signals]
            prop = _propagation_signal_for(conn, result.entity_metadata)
            if prop is not None:
                signals.append(_signal_row(prop))
            if signals:
                flagged_count += 1
            replace_reference_signals(conn, manuscript_id, int(row["reference_id"]), signals)
        seen_reference_ids = {int(row["reference_id"]) for row in cited_rows}
        for old_id in conn.execute(
            select(wip_reference_signals.c.reference_id)
            .where(wip_reference_signals.c.manuscript_id == manuscript_id)
            .distinct()
        ).scalars():
            if int(old_id) not in seen_reference_ids:
                replace_reference_signals(conn, manuscript_id, int(old_id), [])
        report_payload = manuscript_reference_report(conn, manuscript_id)
    provider_statuses.append(
        {
            "provider": "Reference detectors",
            "status": "partial" if skipped_count else "success",
            "detail": f"Checked {len(cited_rows) - skipped_count} references; skipped {skipped_count}; "
            f"surfaced {flagged_count} flagged references.",
            "result_count": flagged_count,
        }
    )
    report_payload["provider_statuses"] = provider_statuses
    return WipReferenceReportModel(**report_payload)


def _propagation_signal_for(conn, entity_metadata: dict[str, Any]):
    """Read-only cross-space lookup: does this same cited work already carry an active Library reference-
    integrity signal? Pure additive read against the existing, untouched Library `reference_entities` table --
    never writes there, never looks at a WIP manuscript's own (separate) signal space."""
    key = entity_key(entity_metadata)
    entity_row = conn.execute(select(reference_entities.c.id).where(reference_entities.c.normalized_key == key)).first()
    if entity_row is None:
        return None
    sources = flagged_sources_for_entity(conn, int(entity_row[0]), exclude_paper_id=0)
    return propagation_signal(sources)


def _signal_row(signal) -> dict:
    return {
        "detector_kind": signal.detector_kind,
        "detector_status": signal.detector_status,
        "evidence_json": signal.evidence,
        "source": signal.source,
        "snapshot_marker": signal.snapshot_marker,
        "signal_key": signal.key,
    }


def _require_manuscript(conn, manuscript_id: int) -> dict:
    manuscript = get_manuscript(conn, manuscript_id)
    if manuscript is None:
        raise HTTPException(status_code=404, detail="WIP manuscript not found")
    return manuscript
