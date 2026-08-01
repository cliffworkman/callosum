"""Meta Reference List — reference-integrity signals for the Theory pane.

Runs a narrow set of negative checks over a selected paper's reference list. Signals remain distinct and
reviewable per citation instance; clearing them never promotes a paper into a positive/verified state.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select

from app.backend.acquisition.registry import PaperRef
from app.backend.api.job_store import JobStore
from app.backend.api.routers.citation_context import _stance_scorer
from app.backend.methods.citation_context import classify_citation_contexts
from app.backend.methods.reference_integrity import (
    ReferenceCandidate,
    inspect_reference,
    instance_key,
    propagation_signal,
)
from app.backend.persistence.reference_integrity_repo import (
    flagged_sources_for_entity,
    paper_reference_report,
    reference_overview,
    replace_instance_signals,
    set_reference_review_state,
    upsert_reference_entity,
    upsert_reference_instance,
)
from app.backend.persistence.retraction_repo import retraction_db_status
from app.backend.persistence.schema import papers
from app.backend.persistence.schema_reference_integrity import reference_instances
from integrations.crossref.adapter import CrossrefClient
from integrations.openalex.adapter import OpenAlexClient
from integrations.semantic_scholar.adapter import SemanticScholarClient

router = APIRouter(tags=["reference-integrity"])


class ReferenceSignalModel(BaseModel):
    id: int
    detector_kind: str
    detector_status: str
    evidence: dict
    source: str
    snapshot_marker: str
    detected_at: str | None = None


class ReferenceItemModel(BaseModel):
    id: int
    citing_paper_id: int
    reference_entity_id: int | None = None
    source: str
    source_ordinal: int
    raw_text: str
    title: str | None = None
    authors: list[str] = []
    year: int | None = None
    doi: str | None = None
    context: dict = {}
    review_state: str
    reviewed_at: str | None = None
    signal_fingerprint: str | None = None
    reopened: bool = False
    signals: list[ReferenceSignalModel] = []


class ReferenceReportModel(BaseModel):
    paper_id: int
    active_count: int
    checked_count: int = 0
    last_checked_at: str | None = None
    provider_statuses: list[dict[str, Any]] = []
    items: list[ReferenceItemModel] = []


class ReferenceOverviewItem(BaseModel):
    paper_id: int
    active_count: int
    unreviewed_count: int
    confirmed_count: int


class ReferenceBulkRunRequest(BaseModel):
    paper_ids: list[int]


class ReferenceBulkRunReport(BaseModel):
    requested_count: int
    checked_count: int
    skipped_no_doi_count: int
    not_found_count: int
    failed_count: int
    active_paper_count: int
    skipped_no_doi: list[int] = []
    not_found: list[int] = []
    failed: list[dict[str, Any]] = []


class ReferenceRunResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    progress: dict[str, Any] | None = None
    report: ReferenceReportModel | None = None
    bulk_report: ReferenceBulkRunReport | None = None


class ReferenceReviewRequest(BaseModel):
    state: Literal["dismissed", "confirmed_problem"]


@router.get("/papers/{paper_id}/reference-integrity", response_model=ReferenceReportModel)
def reference_integrity_get(paper_id: int, request: Request) -> ReferenceReportModel:
    with request.app.state.engine.begin() as conn:
        _require_paper(conn, paper_id)
        return ReferenceReportModel(**paper_reference_report(conn, paper_id))


@router.get("/reference-integrity/overview", response_model=list[ReferenceOverviewItem])
def reference_integrity_overview(request: Request) -> list[ReferenceOverviewItem]:
    with request.app.state.engine.begin() as conn:
        return [ReferenceOverviewItem(**row) for row in reference_overview(conn)]


@router.post(
    "/papers/{paper_id}/reference-integrity/run",
    response_model=ReferenceRunResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def reference_integrity_run(paper_id: int, background_tasks: BackgroundTasks, request: Request) -> ReferenceRunResponse:
    with request.app.state.engine.begin() as conn:
        row = _require_paper(conn, paper_id)
        if not row["doi"]:
            raise HTTPException(
                status_code=422,
                detail="This paper has no DOI, so Semantic Scholar can't supply its linked reference list.",
            )
    job_id = request.app.state.reference_integrity_jobs.create(nav={"paper_id": paper_id})
    background_tasks.add_task(_run_reference_integrity_job, request.app, job_id, paper_id)
    return ReferenceRunResponse(job_id=job_id, status="pending")


@router.post(
    "/reference-integrity/run-selected",
    response_model=ReferenceRunResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def reference_integrity_run_selected(
    body: ReferenceBulkRunRequest, background_tasks: BackgroundTasks, request: Request
) -> ReferenceRunResponse:
    paper_ids = _unique_ids(body.paper_ids)
    if not paper_ids:
        raise HTTPException(status_code=422, detail="Select at least one paper.")
    if len(paper_ids) > 200:
        raise HTTPException(status_code=422, detail="Reference checks are limited to 200 selected papers at a time.")
    job_id = request.app.state.reference_integrity_jobs.create(nav={"paper_ids": paper_ids})
    background_tasks.add_task(_run_reference_integrity_bulk_job, request.app, job_id, paper_ids)
    return ReferenceRunResponse(job_id=job_id, status="pending")


@router.get("/reference-integrity/run/{job_id}", response_model=ReferenceRunResponse)
def reference_integrity_run_status(job_id: str, request: Request) -> ReferenceRunResponse:
    job = request.app.state.reference_integrity_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Reference-integrity job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    progress = None
    if job.progress is not None:
        progress = {
            "current": job.progress.current,
            "total": job.progress.total,
            "label": job.progress.label,
            "eta_seconds": job.eta_seconds(),
        }
    return ReferenceRunResponse(job_id=job_id, status=job.status, detail=job.detail, progress=progress)


@router.post("/reference-integrity/instances/{instance_id}/review", response_model=ReferenceReportModel)
def reference_integrity_review(
    instance_id: int, body: ReferenceReviewRequest, request: Request
) -> ReferenceReportModel:
    with request.app.state.engine.begin() as conn:
        row = (
            conn.execute(select(reference_instances).where(reference_instances.c.id == instance_id)).mappings().first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Reference instance not found")
        result = set_reference_review_state(conn, instance_id, body.state)
        errors = {
            "bad-state": (422, "state must be dismissed or confirmed_problem"),
            "no-active-signals": (422, "This reference instance has no active signals to review"),
            "not-found": (404, "Reference instance not found"),
        }
        if result in errors:
            raise HTTPException(status_code=errors[result][0], detail=errors[result][1])
        return ReferenceReportModel(**paper_reference_report(conn, int(row["citing_paper_id"])))


def _run_reference_integrity_job(app: FastAPI, job_id: str, paper_id: int) -> None:
    jobs: JobStore[ReferenceRunResponse] = app.state.reference_integrity_jobs
    jobs.mark_running(job_id)
    try:
        report = _check_references_for_paper(app, paper_id, jobs=jobs, job_id=job_id)
        complete_total = max(1, report.checked_count)
        jobs.mark_done(
            job_id,
            ReferenceRunResponse(
                job_id=job_id,
                status="done",
                progress={
                    "current": complete_total,
                    "total": complete_total,
                    "label": "Reference check complete",
                    "eta_seconds": 0,
                },
                report=report,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _run_reference_integrity_bulk_job(app: FastAPI, job_id: str, paper_ids: list[int]) -> None:
    jobs: JobStore[ReferenceRunResponse] = app.state.reference_integrity_jobs
    jobs.mark_running(job_id)
    skipped_no_doi: list[int] = []
    not_found: list[int] = []
    failed: list[dict[str, Any]] = []
    checked = 0
    active = 0
    total = len(paper_ids)
    try:
        for index, paper_id in enumerate(paper_ids, start=1):
            jobs.mark_progress(job_id, index, total, f"Checking paper {index} of {total}")
            try:
                with app.state.engine.begin() as conn:
                    row = _require_paper(conn, paper_id)
                    if not row["doi"]:
                        skipped_no_doi.append(paper_id)
                        continue
                report = _check_references_for_paper(app, paper_id, update_progress=False)
                checked += 1
                if report.active_count > 0:
                    active += 1
            except HTTPException as exc:
                if exc.status_code == 404:
                    not_found.append(paper_id)
                else:
                    failed.append({"paper_id": paper_id, "error": str(exc.detail)})
            except Exception as exc:  # noqa: BLE001
                failed.append({"paper_id": paper_id, "error": f"{type(exc).__name__}: {exc}"})
        summary = ReferenceBulkRunReport(
            requested_count=total,
            checked_count=checked,
            skipped_no_doi_count=len(skipped_no_doi),
            not_found_count=len(not_found),
            failed_count=len(failed),
            active_paper_count=active,
            skipped_no_doi=skipped_no_doi,
            not_found=not_found,
            failed=failed,
        )
        jobs.mark_done(
            job_id,
            ReferenceRunResponse(
                job_id=job_id,
                status="done",
                progress={
                    "current": total,
                    "total": total,
                    "label": "Selected reference checks complete",
                    "eta_seconds": 0,
                },
                bulk_report=summary,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _check_references_for_paper(
    app: FastAPI,
    paper_id: int,
    *,
    jobs: JobStore[ReferenceRunResponse] | None = None,
    job_id: str | None = None,
    update_progress: bool = True,
) -> ReferenceReportModel:
    client: SemanticScholarClient = app.state.semantic_scholar_client or SemanticScholarClient()
    crossref_client: CrossrefClient | None = app.state.crossref_client
    openalex_client: OpenAlexClient = app.state.openalex_client or OpenAlexClient()
    with app.state.engine.begin() as conn:
        row = _require_paper(conn, paper_id)
        snapshot = retraction_db_status(conn)
    if not row["doi"]:
        raise HTTPException(
            status_code=422,
            detail="This paper has no DOI, so Semantic Scholar can't supply its linked reference list.",
        )
    doi = row["doi"]
    provider_statuses: list[dict[str, Any]] = []
    if update_progress and jobs and job_id:
        jobs.mark_progress(job_id, 0, 1, "Fetching linked references")
    try:
        with app.state.engine.begin() as conn:
            contexts = client.fetch_reference_contexts(conn, doi)
    except Exception as exc:  # noqa: BLE001 - provider failures are surfaced as coverage, not a verdict
        contexts = []
        provider_statuses.append(
            {
                "provider": "Semantic Scholar",
                "status": "failed",
                "detail": f"{type(exc).__name__}: {exc}",
                "result_count": 0,
            }
        )
    else:
        provider_statuses.append(
            {
                "provider": "Semantic Scholar",
                "status": "success" if contexts else "empty",
                "detail": f"{len(contexts)} linked reference records"
                if contexts
                else "No linked reference records returned for this DOI.",
                "result_count": len(contexts),
            }
        )
    candidates = _candidates_from_semantic_contexts(contexts, _stance_scorer(app))
    if not candidates:
        if update_progress and jobs and job_id:
            jobs.mark_progress(job_id, 0, 1, "Trying OpenAlex reference fallback")
        try:
            with app.state.engine.begin() as conn:
                candidates = _candidates_from_openalex_references(conn, openalex_client, doi)
        except Exception as exc:  # noqa: BLE001
            candidates = []
            provider_statuses.append(
                {
                    "provider": "OpenAlex",
                    "status": "failed",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "result_count": 0,
                }
            )
        else:
            provider_statuses.append(
                {
                    "provider": "OpenAlex",
                    "status": "success" if candidates else "empty",
                    "detail": f"{len(candidates)} referenced-work records"
                    if candidates
                    else "No referenced-work records returned or resolved for this DOI.",
                    "result_count": len(candidates),
                }
            )
    else:
        provider_statuses.append(
            {
                "provider": "OpenAlex",
                "status": "not_searched",
                "detail": "Fallback was not needed because Semantic Scholar returned linked references.",
                "result_count": 0,
            }
        )
    retraction_snapshot = f"rw:{snapshot['retrieved_at'] or 'not-downloaded'}:{snapshot['count']}"
    provider_statuses.append(
        {
            "provider": "Retraction data",
            "status": "success" if snapshot["count"] else "unavailable",
            "detail": f"{snapshot['count']} local records; snapshot {snapshot['retrieved_at'] or 'not downloaded'}",
            "result_count": int(snapshot["count"] or 0),
        }
    )
    total = max(1, len(candidates))
    skipped_count = 0
    inspected: list[tuple[ReferenceCandidate, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if update_progress and jobs and job_id:
            jobs.mark_progress(job_id, index, total, "Checking reference signals")
        try:
            with app.state.engine.begin() as conn:
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
        inspected.append((candidate, result))
    seen_instance_ids: set[int] = set()
    flagged_count = 0
    with app.state.engine.begin() as conn:
        _require_paper(conn, paper_id)
        for candidate, result in inspected:
            entity_id = upsert_reference_entity(conn, result.entity_metadata)
            iid = upsert_reference_instance(
                conn,
                citing_paper_id=paper_id,
                entity_id=entity_id,
                instance_key=instance_key(candidate),
                source=candidate.context.get("reference_source") or "semantic-scholar",
                source_ordinal=candidate.source_ordinal,
                raw_text=candidate.raw_text,
                title=result.entity_metadata.get("title") or candidate.title,
                authors=list(result.entity_metadata.get("authors") or candidate.authors),
                year=result.entity_metadata.get("year") or candidate.year,
                doi=result.entity_metadata.get("doi") or candidate.doi,
                context=candidate.context,
            )
            seen_instance_ids.add(iid)
            signals = [_signal_row(s) for s in result.signals]
            prop = propagation_signal(flagged_sources_for_entity(conn, entity_id, exclude_paper_id=paper_id))
            if prop is not None:
                signals.append(_signal_row(prop))
            if signals:
                flagged_count += 1
            replace_instance_signals(conn, iid, signals)
        for old_id in conn.execute(
            select(reference_instances.c.id).where(reference_instances.c.citing_paper_id == paper_id)
        ).scalars():
            if int(old_id) not in seen_instance_ids:
                replace_instance_signals(conn, int(old_id), [])
        report_payload = paper_reference_report(conn, paper_id)
    provider_statuses.append(
        {
            "provider": "Reference detectors",
            "status": "partial" if skipped_count else "success",
            "detail": f"Checked {len(candidates) - skipped_count} references; skipped {skipped_count}; surfaced {flagged_count} flagged references.",
            "result_count": flagged_count,
        }
    )
    report_payload["provider_statuses"] = provider_statuses
    return ReferenceReportModel(**report_payload)


def _candidates_from_semantic_contexts(contexts, stance_scorer) -> list[ReferenceCandidate]:
    classified = classify_citation_contexts(contexts=contexts, focal_claim="", stance_scorer=stance_scorer)
    candidates: list[ReferenceCandidate] = []
    for ix, ctx in enumerate(contexts):
        item = classified.items[ix] if ix < len(classified.items) else None
        candidates.append(_candidate_from_context(ix, ctx, item))
    return candidates


def _candidates_from_openalex_references(conn, openalex_client: OpenAlexClient, doi: str) -> list[ReferenceCandidate]:
    candidates: list[ReferenceCandidate] = []
    for ix, work_id in enumerate(openalex_client.fetch_referenced_works(conn, PaperRef(doi=doi))):
        meta = openalex_client.fetch_work_meta(conn, work_id)
        if not meta:
            continue
        title = meta.get("title")
        authors = list(meta.get("authors") or [])
        year = meta.get("year")
        ref_doi = meta.get("doi")
        bits = [", ".join(authors[:3]) if authors else None, f"({year})" if year else None, title, ref_doi]
        candidates.append(
            ReferenceCandidate(
                source_ordinal=ix,
                title=title,
                authors=authors,
                year=year,
                doi=ref_doi,
                raw_text=" ".join(str(b) for b in bits if b).strip() or f"OpenAlex reference {ix + 1}",
                context={"reference_source": "openalex:referenced_works", "openalex_work_id": work_id},
            )
        )
    return candidates


def _candidate_from_context(ix: int, ctx, item) -> ReferenceCandidate:
    title = getattr(ctx, "citing_title", None)
    authors = list(getattr(ctx, "citing_authors", []) or [])
    year = getattr(ctx, "citing_year", None)
    doi = getattr(ctx, "citing_doi", None)
    bits = [", ".join(authors[:3]) if authors else None, f"({year})" if year else None, title, doi]
    raw = " ".join(str(b) for b in bits if b).strip() or f"Reference {ix + 1}"
    context = {
        "reference_source": "semantic-scholar",
        "sentence": item.sentence if item else "",
        "hint": _context_hint(item.stance if item else None),
        "stance": item.stance if item else None,
        "confidence": item.confidence if item else None,
    }
    return ReferenceCandidate(
        source_ordinal=ix,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        raw_text=raw,
        context=context,
    )


def _context_hint(stance: str | None) -> str | None:
    if stance == "contrast":
        return "Context hint: citation may be used critically or contrastively"
    if stance == "support":
        return "Context hint: citation may be used supportively"
    if stance == "mention":
        return "Context hint: citation may be a mention or background use"
    return None


def _unique_ids(values: list[int]) -> list[int]:
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


def _signal_row(signal) -> dict:
    return {
        "detector_kind": signal.detector_kind,
        "detector_status": signal.detector_status,
        "evidence_json": signal.evidence,
        "source": signal.source,
        "snapshot_marker": signal.snapshot_marker,
        "signal_key": signal.key,
    }


def _require_paper(conn, paper_id: int):
    row = conn.execute(select(papers.c.id, papers.c.doi).where(papers.c.id == paper_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return row
