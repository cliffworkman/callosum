"""Inc 616: index builds never knowingly fill the library's disk, and recover by themselves once space returns.

Everything here is simulated on disposable databases: a fake ``disk_usage`` reports low space, and a genuine
SQLite ``database or disk is full`` is produced with ``PRAGMA max_page_count`` on the *worker's* connections only,
so no test fills a real disk. Thread-launcher tests drive the real ``run_worker`` loop; subprocess tests launch a
genuinely separate worker process (``tests.index_worker_fake``) so exit codes and restarts are the production ones.
"""

from __future__ import annotations

import dataclasses
import errno
import importlib.util
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select, text
from sqlalchemy.exc import OperationalError

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.backend.embeddings import disk_guard, index_runs
from app.backend.embeddings import index_worker as worker
from app.backend.embeddings.index_supervisor import (
    IndexSupervisor,
    SubprocessLauncher,
    SupervisorConfig,
    ThreadLauncher,
)
from app.backend.embeddings.profile_index import vector_integrity
from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, PROFILES, profile_coverage
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import embeddings
from tests.test_index_recovery import (
    ARCTIC,
    ARCTIC_ENCODER,
    Probe,
    ScriptedArctic,
    _arctic_rows,
    _due_now,
    _seed,
    _settle,
    _wait,
)

PLENTY = 10**12
TIGHT = 512 * 2**20  # below the guard's 1 GB reserve, above the 256 MB hard stop: the worker declines the batch
KEY = ARCTIC_S_PROFILE_KEY


@pytest.fixture()
def small_arctic(monkeypatch: pytest.MonkeyPatch):
    profile = dataclasses.replace(ARCTIC, dimension=3)
    monkeypatch.setitem(PROFILES, KEY, profile)
    return profile


class Disk:
    """A ``shutil.disk_usage`` stand-in. ``free`` maps a path prefix to free bytes; the rest get ``default``."""

    def __init__(self, default: int = PLENTY, **_: object) -> None:
        self.default = default
        self.by_prefix: dict[Path, int] = {}
        self.paths: list[Path] = []

    def __call__(self, path: Path) -> SimpleNamespace:
        path = Path(path).resolve()
        self.paths.append(path)
        for prefix, free in self.by_prefix.items():
            if path == prefix or prefix in path.parents:
                return SimpleNamespace(free=free)
        return SimpleNamespace(free=self.default)


def _db_path(db_url: str) -> Path:
    return Path(db_url.removeprefix("sqlite:///")).resolve()


def _supervisor(engine, model, disk: Disk, *, worker_engine=None, **config) -> IndexSupervisor:  # type: ignore[no-untyped-def]
    cfg = SupervisorConfig(db_url=engine.url.render_as_string(hide_password=False), **config)
    launcher = ThreadLauncher(worker_engine or engine, lambda _k: model, InMemoryVectorStore(), Probe(), disk)
    return IndexSupervisor(engine, cfg, launcher, probe=Probe(), disk_usage=disk)


def _minilm_rows(engine, chunk_ids: list[int]) -> list[tuple]:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        for i, cid in enumerate(chunk_ids):
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
            )
    return _minilm_snapshot(engine)


def _minilm_snapshot(engine) -> list[tuple]:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        rows = conn.execute(select(embeddings).where(embeddings.c.model_name == "all-MiniLM-L6-v2"))
        return sorted(tuple(r) for r in rows)


def _integrity(db_url: str) -> str:
    with sqlite3.connect(_db_path(db_url)) as conn:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]


def _vacuum_and_page_count(db_url: str) -> int:
    """No free pages: every new row needs a page beyond the current count."""
    with sqlite3.connect(_db_path(db_url)) as conn:
        conn.execute("VACUUM")
        return conn.execute("PRAGMA page_count").fetchone()[0]


# ---- the floor itself ------------------------------------------------------------------------------------------


def test_floor_stacks_reserve_wal_and_in_flight_batches_and_never_demands_the_whole_build() -> None:
    need = disk_guard.required_free_bytes(8)
    in_flight = 8 * disk_guard.BYTES_PER_CHUNK * disk_guard.LOOKAHEAD_BATCHES * disk_guard.WAL_FACTOR
    assert need == disk_guard.RESERVE_BYTES + disk_guard.WAL_ALLOWANCE_BYTES + in_flight
    # After the next LOOKAHEAD batches are written (twice, via the WAL), the reserve is still untouched -- the
    # property ``max(1 GB, 2 x batches)`` lacks once the batch term reaches the reserve.
    assert need - in_flight - disk_guard.WAL_ALLOWANCE_BYTES == disk_guard.RESERVE_BYTES
    assert disk_guard.required_free_bytes(1_000) > disk_guard.required_free_bytes(8)  # scales with the batch
    # A 4,000-paper library (~1.2M passages) needs only the bounded step, not its ~2.5 GB estimate, to start.
    check = disk_guard.check(
        "sqlite:///" + str(Path.cwd() / "x.sqlite"),
        batch_size=8,
        remaining_chunks=1_200_000,
        usage=lambda _p: SimpleNamespace(free=2 * 2**30),
    )
    assert check.ok and check.estimated_remaining_bytes > check.free_bytes
    assert disk_guard.HARD_STOP_BYTES < disk_guard.RESERVE_BYTES


