"""Generic in-memory async-job store shared by the router job subsystems.

The async endpoints (summarize, axis score, axis suggest, duplicate scan) all follow the same
pattern: a POST starts a background job and returns a job id; a GET polls its status. Each router
used to carry a near-identical ``_XJob`` dataclass + ``_XJobStore`` class differing only in the
result type — this consolidates them into one generic, thread-safe store (Phase 5 dedup).

Ephemeral + process-local: jobs live in memory and a restart clears them, which is fine for the
single-user local app (the work is re-runnable).
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Generic, Literal, TypeVar
from uuid import uuid4

JobStatus = Literal["pending", "running", "done", "error"]
R = TypeVar("R")


@dataclass(frozen=True)
class JobProgress:
    """Determinate progress for a long-running job (inc 142) — so the UI shows "Embedding 184 / 412" + a fill bar
    instead of an opaque pulse. Optional: a job that doesn't report progress just stays indeterminate."""

    current: int
    total: int
    label: str


@dataclass(frozen=True)
class Job(Generic[R]):
    status: JobStatus
    result: R | None = None
    detail: str | None = None
    progress: JobProgress | None = None


class JobStore(Generic[R]):
    """Thread-safe ``job_id`` → :class:`Job` map for one async-job subsystem."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job[R]] = {}
        self._lock = Lock()

    def create(self) -> str:
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = Job(status="pending")
        return job_id

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            self._jobs[job_id] = Job(status="running")

    def mark_progress(self, job_id: str, current: int, total: int, label: str) -> None:
        """Update a running job's determinate progress (inc 142). Cheap + frequent (per item); the UI polls it."""
        with self._lock:
            self._jobs[job_id] = Job(status="running", progress=JobProgress(current=current, total=total, label=label))

    def mark_done(self, job_id: str, result: R) -> None:
        with self._lock:
            self._jobs[job_id] = Job(status="done", result=result)

    def mark_error(self, job_id: str, detail: str) -> None:
        with self._lock:
            self._jobs[job_id] = Job(status="error", detail=detail)

    def get(self, job_id: str) -> Job[R] | None:
        with self._lock:
            return self._jobs.get(job_id)
