"""Followed authors — a lightweight OpenAlex-author subscription (backlog #29, inc 454; consolidated
into Discover -> Feed, dropping the standalone tab's gap-candidate view, 2026-08-27).

Follow an author (by name/ORCID, or directly from an already-resolved id, e.g. the My-Publications citing-authors
panel, or Feed's own "Author" add-source option). GET reads are cache-only (zero egress); resolving a name/ORCID
is the only call that reaches OpenAlex.

inc 455: follow/unfollow here also keeps a matching `feed_subscriptions` row (kind="followed_author") in sync,
so the SAME author's works flow into the chronological Feed (Discover → Feed) via `FollowedAuthorFeedSource` —
this router's whole remaining job is just "the follow/unfollow primitive," not a second content surface. The
reverse sync (unfollowing via Feed's own subscription chip) lives in `routers/feed.py::remove_subscription`.
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app.backend.api.dependencies import get_connection, get_engine
from app.backend.persistence import feed_repo
from app.backend.persistence.followed_author_repo import (
    add_followed_author,
    get_followed_author,
    list_followed_authors,
    remove_followed_author,
)
from app.backend.persistence.sqlite_retry import run_write
from app.backend.researcher_identity import InvalidOrcid, normalize_orcid
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
    try:
        canonical_orcid = normalize_orcid(payload.orcid)
    except InvalidOrcid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    def _do_resolve(conn: Connection) -> FollowResponse:
        author = _author_client(request.app).resolve_author(conn, orcid=canonical_orcid, name=payload.name)
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


def _author_client(app: FastAPI) -> OpenAlexAuthorClient:
    injected = app.state.openalex_author_client
    return injected if injected is not None else OpenAlexAuthorClient()
