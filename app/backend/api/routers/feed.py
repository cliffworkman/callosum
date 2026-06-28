"""Literature Feed endpoints (backlog #28 SP2, inc 187): subscription CRUD + an async refresh (poll the followed
sources) + the item list with read/starred state. Pull-only, opt-in — nothing auto-subscribes, nothing pushes.
Public-metadata polling (bioRxiv now) — NOT the Gemini gate. Save reuses /discovery/save (metadata-only, no PDF)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.api.job_store import JobStore
from app.backend.discovery.feed import feed_view, refresh_subscriptions
from app.backend.persistence import feed_repo

router = APIRouter()


class SubscriptionRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=500)
    label: str | None = Field(default=None, max_length=300)


@router.get("/feed/subscriptions")
def list_subscriptions(request: Request, conn: Connection = Depends(get_connection)) -> dict[str, Any]:
    subs = [
        {
            "id": int(s["id"]),
            "kind": s["kind"],
            "value": s["value"],
            "label": s["label"],
            "last_polled_at": s["last_polled_at"].isoformat() if s["last_polled_at"] else None,
        }
        for s in feed_repo.list_subscriptions(conn)
    ]
    return {"subscriptions": subs, "kinds": request.app.state.feed_registry.kinds}


@router.post("/feed/subscriptions")
def add_subscription(
    payload: SubscriptionRequest, request: Request, conn: Connection = Depends(get_connection)
) -> dict[str, Any]:
    if payload.kind not in request.app.state.feed_registry.kinds:
        raise HTTPException(status_code=422, detail=f"Unknown feed source kind: {payload.kind}")
    row = feed_repo.add_subscription(conn, kind=payload.kind, value=payload.value.strip(), label=payload.label)
    conn.commit()
    return {"id": int(row["id"]), "kind": row["kind"], "value": row["value"], "label": row["label"]}


@router.delete("/feed/subscriptions/{sub_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def remove_subscription(sub_id: int, conn: Connection = Depends(get_connection)) -> Response:
    feed_repo.remove_subscription(conn, sub_id)  # idempotent — deleting a gone subscription is a no-op
    conn.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


class FeedRefreshResult(BaseModel):
    subscriptions: int = 0
    new_items: int = 0


class FeedRefreshResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    result: FeedRefreshResult | None = None


@router.post("/feed/refresh", response_model=FeedRefreshResponse, status_code=http_status.HTTP_202_ACCEPTED)
def feed_refresh(background_tasks: BackgroundTasks, request: Request) -> FeedRefreshResponse:
    job_id = request.app.state.feed_jobs.create()
    background_tasks.add_task(_run_feed_refresh, request.app, job_id)
    return FeedRefreshResponse(job_id=job_id, status="pending")


@router.get("/feed/refresh/{job_id}", response_model=FeedRefreshResponse)
def feed_refresh_status(job_id: str, request: Request) -> FeedRefreshResponse:
    job = request.app.state.feed_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Feed refresh job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return FeedRefreshResponse(job_id=job_id, status=job.status, detail=job.detail)


@router.get("/feed")
def feed_items(
    unread: bool = Query(default=False),
    starred: bool = Query(default=False),
    subscription_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    conn: Connection = Depends(get_connection),
) -> dict[str, Any]:
    items = feed_view(conn, unread_only=unread, starred_only=starred, subscription_id=subscription_id, limit=limit)
    return {"items": items, "unread_count": feed_repo.unread_count(conn)}


class ItemStateRequest(BaseModel):
    is_read: bool | None = None
    is_starred: bool | None = None


@router.post("/feed/items/{item_id}/state")
def set_item_state(
    item_id: int, payload: ItemStateRequest, conn: Connection = Depends(get_connection)
) -> dict[str, Any]:
    changed = feed_repo.set_item_state(conn, item_id, is_read=payload.is_read, is_starred=payload.is_starred)
    if not changed:
        raise HTTPException(status_code=404, detail="Feed item not found (or no state change requested)")
    conn.commit()
    return {"id": item_id, "changed": True}


class MarkReadRequest(BaseModel):
    subscription_id: int | None = None


@router.post("/feed/mark-read")
def mark_read(payload: MarkReadRequest, conn: Connection = Depends(get_connection)) -> dict[str, Any]:
    marked = feed_repo.mark_all_read(conn, subscription_id=payload.subscription_id)
    conn.commit()
    return {"marked": marked}


def _run_feed_refresh(app: FastAPI, job_id: str) -> None:
    jobs: JobStore[FeedRefreshResponse] = app.state.feed_jobs
    jobs.mark_running(job_id)
    try:
        with app.state.engine.begin() as conn:
            counts = refresh_subscriptions(conn, app.state.feed_registry)
        result = FeedRefreshResult(subscriptions=counts["subscriptions"], new_items=counts["new_items"])
        jobs.mark_done(job_id, FeedRefreshResponse(job_id=job_id, status="done", result=result))
    except Exception as exc:  # noqa: BLE001
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
