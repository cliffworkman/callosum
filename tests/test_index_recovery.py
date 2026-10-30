"""Inc 610: supervised, resource-aware, automatically recovering profile index builds.

Thread-launcher tests drive the real ``run_worker`` loop with fake encoders for policy cases. Subprocess tests
launch a genuinely separate worker process (``tests.index_worker_fake``) so external kills, exit codes and app
restarts behave as they do in production -- an exception raised in-process would not reproduce a worker that
vanishes without running any cleanup code. No real model is loaded anywhere here.
"""

from __future__ import annotations

import dataclasses
import os
import signal
import subprocess
import sys
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

from app.backend.embeddings import index_runs
from app.backend.embeddings import index_worker as worker
from app.backend.embeddings.index_lock import worker_holds_lock
from app.backend.embeddings.index_supervisor import (
    IndexSupervisor,
    SubprocessLauncher,
    SupervisorConfig,
    ThreadLauncher,
)
from app.backend.embeddings.profile_index import vector_integrity
from app.backend.embeddings.profiles import (
    ARCTIC_S_PROFILE_KEY,
    PROFILES,
    IncompleteEmbeddingIndexError,
    profile_coverage,
    require_complete_index,
)
from app.backend.embeddings.resources import ResourcePolicy, ResourceSnapshot, measure
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import chunks, embedding_index_runs, embeddings
from tests.test_embedding_profiles import FakeArctic

ARCTIC = PROFILES[ARCTIC_S_PROFILE_KEY]
PLENTY = ResourceSnapshot(16000, 8000, 26000, 9000, "test")
LOW = ResourceSnapshot(16000, 300, 26000, 300, "test")  # below the 16 GB machine's pause floor (600 MB)