def test_unmeasurable_disk_never_blocks_and_values_carry_no_path(tmp_path: Path) -> None:
    def broken(_p):  # type: ignore[no-untyped-def]
        raise OSError("unreadable volume")

    assert disk_guard.check("sqlite://", batch_size=8, remaining_chunks=5).ok  # in-memory: no file
    check = disk_guard.check(f"sqlite:///{tmp_path / 'lib.sqlite'}", batch_size=8, remaining_chunks=5, usage=broken)
    assert check.ok and check.free_bytes is None
    assert all(isinstance(v, int | None) for v in check.row_values().values())


def test_sqlite_full_and_enospc_are_recognised_however_wrapped() -> None:
    raw = sqlite3.OperationalError("database or disk is full")
    wrapped = OperationalError("INSERT ...", {}, raw)
    chained = RuntimeError("batch failed")
    chained.__cause__ = wrapped
    assert disk_guard.is_disk_full(raw) and disk_guard.is_disk_full(wrapped) and disk_guard.is_disk_full(chained)
    assert disk_guard.is_disk_full(OSError(errno.ENOSPC, "No space left on device"))
    assert not disk_guard.is_disk_full(OperationalError("x", {}, sqlite3.OperationalError("database is locked")))
    assert not disk_guard.is_disk_full(OSError(errno.EACCES, "denied"))
    assert not disk_guard.is_disk_full(MemoryError())


# ---- supervisor + worker contract (thread launcher) ------------------------------------------------------------


def test_low_disk_before_the_first_batch_waits_without_a_worker_then_resumes(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url, n=6)
    engine = make_engine(temp_db_url)
    disk = Disk(TIGHT)
    supervisor = _supervisor(engine, ScriptedArctic(), disk)
    supervisor.start(small_arctic)
    row = supervisor.row(KEY)
    assert row["state"] == "waiting_disk" and row["failure_kind"] == "disk_low", row
    assert supervisor._live == {} and row["attempts"] == 0 and _arctic_rows(engine) == 0  # no worker, no model
    assert row["disk_required_bytes"] == disk_guard.required_free_bytes(8) and row["disk_free_bytes"] == TIGHT
    assert row["disk_estimated_bytes"] == 6 * disk_guard.BYTES_PER_CHUNK
    assert row["failures_without_progress"] == 0 and row["next_retry_at"] > index_runs.now()
    supervisor.tick()  # before the recheck interval: nothing is attempted
    assert supervisor.row(KEY)["attempts"] == 0
    assert {p for p in disk.paths} == {_db_path(temp_db_url).parent}  # the library's filesystem, nothing else
    disk.default = PLENTY
    _due_now(engine)
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    assert _arctic_rows(engine) == 6
    engine.dispose()


@dataclasses.dataclass
class FillingArctic(ScriptedArctic):
    """After ``after`` encoded batches, something else on the machine takes the free space."""

    disk: Disk | None = None
    after: int = 2
    calls: int = 0

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        out = super().encode_texts(texts)
        self.calls += 1
        if self.calls >= self.after and self.disk is not None:
            self.disk.default = TIGHT
        return out


def test_disk_running_low_after_committed_batches_keeps_them_and_resumes(temp_db_url: str, small_arctic) -> None:
    ids = _seed(temp_db_url, n=8)
    engine = make_engine(temp_db_url)
    minilm = _minilm_rows(engine, ids)
    disk = Disk(PLENTY)
    model = FillingArctic(disk=disk)
    supervisor = _supervisor(engine, model, disk, initial_batch_size=2)
    supervisor.start(small_arctic)
    row = _settle(supervisor, ("waiting_disk",))
    assert row["state"] == "waiting_disk" and row["failure_kind"] == "disk_low", row
    assert _arctic_rows(engine) == 4 and row["indexed_chunks"] == 4  # both committed batches stay
    assert row["batch_size"] == 2 and row["failures_without_progress"] == 0  # a shortage is not a failure
    assert "exit 74" in row["diagnostic"]
    disk.default = PLENTY
    model.disk = None
    _due_now(engine)
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    assert _arctic_rows(engine) == 8 and _minilm_snapshot(engine) == minilm
    assert _integrity(temp_db_url) == "ok"
    engine.dispose()


