"""My Publications Layer-4 grounded citation-gap endpoints (inc 386)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection, select

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.clustering.my_publication_gap_scope import CitationGapScope, resolve_citation_gap_scope
from app.backend.clustering.my_publication_gaps import compute_my_publication_citation_gaps
from app.backend.persistence.my_publication_gap_repo import (
    read_my_publication_citation_gap_cache,
    replace_my_publication_citation_gap_cache,
)
from app.backend.persistence.profile_repo import dismissed_gaps
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.schema import papers
from app.backend.persistence.sqlite_retry import run_write
from integrations.openalex.adapter import OpenAlexClient

router = APIRouter()


class CitationGapSourcePaper(BaseModel):
    paper_id: int
    title: str


class CitationGapEvidence(BaseModel):
    reference_openalex_work_id: str
    reference_title: str | None = None
    reference_doi: str | None = None
    source_papers: list[CitationGapSourcePaper] = []


class CitationGapCandidate(BaseModel):
    openalex_work_id: str
    doi: str | None = None
    title: str | None = None
    authors: list[str] = []
    year: int | None = None
    shared_reference_count: int
    source_publication_count: int
    evidence: list[CitationGapEvidence] = []


class CitationGapCoverage(BaseModel):
    checked: int = 0
    with_doi: int = 0
    total: int = 0
    library_total: int = 0
    shared_anchor_count: int = 0
    publication_cap_reached: bool = False
    scope_kind: Literal["all", "domains"] = "all"
    domain_count: int = 0
    domain_labels: list[str] = []
    note: str = ""


class CitationGapScopeOut(BaseModel):
    kind: Literal["all", "domains"] = "all"
    domain_keys: list[str] = []
    domain_labels: list[str] = []


class CitationGapListResponse(BaseModel):
    candidates: list[CitationGapCandidate] = []
    computed_at: str | None = None
    coverage: CitationGapCoverage | None = None
    scope: CitationGapScopeOut = CitationGapScopeOut()


class CitationGapRefreshResult(BaseModel):
    count: int = 0
    coverage: CitationGapCoverage
    computed_at: str
    scope: CitationGapScopeOut


class CitationGapRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: CitationGapRefreshResult | None = None


class CitationGapRefreshRequest(BaseModel):
    domain_keys: list[str] = []


@router.get("/my-publications/citation-gaps", response_model=CitationGapListResponse)
def list_my_publication_citation_gaps(
    domain_key: list[str] = Query(default=[]),
    conn: Connection = Depends(get_connection),
) -> CitationGapListResponse:
    """Read the local snapshot only. Opening the dashboard never triggers metadata egress."""
    scope = _resolve_scope_or_422(conn, domain_key)
    scope_out = _scope_out(scope)
    snapshot = read_my_publication_citation_gap_cache(conn, scope_key=scope.key)
    if snapshot is None:
        return CitationGapListResponse(scope=scope_out)
    parsed_candidates: list[dict[str, Any]] = []
    raw_candidates = snapshot.get("candidates")
    for raw in raw_candidates if isinstance(raw_candidates, list) else []:
        try:
            parsed = CitationGapCandidate.model_validate(raw)
        except (TypeError, ValidationError):
            continue
        if re.fullmatch(r"W\d+", parsed.openalex_work_id) is None:
            continue
        parsed_candidates.append(parsed.model_dump())
    candidates = _visible_candidates(
        conn,
        parsed_candidates,
        dismissed=dismissed_gaps(conn),
    )
    try:
        coverage = CitationGapCoverage.model_validate(snapshot.get("coverage"))
    except (TypeError, ValidationError):
        coverage = None
    return CitationGapListResponse(
        candidates=[CitationGapCandidate(**candidate) for candidate in candidates],
        computed_at=str(snapshot["computed_at"]),
        coverage=coverage,
        scope=scope_out,
    )


@router.post(
    "/my-publications/citation-gaps/refresh",
    response_model=CitationGapRefreshResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def refresh_my_publication_citation_gaps(
    payload: CitationGapRefreshRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> CitationGapRefreshResponse:
    scope = _resolve_scope_or_422(conn, payload.domain_keys)
    job_id = request.app.state.my_publication_gap_jobs.create()
    background_tasks.add_task(_run_refresh, request.app, job_id, scope)
    return CitationGapRefreshResponse(job_id=job_id, status="pending")


@router.get(
    "/my-publications/citation-gaps/refresh/{job_id}",
    response_model=CitationGapRefreshResponse,
)
def my_publication_citation_gap_refresh_status(
    job_id: str,
    request: Request,
) -> CitationGapRefreshResponse:
    job = request.app.state.my_publication_gap_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Citation-gap refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return CitationGapRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_refresh(app: FastAPI, job_id: str, scope: CitationGapScope) -> None:
    jobs: JobStore[CitationGapRefreshResponse] = app.state.my_publication_gap_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        client = app.state.openalex_client or OpenAlexClient()
        fetch_client = client.with_cache_engine(engine) if hasattr(client, "with_cache_engine") else client
        computed_at = datetime.now(timezone.utc).isoformat()
        with engine.connect() as conn:
            candidates, coverage = compute_my_publication_citation_gaps(
                conn,
                openalex_client=fetch_client,
                dismissed=dismissed_gaps(conn),
                paper_ids=scope.paper_ids,
            )
            coverage = {
                **coverage,
                "scope_kind": scope.kind,
                "domain_count": len(scope.domain_keys),
                "domain_labels": list(scope.domain_labels),
            }
        run_write(
            engine,
            lambda conn: replace_my_publication_citation_gap_cache(
                conn,
                candidates,
                coverage,
                computed_at=computed_at,
                scope_key=scope.key,
                scope=scope.to_dict(),
            ),
        )
        result = CitationGapRefreshResult(
            count=len(candidates),
            coverage=CitationGapCoverage(**coverage),
            computed_at=computed_at,
            scope=_scope_out(scope),
        )
        jobs.mark_done(job_id, CitationGapRefreshResponse(job_id=job_id, status="done", result=result))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _visible_candidates(
    conn: Connection,
    candidates: list[dict[str, Any]],
    *,
    dismissed: set[str],
) -> list[dict[str, Any]]:
    source_ids = {
        paper_id
        for candidate in candidates
        for evidence in candidate.get("evidence") or []
        for source in evidence.get("source_papers") or []
        if (paper_id := _positive_int(source.get("paper_id"))) is not None
    }
    dismissed_keys = {str(key).strip().casefold() for key in dismissed if str(key).strip()}
    live_ids = (
        {
            int(paper_id)
            for paper_id in conn.execute(
                select(papers.c.id).where(papers.c.id.in_(source_ids), papers.c.deleted_at.is_(None))
            ).scalars()
        }
        if source_ids
        else set()
    )
    visible: list[dict[str, Any]] = []
    for candidate in candidates:
        work_id = str(candidate.get("openalex_work_id") or "")
        doi = candidate.get("doi")
        if work_id.casefold() in dismissed_keys or (doi and str(doi).casefold() in dismissed_keys):
            continue
        if (
            find_existing_paper_by_identity(
                conn,
                doi=doi,
                openalex_work_id=work_id,
                title=candidate.get("title"),
                year=candidate.get("year"),
            )
            is not None
        ):
            continue
        evidence = []
        source_union: set[int] = set()
        for item in candidate.get("evidence") or []:
            sources = [
                source
                for source in (item.get("source_papers") or [])
                if _positive_int(source.get("paper_id")) in live_ids
            ]
            if not sources:
                continue
            source_union.update(int(source["paper_id"]) for source in sources)
            evidence.append({**item, "source_papers": sources})
        if not evidence:
            continue
        visible.append(
            {
                **candidate,
                "evidence": evidence,
                "shared_reference_count": len(evidence),
                "source_publication_count": len(source_union),
            }
        )
    return visible


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _resolve_scope_or_422(conn: Connection, domain_keys: list[str]) -> CitationGapScope:
    try:
        return resolve_citation_gap_scope(conn, domain_keys)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _scope_out(scope: CitationGapScope) -> CitationGapScopeOut:
    return CitationGapScopeOut(
        kind=scope.kind,
        domain_keys=list(scope.domain_keys),
        domain_labels=list(scope.domain_labels),
    )
