"""My Publications Layer-4 emerging citing-topic endpoints (inc 390)."""

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
from app.backend.clustering.my_publication_gap_scope import CitationGapScope, resolve_citation_gap_scope
from app.backend.clustering.my_publication_topics import (
    MIN_RECENT_WORKS,
    compute_emerging_citing_topics,
)
from app.backend.clustering.my_publications_domains import confirmed_member_rows
from app.backend.persistence.my_publication_topic_repo import (
    read_emerging_topic_cache,
    replace_emerging_topic_cache,
)
from app.backend.persistence.sqlite_retry import run_write
from integrations.openalex.adapter import OpenAlexClient
from integrations.openalex.citing_topics import OpenAlexCitingTopicsClient

router = APIRouter()


class CitingTopicSourcePaper(BaseModel):
    paper_id: int
    title: str


class CitingTopicWork(BaseModel):
    openalex_work_id: str
    doi: str | None = None
    title: str | None = None
    year: int
    authors: list[str] = []
    cited_publications: list[CitingTopicSourcePaper] = []


class EmergingCitingTopicOut(BaseModel):
    topic_id: str
    name: str
    subfield: str | None = None
    field: str | None = None
    domain: str | None = None
    recent_count: int
    previous_count: int
    increase: int
    recent_works: list[CitingTopicWork] = []
    previous_works: list[CitingTopicWork] = []


class EmergingTopicCoverage(BaseModel):
    checked: int = 0
    with_doi: int = 0
    total: int = 0
    library_total: int = 0
    unresolved_openalex_count: int = 0
    recent_start_year: int
    recent_end_year: int
    previous_start_year: int
    previous_end_year: int
    recent_work_count: int = 0
    previous_work_count: int = 0
    missing_primary_topic_count: int = 0
    publication_cap_reached: bool = False
    recent_window_cap_reached: bool = False
    previous_window_cap_reached: bool = False
    scope_kind: Literal["all", "domains"] = "all"
    domain_count: int = 0
    domain_labels: list[str] = []
    note: str = ""


class EmergingTopicScopeOut(BaseModel):
    kind: Literal["all", "domains"] = "all"
    domain_keys: list[str] = []
    domain_labels: list[str] = []


class EmergingTopicListResponse(BaseModel):
    topics: list[EmergingCitingTopicOut] = []
    computed_at: str | None = None
    coverage: EmergingTopicCoverage | None = None
    scope: EmergingTopicScopeOut = EmergingTopicScopeOut()


class EmergingTopicRefreshResult(BaseModel):
    count: int = 0
    coverage: EmergingTopicCoverage
    computed_at: str
    scope: EmergingTopicScopeOut


class EmergingTopicRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: EmergingTopicRefreshResult | None = None


class EmergingTopicRefreshRequest(BaseModel):
    domain_keys: list[str] = []


@router.get("/my-publications/emerging-citing-topics", response_model=EmergingTopicListResponse)
def list_emerging_citing_topics(
    domain_key: list[str] = Query(default=[]),
    conn: Connection = Depends(get_connection),
) -> EmergingTopicListResponse:
    """Read a local snapshot only; ordinary dashboard opens never query OpenAlex."""
    scope = _resolve_scope_or_422(conn, domain_key)
    scope_out = _scope_out(scope)
    snapshot = read_emerging_topic_cache(conn, scope_key=scope.key)
    if snapshot is None:
        return EmergingTopicListResponse(scope=scope_out)
    parsed: list[dict[str, Any]] = []
    for raw in snapshot.get("topics") if isinstance(snapshot.get("topics"), list) else []:
        try:
            topic = EmergingCitingTopicOut.model_validate(raw)
        except (TypeError, ValidationError):
            continue
        if re.fullmatch(r"T\d+", topic.topic_id) is None:
            continue
        parsed.append(topic.model_dump())
    topics = _visible_topics(conn, parsed, scope)
    try:
        coverage = EmergingTopicCoverage.model_validate(snapshot.get("coverage"))
    except (TypeError, ValidationError):
        coverage = None
    return EmergingTopicListResponse(
        topics=[EmergingCitingTopicOut(**topic) for topic in topics],
        computed_at=str(snapshot["computed_at"]),
        coverage=coverage,
        scope=scope_out,
    )