def test_genuine_sqlite_full_rolls_back_the_batch_never_trips_the_breaker_and_recovers(
    temp_db_url: str, small_arctic
) -> None:
    ids = _seed(temp_db_url, n=200)
    engine = make_engine(temp_db_url)
    minilm = _minilm_rows(engine, ids[:5])
    cap: dict[str, int | None] = {"pages": None}
    worker_engine = make_engine(temp_db_url)

    @event.listens_for(worker_engine, "connect")
    def _cap(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        if cap["pages"] is not None:
            dbapi_conn.execute(f"PRAGMA max_page_count = {int(cap['pages'])}")

    engine.dispose()
    cap["pages"] = _vacuum_and_page_count(temp_db_url)  # the free check says plenty; SQLite says full
    disk = Disk(PLENTY)
    supervisor = _supervisor(
        engine, ScriptedArctic(), disk, worker_engine=worker_engine, max_failures_without_progress=3
    )
    supervisor.start(small_arctic)
    row = _settle(supervisor, ("waiting_disk", "failed"))
    assert row["state"] == "waiting_disk" and row["failure_kind"] == "disk_full", row
    first = _arctic_rows(engine)
    assert first % 8 == 0 and first < 200  # whole batches only: the failing batch rolled back entirely
    assert _integrity(temp_db_url) == "ok" and row["disk_required_bytes"] is not None
    for _ in range(5):  # more retries than the breaker allows, all against a still-full database
        _due_now(engine)
        row = _settle(supervisor, ("waiting_disk", "failed"))
        assert row["state"] == "waiting_disk" and row["failures_without_progress"] == 0, row
    assert row["attempts"] >= 6 and _integrity(temp_db_url) == "ok"
    cap["pages"] = None  # space returns
    worker_engine.dispose()
    _due_now(engine)
    assert _settle(supervisor, ("completed",))["state"] == "completed"
    with engine.connect() as conn:
        assert profile_coverage(conn, small_arctic)["complete"]
        integrity = vector_integrity(conn, ScriptedArctic(), dimension=3)
    assert integrity["missing_vector_ids"] == [] and integrity["duplicate_current_chunks"] == 0
    assert _arctic_rows(engine) == 200 and _minilm_snapshot(engine) == minilm and _integrity(temp_db_url) == "ok"
    worker_engine.dispose()
    engine.dispose()


def test_pause_stays_authoritative_over_a_disk_wait_across_restart(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url, n=4)
    engine = make_engine(temp_db_url)
    disk = Disk(TIGHT)
    supervisor = _supervisor(engine, ScriptedArctic(), disk)
    supervisor.start(small_arctic)
    assert supervisor.row(KEY)["state"] == "waiting_disk"
    assert supervisor.pause(KEY)["state"] == "paused"
    disk.default = PLENTY
    _due_now(engine)
    supervisor.tick()
    assert supervisor.row(KEY)["state"] == "paused" and supervisor._live == {}
    restarted = _supervisor(engine, ScriptedArctic(), disk)
    restarted.reconcile_on_startup()
    restarted.tick()
    assert restarted.row(KEY)["state"] == "paused" and _arctic_rows(engine) == 0
    restarted.start(small_arctic)  # the explicit Resume
    assert _settle(restarted, ("completed",))["state"] == "completed"
    engine.dispose()


def test_app_killed_while_waiting_for_disk_recovers_on_restart(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url, n=4)
    engine = make_engine(temp_db_url)
    disk = Disk(TIGHT)
    _supervisor(engine, ScriptedArctic(), disk).start(small_arctic)  # then the app dies: no shutdown() runs
    assert index_runs.get_run(engine.connect(), KEY)["state"] == "waiting_disk"
    still_low = _supervisor(engine, ScriptedArctic(), disk)
    [row] = still_low.reconcile_on_startup()
    assert row["state"] == "waiting_disk" and row["failure_kind"] == "disk_low"  # not relabelled "interrupted"
    still_low.tick()
    row = still_low.row(KEY)
    assert row["state"] == "waiting_disk" and row["failures_without_progress"] == 0 and row["attempts"] == 0
    disk.default = PLENTY
    later = _supervisor(engine, ScriptedArctic(), disk)  # another restart, now with room
    later.reconcile_on_startup()
    assert _settle(later, ("completed",))["state"] == "completed" and _arctic_rows(engine) == 4
    engine.dispose()


def test_disk_shortage_with_a_pause_requested_ends_paused(temp_db_url: str, small_arctic) -> None:
    _seed(temp_db_url, n=4)
    engine = make_engine(temp_db_url)
    supervisor = _supervisor(engine, ScriptedArctic(), Disk(PLENTY))
    index_runs.upsert_requested(engine, small_arctic, batch_size=8)
    row = supervisor.row(KEY)
    index_runs.update_run(engine, KEY, intent="pause")
    live = SimpleNamespace(handle=SimpleNamespace(diagnostic_tail=lambda: None), indexed_at_launch=0, stop_reason=None)
    supervisor._on_exit(row, live, worker.EXIT_DISK)  # the worker reported a shortage after the user paused
    assert supervisor.row(KEY)["state"] == "paused"
    engine.dispose()


# ---- separate volumes ------------------------------------------------------------------------------------------


def test_model_cache_and_library_on_different_volumes_are_checked_independently(
    temp_db_url: str, small_arctic, tmp_path: Path
) -> None:
    from tests import test_model_provisioning as tmp_prov

    cache = tmp_path / "cache-volume" / "hub"
    cache.mkdir(parents=True)
    disk = Disk(PLENTY)
    disk.by_prefix[cache.parent.resolve()] = 10 * 2**20  # the cache volume is nearly full
    provisioner = tmp_prov.make(
        tmp_path / "prov", tmp_prov.FakeHub(tmp_prov.CONTENT), free_bytes=lambda p: disk_guard.free_bytes(p, disk)
    )
    provisioner.cache_dir = cache
    assert provisioner.provision_once()["state"] == "insufficient_resources"
    _seed(temp_db_url, n=3)
    engine = make_engine(temp_db_url)
    supervisor = _supervisor(engine, ScriptedArctic(), disk)
    supervisor.start(small_arctic)
    assert _settle(supervisor, ("completed",))["state"] == "completed"  # the library volume has room
    disk.by_prefix = {_db_path(temp_db_url).parent: TIGHT}  # now the reverse
    assert disk_guard.check(temp_db_url, batch_size=8, remaining_chunks=1, usage=disk).ok is False
    assert provisioner.provision_once()["state"] == "verified"
    engine.dispose()


# ---- real worker processes -------------------------------------------------------------------------------------


def _process_supervisor(db_url: str, engine, disk: Disk, **config) -> IndexSupervisor:  # type: ignore[no-untyped-def]
    cfg = SupervisorConfig(db_url=db_url, poll_seconds=0.1, **config)
    launcher = SubprocessLauncher(cfg, module="tests.index_worker_fake")
    return IndexSupervisor(engine, cfg, launcher, probe=Probe(), disk_usage=disk)


def _until(supervisor: IndexSupervisor, states: tuple[str, ...], timeout: float = 90.0) -> dict:
    try:
        _wait(lambda: supervisor.tick() or (supervisor.row(KEY) or {})["state"] in states, timeout)
    except AssertionError:
        raise AssertionError(str(supervisor.row(KEY))) from None
    return supervisor.row(KEY) or {}


def test_process_worker_declines_a_batch_on_low_disk_with_its_exit_code(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(temp_db_url, n=4)
    engine = make_engine(temp_db_url)
    monkeypatch.setenv("CALLOSUM_FAKE_FREE_BYTES", str(TIGHT))  # space vanished between preflight and batch
    supervisor = _process_supervisor(temp_db_url, engine, Disk(PLENTY))
    supervisor.start(ARCTIC)
    handle = supervisor._live[KEY].handle
    row = _until(supervisor, ("waiting_disk", "failed", "retrying"))
    assert handle.poll() == worker.EXIT_DISK
    assert row["state"] == "waiting_disk" and row["failure_kind"] == "disk_low", row
    assert row["disk_free_bytes"] == TIGHT and row["failures_without_progress"] == 0
    monkeypatch.delenv("CALLOSUM_FAKE_FREE_BYTES")
    _due_now(engine)
    assert _until(supervisor, ("completed",))["state"] == "completed"
    engine.dispose()


def test_process_worker_hitting_a_real_sqlite_full_recovers_after_restart(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _seed(temp_db_url, n=10)
    engine = make_engine(temp_db_url)
    minilm = _minilm_rows(engine, ids[:3])
    engine.dispose()
    monkeypatch.setenv("CALLOSUM_FAKE_MAX_PAGES", str(_vacuum_and_page_count(temp_db_url)))
    supervisor = _process_supervisor(temp_db_url, engine, Disk(PLENTY), initial_batch_size=2)
    supervisor.start(ARCTIC)
    handle = supervisor._live[KEY].handle
    row = _until(supervisor, ("waiting_disk", "failed", "retrying"))
    assert handle.poll() == worker.EXIT_DISK
    assert row["state"] == "waiting_disk" and row["failure_kind"] == "disk_full", row
    assert row["failures_without_progress"] == 0 and _integrity(temp_db_url) == "ok"
    assert _minilm_snapshot(engine) == minilm
    # The app dies while waiting (no shutdown); space is freed; the next launch resumes with no user action.
    monkeypatch.delenv("CALLOSUM_FAKE_MAX_PAGES")
    restarted = _process_supervisor(temp_db_url, engine, Disk(PLENTY), initial_batch_size=2)
    restarted.reconcile_on_startup()
    assert _until(restarted, ("completed",))["state"] == "completed"
    with engine.connect() as conn:
        assert profile_coverage(conn, ARCTIC)["complete"]
        integrity = vector_integrity(conn, ARCTIC_ENCODER, dimension=ARCTIC.dimension)
    assert integrity["missing_vector_ids"] == [] and integrity["duplicate_current_chunks"] == 0
    assert _arctic_rows(engine) == 10 and _minilm_snapshot(engine) == minilm and _integrity(temp_db_url) == "ok"
    engine.dispose()


# ---- API: status contract, ordinary use unaffected -------------------------------------------------------------


def test_disk_wait_is_structured_in_status_and_browsing_keeps_working(temp_db_url: str, small_arctic) -> None:
    from app.backend.api.app import create_app
    from app.backend.api.routers.embedding_index import index_supervisor

    _seed(temp_db_url, n=3)
    app = create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore())
    supervisor = index_supervisor(app)
    supervisor.probe = Probe()
    supervisor.disk_usage = Disk(TIGHT)
    client = TestClient(app)
    job = client.post(f"/embedding-profiles/{KEY}/index").json()["job_id"]
    run = client.get(f"/embedding-profiles/index/{job}").json()["run"]
    assert run["state"] == "waiting_disk" and run["auto_retry_scheduled"] and run["actions"] == ["pause", "cancel"]
    assert run["disk"] == {
        "required_free_bytes": disk_guard.required_free_bytes(8),
        "free_bytes": TIGHT,
        "estimated_remaining_bytes": 3 * disk_guard.BYTES_PER_CHUNK,
    }
    assert "needs about 1.1 GB free, 0.5 GB free now" in run["message"] and "%" not in run["message"]
    body = client.get("/embedding-profiles").text
    db_file = _db_path(temp_db_url)
    assert str(db_file.parent) not in body and db_file.name not in body  # no private path in status
    jobs = client.get("/status/jobs")
    assert jobs.status_code == 200 and str(db_file.parent) not in jobs.text
    papers = client.get("/papers")
    assert papers.status_code == 200 and "Indexing fixture" in papers.text  # the library is fully usable
    assert client.post(f"/embedding-profiles/{KEY}/index/pause").json()["state"] == "paused"


# ---- migration -------------------------------------------------------------------------------------------------


def _load(name: str):  # type: ignore[no-untyped-def]
    path = Path("alembic/versions") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_migration_0087_upgrades_an_inc_610_table_keeping_rows_and_is_idempotent(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'old.sqlite').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.begin() as conn:  # rebuild the table exactly as an inc-610 library has it
        conn.exec_driver_sql("DROP TABLE embedding_index_runs")
        with Operations.context(MigrationContext.configure(conn)):
            _load("0086_embedding_index_runs").upgrade()
        assert (
            "waiting_disk"
            not in conn.execute(text("SELECT sql FROM sqlite_master WHERE name='embedding_index_runs'")).scalar_one()
        )
        conn.exec_driver_sql(
            "INSERT INTO embedding_index_runs (profile_key, model_version, state, intent, batch_size, indexed_chunks)"
            " VALUES ('arctic-s', 'v1', 'waiting_resources', 'run', 4, 17)"
        )
    for _ in range(2):  # the second run must be a no-op
        with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            _load("0087_index_run_waiting_disk").upgrade()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT state, batch_size, indexed_chunks, disk_free_bytes FROM embedding_index_runs")
        ).one()
        assert tuple(row) == ("waiting_resources", 4, 17, None)
        conn.exec_driver_sql("UPDATE embedding_index_runs SET state = 'waiting_disk', disk_free_bytes = 5")
        with pytest.raises(Exception, match="CHECK"):
            conn.exec_driver_sql("UPDATE embedding_index_runs SET state = 'bogus'")
    assert _integrity(url) == "ok"
    engine.dispose()
