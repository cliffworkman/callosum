"""Supervise embedding-profile index builds: one worker process per library profile, bounded automatic recovery.

The supervisor owns the worker it launched, watches it (exit code, heartbeat, system memory), and drives the
durable ``embedding_index_runs`` row through its lifecycle. It never decides that an index is complete: after
every exit it re-derives coverage from the stored vectors. Recovery is bounded on purpose:

* resource exits halve the batch (down to one passage) and wait, with backoff, until headroom returns;
* an exit without new committed vectors counts against a small budget; at the limit the run stops in
  ``failed`` and only the user's explicit Resume restarts it (the circuit breaker);
* model unavailable / contract mismatch is never retried automatically, and a model whose checkpoint the
  provisioner manages is never loaded before it is verified (inc 618: the build waits instead);
* low or full disk (inc 616) waits in ``waiting_disk`` and re-checks at a fixed interval; it never trips the
  breaker, never shrinks the batch, and never deletes anything to make room;
* the user's pause or cancel is durable and survives restarts.

Startup reconciliation handles the case cleanup code cannot: a worker or app killed from outside. A row left
``running`` whose worker no longer exists is an interruption of unknown cause, recovered from what is stored.
"""

from __future__ import annotations

import contextlib
import os
import subprocess  # nosec B404 -- fixed-argv worker launch only
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine

from app.backend.embeddings import disk_guard, index_runs
from app.backend.embeddings import index_worker as worker
from app.backend.embeddings.index_lock import WorkerLock, held_elsewhere, launch_lease_path, try_lock, worker_holds_lock
from app.backend.embeddings.profile_index import DEFAULT_INDEX_BATCH
from app.backend.embeddings.profiles import EmbeddingProfile, get_profile
from app.backend.embeddings.resources import DEFAULT_WORKER_ESTIMATE_MB, ResourcePolicy, ResourceSnapshot, measure
from app.backend.model_provisioning import checkpoint_pending, local_files_only_for

_SOURCE_ROOT = Path(__file__).resolve().parents[3]  # the directory holding ``app/`` (dev checkout or packaged)

_LAUNCHABLE = ("queued", "retrying", "waiting_resources", "waiting_disk")


