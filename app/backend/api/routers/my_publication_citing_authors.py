"""My Publications Layer-4 authors-citing-your-work endpoints (inc 391)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.clustering.my_publication_citing_authors import (
    MIN_CITED_PUBLICATIONS,
    MIN_CITING_WORKS,
    compute_citing_authors,
)
from app.backend.clustering.my_publication_gap_scope import CitationGapScope, resolve_citation_gap_scope
from app.backend.clustering.my_publications_domains import confirmed_member_rows
from app.backend.persistence.my_publication_citing_author_repo import (
    read_citing_author_cache,
    replace_citing_author_cache,
)
from app.backend.persistence.profile_repo import get_profile
from app.backend.persistence.sqlite_retry import run_write
from integrations.openalex.adapter import OpenAlexClient
from integrations.openalex.citing_authors import OpenAlexCitingAuthorsClient

router = APIRouter()


class CitingAuthorSourcePaper(BaseModel):
    paper_id: int
    title: str


class CitingAuthorWork(BaseModel):
    openalex_work_id: str
    doi: str | None = None
    title: str | None = None
    year: int
    cited_publications: list[CitingAuthorSourcePaper] = []


class CitingAuthorOut(BaseModel):
    author_id: str
    name: str
    citing_work_count: int
    cited_publication_count: int
    latest_year: int
    citing_works: list[CitingAuthorWork] = []


class CitingAuthorCoverage(BaseModel):
    checked: int = 0
    with_doi: int = 0
    total: int = 0
    library_total: int = 0
    unresolved_openalex_count: int = 0
    start_year: int
    end_year: int
    citing_work_count: int = 0
    coauthor_checked_publication_count: int = 0
    coauthor_unresolved_publication_count: int = 0
    excluded_coauthor_count: int = 0
    missing_author_id_count: int = 0
    source_authorship_cap_count: int = 0
    citing_authorship_cap_count: int = 0
    publication_cap_reached: bool = False
    citing_window_cap_reached: bool = False
    scope_kind: Literal["all", "domains"] = "all"
    domain_count: int = 0
    domain_labels: list[str] = []
    note: str = ""


class CitingAuthorScopeOut(BaseModel):
    kind: Literal["all", "domains"] = "all"
    domain_keys: list[str] = []
    domain_labels: list[str] = []


class CitingAuthorListResponse(BaseModel):
    authors: list[CitingAuthorOut] = []
    computed_at: str | None = None
    coverage: CitingAuthorCoverage | None = None
    scope: CitingAuthorScopeOut = CitingAuthorScopeOut()


class CitingAuthorRefreshResult(BaseModel):
    count: int = 0
    coverage: CitingAuthorCoverage
    computed_at: str
    scope: CitingAuthorScopeOut


class CitingAuthorRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: CitingAuthorRefreshResult | None = None


class CitingAuthorRefreshRequest(BaseModel):
    domain_keys: list[str] = []


@router.get("/my-publications/citing-authors", response_model=CitingAuthorListResponse)
def list_citing_authors(
    domain_key: list[str] = Query(default=[]),
    conn: Connection = Depends(get_connection),
) -> CitingAuthorListResponse:
    """Read a local snapshot only; ordinary dashboard opens never query OpenAlex."""
    scope = _resolve_scope_or_422(conn, domain_key)
    scope_out = _scope_out(scope)
    snapshot = read_citing_author_cache(conn, scope_key=scope.key)
    if snapshot is None:
        return CitingAuthorListResponse(scope=scope_out)
    parsed: list[dict[str, Any]] = []
    for raw in snapshot.get("authors") if isinstance(snapshot.get("authors"), list) else []:
        try:
            author = CitingAuthorOut.model_validate(raw)
        except (TypeError, ValidationError):
            continue
        if re.fullmatch(r"A\d+", author.author_id) is None:
            continue
        parsed.append(author.model_dump())
    authors = _visible_authors(conn, parsed, scope)
    try:
        coverage = CitingAuthorCoverage.model_validate(snapshot.get("coverage"))
    except (TypeError, ValidationError):
        coverage = None
    return CitingAuthorListResponse(
        authors=[CitingAuthorOut(**author) for author in authors],
        computed_at=str(snapshot["computed_at"]),
        coverage=coverage,
        scope=scope_out,
    )


@router.post(
    "/my-publications/citing-authors/refresh",
    response_model=CitingAuthorRefreshResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def refresh_citing_authors(
    payload: CitingAuthorRefreshRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> CitingAuthorRefreshResponse:
    scope = _resolve_scope_or_422(conn, payload.domain_keys)
    job_id = request.app.state.my_publication_citing_author_jobs.create()
    background_tasks.add_task(_run_refresh, request.app, job_id, scope)
    return CitingAuthorRefreshResponse(job_id=job_id, status="pending")


@router.get(
    "/my-publications/citing-authors/refresh/{job_id}",
    response_model=CitingAuthorRefreshResponse,
)
def citing_author_refresh_status(job_id: str, request: Request) -> CitingAuthorRefreshResponse:
    job = request.app.state.my_publication_citing_author_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Citing-author refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return CitingAuthorRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_refresh(app: FastAPI, job_id: str, scope: CitationGapScope) -> None:
    jobs: JobStore[CitingAuthorRefreshResponse] = app.state.my_publication_citing_author_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        base_client = app.state.openalex_client or OpenAlexClient()
        fetch_client = (
            base_client.with_cache_engine(engine) if hasattr(base_client, "with_cache_engine") else base_client
        )
        citing_client = app.state.openalex_citing_authors_client
        if citing_client is None:
            citing_client = OpenAlexCitingAuthorsClient(
                base_client,
                window_client=app.state.openalex_citing_topics_client,
            )
        fetch_citing_client = (
            citing_client.with_cache_engine(engine) if hasattr(citing_client, "with_cache_engine") else citing_client
        )
        computed_at = datetime.now(timezone.utc).isoformat()
        with engine.connect() as conn:
            authors, coverage = compute_citing_authors(
                conn,
                openalex_client=fetch_client,
                citing_client=fetch_citing_client,
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
            lambda conn: replace_citing_author_cache(
                conn,
                authors,
                coverage,
                computed_at=computed_at,
                scope_key=scope.key,
                scope=scope.to_dict(),
            ),
        )
        result = CitingAuthorRefreshResult(
            count=len(authors),
            coverage=CitingAuthorCoverage(**coverage),
            computed_at=computed_at,
            scope=_scope_out(scope),
        )
        jobs.mark_done(job_id, CitingAuthorRefreshResponse(job_id=job_id, status="done", result=result))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _visible_authors(
    conn: Connection,
    authors: list[dict[str, Any]],
    scope: CitationGapScope,
) -> list[dict[str, Any]]:
    allowed_ids = {int(row["id"]) for row in confirmed_member_rows(conn)}
    if scope.paper_ids is not None:
        allowed_ids &= set(scope.paper_ids)
    profile = get_profile(conn) or {}
    self_author_id = str(profile.get("openalex_author_id") or "").rsplit("/", 1)[-1]
    visible: list[dict[str, Any]] = []
    for author in authors:
        if author.get("author_id") == self_author_id:
            continue
        works = []
        cited_paper_ids: set[int] = set()
        for work in author.get("citing_works") or []:
            work_id = str(work.get("openalex_work_id") or "")
            if re.fullmatch(r"W\d+", work_id) is None:
                continue
            sources = [
                source
                for source in (work.get("cited_publications") or [])
                if _positive_int(source.get("paper_id")) in allowed_ids
            ]
            if not sources:
                continue
            cited_paper_ids.update(int(source["paper_id"]) for source in sources)
            works.append({**work, "cited_publications": sources})
        if len(works) < MIN_CITING_WORKS or len(cited_paper_ids) < MIN_CITED_PUBLICATIONS:
            continue
        visible.append(
            {
                **author,
                "citing_work_count": len(works),
                "cited_publication_count": len(cited_paper_ids),
                "latest_year": max(int(work["year"]) for work in works),
                "citing_works": works,
            }
        )
    visible.sort(
        key=lambda author: (
            -int(author["cited_publication_count"]),
            -int(author["citing_work_count"]),
            str(author.get("name") or "").casefold(),
            str(author.get("author_id") or ""),
        )
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


def _scope_out(scope: CitationGapScope) -> CitingAuthorScopeOut:
    return CitingAuthorScopeOut(
        kind=scope.kind,
        domain_keys=list(scope.domain_keys),
        domain_labels=list(scope.domain_labels),
    )
