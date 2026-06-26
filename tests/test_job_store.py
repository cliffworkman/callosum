"""inc 142 — JobStore determinate progress (the migrator's "X of N" + fill bar)."""

from __future__ import annotations

from app.backend.api.job_store import JobStore


def test_mark_progress_sets_running_with_determinate_progress() -> None:
    store: JobStore = JobStore()
    job_id = store.create()
    store.mark_progress(job_id, 3, 10, "Embedding papers")
    job = store.get(job_id)
    assert job is not None and job.status == "running"
    assert job.progress is not None
    assert (job.progress.current, job.progress.total, job.progress.label) == (3, 10, "Embedding papers")


def test_done_and_error_carry_no_progress() -> None:
    store: JobStore = JobStore()
    job_id = store.create()
    store.mark_progress(job_id, 5, 5, "x")  # mid-run progress …
    store.mark_done(job_id, {"ok": True})  # … is cleared once the job finishes
    done = store.get(job_id)
    assert done is not None and done.status == "done" and done.progress is None

    other = store.create()
    store.mark_error(other, "boom")
    err = store.get(other)
    assert err is not None and err.status == "error" and err.progress is None
