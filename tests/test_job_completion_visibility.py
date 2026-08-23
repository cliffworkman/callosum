"""Long-poll completion notification for model-backed JobStore workflows."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.api.job_store import JobStore

Waiter = tuple[asyncio.AbstractEventLoop, asyncio.Event]


class _ObservedWaiters(dict[str, list[Waiter]]):
    """Expose registration as synchronization, without changing production code."""

    def __init__(self) -> None:
        super().__init__()
        self.registered = threading.Event()

    def setdefault(self, key: str, default: list[Waiter] | None = None) -> list[Waiter]:
        waiters = super().setdefault(key, [] if default is None else default)
        # JobStore still holds its lock here. A mutator awakened by this signal
        # therefore cannot pass the state-check/registration boundary.
        self.registered.set()
        return waiters


class _RegistrationRaceWaiters(_ObservedWaiters):
    """Attempt a state mutation while JobStore still holds the registration lock."""

    def __init__(self, mutation: Callable[[], None]) -> None:
        super().__init__()
        self._mutation = mutation
        self.mutation_attempted = threading.Event()
        self.mutator: threading.Thread | None = None

    def setdefault(self, key: str, default: list[Waiter] | None = None) -> list[Waiter]:
        waiters = super().setdefault(key, default)

        def mutate() -> None:
            self.mutation_attempted.set()
            self._mutation()

        self.mutator = threading.Thread(target=mutate, name="job-registration-race")
        self.mutator.start()
        assert self.mutation_attempted.wait(timeout=10)
        return waiters


async def _registered_events(store: JobStore, job_id: str, expected: int) -> list[asyncio.Event]:
    """Yield until the expected waiters exist; fail by progress, not elapsed milliseconds."""
    for _ in range(1_000):
        with store._lock:
            registered = list(store._waiters.get(job_id, []))
        if len(registered) == expected:
            return [event for _, event in registered]
        await asyncio.sleep(0)
    raise AssertionError(f"expected {expected} registered waiter(s), found {len(registered)}")


def test_wait_for_update_wakes_on_completion_without_polling() -> None:
    async def scenario() -> None:
        store: JobStore[str] = JobStore()
        job_id = store.create()
        store.mark_running(job_id)
        waiter = asyncio.create_task(store.wait_for_update(job_id, 20.0))
        events = await _registered_events(store, job_id, 1)
        store.mark_done(job_id, "result")
        await asyncio.sleep(0)
        assert events[0].is_set()  # the notification path ran; this was not a timeout return
        job = await waiter
        assert job is not None and job.status == "done" and job.result == "result"
        assert store._waiters == {}

    asyncio.run(scenario())


def test_state_change_during_waiter_registration_is_not_missed() -> None:
    async def scenario() -> None:
        store: JobStore[str] = JobStore()
        job_id = store.create()
        store.mark_running(job_id)
        observed_waiters = _RegistrationRaceWaiters(lambda: store.mark_done(job_id, "raced"))
        store._waiters = observed_waiters

        job = await store.wait_for_update(job_id, 20.0)
        assert observed_waiters.mutator is not None
        observed_waiters.mutator.join(timeout=10)
        assert not observed_waiters.mutator.is_alive()
        assert job is not None and job.status == "done" and job.result == "raced"
        assert store._waiters == {}

    asyncio.run(scenario())


def test_wait_for_update_wakes_all_observers_and_cleans_up() -> None:
    async def scenario() -> None:
        store: JobStore[str] = JobStore()
        job_id = store.create()
        store.mark_running(job_id)
        waiters = [asyncio.create_task(store.wait_for_update(job_id, 20.0)) for _ in range(50)]
        events = await _registered_events(store, job_id, 50)
        store.mark_done(job_id, "shared")
        await asyncio.sleep(0)
        assert all(event.is_set() for event in events)
        jobs = await asyncio.gather(*waiters)
        assert all(job is not None and job.status == "done" and job.result == "shared" for job in jobs)
        assert store._waiters == {}

    asyncio.run(scenario())


def test_wait_for_update_timeout_error_terminal_and_dismiss() -> None:
    async def scenario() -> None:
        store: JobStore[str] = JobStore()
        running_id = store.create()
        store.mark_running(running_id)
        timeout_wait = asyncio.create_task(store.wait_for_update(running_id, 0.1))
        timeout_events = await _registered_events(store, running_id, 1)
        assert not timeout_wait.done()
        unchanged = await timeout_wait
        assert unchanged is not None and unchanged.status == "running"
        assert not timeout_events[0].is_set()  # no mutation notified this waiter; the bounded timeout returned it
        assert store._waiters == {}

        error_wait = asyncio.create_task(store.wait_for_update(running_id, 20.0))
        error_events = await _registered_events(store, running_id, 1)
        store.mark_error(running_id, "expected")
        await asyncio.sleep(0)
        assert error_events[0].is_set()
        failed = await error_wait
        assert failed is not None and failed.status == "error" and failed.detail == "expected"

        waiters_before_terminal_read = dict(store._waiters)
        assert (await store.wait_for_update(running_id, 1.0)).status == "error"  # type: ignore[union-attr]
        assert store._waiters == waiters_before_terminal_read  # terminal reads never register a held request

        dismissed_id = store.create()
        dismissed_wait = asyncio.create_task(store.wait_for_update(dismissed_id, 20.0))
        dismissed_events = await _registered_events(store, dismissed_id, 1)
        assert store.dismiss(dismissed_id)
        await asyncio.sleep(0)
        assert dismissed_events[0].is_set()
        assert await dismissed_wait is None
        assert store._waiters == {}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("store_name", "path"),
    [
        ("summary_jobs", "/summarize/{job_id}"),
        ("critical_review_jobs", "/critical-read/{job_id}"),
        ("critical_review_set_jobs", "/critical-read/set/{job_id}"),
        ("wip_critical_review_jobs", "/wip/critical-read/{job_id}"),
    ],
)
def test_model_job_status_routes_wake_on_error(temp_db_url: str, store_name: str, path: str) -> None:
    app = create_app(db_url=temp_db_url)
    store: JobStore = getattr(app.state, store_name)
    observed_waiters = _ObservedWaiters()
    store._waiters = observed_waiters
    job_id = store.create()
    store.mark_running(job_id)
    with TestClient(app) as client:
        client.get("/health")  # exclude TestClient/middleware first-request setup
        with ThreadPoolExecutor(max_workers=1) as executor:
            response_future = executor.submit(client.get, path.format(job_id=job_id) + "?wait_seconds=20")
            assert observed_waiters.registered.wait(timeout=10), "status route did not register its held request"
            with store._lock:
                registered_event = store._waiters[job_id][0][1]
            store.mark_error(job_id, "controlled failure")
            response = response_future.result(timeout=10)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "error"
    assert response.json()["detail"] == "controlled failure"
    assert registered_event.is_set()
    assert store._waiters == {}


def test_status_route_remains_immediate_by_default_and_bounds_wait(temp_db_url: str) -> None:
    app = create_app(db_url=temp_db_url)
    job_id = app.state.summary_jobs.create()
    with TestClient(app) as client:
        client.get("/health")  # exclude TestClient/middleware first-request setup
        response = client.get(f"/summarize/{job_id}")
        invalid = client.get(f"/summarize/{job_id}?wait_seconds=26")
    assert response.status_code == 200 and response.json()["status"] == "pending"
    assert app.state.summary_jobs._waiters == {}  # default wait_seconds=0 must not register a held request
    assert invalid.status_code == 422


def test_frontend_uses_one_shared_abortable_observer_for_model_jobs() -> None:
    helper = Path("app/frontend/js/02b_job_completion.jsx").read_text(encoding="utf-8")
    synthesis = Path("app/frontend/js/20_synthesis.jsx").read_text(encoding="utf-8")
    critical = Path("app/frontend/js/08x_methods_critical.jsx").read_text(encoding="utf-8")
    critical_set = Path("app/frontend/js/08y_critical_set.jsx").read_text(encoding="utf-8")

    assert "function observeJobUntilTerminal(" in helper
    assert "JOB_STATUS_WAIT_SECONDS = 20" in helper
    assert "JOB_STATUS_FALLBACK_RETRY_MS = 1200" in helper
    assert "new AbortController()" in helper and "controller.abort()" in helper
    assert "requestStatus(0)" in helper  # immediate terminal/reload discovery + fallback
    assert "requestStatus(JOB_STATUS_WAIT_SECONDS)" in helper
    assert "rememberActiveJob" in helper and "recalledActiveJob" in helper

    assert "observeJobUntilTerminal(`/summarize/${jobId}`" in synthesis
    assert "observeJobUntilTerminal(`/critical-read/${jobId}`" in critical
    assert "observeJobUntilTerminal(`/wip/critical-read/${jobId}`" in critical
    assert "observeJobUntilTerminal(`/critical-read/set/${jobId}`" in critical_set
    assert "setTimeout(() => pollJob(jobId), 1200)" not in synthesis
    assert "setTimeout(() => poll(jid), 1200)" not in critical
    assert "setTimeout(() => poll(jid), 1200)" not in critical_set
    assert "setTimeout(() => poll(jobId), 1000)" not in critical


def test_frontend_get_supports_abort_and_preserves_http_status() -> None:
    source = Path("app/frontend/js/00_lib.jsx").read_text(encoding="utf-8")
    assert "async function api(path, options)" in source
    assert "if (options && options.signal) init.signal = options.signal" in source
    assert "status: res.status" in source