def _seed(db_url: str, n: int = 12) -> list[int]:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        paper = create_paper(
            conn,
            title="Indexing fixture",
            csl_json={"type": "article-journal", "title": "x"},
            processing_tier="fully-chunked",
        )
        attachment = create_attachment(
            conn,
            paper_id=paper,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="idx-fixture",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        ids = [
            create_chunk(
                conn,
                paper_id=paper,
                attachment_id=attachment,
                text=f"Passage {i} about cognition.",
                page_start=1,
                page_end=1,
                bbox_coordinate_system="pdf-points-top-left",
                extraction_tool="fixture",
                extraction_version="1",
                chunking_strategy="paragraph",
                chunk_version=f"v{i}",
                source_attachment_checksum="idx-fixture",
                bbox_json=[],
            )
            for i in range(n)
        ]
    engine.dispose()
    return ids


@pytest.fixture()
def small_arctic(monkeypatch: pytest.MonkeyPatch):
    profile = dataclasses.replace(ARCTIC, dimension=3)
    monkeypatch.setitem(PROFILES, ARCTIC_S_PROFILE_KEY, profile)
    return profile


@dataclasses.dataclass
class ScriptedArctic(FakeArctic):
    """Fails on demand: ``fail`` is an exception instance raised by every encode while set."""

    fail: BaseException | None = None
    delay: float = 0.0

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        if self.fail is not None:
            raise self.fail
        if self.delay:
            time.sleep(self.delay)
        return super().encode_texts(texts)


class Probe:
    def __init__(self, snapshot: ResourceSnapshot = PLENTY) -> None:
        self.snapshot = snapshot

    def __call__(self) -> ResourceSnapshot:
        return self.snapshot


def _threaded(engine, model, probe: Probe, **config) -> IndexSupervisor:  # type: ignore[no-untyped-def]
    cfg = SupervisorConfig(db_url=engine.url.render_as_string(hide_password=False), **config)
    launcher = ThreadLauncher(engine, lambda _key: model, InMemoryVectorStore(), probe=probe)
    return IndexSupervisor(engine, cfg, launcher, probe=probe)


def _settle(supervisor: IndexSupervisor, until: tuple[str, ...], timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        for live in list(supervisor._live.values()):
            join = getattr(live.handle, "join", None)
            if join:
                join(0.2)
        supervisor.tick()
        row = supervisor.row(ARCTIC_S_PROFILE_KEY) or {}
        if row.get("state") in until or time.monotonic() > deadline:
            return row
        time.sleep(0.05)


def _due_now(engine) -> None:  # type: ignore[no-untyped-def]
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, next_retry_at=index_runs.now() - timedelta(seconds=1))


def _arctic_rows(engine) -> int:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        return conn.execute(
            select(func.count()).select_from(embeddings).where(embeddings.c.model_name == ARCTIC.model_name)
        ).scalar_one()


# ---- resources -------------------------------------------------------------------------------------------------


def test_policy_floors_scale_with_the_machine_not_a_fixed_16gb() -> None:
    small = ResourcePolicy.for_machine(ResourceSnapshot(8000, 2000, None, None, "t"))
    large = ResourcePolicy.for_machine(ResourceSnapshot(64000, 2000, None, None, "t"))
    assert small.reserve_mb == 512 and large.reserve_mb == 3200
    assert small.stop_mb < small.pause_mb < small.reserve_mb
    assert small.can_start(ResourceSnapshot(8000, 2000, None, None, "t"), 1200)
    # Available commit binds on Windows even when physical memory looks fine.
    assert not small.can_start(ResourceSnapshot(8000, 4000, 9000, 900, "t"), 1200)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows commit accounting")
def test_windows_measurement_reports_real_commit_limit() -> None:
    snap = measure()
    assert snap.source == "GlobalMemoryStatusEx"
    assert snap.commit_limit_mb >= snap.total_physical_mb and 0 < snap.available_commit_mb <= snap.commit_limit_mb


# ---- policy (thread launcher) ----------------------------------------------------------------------------------


def test_fresh_build_completes_and_a_rerun_adds_nothing(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    supervisor.start(small_arctic)
    row = _settle(supervisor, ("completed",))
    assert row["state"] == "completed" and row["worker_pid"] is None
    rows = _arctic_rows(engine)
    supervisor.start(small_arctic)
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    assert _arctic_rows(engine) == rows == 12
    with engine.connect() as conn:
        assert vector_integrity(conn, ScriptedArctic(), dimension=3)["duplicate_current_chunks"] == 0
    engine.dispose()


def test_low_memory_at_start_waits_without_launching_then_starts(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url)
    engine = make_engine(temp_db_url)
    probe = Probe(LOW)
    supervisor = _threaded(engine, ScriptedArctic(), probe)
    row = supervisor.start(small_arctic)
    assert row["state"] == "waiting_resources" and row["attempts"] == 0 and not supervisor._live
    supervisor.tick()
    assert supervisor.row(ARCTIC_S_PROFILE_KEY)["attempts"] == 0  # waiting is not a failed attempt
    probe.snapshot = PLENTY
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    engine.dispose()


def test_pressure_mid_build_halves_batch_waits_and_resumes(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url)
    engine = make_engine(temp_db_url)
    probe = Probe()
    model = ScriptedArctic(delay=0.05)
    supervisor = _threaded(engine, model, probe, initial_batch_size=2)
    supervisor.start(small_arctic)
    deadline = time.monotonic() + 10
    while _arctic_rows(engine) < 4 and time.monotonic() < deadline:
        time.sleep(0.02)
    probe.snapshot = LOW  # the worker sees it before its next batch, commits nothing partial, exits
    row = _settle(supervisor, ("waiting_resources",))
    assert row["state"] == "waiting_resources" and row["batch_size"] == 1 and row["failures_without_progress"] == 0
    kept = _arctic_rows(engine)
    assert 4 <= kept < 12
    _due_now(engine)
    supervisor.tick()
    assert not supervisor._live  # still low: no relaunch, no thrash
    probe.snapshot = PLENTY
    row = _settle(supervisor, ("completed",))
    assert row["state"] == "completed" and _arctic_rows(engine) == 12  # resumed from kept work, no duplicates
    engine.dispose()


def test_persistent_allocation_failure_ends_in_an_honest_blocked_state_then_manual_resume(
    temp_db_url: str, small_arctic
) -> None:
    _seed(temp_db_url)
    engine = make_engine(temp_db_url)
    model = ScriptedArctic(fail=MemoryError("cannot allocate"))
    supervisor = _threaded(engine, model, Probe(), initial_batch_size=2, max_failures_without_progress=3)
    supervisor.start(small_arctic)
    for _ in range(4):
        row = _settle(supervisor, ("waiting_resources", "failed"))
        if row["state"] == "failed":
            break
        _due_now(engine)
    assert row["state"] == "failed" and row["failure_kind"] == "insufficient_memory", row
    assert row["batch_size"] == 1 and row["attempts"] == 3
    attempts = row["attempts"]
    supervisor.tick()
    assert supervisor.row(ARCTIC_S_PROFILE_KEY)["attempts"] == attempts  # circuit breaker: no automatic retry
    model.fail = None
    supervisor.start(small_arctic)  # the explicit Resume clears the breaker
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    engine.dispose()


def test_model_unavailable_is_never_retried_automatically(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(fail=OSError("not in local cache")), Probe())
    supervisor.start(small_arctic)
    row = _settle(supervisor, ("failed",))
    assert row["state"] == "failed" and row["failure_kind"] == "model_unavailable" and row["next_retry_at"] is None
    supervisor.tick()
    assert supervisor.row(ARCTIC_S_PROFILE_KEY)["attempts"] == 1
    assert "not in local cache" in row["diagnostic"] and "not in local cache" not in (row["failure_detail"] or "")
    engine.dispose()


def test_pause_and_cancel_are_durable_across_restart(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(delay=0.05), Probe(), initial_batch_size=1)
    supervisor.start(small_arctic)
    time.sleep(0.2)
    supervisor.pause(ARCTIC_S_PROFILE_KEY)
    assert _settle(supervisor, ("paused",))["state"] == "paused"
    restarted = _threaded(engine, ScriptedArctic(), Probe())
    restarted.reconcile_on_startup()
    restarted.tick()
    assert restarted.row(ARCTIC_S_PROFILE_KEY)["state"] == "paused" and not restarted._live
    restarted.cancel(ARCTIC_S_PROFILE_KEY)
    again = _threaded(engine, ScriptedArctic(), Probe())
    again.reconcile_on_startup()
    again.tick()
    assert again.row(ARCTIC_S_PROFILE_KEY)["state"] == "cancelled" and not again._live
    engine.dispose()


def test_partial_vectors_are_repaired_and_minilm_rows_are_untouched(temp_db_url: str, small_arctic) -> None:
    ids = _seed(temp_db_url, n=4)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        minilm = [
            conn.execute(
                insert(embeddings).values(
                    target_type="chunk",
                    target_id=cid,
                    model_name="all-MiniLM-L6-v2",
                    model_version="all-MiniLM-L6-v2",
                    dimension=3,
                    normalization="whitespace-lower-v1",
                    source_text_version=f"v{i}",
                    source_chunk_version=f"v{i}",
                    vector_store_kind="memory",
                    vector_store_ref=f"m{i}",
                )
            ).inserted_primary_key[0]
            for i, cid in enumerate(ids)
        ]
        # An Arctic identity row whose vector never landed would otherwise count as indexed.
        conn.execute(
            insert(embeddings).values(
                target_type="chunk",
                target_id=ids[0],
                model_name=ARCTIC.model_name,
                model_version=ARCTIC.model_version,
                dimension=3,
                normalization=ARCTIC.normalization,
                source_text_version="v0",
                source_chunk_version="v0",
                vector_store_kind="memory",
                vector_store_ref=None,
            )
        )
        assert profile_coverage(conn, small_arctic)["indexed_chunks"] == 1
        before = [tuple(r) for r in conn.execute(select(embeddings).where(embeddings.c.id.in_(minilm)))]
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    supervisor.start(small_arctic)
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    with engine.connect() as conn:
        integrity = vector_integrity(conn, ScriptedArctic(), dimension=3)
        assert integrity["missing_vector_ids"] == [] and integrity["duplicate_current_chunks"] == 0
        assert [tuple(r) for r in conn.execute(select(embeddings).where(embeddings.c.id.in_(minilm)))] == before
    engine.dispose()


def test_changed_chunk_reopens_the_index_and_ask_fails_closed_until_rebuilt(temp_db_url: str, small_arctic) -> None:
    ids = _seed(temp_db_url, n=3)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    supervisor.start(small_arctic)
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    with engine.begin() as conn:
        conn.execute(update(chunks).where(chunks.c.id == ids[1]).values(chunk_version="v1-edited"))
        assert not profile_coverage(conn, small_arctic)["complete"]
        with pytest.raises(IncompleteEmbeddingIndexError):
            require_complete_index(conn, small_arctic)
    supervisor.start(small_arctic)
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    with engine.connect() as conn:
        assert profile_coverage(conn, small_arctic)["complete"]
        assert vector_integrity(conn, ScriptedArctic(), dimension=3)["stale_rows"] == 1  # history kept, not counted
    engine.dispose()


def test_restart_reconciles_a_dead_worker_from_stored_vectors(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url, n=5)
    engine = make_engine(temp_db_url)
    index_runs.upsert_requested(engine, small_arctic, batch_size=8)
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    index_runs.update_run(
        engine, ARCTIC_S_PROFILE_KEY, state="running", worker_pid=dead.pid, worker_token="t" * 32, indexed_chunks=999
    )  # a volatile counter that lies
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    [row] = supervisor.reconcile_on_startup()
    assert row["state"] == "retrying" and row["failure_kind"] == "interrupted_unknown_cause"
    assert row["indexed_chunks"] == 0 and row["worker_pid"] is None  # re-derived from embeddings, not the counter
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    engine.dispose()


# ---- real worker processes -------------------------------------------------------------------------------------


def _process_supervisor(db_url: str, engine, **config) -> IndexSupervisor:  # type: ignore[no-untyped-def]
    cfg = SupervisorConfig(db_url=db_url, poll_seconds=0.1, **config)
    return IndexSupervisor(engine, cfg, SubprocessLauncher(cfg, module="tests.index_worker_fake"), probe=Probe())


def _hard_kill(pid: int) -> None:
    """External and abrupt: TerminateProcess on Windows, SIGKILL elsewhere. No cleanup code runs in the target."""
    os.kill(pid, signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL)


def _wait(predicate, timeout: float = 60.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def test_subprocess_worker_killed_externally_is_detected_and_resumed(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(temp_db_url, n=10)
    engine = make_engine(temp_db_url)
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "slow")
    supervisor = _process_supervisor(temp_db_url, engine, initial_batch_size=2)
    supervisor.start(ARCTIC)
    handle = supervisor._live[ARCTIC_S_PROFILE_KEY].handle
    _wait(lambda: _arctic_rows(engine) >= 2)
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    _hard_kill(handle.pid)
    _wait(lambda: handle.poll() is not None)
    supervisor.tick()
    row = supervisor.row(ARCTIC_S_PROFILE_KEY)
    kept = _arctic_rows(engine)
    assert row["state"] == "retrying" and row["failure_kind"] == "interrupted_unknown_cause", row
    assert row["batch_size"] == 1 and row["failures_without_progress"] == 0 and kept >= 2
    assert bystander.poll() is None  # nothing but the owned worker was touched
    bystander.kill()
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "normal")
    _due_now(engine)
    supervisor.tick()
    try:
        _wait(lambda: supervisor.tick() or (supervisor.row(ARCTIC_S_PROFILE_KEY) or {})["state"] == "completed", 90)
    except AssertionError:
        raise AssertionError(str(supervisor.row(ARCTIC_S_PROFILE_KEY))) from None
    with engine.connect() as conn:
        assert profile_coverage(conn, ARCTIC)["complete"]
        integrity = vector_integrity(conn, ARCTIC_ENCODER, dimension=ARCTIC.dimension)
    assert integrity["missing_vector_ids"] == [] and integrity["duplicate_current_chunks"] == 0
    assert _arctic_rows(engine) == 10
    engine.dispose()


ARCTIC_ENCODER = type("Identity", (), {"name": ARCTIC.model_name, "version": ARCTIC.model_version})()


def test_api_server_survives_worker_failure_and_status_stays_available(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.backend.api.app import create_app
    from app.backend.api.routers.embedding_index import index_supervisor

    _seed(temp_db_url, n=4)
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "oom")
    app = create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore())
    supervisor = index_supervisor(app)
    supervisor.launcher = SubprocessLauncher(supervisor.config, module="tests.index_worker_fake")
    monkeypatch.setattr("app.backend.api.routers.embedding_index._launcher_for", lambda _app, sup: sup.launcher)
    supervisor.probe = Probe()
    client = TestClient(app)
    job = client.post(f"/embedding-profiles/{ARCTIC_S_PROFILE_KEY}/index").json()["job_id"]
    _wait(lambda: client.get(f"/embedding-profiles/index/{job}").json()["run"]["state"] == "waiting_resources")
    state = client.get("/embedding-profiles")
    assert state.status_code == 200 and client.get("/status/jobs").status_code == 200
    run = next(p for p in state.json()["profiles"] if p["key"] == ARCTIC_S_PROFILE_KEY)["index_run"]
    assert run["auto_retry_scheduled"] and run["batch_size"] == 4 and "memory is low" in run["message"]
    assert "MemoryError" not in run["message"] and "MemoryError" in run["diagnostic"]
    assert client.post(f"/embedding-profiles/{ARCTIC_S_PROFILE_KEY}/index/cancel").json()["state"] == "cancelled"


def test_app_shutdown_stops_only_its_own_worker(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(temp_db_url, n=40)
    engine = make_engine(temp_db_url)
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "slow")
    supervisor = _process_supervisor(temp_db_url, engine, initial_batch_size=1)
    supervisor.start(ARCTIC)
    handle = supervisor._live[ARCTIC_S_PROFILE_KEY].handle
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    _wait(lambda: _arctic_rows(engine) >= 1)
    supervisor.shutdown()
    assert handle.poll() is not None
    assert not worker_holds_lock(temp_db_url, ARCTIC_S_PROFILE_KEY)  # the OS released the build lock
    assert bystander.poll() is None
    bystander.kill()
    row = supervisor.row(ARCTIC_S_PROFILE_KEY)
    assert row["state"] == "interrupted" and row["failure_kind"] == "app_closed" and row["intent"] == "run"
    with engine.connect() as conn:
        assert conn.execute(select(embedding_index_runs.c.worker_pid)).scalar_one() is None
    engine.dispose()


def test_orphaned_worker_exits_when_its_app_dies(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A killed app runs no shutdown code; the worker's parent watch must end it (no orphan holding the model)."""
    _seed(temp_db_url, n=40)
    engine = make_engine(temp_db_url)
    index_runs.upsert_requested(engine, ARCTIC, batch_size=1)
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, worker_token="o" * 32)
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "slow")
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.index_worker_fake",
            "--db-url",
            temp_db_url,
            "--profile",
            ARCTIC_S_PROFILE_KEY,
            "--token",
            "o" * 32,
            "--batch-size",
            "1",
            "--parent-pid",
            str(parent.pid),
        ]
    )
    _wait(lambda: _arctic_rows(engine) >= 1)
    assert worker_holds_lock(temp_db_url, ARCTIC_S_PROFILE_KEY)
    # A second worker for the same library and profile refuses to start while the first is alive.
    second = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.index_worker_fake",
            "--db-url",
            temp_db_url,
            "--profile",
            ARCTIC_S_PROFILE_KEY,
            "--token",
            "o" * 32,
            "--batch-size",
            "1",
            "--parent-pid",
            str(os.getpid()),
        ],
        timeout=120,
    )
    assert second.returncode == worker.EXIT_NOT_OWNER
    parent.kill()
    assert child.wait(timeout=30) == worker.EXIT_ORPHANED
    assert not worker_holds_lock(temp_db_url, ARCTIC_S_PROFILE_KEY)
    engine.dispose()


