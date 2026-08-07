"""Followed authors — a lightweight OpenAlex-author subscription that feeds gap-finder (backlog #29, inc 454).

Follow an author (by name/ORCID, or directly from an already-resolved id, e.g. the My-Publications citing-authors
panel); Refresh fetches their works (cached, bounded) and surfaces those absent from the library, "by <author>
(followed)". GET reads are cache-only (zero egress); only the explicit Refresh job calls OpenAlex. Add/Dismiss
reuse gap-finder's own metadata-import path and its shared `profile.dismissed_gap_works` list — one dismissal
domain across both sources, since a dismissal is about the work, not which generator re-derived it.

inc 455: follow/unfollow here also keeps a matching `feed_subscriptions` row (kind="followed_author") in sync,
so the SAME author's works also flow into the chronological Feed (Discover → Feed), not just this dedicated
"what am I missing" list — two purpose-built reads of one underlying "I follow this author" fact. The reverse
sync (unfollowing via Feed's own subscription chip) lives in `routers/feed.py::remove_subscription`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.api.job_store import JobStore
from app.backend.clustering.followed_authors import (
    FOLLOWED_AUTHOR_MAX_CANDIDATES,
    FOLLOWED_AUTHOR_NOTE,
    compute_followed_author_candidates,
)
from app.backend.clustering.my_publications import import_citing_work
from app.backend.persistence import feed_repo
from app.backend.persistence.followed_author_repo import (
    add_followed_author,
    get_followed_author,
    list_followed_authors,
    read_followed_author_candidates,
    remove_followed_author,
    replace_followed_author_candidates,
    set_last_refreshed,
)
from app.backend.persistence.profile_repo import dismiss_gap, dismissed_gaps
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.sqlite_retry import run_write
from integrations.openalex import OpenAlexAuthorClient

router = APIRouter()

MAX_FOLLOW_NAME_LEN = 300
_AUTHOR_ID_RE = re.compile(r"^A\d+$")


class FollowedAuthorOut(BaseModel):
    author_id: str
    display_name: str
    orcid: str | None = None
    matched_by: str
    last_refreshed_at: str | None = None


@router.get("/followed-authors", response_model=list[FollowedAuthorOut])
def followed_authors_list(conn: Connection = Depends(get_connection)) -> list[FollowedAuthorOut]:
    return [FollowedAuthorOut(**row) for row in list_followed_authors(conn)]


class FollowRequest(BaseModel):
    author_id: str | None = None  # direct add (already-resolved, e.g. from a citing-authors card)
    display_name: str | None = None  # required with author_id
    name: str | None = Field(default=None, max_length=MAX_FOLLOW_NAME_LEN)
    orcid: str | None = Field(default=None, max_length=64)


class FollowResponse(BaseModel):
    status: Literal["followed", "already-following", "no-match"]
    author: FollowedAuthorOut | None = None


@router.post("/followed-authors", response_model=FollowResponse)
def follow_author(payload: FollowRequest, request: Request, engine: Engine = Depends(get_engine)) -> FollowResponse:
    if payload.author_id:
        if not _AUTHOR_ID_RE.fullmatch(payload.author_id):
            raise HTTPException(status_code=422, detail="author_id must be a bare OpenAlex id (e.g. A5023888391).")
        if not (payload.display_name or "").strip():
            raise HTTPException(status_code=422, detail="display_name is required with a direct author_id.")
        if len(payload.display_name) > MAX_FOLLOW_NAME_LEN:
            raise HTTPException(status_code=422, detail=f"display_name exceeds {MAX_FOLLOW_NAME_LEN} characters.")

        def _do_direct(conn: Connection) -> FollowResponse:
            existing = get_followed_author(conn, payload.author_id)
            row = add_followed_author(
                conn, author_id=payload.author_id, display_name=payload.display_name, orcid=None, matched_by="direct"
            )
            feed_repo.add_subscription(conn, kind="followed_author", value=row["author_id"], label=row["display_name"])
            return FollowResponse(
                status="already-following" if existing else "followed", author=FollowedAuthorOut(**row)
            )

        return run_write(engine, _do_direct)

    if not (payload.name or "").strip() and not (payload.orcid or "").strip():
        raise HTTPException(status_code=422, detail="A name or ORCID is required to follow an author.")

    def _do_resolve(conn: Connection) -> FollowResponse:
        author = _author_client(request.app).resolve_author(conn, orcid=payload.orcid, name=payload.name)
        if author is None:
            return FollowResponse(status="no-match")
        existing = get_followed_author(conn, author.author_id)
        row = add_followed_author(
            conn,
            author_id=author.author_id,
            display_name=author.display_name,
            orcid=author.orcid,
            matched_by=author.matched_by,
        )
        feed_repo.add_subscription(conn, kind="followed_author", value=row["author_id"], label=row["display_name"])
        return FollowResponse(status="already-following" if existing else "followed", author=FollowedAuthorOut(**row))

    return run_write(engine, _do_resolve)


@router.delete("/followed-authors/{author_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def unfollow_author(author_id: str, engine: Engine = Depends(get_engine)) -> Response:
    if not _AUTHOR_ID_RE.fullmatch(author_id):
        raise HTTPException(status_code=422, detail="Invalid author id.")

    def _do(conn: Connection) -> Response:
        remove_followed_author(conn, author_id)  # no-op if not followed -- idempotent, mirrors Feed's unfollow
        sub = feed_repo.find_subscription(conn, kind="followed_author", value=author_id)
        if sub is not None:
            feed_repo.remove_subscription(conn, int(sub["id"]))
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


class FollowedAuthorCandidateOut(BaseModel):
    author_id: str
    author_display_name: str | None = None
    openalex_work_id: str | None = None
    doi: str | None = None
    title: str | None = None
    year: int | None = None
    cited_by_count: int = 0


class FollowedAuthorCandidatesResponse(BaseModel):
    candidates: list[FollowedAuthorCandidateOut] = []


@router.get("/followed-authors/candidates", response_model=FollowedAuthorCandidatesResponse)
def followed_author_candidates_list(conn: Connection = Depends(get_connection)) -> FollowedAuthorCandidatesResponse:
    rows = read_followed_author_candidates(conn)
    dismissed = dismissed_gaps(conn)
    out: list[FollowedAuthorCandidateOut] = []
    for row in rows:  # filter at read time, exactly like GET /gaps -- Add/Dismiss take effect without a recompute
        if (row["openalex_work_id"] and row["openalex_work_id"] in dismissed) or (
            row["doi"] and row["doi"] in dismissed
        ):
            continue
        if row["doi"] and find_existing_paper_by_identity(conn, doi=row["doi"]) is not None:
            continue
        out.append(FollowedAuthorCandidateOut(**row))
    return FollowedAuthorCandidatesResponse(candidates=out)


class FollowedAuthorRefreshRequest(BaseModel):
    author_id: str | None = None  # omit/null = refresh every followed author in one job


class FollowedAuthorRefreshResult(BaseModel):
    authors_refreshed: int = 0
    works_checked: int = 0
    count: int = 0
    note: str = ""


class FollowedAuthorRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: FollowedAuthorRefreshResult | None = None


@router.post(
    "/followed-authors/refresh", response_model=FollowedAuthorRefreshResponse, status_code=http_status.HTTP_202_ACCEPTED
)
def followed_authors_refresh(
    payload: FollowedAuthorRefreshRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: Connection = Depends(get_connection),
) -> FollowedAuthorRefreshResponse:
    if payload.author_id and get_followed_author(conn, payload.author_id) is None:
        raise HTTPException(status_code=404, detail="Followed author not found")
    job_id = request.app.state.followed_author_jobs.create()
    background_tasks.add_task(_run_followed_author_refresh, request.app, job_id, payload.author_id)
    return FollowedAuthorRefreshResponse(job_id=job_id, status="pending")


@router.get("/followed-authors/refresh/{job_id}", response_model=FollowedAuthorRefreshResponse)
def followed_authors_refresh_status(job_id: str, request: Request) -> FollowedAuthorRefreshResponse:
    job = request.app.state.followed_author_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Followed-authors refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return FollowedAuthorRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


class FollowedAuthorAddRequest(BaseModel):
    doi: str
    openalex_work_id: str | None = None
    title: str | None = None


class FollowedAuthorAddResponse(BaseModel):
    status: str  # imported | exists | invalid
    paper_id: int | None = None


@router.post("/followed-authors/add", response_model=FollowedAuthorAddResponse)
def followed_authors_add(
    payload: FollowedAuthorAddRequest, request: Request, engine: Engine = Depends(get_engine)
) -> FollowedAuthorAddResponse:
    def _do(conn: Connection) -> FollowedAuthorAddResponse:
        result = import_citing_work(
            conn,
            doi=payload.doi,
            openalex_work_id=payload.openalex_work_id,
            title=payload.title,
            crossref_client=request.app.state.crossref_client,
            imported_source="followed-author-import",
        )
        if result.get("status") == "invalid":
            raise HTTPException(status_code=422, detail="A DOI is required to add a followed-author candidate.")
        return FollowedAuthorAddResponse(status=str(result.get("status")), paper_id=result.get("paper_id"))

    return run_write(engine, _do)


class FollowedAuthorDismissRequest(BaseModel):
    openalex_work_id: str | None = None
    doi: str | None = None


@router.post("/followed-authors/dismiss", status_code=http_status.HTTP_204_NO_CONTENT)
def followed_authors_dismiss(payload: FollowedAuthorDismissRequest, engine: Engine = Depends(get_engine)) -> Response:
    def _do(conn: Connection) -> Response:
        for key in (payload.openalex_work_id, payload.doi):
            if key:
                dismiss_gap(conn, key)  # SAME list as /gaps/dismiss -- source-agnostic by design
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    return run_write(engine, _do)


def _author_client(app: FastAPI) -> OpenAlexAuthorClient:
    injected = app.state.openalex_author_client
    return injected if injected is not None else OpenAlexAuthorClient()


def _run_followed_author_refresh(app: FastAPI, job_id: str, author_id: str | None) -> None:
    jobs: JobStore[FollowedAuthorRefreshResponse] = app.state.followed_author_jobs
    jobs.mark_running(job_id)
    try:
        engine = app.state.engine
        client = _author_client(app)
        # inc D: fetches run on a READ connection with the client caching self-committingly, so they never hold
        # the write lock; the final batch persist is one short run_write.
        fetch_client = client.with_cache_engine(engine) if hasattr(client, "with_cache_engine") else client
        computed_at = datetime.now(timezone.utc).isoformat()
        with engine.connect() as conn:
            targets = [
                t for t in ([get_followed_author(conn, author_id)] if author_id else list_followed_authors(conn)) if t
            ]
            dismissed = dismissed_gaps(conn)
            per_author: list[tuple[str, list, int]] = []
            for row in targets:
                candidates, coverage = compute_followed_author_candidates(
                    conn,
                    author_client=fetch_client,
                    author_id=row["author_id"],
                    author_display_name=row["display_name"],
                    dismissed=dismissed,
                    max_candidates=FOLLOWED_AUTHOR_MAX_CANDIDATES,
                )
                per_author.append((row["author_id"], candidates, coverage["works_checked"]))

        def _persist(conn: Connection) -> None:
            for aid, candidates, _checked in per_author:
                replace_followed_author_candidates(conn, aid, candidates, computed_at=computed_at)
                set_last_refreshed(conn, aid, refreshed_at=computed_at)

        run_write(engine, _persist)
        result = FollowedAuthorRefreshResult(
            authors_refreshed=len(per_author),
            works_checked=sum(c for _, _, c in per_author),
            count=sum(len(c) for _, c, _ in per_author),
            note=FOLLOWED_AUTHOR_NOTE,
        )
        jobs.mark_done(job_id, FollowedAuthorRefreshResponse(job_id=job_id, status="done", result=result))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
