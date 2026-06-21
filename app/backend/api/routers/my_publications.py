"""My Publications endpoints (inc 78) — the user's own-papers axis.

A profile (name/variants/ORCID), an async **refresh** that resolves the identity via OpenAlex and (re)writes
the pinned ``kind="my_publications"`` axis, a **decide** (confirm/reject a candidate, persisted), and a
**delete** (dismiss the card without losing the profile/decisions). LLM-free; OpenAlex is metadata egress, not
the Gemini gate.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import Connection, delete
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.clustering.axis_assignments import add_manual_assignment, remove_assignment
from app.backend.clustering.my_publications import _get_axis_id, resolve_my_publications
from app.backend.persistence.profile_repo import (
    get_profile,
    set_decision,
    set_my_publications_dismissed,
    upsert_profile,
)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.schema import axes
from integrations.openalex import OpenAlexAuthorClient

router = APIRouter()


class ProfileResponse(BaseModel):
    display_name: str | None = None
    name_variants: list[str] = []
    orcid: str | None = None
    has_author_id: bool = False
    dismissed: bool = False


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    name_variants: list[str] = []
    orcid: str | None = None


class MyPubsSummary(BaseModel):
    status: str
    name: str | None = None
    matched_by: str | None = None
    indexed_works: int | None = None
    in_library: int | None = None
    confirmed: int | None = None
    candidates: int | None = None
    axis_id: int | None = None


class RefreshJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary: MyPubsSummary | None = None


class DecideRequest(BaseModel):
    paper_id: int
    decision: Literal["confirmed", "rejected"]


@router.get("/my-publications/profile", response_model=ProfileResponse)
def get_my_publications_profile(conn: Connection = Depends(get_connection)) -> ProfileResponse:
    return _profile_response(get_profile(conn))


@router.put("/my-publications/profile", response_model=ProfileResponse)
def put_my_publications_profile(
    payload: ProfileUpdateRequest, conn: Connection = Depends(get_connection)
) -> ProfileResponse:
    profile = upsert_profile(
        conn, display_name=payload.display_name, name_variants=payload.name_variants, orcid=payload.orcid
    )
    conn.commit()
    return _profile_response(profile)


@router.post("/my-publications/refresh", response_model=RefreshJobResponse, status_code=http_status.HTTP_202_ACCEPTED)
def refresh_my_publications(background_tasks: BackgroundTasks, request: Request) -> RefreshJobResponse:
    # Async: resolving + paginating a prolific author's works is slow. A manual refresh clears the dismissed flag.
    job_id = request.app.state.mypubs_jobs.create()
    background_tasks.add_task(_run_refresh_job, request.app, job_id)
    return RefreshJobResponse(job_id=job_id, status="pending")


@router.get("/my-publications/refresh/{job_id}", response_model=RefreshJobResponse)
def refresh_my_publications_status(job_id: str, request: Request) -> RefreshJobResponse:
    job = request.app.state.mypubs_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return RefreshJobResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.post("/my-publications/decide", status_code=http_status.HTTP_204_NO_CONTENT)
def decide_my_publications(payload: DecideRequest, conn: Connection = Depends(get_connection)) -> Response:
    try:
        get_paper(conn, payload.paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    set_decision(conn, payload.paper_id, payload.decision)
    axis_id = _get_axis_id(conn)
    if axis_id is not None:
        if payload.decision == "confirmed":
            add_manual_assignment(conn, axis_id=int(axis_id), paper_id=payload.paper_id)  # → manual member (NULL)
        else:
            remove_assignment(conn, axis_id=int(axis_id), paper_id=payload.paper_id)  # drop the rejected candidate
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.delete("/my-publications", status_code=http_status.HTTP_204_NO_CONTENT)
def dismiss_my_publications(conn: Connection = Depends(get_connection)) -> Response:
    # Dismiss the card (the deleted-don't-auto-regenerate flag) + remove the axis (CASCADE clears memberships).
    # The profile + decisions survive; a manual refresh clears the flag and rebuilds.
    set_my_publications_dismissed(conn, True)
    axis_id = _get_axis_id(conn)
    if axis_id is not None:
        conn.execute(delete(axes).where(axes.c.id == int(axis_id)))
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


def _profile_response(profile: dict[str, Any] | None) -> ProfileResponse:
    if not profile:
        return ProfileResponse()
    return ProfileResponse(
        display_name=profile.get("display_name"),
        name_variants=list(profile.get("name_variants") or []),
        orcid=profile.get("orcid"),
        has_author_id=bool(profile.get("openalex_author_id")),
        dismissed=bool(profile.get("my_publications_dismissed")),
    )


def _author_client(app: FastAPI) -> OpenAlexAuthorClient:
    injected = app.state.openalex_author_client
    return injected if injected is not None else OpenAlexAuthorClient()


def _run_refresh_job(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[RefreshJobResponse] = app.state.mypubs_jobs
    jobs.mark_running(job_id)
    try:
        client = _author_client(app)
        with app.state.engine.begin() as conn:  # resolve writes the openalex_* cache within the txn
            set_my_publications_dismissed(conn, False)  # a manual refresh un-dismisses
            summary = resolve_my_publications(conn, author_client=client, force=True)
        jobs.mark_done(job_id, RefreshJobResponse(job_id=job_id, status="done", summary=MyPubsSummary(**summary)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