def test_a_worker_lost_while_the_app_runs_is_recovered_without_a_restart(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The supervisor's own handle is gone (e.g. a second app session observes a dead first one): the row still
    says running, but no process holds the OS lock, so a tick recovers it from stored vectors."""
    _seed(temp_db_url, n=4)
    engine = make_engine(temp_db_url)
    index_runs.upsert_requested(engine, ARCTIC, batch_size=2)
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, state="running", worker_token="x" * 32, worker_pid=999999)
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "normal")
    supervisor = _process_supervisor(temp_db_url, engine)
    supervisor.tick()
    row = supervisor.row(ARCTIC_S_PROFILE_KEY)
    assert row["state"] == "retrying" and row["failure_kind"] == "interrupted_unknown_cause"
    _wait(lambda: supervisor.tick() or (supervisor.row(ARCTIC_S_PROFILE_KEY) or {})["state"] == "completed", 90)
    engine.dispose()


def test_production_code_does_not_depend_on_psutil() -> None:
    """The packaged runtime installs only the locked dependencies, and psutil is not among them."""
    from pathlib import Path

    offenders = [
        str(path)
        for path in Path("app").rglob("*.py")
        if any(
            line.strip().startswith(("import psutil", "from psutil"))
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    ]
    assert offenders == []
    assert "psutil" not in Path("uv.lock").read_text(encoding="utf-8")
