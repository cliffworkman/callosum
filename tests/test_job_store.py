"""inc 142 — JobStore determinate progress (the migrator's "X of N" + fill bar)."""

from __future__ import annotations

import time

from app.backend.api.job_store import Job, JobProgress, JobStore


def test_mark_progress_sets_running_with_determinate_progress() -> None:
    store: JobStore = JobStore()
    job_id = store.create()
    store.mark_progress(job_id, 3, 10, "Embedding papers")
    job = store.get(job_id)
    assert job is not None and job.status == "running"
    assert job.progress is not None
    assert (job.progress.current, job.progress.total, job.progress.label) == (3, 10, "Embedding papers")


def test_mark_done_carries_forward_the_last_known_progress() -> None:
    # inc 406: previously mark_done discarded progress entirely — a finished job's row couldn't say what it
    # was partway through. Now it's preserved unless a caller passes a different snapshot explicitly.
    store: JobStore = JobStore()
    job_id = store.create()
    store.mark_progress(job_id, 5, 5, "x")
    store.mark_done(job_id, {"ok": True})
    done = store.get(job_id)
    assert done is not None and done.status == "done"
    assert done.progress is not None and (done.progress.current, done.progress.total) == (5, 5)
    assert done.finished_at is not None


def test_mark_done_accepts_an_explicit_progress_override() -> None:
    store: JobStore = JobStore()
    job_id = store.create()
    store.mark_progress(job_id, 5, 5, "x")
    override = JobProgress(current=1, total=1, label="final tally")
    store.mark_done(job_id, {"ok": True}, progress=override)
    assert store.get(job_id).progress == override


def test_mark_error_carries_no_progress_but_stamps_finished_at() -> None:
    store: JobStore = JobStore()
    other = store.create()
    store.mark_progress(other, 5, 5, "x")
    store.mark_error(other, "boom")
    err = store.get(other)
    assert err is not None and err.status == "error" and err.progress is None
    assert err.finished_at is not None


def test_started_at_is_stamped_once_and_preserved_across_progress() -> None:
    # inc 225: the ETA measures from when the job began running — started_at is set on mark_running and carried
    # through every mark_progress (not reset each tick).
    store: JobStore = JobStore()
    job_id = store.create()
    assert store.get(job_id).started_at is None  # pending, not started
    store.mark_running(job_id)
    t0 = store.get(job_id).started_at
    assert t0 is not None
    store.mark_progress(job_id, 1, 10, "x")
    store.mark_progress(job_id, 2, 10, "x")
    assert store.get(job_id).started_at == t0  # preserved across ticks


def test_eta_seconds_extrapolates_remaining() -> None:
    # eta = elapsed / current * remaining. Construct a Job directly with a known started_at so it's deterministic.
    started = time.monotonic() - 10.0  # 10s elapsed
    job = Job(status="running", progress=JobProgress(current=2, total=10, label="x"), started_at=started)
    eta = job.eta_seconds()
    assert eta is not None and 35 <= eta <= 45  # ~10s for 2 → ~40s for the remaining 8

    # None until there's a started_at + ≥1 unit of progress; 0 once complete.
    assert Job(status="running", started_at=started).eta_seconds() is None  # no progress yet
    assert Job(status="running", progress=JobProgress(0, 10, "x"), started_at=started).eta_seconds() is None
    assert Job(status="running", progress=JobProgress(10, 10, "x"), started_at=started).eta_seconds() == 0
    assert Job(status="running", progress=JobProgress(1, 5, "x")).eta_seconds() is None  # no started_at
