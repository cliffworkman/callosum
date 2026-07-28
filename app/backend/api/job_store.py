"""Generic in-memory async-job store shared by the router job subsystems.

The async endpoints (summarize, axis score, axis suggest, duplicate scan) all follow the same
pattern: a POST starts a background job and returns a job id; a GET polls its status. Each router
used to carry a near-identical ``_XJob`` dataclass + ``_XJobStore`` class differing only in the
result type — this consolidates them into one generic, thread-safe store (Phase 5 dedup).

Ephemeral + process-local: jobs live in memory and a restart clears them, which is fine for the
single-user local app (the work is re-runnable).
"""

from __future__ import annotations

import time
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
    started_at: float | None = None  # monotonic clock when the job began running (inc 225 — for the ETA)
    finished_at: float | None = None  # monotonic clock when the job reached done/error (inc 406 — for expiry)

    def eta_seconds(self) -> int | None:
        """Rough seconds-remaining = elapsed-so-far × the remaining fraction (inc 225). None until there's both a
        `started_at` and ≥1 unit of progress; 0 once complete. A linear estimate, shown as "~Ns left" — not a promise."""
        p = self.progress
        if self.started_at is None or p is None or p.current <= 0:
            return None
        remaining = p.total - p.current
        if remaining <= 0:
            return 0
        return int((time.monotonic() - self.started_at) / p.current * remaining)


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
            self._jobs[job_id] = Job(status="running", started_at=self._started_at(job_id))

    def mark_progress(self, job_id: str, current: int, total: int, label: str) -> None:
        """Update a running job's determinate progress (inc 142). Cheap + frequent (per item); the UI polls it.
        Preserves the job's `started_at` (inc 225) so the ETA measures from when the job began, not the last tick."""
        with self._lock:
            self._jobs[job_id] = Job(
                status="running",
                progress=JobProgress(current=current, total=total, label=label),
                started_at=self._started_at(job_id),
            )

    def _started_at(self, job_id: str) -> float:
        """The job's existing start time, else now (caller holds the lock)."""
        prev = self._jobs.get(job_id)
        return prev.started_at if prev is not None and prev.started_at is not None else time.monotonic()

    def mark_done(self, job_id: str, result: R, progress: JobProgress | None = None) -> None:
        """Marks a job complete. Preserves the job's last known progress (e.g. a final "142 / 142") unless a
        different snapshot is passed — previously this always discarded it, which meant a finished job's row
        had no memory of what it was partway through (inc 406, for the cross-feature Status popover)."""
        with self._lock:
            prev = self._jobs.get(job_id)
            final_progress = progress if progress is not None else (prev.progress if prev is not None else None)
            self._jobs[job_id] = Job(
                status="done",
                result=result,
                progress=final_progress,
                started_at=prev.started_at if prev is not None else None,
                finished_at=time.monotonic(),
            )

    def mark_error(self, job_id: str, detail: str) -> None:
        with self._lock:
            prev = self._jobs.get(job_id)
            self._jobs[job_id] = Job(
                status="error",
                detail=detail,
                started_at=prev.started_at if prev is not None else None,
                finished_at=time.monotonic(),
            )

    def get(self, job_id: str) -> Job[R] | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_all(self) -> list[tuple[str, Job[R]]]:
        """Thread-safe snapshot of every job in this store (inc 406 — the cross-feature status aggregator)."""
        with self._lock:
            return list(self._jobs.items())

    def dismiss(self, job_id: str) -> bool:
        """Removes a job the user has acknowledged. Returns whether it existed (inc 406)."""
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def prune_finished_older_than(self, seconds: float) -> None:
        """Drops done/error jobs whose finished_at is older than `seconds` ago — a lazy sweep-on-read backstop
        against unbounded growth in a long session, on top of the user's own explicit dismiss (inc 406)."""
        cutoff = time.monotonic() - seconds
        with self._lock:
            stale = [jid for jid, job in self._jobs.items() if job.finished_at is not None and job.finished_at < cutoff]
            for jid in stale:
                del self._jobs[jid]