@router.post(
    "/my-publications/emerging-citing-topics/refresh",
    response_model=EmergingTopicRefreshResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def refresh_emerging_citing_topics(
    payload: EmergingTopicRefreshRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> EmergingTopicRefreshResponse:
    scope = _resolve_scope_or_422(conn, payload.domain_keys)
    job_id = request.app.state.my_publication_topic_jobs.create()
    background_tasks.add_task(_run_refresh, request.app, job_id, scope)
    return EmergingTopicRefreshResponse(job_id=job_id, status="pending")


@router.get(
    "/my-publications/emerging-citing-topics/refresh/{job_id}",
    response_model=EmergingTopicRefreshResponse,
)
def emerging_citing_topic_refresh_status(job_id: str, request: Request) -> EmergingTopicRefreshResponse:
    job = request.app.state.my_publication_topic_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Emerging-topic refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return EmergingTopicRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_refresh(app: FastAPI, job_id: str, scope: CitationGapScope) -> None:
    jobs: JobStore[EmergingTopicRefreshResponse] = app.state.my_publication_topic_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        base_client = app.state.openalex_client or OpenAlexClient()
        fetch_client = (
            base_client.with_cache_engine(engine) if hasattr(base_client, "with_cache_engine") else base_client
        )
        topic_client = app.state.openalex_citing_topics_client
        if topic_client is None:
            topic_client = OpenAlexCitingTopicsClient(base_client)
        fetch_topic_client = (
            topic_client.with_cache_engine(engine) if hasattr(topic_client, "with_cache_engine") else topic_client
        )
        computed_at = datetime.now(timezone.utc).isoformat()
        with engine.connect() as conn:
            topics, coverage = compute_emerging_citing_topics(
                conn,
                openalex_client=fetch_client,
                topic_client=fetch_topic_client,
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
            lambda conn: replace_emerging_topic_cache(
                conn,
                topics,
                coverage,
                computed_at=computed_at,
                scope_key=scope.key,
                scope=scope.to_dict(),
            ),
        )
        result = EmergingTopicRefreshResult(
            count=len(topics),
            coverage=EmergingTopicCoverage(**coverage),
            computed_at=computed_at,
            scope=_scope_out(scope),
        )
        jobs.mark_done(job_id, EmergingTopicRefreshResponse(job_id=job_id, status="done", result=result))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")


def _visible_topics(
    conn: Connection,
    topics: list[dict[str, Any]],
    scope: CitationGapScope,
) -> list[dict[str, Any]]:
    allowed_ids = {int(row["id"]) for row in confirmed_member_rows(conn)}
    if scope.paper_ids is not None:
        allowed_ids &= set(scope.paper_ids)
    visible: list[dict[str, Any]] = []
    for topic in topics:
        periods: dict[str, list[dict[str, Any]]] = {}
        for period in ("recent", "previous"):
            works = []
            for work in topic.get(f"{period}_works") or []:
                work_id = str(work.get("openalex_work_id") or "")
                if re.fullmatch(r"W\d+", work_id) is None:
                    continue
                sources = [
                    source
                    for source in (work.get("cited_publications") or [])
                    if _positive_int(source.get("paper_id")) in allowed_ids
                ]
                if sources:
                    works.append({**work, "cited_publications": sources})
            periods[period] = works
        recent_count = len(periods["recent"])
        previous_count = len(periods["previous"])
        if recent_count < MIN_RECENT_WORKS or recent_count <= previous_count:
            continue
        visible.append(
            {
                **topic,
                "recent_count": recent_count,
                "previous_count": previous_count,
                "increase": recent_count - previous_count,
                "recent_works": periods["recent"],
                "previous_works": periods["previous"],
            }
        )
    visible.sort(
        key=lambda topic: (
            -int(topic["increase"]),
            -int(topic["recent_count"]),
            str(topic.get("name") or "").casefold(),
            str(topic.get("topic_id") or ""),
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


def _scope_out(scope: CitationGapScope) -> EmergingTopicScopeOut:
    return EmergingTopicScopeOut(
        kind=scope.kind,
        domain_keys=list(scope.domain_keys),
        domain_labels=list(scope.domain_labels),
    )