@dataclass(frozen=True)
class SupervisorConfig:
    db_url: str
    initial_batch_size: int = DEFAULT_INDEX_BATCH
    max_failures_without_progress: int = 3
    backoff_seconds: tuple[float, ...] = (30.0, 120.0, 600.0)
    resume_delay_seconds: float = 5.0  # after an attempt that made progress
    stall_seconds: float = 600.0
    pause_grace_seconds: float = 120.0
    poll_seconds: float = 2.0
    local_files_only: bool = False
    threads: int = field(default_factory=lambda: max(1, min(4, (os.cpu_count() or 2) // 2)))
    resume_on_startup: bool = True
    disk_recheck_seconds: float = disk_guard.RECHECK_SECONDS


class WorkerHandle(Protocol):
    pid: int

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def diagnostic_tail(self) -> str | None: ...


class _ProcessHandle:
    def __init__(self, process: subprocess.Popen, stderr_path: str) -> None:
        self._process = process
        self._stderr_path = stderr_path
        self.pid = process.pid

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate(self) -> None:
        with contextlib.suppress(OSError):
            self._process.kill()  # only this worker; it starts no children of its own
        with contextlib.suppress(subprocess.TimeoutExpired):
            self._process.wait(timeout=10)

    def diagnostic_tail(self) -> str | None:
        try:
            with open(self._stderr_path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                handle.seek(max(0, handle.tell() - 1500))
                tail = handle.read().decode("utf-8", "replace").strip()
            os.remove(self._stderr_path)
        except OSError:
            return None
        return worker._scrub(tail) or None


class SubprocessLauncher:
    """Production: ``python -m app.backend.embeddings.index_worker`` with the source root as cwd (the packaged
    app launches uvicorn the same way), below-normal priority, no console window, and stdout discarded."""

    def __init__(self, config: SupervisorConfig, module: str = "app.backend.embeddings.index_worker") -> None:
        self._config = config
        self._module = module

    def launch(self, profile_key: str, token: str, batch_size: int) -> WorkerHandle:
        argv = [
            sys.executable,
            "-m",
            self._module,
            "--db-url",
            self._config.db_url,
            "--profile",
            profile_key,
            "--token",
            token,
            "--batch-size",
            str(batch_size),
            "--parent-pid",
            str(os.getpid()),
            "--threads",
            str(self._config.threads),
        ]
        if self._config.local_files_only or local_files_only_for(get_profile(profile_key).model_name):
            argv.append("--local-files-only")  # inc 615: a provisioned checkpoint never reaches the network
        fd, stderr_path = tempfile.mkstemp(prefix="callosum-index-", suffix=".log")
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS  # type: ignore[attr-defined]
        with os.fdopen(fd, "wb") as stderr:
            process = subprocess.Popen(  # noqa: S603  # nosec B603 -- fixed argv: interpreter, module, validated options
                argv,
                cwd=str(_SOURCE_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                creationflags=flags,
                preexec_fn=(lambda: os.nice(5)) if hasattr(os, "nice") else None,  # noqa: PLW1509
            )
        return _ProcessHandle(process, stderr_path)


class ThreadLauncher:
    """In-process worker for injected models (tests, fake profiles): same ``run_worker`` loop, same row protocol.
    ``terminate`` can only request a stop between batches; real-kill behaviour is tested with the subprocess."""

    def __init__(
        self,
        engine: Engine,
        model_for: Callable[[str], object],
        vector_store: object,
        probe: Callable[[], ResourceSnapshot] = measure,
        disk_usage: disk_guard.DiskUsage | None = None,
    ) -> None:
        self._engine = engine
        self._model_for = model_for
        self._vector_store = vector_store
        self._probe = probe
        self._disk_usage = disk_usage

    def launch(self, profile_key: str, token: str, batch_size: int) -> WorkerHandle:
        return _ThreadHandle(self, profile_key, token, batch_size)


class _ThreadHandle:
    def __init__(self, launcher: ThreadLauncher, profile_key: str, token: str, batch_size: int) -> None:
        self.pid = os.getpid()
        self._stop = threading.Event()
        self._code: int | None = None
        self._outcome: worker.WorkerOutcome | None = None

        def run() -> None:
            outcome = worker.run_worker(
                launcher._engine,
                profile=get_profile(profile_key),
                token=token,
                model=launcher._model_for(profile_key),  # type: ignore[arg-type]
                vector_store=launcher._vector_store,  # type: ignore[arg-type]
                batch_size=batch_size,
                probe=launcher._probe,
                should_stop=self._stop.is_set,
                disk_check=lambda size, remaining: disk_guard.check(
                    launcher._engine.url.render_as_string(hide_password=False),
                    batch_size=size,
                    remaining_chunks=remaining,
                    usage=launcher._disk_usage,
                ),
            )
            if outcome.failure_kind is not None:
                with contextlib.suppress(Exception):  # as in the process worker: a full disk may refuse this too
                    index_runs.update_run(
                        launcher._engine,
                        profile_key,
                        failure_kind=outcome.failure_kind,
                        diagnostic=outcome.diagnostic,
                        **outcome.row_values,
                    )
            self._code = outcome.exit_code

        self._thread = threading.Thread(target=run, name=f"index-{profile_key}", daemon=True)
        self._thread.start()

    def poll(self) -> int | None:
        return None if self._thread.is_alive() else self._code

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def terminate(self) -> None:
        self._stop.set()
        self._thread.join(timeout=30)
        if self._code is None:
            self._code = worker.EXIT_STOPPED

    def diagnostic_tail(self) -> str | None:
        return None


@dataclass
class _Live:
    handle: WorkerHandle
    indexed_at_launch: int
    launched_at: float
    stop_reason: str | None = None  # why the supervisor itself terminated the worker, if it did
    pausing_since: float | None = None
    lease: WorkerLock | None = None  # inc 617: this process's launch lease, released once the exit is observed


class IndexSupervisor:
    def __init__(
        self,
        engine: Engine,
        config: SupervisorConfig,
        launcher: object | None = None,
        *,
        probe: Callable[[], ResourceSnapshot] = measure,
        clock: Callable[[], float] = time.monotonic,
        on_update: Callable[[dict], None] | None = None,
        disk_usage: disk_guard.DiskUsage | None = None,
    ) -> None:
        self.engine = engine
        self.config = config
        self.launcher = launcher or SubprocessLauncher(config)
        self.probe = probe
        self.clock = clock
        self.on_update = on_update
        self.disk_usage = disk_usage
        self._live: dict[str, _Live] = {}
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closing = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- user actions -----------------------------------------------------------------------------------------

    def start(self, profile: EmbeddingProfile) -> dict:
        """Start or explicitly resume (also clears a failed/cancelled state and the retry budget)."""
        with self._lock:
            if profile.key in self._live:
                index_runs.update_run(self.engine, profile.key, intent="run")
            else:
                index_runs.upsert_requested(self.engine, profile, batch_size=self.config.initial_batch_size)
        return self._after_action(profile.key)

    def pause(self, profile_key: str) -> dict:
        return self._stop(profile_key, "pause", "paused")

    def cancel(self, profile_key: str) -> dict:
        return self._stop(profile_key, "cancel", "cancelled")

    def _stop(self, profile_key: str, intent: str, idle_state: str) -> dict:
        with self._lock:
            live = self._live.get(profile_key)
            current = self.row(profile_key)
            if live is None and (current is None or current["state"] in ("completed", idle_state)):
                return current or {}  # nothing running to stop; a finished build is never relabelled
            index_runs.update_run(
                self.engine, profile_key, intent=intent, state="pausing" if live else idle_state, next_retry_at=None
            )
            if live is not None:
                live.pausing_since = self.clock()
        return self._after_action(profile_key)

    def _after_action(self, profile_key: str) -> dict:
        self.tick()
        self._wake.set()
        return self.row(profile_key) or {}

    def row(self, profile_key: str) -> dict | None:
        with self.engine.connect() as conn:
            return index_runs.get_run(conn, profile_key)

    # ---- lifecycle --------------------------------------------------------------------------------------------

    def reconcile_on_startup(self) -> list[dict]:
        """Rows a previous session left active: re-derive coverage, repair state, schedule safe recovery."""
        with self.engine.connect() as conn:
            rows = [r for r in index_runs.list_runs(conn) if r["state"] in (*index_runs.ACTIVE_STATES, "interrupted")]
        with self._lock:
            for row in rows:
                self._recover_unowned(row)
        return [self.row(r["profile_key"]) or {} for r in rows]

    def _recover_unowned(self, row: dict) -> None:
        """A row this supervisor holds no worker for. If no live process holds the build's OS lock, the worker is
        gone -- killed, crashed, or its app died -- whatever the row claims. Coverage is re-derived from the stored
        vectors and the build is resumed (per policy) or left for the user. A lock that is still held means a live
        worker of another Callosum process: never start a second one."""
        key = row["profile_key"]
        try:
            profile = get_profile(key)
        except Exception:
            index_runs.update_run(
                self.engine,
                key,
                state="failed",
                failure_kind="unknown_profile",
                failure_detail="This index belongs to a retrieval model this version does not know.",
            )
            return
        if row["model_version"] != profile.model_version:
            index_runs.update_run(
                self.engine,
                key,
                state="failed",
                failure_kind="model_version_changed",
                failure_detail="The retrieval model's pinned version changed. Start the build again.",
            )
            return
        if self._owned_elsewhere(key):
            return
        index_runs.reconcile_counts(self.engine, profile)
        if row["state"] == "waiting_disk" and row["intent"] == "run" and self.config.resume_on_startup:
            index_runs.update_run(self.engine, key, worker_pid=None, worker_token=None, next_retry_at=index_runs.now())
            self._notify(key)  # no worker ran while waiting: re-check the disk now, not after an interruption
            return
        kind = row["failure_kind"] if row["state"] == "interrupted" else None
        values: dict = {"worker_pid": None, "worker_token": None, "failure_kind": kind or "interrupted_unknown_cause"}  # nosec B105
        if row["intent"] == "run" and self.config.resume_on_startup:
            values.update(state="retrying", next_retry_at=index_runs.now())
        elif row["intent"] == "run":
            values.update(state="interrupted")
        else:
            values.update(state={"pause": "paused", "cancel": "cancelled"}[row["intent"]], failure_kind=None)
        index_runs.update_run(self.engine, key, **values)
        self._notify(key)

    def start_monitor(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._monitor, name="index-supervisor", daemon=True)
            self._thread.start()

    def _monitor(self) -> None:
        while not self._closing.is_set():
            with contextlib.suppress(Exception):  # a monitor crash must never take the app down
                self.tick()
            self._wake.wait(self.config.poll_seconds)
            self._wake.clear()

    def shutdown(self) -> None:
        """App exit: stop owned workers now. Committed batches stay; the row says ``interrupted`` so the next
        launch resumes per policy. No background service outlives the app."""
        self._closing.set()
        self._wake.set()
        with self._lock:
            for key, live in list(self._live.items()):
                live.handle.terminate()
                index_runs.update_run(
                    self.engine, key, state="interrupted", failure_kind="app_closed", worker_pid=None, worker_token=None
                )
                self._live.pop(key, None)
                if live.lease is not None:
                    live.lease.release()
        if self._thread is not None:
            self._thread.join(timeout=5)

    # ---- the state machine ------------------------------------------------------------------------------------

    def tick(self) -> None:
        with self._lock:
            with self.engine.connect() as conn:
                rows = index_runs.list_runs(conn)
            for row in rows:
                key = row["profile_key"]
                if key in self._live:
                    self._watch(row, self._live[key])
                elif row["state"] in _LAUNCHABLE and row["intent"] == "run":
                    self._maybe_launch(row)
                elif row["state"] in ("running", "pausing"):
                    self._recover_unowned(row)  # its worker vanished while the app kept running

    def _owned_elsewhere(self, key: str) -> bool:
        """Another process's worker is running, or another process launched one that may still be starting."""
        url = self.config.db_url
        return worker_holds_lock(url, key) or held_elsewhere(launch_lease_path(url, key))

    def _maybe_launch(self, row: dict) -> None:
        key = row["profile_key"]
        if row["next_retry_at"] is not None and row["next_retry_at"] > index_runs.now():
            return
        if self._owned_elsewhere(key):
            return  # a worker of another Callosum process on this library
        if checkpoint_pending(get_profile(key).model_name):  # inc 618: only the inc-615 provisioner fetches weights
            return index_runs.hold_for_model(self.engine, key, self.config.disk_recheck_seconds)
        remaining = max(0, int(row["eligible_chunks"]) - int(row["indexed_chunks"]))
        disk = disk_guard.check(
            self.config.db_url, batch_size=int(row["batch_size"]), remaining_chunks=remaining, usage=self.disk_usage
        )
        if not disk.ok:  # preflight: no worker (and no model load) while the next batches would not fit
            self._wait_for_disk(key, "disk_low", disk.row_values())
            return
        snapshot = self.probe()
        policy = ResourcePolicy.for_machine(snapshot)
        if not policy.can_start(snapshot, max(int(row["peak_worker_rss_mb"] or 0), DEFAULT_WORKER_ESTIMATE_MB)):
            if row["state"] != "waiting_resources":
                index_runs.update_run(
                    self.engine,
                    key,
                    state="waiting_resources",
                    failure_kind="memory_pressure",
                    min_available_mb=snapshot.available_physical_mb,
                )
                self._notify(key)
            return
        lease = try_lock(launch_lease_path(self.config.db_url, key))
        if lease is None:
            return  # another process is launching this build right now
        token = uuid.uuid4().hex
        index_runs.update_run(
            self.engine,
            key,
            state="running",
            worker_token=token,
            worker_pid=None,
            worker_started_at=index_runs.now(),
            heartbeat_at=index_runs.now(),
            attempts=int(row["attempts"]) + 1,
            next_retry_at=None,
            failure_kind=None,
            failure_detail=None,
            diagnostic=None,
            **disk.row_values(),  # the remaining-growth estimate is known before the first batch
        )
        try:
            handle = self.launcher.launch(key, token, int(row["batch_size"]))  # type: ignore[attr-defined]
        except BaseException:
            lease.release()
            raise
        index_runs.update_run(self.engine, key, worker_pid=handle.pid)
        self._live[key] = _Live(handle, int(row["indexed_chunks"]), self.clock(), lease=lease)
        self._notify(key)

    def _watch(self, row: dict, live: _Live) -> None:
        key = row["profile_key"]
        code = live.handle.poll()
        if code is not None:
            self._live.pop(key, None)
            self._on_exit(row, live, code)
            return
        snapshot = self.probe()
        policy = ResourcePolicy.for_machine(snapshot)
        floor = row["min_available_mb"]
        if floor is None or snapshot.available_physical_mb < floor:
            index_runs.update_run(self.engine, key, min_available_mb=snapshot.available_physical_mb)
        if policy.must_stop(snapshot):
            live.stop_reason = "memory_stop"
        elif disk_guard.must_stop(self.config.db_url, self.disk_usage):
            live.stop_reason = "disk_stop"  # something else is filling the disk while a batch is in flight
        elif (
            row["heartbeat_at"] is not None
            and (index_runs.now() - row["heartbeat_at"]).total_seconds() > self.config.stall_seconds
        ):
            live.stop_reason = "stalled"
        elif live.pausing_since is not None and self.clock() - live.pausing_since > self.config.pause_grace_seconds:
            live.stop_reason = "user_stop"
        if live.stop_reason is not None:
            live.handle.terminate()  # only the worker this supervisor launched
            code = live.handle.poll()
            self._live.pop(key, None)
            self._on_exit(row, live, worker.EXIT_UNEXPECTED if code is None else code)
            return
        self._notify(key)

    def _disk_wait_values(self, kind: str) -> dict:
        return {
            "state": "waiting_disk",
            "failure_kind": kind,
            "failure_detail": None,
            "next_retry_at": index_runs.now() + timedelta(seconds=self.config.disk_recheck_seconds),
        }

    def _wait_for_disk(self, key: str, kind: str, disk_values: dict) -> None:
        index_runs.update_run(self.engine, key, **disk_values, **self._disk_wait_values(kind))
        self._notify(key)

    def _backoff(self, failures: int) -> float:
        steps = self.config.backoff_seconds
        return steps[min(max(failures, 1), len(steps)) - 1]

    def _on_exit(self, row: dict, live: _Live, code: int) -> None:
        key = row["profile_key"]
        if live.lease is not None:
            live.lease.release()
        profile = get_profile(key)
        coverage = index_runs.reconcile_counts(self.engine, profile)
        progressed = coverage["indexed_chunks"] > live.indexed_at_launch
        failures = 0 if progressed else int(row["failures_without_progress"]) + 1
        current = self.row(key) or row
        batch = int(current["batch_size"])
        values: dict = {"worker_pid": None, "worker_token": None, "failures_without_progress": failures}  # nosec B105
        # What the worker reported (if it lived to report), the exit code, and its stderr tail: technical only.
        parts = [f"exit {code}", current["diagnostic"], live.handle.diagnostic_tail()]
        values["diagnostic"] = " | ".join(p for p in parts if p)
        intent = current["intent"]

        def retry(state: str, kind: str, delay: float | None = None) -> None:
            if failures >= self.config.max_failures_without_progress:
                blocked = kind in ("memory_pressure", "allocation_failure", "memory_stop") and batch <= 1
                values.update(
                    state="failed",
                    failure_kind="insufficient_memory" if blocked else "no_progress",
                    failure_detail=(
                        "Not enough free memory to index even one passage at a time. Your existing index is preserved."
                        if blocked
                        else "Indexing stopped after repeated unsuccessful attempts. Your existing index is preserved. You can retry manually."
                    ),
                    next_retry_at=None,
                )
                return
            wait = (
                self.config.resume_delay_seconds
                if progressed
                else (delay if delay is not None else self._backoff(failures))
            )
            values.update(
                state=state,
                failure_kind=kind,
                failure_detail=None,
                next_retry_at=index_runs.now() + timedelta(seconds=wait),
            )

        if live.stop_reason == "user_stop" or (code in (worker.EXIT_STOPPED, worker.EXIT_DISK) and intent != "run"):
            values.update(
                state={"pause": "paused", "cancel": "cancelled"}.get(intent, "paused"), failures_without_progress=0
            )
        elif code == worker.EXIT_COMPLETE and live.stop_reason is None:
            if coverage["complete"]:
                values.update(state="completed", failure_kind=None, failure_detail=None, failures_without_progress=0)
            else:  # new or edited passages appeared meanwhile, or rows were repaired: go again
                retry("retrying", "more_work_appeared")
        elif code == worker.EXIT_MODEL:
            values.update(
                state="failed",
                failure_kind=current["failure_kind"] or "model_unavailable",
                failure_detail="The retrieval model could not be loaded or does not match its pinned recipe. Nothing was retried automatically.",
            )
        elif code == worker.EXIT_NOT_OWNER:
            values.update(
                state="failed", failure_kind="not_owner", failure_detail="Another indexing process holds this index."
            )
        elif code == worker.EXIT_DISK or live.stop_reason == "disk_stop":
            # Outside the breaker: a shortage is not a failed attempt. Same batch size; the floor already scales.
            values["failures_without_progress"] = 0 if progressed else int(row["failures_without_progress"])
            kind = "disk_stop" if live.stop_reason == "disk_stop" else (current["failure_kind"] or "disk_full")
            if current["disk_required_bytes"] is None or live.stop_reason == "disk_stop":
                remaining = max(0, coverage["eligible_chunks"] - coverage["indexed_chunks"])
                check = disk_guard.check(
                    self.config.db_url, batch_size=batch, remaining_chunks=remaining, usage=self.disk_usage
                )
                values.update(check.row_values())
            values.update(self._disk_wait_values(kind))
        elif code == worker.EXIT_RESOURCES or live.stop_reason == "memory_stop":
            values["batch_size"] = max(1, batch // 2)
            retry(
                "waiting_resources",
                "memory_stop" if live.stop_reason == "memory_stop" else (current["failure_kind"] or "memory_pressure"),
            )
        elif code == worker.EXIT_DATABASE_BUSY:
            retry("retrying", "database_busy")
        else:
            # Killed from outside, crashed, stalled or an unexpected error: cause unknown unless evidenced. A
            # silent kill is often the OS reclaiming memory, so the next attempt also uses a smaller batch.
            kind = live.stop_reason or current["failure_kind"] or "interrupted_unknown_cause"
            if kind != "unexpected_error":
                values["batch_size"] = max(1, batch // 2)
            retry("retrying", kind)
        index_runs.update_run(self.engine, key, **values)
        self._notify(key)

    def _notify(self, key: str) -> None:
        if self.on_update is not None:
            row = self.row(key)
            if row is not None:
                with contextlib.suppress(Exception):
                    self.on_update(row)
