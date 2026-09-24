"""App-scoped capture invalidation, following JobStore's bounded async-wait pattern.

Only an opaque revision crosses this endpoint. Queue/paper GETs remain authoritative. The
current single-worker launch contract is required, as for JobStore; no DB connection is held.
"""

from __future__ import annotations

import asyncio
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


class CaptureUpdates:
    def __init__(self) -> None:
        self._lock = Lock()
        self._revision = uuid4().hex  # Restart cannot reuse a client's last revision.
        self._waiters: list[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = []

    @property
    def revision(self) -> str:
        with self._lock:
            return self._revision

    def changed(self) -> None:
        with self._lock:
            self._revision = uuid4().hex
            waiters, self._waiters = self._waiters, []
        for loop, event in waiters:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:  # Disconnected client's loop closed; the revision persists.
                pass

    async def wait(self, after: str, seconds: float) -> str:
        waiter = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            if after != self._revision or seconds <= 0:
                return self._revision
            if len(self._waiters) >= 64:
                raise HTTPException(status_code=503, detail="Too many capture update observers.")
            self._waiters.append(waiter)
        try:
            try:
                await asyncio.wait_for(waiter[1].wait(), timeout=seconds)
            except TimeoutError:
                pass
        finally:
            with self._lock:
                self._waiters = [item for item in self._waiters if item is not waiter]
        return self.revision


@router.get("/library/capture-updates")
async def capture_updates(
    request: Request,
    after: str = Query(default="", max_length=32, pattern=r"^[a-f0-9]*$"),
    wait_seconds: float = Query(default=20, ge=0, le=25),
) -> dict[str, str]:
    return {"revision": await request.app.state.capture_updates.wait(after, wait_seconds)}
