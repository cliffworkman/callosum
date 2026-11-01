"""Inc 617: automatic background modernization (source-role v2 classification + Arctic S index scheduling).

Disposable databases, synthetic encoders, simulated resources. Thread-launched index workers drive the real inc-610
``run_worker`` loop; the process tests use real separate processes (``tests.modernization_child`` for a competing
coordinator, ``tests.index_worker_fake`` for index workers) so kills and OS-lock ownership behave as in production.
No real model is loaded and the real disk is never filled.
"""

from __future__ import annotations

import dataclasses
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import OperationalError

from app.backend.embeddings import index_runs
from app.backend.embeddings.index_lock import launch_lease_path, worker_holds_lock
from app.backend.embeddings.index_supervisor import IndexSupervisor, SubprocessLauncher, SupervisorConfig
from app.backend.embeddings.profile_index import vector_integrity
from app.backend.embeddings.profiles import (
    ACTIVE_RETRIEVAL_PROFILE_SETTING,
    ARCTIC_S_PROFILE_KEY,
    PROFILES,
    active_retrieval_profile,
    profile_coverage,
)
from app.backend.modernization import AUTO, PAUSED, CoordinatorConfig, ModernizationCoordinator, read_intent
from app.backend.modernization.classification import SourceRoleClassifier
from app.backend.pdf_processing.structure_backfill import coverage as class_coverage
from app.backend.pdf_processing.structure_backfill import derive_paper
from app.backend.persistence.annotations_repo import create_annotation
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import annotations, chunks, embeddings, library_settings, papers
from app.backend.persistence.schema_chunk_structure import chunk_structure
from tests.test_index_recovery import LOW, PLENTY, Probe, ScriptedArctic, _threaded, _wait
from tests.test_source_role_migration import PLAIN

ARCTIC = PROFILES[ARCTIC_S_PROFILE_KEY]
VERIFIED = {"track": "arctic-s", "state": "verified"}
ABSENT = {"track": "arctic-s", "state": "absent"}
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def small_arctic(monkeypatch: pytest.MonkeyPatch):
    profile = dataclasses.replace(ARCTIC, dimension=3)
    monkeypatch.setitem(PROFILES, ARCTIC_S_PROFILE_KEY, profile)
    return profile


class Disk:
    def __init__(self, free: int = 10**12) -> None:
        self.free = free

    def __call__(self, _path: Path) -> SimpleNamespace:
        return SimpleNamespace(free=self.free)


# ---- fixtures ------------------------------------------------------------------------------------------------------


def _add_paper(conn, title: str, roles: list[str | None], per_attachment: int = 2) -> tuple[int, list[int]]:  # type: ignore[no-untyped-def]
    paper_id = create_paper(conn, title=title, csl_json={"title": title}, processing_tier="fully-chunked")
    ids: list[int] = []
    for i, role in enumerate(roles):
        att = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum=f"mod-{title}-{i}",
            role=role,
        )
        for j in range(per_attachment):
            ids.append(
                create_chunk(
                    conn,
                    paper_id=paper_id,
                    attachment_id=att,
                    text=f"{PLAIN} ({title} {i}.{j})",
                    page_start=2,
                    page_end=2,
                    bbox_coordinate_system="pdf-points-top-left",
                    extraction_tool="fixture",
                    extraction_version="1",
                    chunking_strategy="paragraph",
                    chunk_version=f"{title}-{i}-{j}-v1",
                    source_attachment_checksum=f"mod-{title}-{i}",
                    section="results",
                )
            )
    return paper_id, ids


def _minilm(conn, chunk_ids: list[int]) -> None:  # type: ignore[no-untyped-def]
    for cid in chunk_ids:
        version = conn.execute(select(chunks.c.chunk_version).where(chunks.c.id == cid)).scalar_one()
        conn.execute(
            insert(embeddings).values(
                target_type="chunk",
                target_id=cid,
                model_name="all-MiniLM-L6-v2",
                model_version="all-MiniLM-L6-v2",
                dimension=3,
                normalization="whitespace-lower-v1",
                source_text_version=version,
                source_chunk_version=version,
                vector_store_kind="memory",
                vector_store_ref=f"m{cid}",
            )
        )


def _library_0516(db_url: str, n_papers: int = 4) -> dict:
    """A 0.5.16-shaped library: legacy ``primary`` attachments, MiniLM vectors, an annotation, no v2 rows."""
    engine = make_engine(db_url)
    with engine.begin() as conn:
        all_ids: list[int] = []
        paper_ids = []
        for i in range(n_papers):
            pid, ids = _add_paper(conn, f"legacy{i}", ["primary"])
            paper_ids.append(pid)
            all_ids += ids
        _minilm(conn, all_ids)
        create_annotation(conn, paper_id=paper_ids[0], page=2, color="yellow", bboxes_json=[], anchor_text="x")
    engine.dispose()
    return {"papers": paper_ids, "chunks": all_ids}


def _library_research_master(db_url: str) -> dict:
    """Research-master shape: mixed attachment roles, a registration-only paper and a metadata-only record."""
    engine = make_engine(db_url)
    with engine.begin() as conn:
        mixed, _ = _add_paper(conn, "mixed", ["article-fulltext", "preregistration", "supplement", "other"])
        legacy, _ = _add_paper(conn, "legacy", ["primary", "protocol"])
        reg_only, _ = _add_paper(conn, "registration-only", ["preregistration"])
        meta = create_paper(conn, title="metadata only", csl_json={"title": "m"}, processing_tier="metadata-only")
    engine.dispose()
    return {"mixed": mixed, "legacy": legacy, "registration_only": reg_only, "metadata_only": meta}


def _snapshot(engine) -> dict:  # type: ignore[no-untyped-def]
    """Everything modernization must never touch."""
    with engine.connect() as conn:
        return {
            "papers": [tuple(r) for r in conn.execute(select(papers).order_by(papers.c.id))],
            "chunks": [tuple(r) for r in conn.execute(select(chunks).order_by(chunks.c.id))],
            "annotations": [tuple(r) for r in conn.execute(select(annotations).order_by(annotations.c.id))],
            "minilm": [
                tuple(r)
                for r in conn.execute(
                    select(embeddings).where(embeddings.c.model_name == "all-MiniLM-L6-v2").order_by(embeddings.c.id)
                )
            ],
        }


def _integrity_ok(engine) -> bool:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        return conn.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"


class Counting:
    """Wraps the production derivation and counts calls per paper."""

    def __init__(self, fail_for: set[int] | None = None, error: BaseException | None = None) -> None:
        self.calls: list[int] = []
        self.fail_for = fail_for or set()
        self.error = error

    def __call__(self, conn, paper_id, references):  # type: ignore[no-untyped-def]
        self.calls.append(paper_id)
        if paper_id in self.fail_for:
            raise self.error or ValueError("malformed paper")
        return derive_paper(conn, paper_id, references)


class Recording:
    """Records ``start``/``pause`` calls the coordinator makes on the supervisor."""

    def __init__(self, inner: IndexSupervisor | None = None) -> None:
        self.inner = inner
        self.starts = 0
        self.pauses = 0

    def start(self, profile):  # type: ignore[no-untyped-def]
        self.starts += 1
        return self.inner.start(profile) if self.inner else {}

    def pause(self, key):  # type: ignore[no-untyped-def]
        self.pauses += 1
        return self.inner.pause(key) if self.inner else {}


def _coordinator(
    engine,
    supervisor=None,
    *,
    model: dict | None = None,
    derive=None,
    probe=None,
    disk=None,
    per_pass: int = 50,
) -> ModernizationCoordinator:  # type: ignore[no-untyped-def]
    url = engine.url.render_as_string(hide_password=False)
    classifier = SourceRoleClassifier(
        engine,
        url,
        probe=probe or Probe(),
        disk_usage=disk or Disk(),
        derive=derive or derive_paper,
        papers_per_pass=per_pass,
    )
    state = {"model": model or VERIFIED}
    coordinator = ModernizationCoordinator(
        engine,
        CoordinatorConfig(db_url=url),
        supervisor=lambda: supervisor,
        model_status=lambda: state["model"],
        classifier=classifier,
    )
    coordinator.model_state = state  # type: ignore[attr-defined]
    return coordinator


def _drive(coordinator: ModernizationCoordinator, supervisor: IndexSupervisor | None, timeout: float = 60.0) -> dict:
    """Tick both until neither has anything left to do. Time-bounded rather than round-bounded: the supervisor's
    own catch-up (e.g. ``more_work_appeared``) waits out a real backoff before relaunching."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        delay = coordinator.tick()
        if supervisor is not None:
            for live in list(supervisor._live.values()):
                join = getattr(live.handle, "join", None)
                if join:
                    join(0.2)
            supervisor.tick()
        status = coordinator.status()
        idle = delay > 0 and (supervisor is None or not supervisor._live)
        if idle and status["indexing"]["run_state"] not in set(index_runs.ACTIVE_STATES):
            return status
        if idle:
            time.sleep(0.1)
    return coordinator.status()


# ---- upgrade and steady state ---------------------------------------------------------------------------------------


def test_a_0516_library_modernizes_automatically_and_touches_nothing_else(temp_db_url: str, small_arctic) -> None:
    lib = _library_0516(temp_db_url, n_papers=4)
    engine = make_engine(temp_db_url)
    before = _snapshot(engine)
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    coordinator = _coordinator(engine, supervisor)
    status = _drive(coordinator, supervisor)

    assert status["classification"]["state"] == "complete", status
    assert status["classification"]["papers_current"] == 4 and status["classification"]["papers_pending"] == 0
    assert status["indexing"]["state"] == "complete" and status["indexing"]["missing_chunks"] == 0, status
    assert status["model"]["verified"] and status["intent"] == AUTO and status["coordinating_here"]
    assert _snapshot(engine) == before  # papers, chunks, annotations and MiniLM vectors untouched
    with engine.connect() as conn:
        assert profile_coverage(conn, small_arctic)["indexed_chunks"] == len(lib["chunks"])
        integrity = vector_integrity(conn, ScriptedArctic(), dimension=3)
        # Scheduling only: the effective retrieval model stays MiniLM and no preference was written.
        assert active_retrieval_profile(conn).key == "minilm"
        assert (
            conn.execute(
                select(library_settings.c.value).where(library_settings.c.key == ACTIVE_RETRIEVAL_PROFILE_SETTING)
            ).first()
            is None
        )
    assert integrity["missing_vector_ids"] == [] and integrity["duplicate_current_chunks"] == 0
    assert _integrity_ok(engine)
    engine.dispose()


def test_research_master_shape_completes_without_registration_or_metadata_papers_blocking(
    temp_db_url: str, small_arctic
) -> None:
    lib = _library_research_master(temp_db_url)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    status = _drive(_coordinator(engine, supervisor), supervisor)
    cls = status["classification"]
    assert cls["state"] == "complete" and cls["papers_with_classified_chunks"] == 2 and cls["papers_pending"] == 0
    assert cls["papers_without_classified_chunks"] == 1  # registration-only: neither pending nor current
    assert status["indexing"]["eligible_chunks"] == 4 and status["indexing"]["state"] == "complete"
    with engine.connect() as conn:
        classified = conn.execute(
            select(func.count())
            .select_from(chunk_structure.join(chunks, chunks.c.id == chunk_structure.c.chunk_id))
            .where(chunks.c.paper_id == lib["registration_only"])
        ).scalar_one()
    assert classified == 0
    engine.dispose()


def test_an_already_modernized_library_starts_no_work(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=3)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    _drive(_coordinator(engine, supervisor), supervisor)

    derive = Counting()
    recording = Recording(supervisor)
    reopened = _coordinator(engine, recording, derive=derive)  # a fresh app session on the same library
    delays = [reopened.tick() for _ in range(5)]
    assert derive.calls == [] and recording.starts == 0 and supervisor._live == {}
    assert all(d == reopened.config.check_seconds for d in delays)  # idle cadence, no busy loop
    status = reopened.status()
    assert status["classification"]["state"] == "complete" and status["indexing"]["state"] == "complete"
    engine.dispose()


def test_a_large_synthetic_library_progresses_in_bounded_passes(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for i in range(240):
            _add_paper(conn, f"bulk{i}", ["primary"], per_attachment=3)
    derive = Counting()
    coordinator = _coordinator(engine, Recording(), model=ABSENT, derive=derive, per_pass=50)
    delays = []
    while True:
        delays.append(coordinator.tick())
        if delays[-1] > 0:
            break
        assert coordinator.status()["classification"]["state"] == "running"
    assert len(delays) == 5 and delays[:4] == [0.0] * 4  # 50 papers per pass, re-reading intent between passes
    assert sorted(derive.calls) == sorted(set(derive.calls)) and len(derive.calls) == 240  # each paper once
    assert class_coverage(engine)["papers_needing_derivation"] == 0
    assert coordinator.status()["indexing"]["state"] == "waiting_for_model"
    engine.dispose()


# ---- interruption and recovery --------------------------------------------------------------------------------------


def test_interrupted_classification_resumes_without_rederiving_current_papers(temp_db_url: str) -> None:
    _library_0516(temp_db_url, n_papers=5)
    engine = make_engine(temp_db_url)
    first = Counting()
    session1 = _coordinator(engine, Recording(), model=ABSENT, derive=first, per_pass=2)
    session1.tick()
    session1.shutdown()  # normal close after two papers
    assert class_coverage(engine)["papers_current"] == 2

    second = Counting()
    session2 = _coordinator(engine, Recording(), model=ABSENT, derive=second, per_pass=2)
    _drive(session2, None)
    assert set(first.calls).isdisjoint(second.calls) and len(second.calls) == 3
    assert class_coverage(engine)["papers_needing_derivation"] == 0 and _integrity_ok(engine)
    engine.dispose()


def test_normal_shutdown_stops_a_running_pass_between_papers(temp_db_url: str) -> None:
    _library_0516(temp_db_url, n_papers=6)
    engine = make_engine(temp_db_url)

    def slow(conn, paper_id, references):  # type: ignore[no-untyped-def]
        time.sleep(0.3)
        return derive_paper(conn, paper_id, references)

    coordinator = _coordinator(engine, Recording(), model=ABSENT, derive=slow)
    coordinator.start()
    _wait(lambda: class_coverage(engine)["papers_current"] >= 1, 30)
    started = time.monotonic()
    coordinator.shutdown()
    assert time.monotonic() - started < 5 and not coordinator._thread.is_alive()  # type: ignore[union-attr]
    done = class_coverage(engine)["papers_current"]
    assert 1 <= done < 6 and _integrity_ok(engine)
    _drive(_coordinator(engine, Recording(), model=ABSENT), None)
    assert class_coverage(engine)["papers_needing_derivation"] == 0
    engine.dispose()


def _child(db_url: str, marker: Path, delay: float = 0.5) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.modernization_child",
            "--db-url",
            db_url,
            "--marker",
            str(marker),
            "--delay",
            str(delay),
        ],
        cwd=str(ROOT),
    )


def _hard_kill(process: subprocess.Popen) -> None:
    os.kill(process.pid, signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL)
    process.wait(timeout=30)


def test_forced_termination_during_classification_then_another_process_takes_over(
    temp_db_url: str, tmp_path: Path
) -> None:
    """A real second process leads and classifies; this process only reports. Killing the leader mid-paper rolls
    that paper back; this process then takes over leadership and completes the rest."""
    _library_0516(temp_db_url, n_papers=6)
    engine = make_engine(temp_db_url)
    before = _snapshot(engine)
    marker = tmp_path / "leading"
    child = _child(temp_db_url, marker)
    try:
        _wait(marker.exists, 120)
        derive = Counting()
        follower = _coordinator(engine, Recording(), model=ABSENT, derive=derive)
        follower.tick()
        assert not follower.is_leader and derive.calls == []
        assert follower.status()["classification"]["state"] == "owned_elsewhere"
        assert not follower.status()["coordinating_here"]
        _hard_kill(child)  # TerminateProcess / SIGKILL: no cleanup code runs in the leader
    finally:
        if child.poll() is None:
            child.kill()
    partial = class_coverage(engine)["papers_current"]
    assert 1 <= partial < 6 and _integrity_ok(engine)
    status = _drive(follower, None)
    assert follower.is_leader and status["classification"]["state"] == "complete"
    assert len(derive.calls) == 6 - partial  # nothing the killed process committed is re-derived
    assert _snapshot(engine) == before and _integrity_ok(engine)
    engine.dispose()


def test_two_coordinators_in_one_process_elect_one_leader(temp_db_url: str) -> None:
    _library_0516(temp_db_url, n_papers=3)
    first_engine, second_engine = make_engine(temp_db_url), make_engine(temp_db_url)
    a_derive, b_derive = Counting(), Counting()
    a = _coordinator(first_engine, Recording(), model=ABSENT, derive=a_derive)
    b = _coordinator(second_engine, Recording(), model=ABSENT, derive=b_derive, per_pass=1)
    b.tick()
    a.tick()
    assert b.is_leader and not a.is_leader and a_derive.calls == []
    b.shutdown()
    _drive(a, None)
    assert a.is_leader and len(a_derive.calls) + len(b_derive.calls) == 3
    first_engine.dispose()
    second_engine.dispose()


def test_model_unavailable_at_startup_keeps_indexing_pending_until_verified(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=2)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    recording = Recording(supervisor)
    coordinator = _coordinator(engine, recording, model=ABSENT)
    status = _drive(coordinator, supervisor)
    assert status["classification"]["state"] == "complete"  # classification never waits for the model
    assert status["indexing"]["state"] == "waiting_for_model" and status["indexing"]["automatic_recovery"]
    assert recording.starts == 0 and supervisor.row(ARCTIC_S_PROFILE_KEY) is None  # nothing loaded or downloaded
    coordinator.model_state["model"] = VERIFIED  # type: ignore[attr-defined]  # provisioning finished later
    status = _drive(coordinator, supervisor)
    assert recording.starts == 1 and status["indexing"]["state"] == "complete"
    engine.dispose()


def test_shutdown_during_arctic_indexing_resumes_on_the_next_launch_without_duplicates(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _library_0516(temp_db_url, n_papers=8)
    engine = make_engine(temp_db_url)
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "slow")

    def process_supervisor() -> IndexSupervisor:
        cfg = SupervisorConfig(db_url=temp_db_url, poll_seconds=0.1, initial_batch_size=2)
        return IndexSupervisor(engine, cfg, SubprocessLauncher(cfg, module="tests.index_worker_fake"), probe=Probe())

    first = process_supervisor()
    coordinator = _coordinator(engine, first)
    coordinator.tick()
    _wait(lambda: (first.row(ARCTIC_S_PROFILE_KEY) or {}).get("indexed_chunks", 0) >= 2, 120)
    coordinator.shutdown()
    first.shutdown()
    row = first.row(ARCTIC_S_PROFILE_KEY)
    assert row["state"] == "interrupted" and row["intent"] == "run"

    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "normal")
    second = process_supervisor()  # next launch
    second.reconcile_on_startup()
    recording = Recording(second)
    relaunch = _coordinator(engine, recording)
    relaunch.tick()
    assert recording.starts == 0  # the supervisor's own recovery owns this build; no second start
    _wait(lambda: second.tick() or (second.row(ARCTIC_S_PROFILE_KEY) or {})["state"] == "completed", 120)
    with engine.connect() as conn:
        assert profile_coverage(conn, ARCTIC)["complete"]
        integrity = vector_integrity(
            conn,
            type("E", (), {"name": ARCTIC.model_name, "version": ARCTIC.model_version})(),
            dimension=ARCTIC.dimension,
        )
    assert integrity["duplicate_current_chunks"] == 0
    engine.dispose()


def test_a_second_supervisor_never_steals_a_build_whose_worker_is_still_starting(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two app instances on one library: B ticks while A's worker process is still importing (no worker lock yet).
    A's launch lease tells B the build is owned, so B neither relabels the row nor launches a second worker."""
    _library_0516(temp_db_url, n_papers=4)
    monkeypatch.setenv("CALLOSUM_FAKE_INDEX_MODE", "normal")
    engine_a, engine_b = make_engine(temp_db_url), make_engine(temp_db_url)
    cfg = SupervisorConfig(db_url=temp_db_url, poll_seconds=0.1)
    a = IndexSupervisor(engine_a, cfg, SubprocessLauncher(cfg, module="tests.index_worker_fake"), probe=Probe())
    b = IndexSupervisor(engine_b, cfg, SubprocessLauncher(cfg, module="tests.index_worker_fake"), probe=Probe())
    a.start(ARCTIC)  # the real profile: worker processes cannot see a test's monkeypatched one
    token = a.row(ARCTIC_S_PROFILE_KEY)["worker_token"]
    assert not worker_holds_lock(temp_db_url, ARCTIC_S_PROFILE_KEY)  # A's worker has not taken its lock yet
    for _ in range(5):
        b.tick()
        b.reconcile_on_startup()
    assert b._live == {} and b.row(ARCTIC_S_PROFILE_KEY)["worker_token"] == token
    _wait(lambda: a.tick() or (a.row(ARCTIC_S_PROFILE_KEY) or {})["state"] == "completed", 120)
    assert a.row(ARCTIC_S_PROFILE_KEY)["failure_kind"] is None
    # The lease is released with the build: B may launch the next one.
    probe = __import__("app.backend.embeddings.index_lock", fromlist=["try_lock"]).try_lock(
        launch_lease_path(temp_db_url, ARCTIC_S_PROFILE_KEY)
    )
    assert probe is not None
    probe.release()
    engine_a.dispose()
    engine_b.dispose()


# ---- intent ----------------------------------------------------------------------------------------------------------


def test_pause_persists_across_restart_and_blocks_classification_and_indexing(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=4)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(delay=0.2), Probe(), initial_batch_size=1)
    coordinator = _coordinator(engine, supervisor, per_pass=1)
    coordinator.tick()  # one paper classified, Arctic build started
    assert supervisor.row(ARCTIC_S_PROFILE_KEY)["state"] in ("running", "queued")
    status = coordinator.pause()
    assert status["intent"] == PAUSED
    _drive(coordinator, supervisor, timeout=20)
    assert supervisor.row(ARCTIC_S_PROFILE_KEY)["state"] == "paused"
    done = class_coverage(engine)["papers_current"]
    coordinator.shutdown()

    derive = Counting()
    restarted_supervisor = _threaded(engine, ScriptedArctic(), Probe())
    restarted_supervisor.reconcile_on_startup()
    recording = Recording(restarted_supervisor)
    restarted = _coordinator(engine, recording, derive=derive)
    for _ in range(3):
        restarted.tick()
        restarted_supervisor.tick()
    assert read_intent(engine) == PAUSED and derive.calls == [] and recording.starts == 0
    assert class_coverage(engine)["papers_current"] == done
    status = restarted.status()
    assert status["classification"]["state"] == "paused" and status["classification"]["needs_user"]
    assert status["indexing"]["state"] == "paused" and status["indexing"]["needs_user"]

    restarted.resume()
    status = _drive(restarted, restarted_supervisor)
    assert status["classification"]["state"] == "complete" and status["indexing"]["state"] == "complete"
    engine.dispose()


def test_an_explicit_index_cancel_is_never_reinterpreted_as_permission_to_restart(
    temp_db_url: str, small_arctic
) -> None:
    _library_0516(temp_db_url, n_papers=3)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(delay=0.2), Probe(), initial_batch_size=1)
    recording = Recording(supervisor)
    coordinator = _coordinator(engine, recording)
    coordinator.tick()
    supervisor.cancel(ARCTIC_S_PROFILE_KEY)  # Settings -> Retrieval model -> Cancel
    _drive(coordinator, supervisor, timeout=20)
    assert supervisor.row(ARCTIC_S_PROFILE_KEY)["state"] == "cancelled"
    starts = recording.starts
    coordinator.shutdown()  # the app closes

    with engine.begin() as conn:  # an import after the cancel
        _add_paper(conn, "imported", ["article-fulltext"])
    restarted_supervisor = _threaded(engine, ScriptedArctic(), Probe())
    restarted_supervisor.reconcile_on_startup()
    recording2 = Recording(restarted_supervisor)
    restarted = _coordinator(engine, recording2)
    status = _drive(restarted, restarted_supervisor)
    assert recording.starts == starts and recording2.starts == 0
    assert status["indexing"]["state"] == "cancelled" and status["indexing"]["needs_user"]
    assert status["classification"]["state"] == "complete"  # the cancel covers the index build only

    restarted.resume()  # an explicit resume *after* the cancel restarts it
    status = _drive(restarted, restarted_supervisor)
    assert recording2.starts == 1 and status["indexing"]["state"] == "complete"
    engine.dispose()


def test_a_settings_pause_of_the_index_is_respected_by_the_coordinator(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=3)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(delay=0.2), Probe(), initial_batch_size=1)
    recording = Recording(supervisor)
    coordinator = _coordinator(engine, recording)
    coordinator.tick()
    supervisor.pause(ARCTIC_S_PROFILE_KEY)
    status = _drive(coordinator, supervisor, timeout=20)
    assert status["indexing"]["state"] == "paused" and recording.starts == 1
    assert read_intent(engine) == AUTO  # modernization itself was not paused; classification finished
    assert status["classification"]["state"] == "complete"
    supervisor.start(small_arctic)  # the existing manual Resume still works
    assert _drive(coordinator, supervisor)["indexing"]["state"] == "complete"
    engine.dispose()


def test_a_failed_build_is_not_restarted_automatically(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=2)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(fail=OSError("checkpoint missing")), Probe())
    recording = Recording(supervisor)
    status = _drive(_coordinator(engine, recording), supervisor)
    assert status["indexing"]["state"] == "failed" and status["indexing"]["needs_user"]
    assert status["indexing"]["run_failure_kind"] and recording.starts == 1
    assert not status["indexing"]["automatic_recovery"]
    engine.dispose()


# ---- catch-up after import --------------------------------------------------------------------------------------------


def test_import_after_completion_is_caught_up_automatically(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=2)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(), Probe())
    recording = Recording(supervisor)
    coordinator = _coordinator(engine, recording)
    _drive(coordinator, supervisor)
    with engine.begin() as conn:
        _add_paper(conn, "new", ["article-fulltext"])
    status = _drive(coordinator, supervisor)
    assert recording.starts == 2 and status["indexing"]["state"] == "complete"
    assert status["indexing"]["missing_chunks"] == 0 and status["classification"]["papers_current"] == 3
    engine.dispose()


def test_import_while_modernization_runs_is_included(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=3)
    engine = make_engine(temp_db_url)
    supervisor = _threaded(engine, ScriptedArctic(delay=0.1), Probe(), initial_batch_size=1)
    coordinator = _coordinator(engine, supervisor, per_pass=1)
    coordinator.tick()
    with engine.begin() as conn:
        _add_paper(conn, "during", ["article-fulltext"])
    status = _drive(coordinator, supervisor)
    assert status["classification"]["papers_current"] == 4 and status["indexing"]["state"] == "complete"
    assert status["indexing"]["eligible_chunks"] == 8 and status["indexing"]["missing_chunks"] == 0
    engine.dispose()


# ---- failures and shortages --------------------------------------------------------------------------------------------


def test_one_failing_paper_is_isolated_reported_and_not_retried_in_a_loop(temp_db_url: str) -> None:
    lib = _library_0516(temp_db_url, n_papers=4)
    engine = make_engine(temp_db_url)
    bad = lib["papers"][1]
    derive = Counting(fail_for={bad})
    coordinator = _coordinator(engine, Recording(), model=ABSENT, derive=derive)
    status = _drive(coordinator, None)
    cls = status["classification"]
    assert cls["state"] == "failed_papers" and cls["papers_current"] == 3 and cls["papers_pending"] == 1
    assert cls["papers_failed_this_session"] == 1 and "could not be classified" in cls["detail"]
    assert derive.calls.count(bad) == 1
    for _ in range(5):
        assert coordinator.tick() == coordinator.config.check_seconds
    assert derive.calls.count(bad) == 1  # remembered, not retried each check
    with engine.begin() as conn:  # the paper's text changes (e.g. reprocessed): it is retried
        conn.execute(update(chunks).where(chunks.c.paper_id == bad).values(chunk_version="fixed-v2"))
    derive.fail_for.clear()
    status = _drive(coordinator, None)
    assert (
        status["classification"]["state"] == "complete" and status["classification"]["papers_failed_this_session"] == 0
    )
    engine.dispose()


def test_database_lock_contention_waits_and_recovers(temp_db_url: str) -> None:
    _library_0516(temp_db_url, n_papers=3)
    engine = make_engine(temp_db_url)
    locked = OperationalError("INSERT", {}, Exception("database is locked"))
    derive = Counting(error=locked)
    derive.fail_for = {0}  # placeholder; replaced below to lock the first attempted paper
    coordinator = _coordinator(engine, Recording(), model=ABSENT, derive=derive)
    first_pending = coordinator.classifier.pending()[0]
    derive.fail_for = {first_pending}
    delay = coordinator.tick()
    assert delay == coordinator.config.retry_seconds
    status = coordinator.status()
    assert status["classification"]["state"] == "database_busy" and status["classification"]["automatic_recovery"]
    assert coordinator.classifier.failures == {}  # contention is not a paper failure
    derive.fail_for.clear()
    assert _drive(coordinator, None)["classification"]["state"] == "complete"
    engine.dispose()


def test_low_disk_and_low_memory_stop_classification_without_writing_then_recover(temp_db_url: str) -> None:
    _library_0516(temp_db_url, n_papers=2)
    engine = make_engine(temp_db_url)
    disk, probe = Disk(free=10**8), Probe(PLENTY)
    derive = Counting()
    coordinator = _coordinator(engine, Recording(), model=ABSENT, derive=derive, disk=disk, probe=probe)
    assert coordinator.tick() == coordinator.config.retry_seconds
    assert coordinator.status()["classification"]["state"] == "waiting_disk" and derive.calls == []
    disk.free = 10**12
    probe.snapshot = LOW
    assert coordinator.tick() == coordinator.config.retry_seconds
    assert coordinator.status()["classification"]["state"] == "waiting_resources" and derive.calls == []
    probe.snapshot = PLENTY
    assert _drive(coordinator, None)["classification"]["state"] == "complete"
    engine.dispose()


def test_a_genuinely_full_disk_during_classification_keeps_committed_papers(temp_db_url: str) -> None:
    _library_0516(temp_db_url, n_papers=3)
    engine = make_engine(temp_db_url)
    full = OperationalError("INSERT", {}, Exception("database or disk is full"))
    derive = Counting(error=full)
    coordinator = _coordinator(engine, Recording(), model=ABSENT, derive=derive)
    derive.fail_for = {coordinator.classifier.pending()[1]}
    coordinator.tick()
    assert coordinator.status()["classification"]["state"] == "waiting_disk"
    assert class_coverage(engine)["papers_current"] == 1 and coordinator.classifier.failures == {}
    derive.fail_for.clear()
    assert _drive(coordinator, None)["classification"]["state"] == "complete" and _integrity_ok(engine)
    engine.dispose()


def test_low_disk_for_indexing_is_left_to_the_supervisor(temp_db_url: str, small_arctic) -> None:
    _library_0516(temp_db_url, n_papers=2)
    engine = make_engine(temp_db_url)
    disk = Disk(free=10**8)
    cfg = SupervisorConfig(db_url=temp_db_url)
    from app.backend.embeddings.index_supervisor import ThreadLauncher
    from app.backend.embeddings.vector_store import InMemoryVectorStore

    launcher = ThreadLauncher(
        engine, lambda _k: ScriptedArctic(), InMemoryVectorStore(), probe=Probe(), disk_usage=disk
    )
    supervisor = IndexSupervisor(engine, cfg, launcher, probe=Probe(), disk_usage=disk)
    recording = Recording(supervisor)
    coordinator = _coordinator(engine, recording)
    for _ in range(4):
        coordinator.tick()
        supervisor.tick()
    status = coordinator.status()
    assert status["indexing"]["state"] == "waiting_disk" and status["indexing"]["automatic_recovery"]
    assert recording.starts == 1  # one request; the supervisor's own waiting_disk recovery takes it from there
    disk.free = 10**12
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, next_retry_at=index_runs.now())
    assert _drive(coordinator, supervisor)["indexing"]["state"] == "complete"
    engine.dispose()


def test_classification_makes_no_network_request(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _library_0516(temp_db_url, n_papers=3)
    engine = make_engine(temp_db_url)
    attempts: list[object] = []

    def refuse(self, address):  # type: ignore[no-untyped-def]
        attempts.append(address)
        raise OSError("network disabled in this test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    status = _drive(_coordinator(engine, Recording(), model=ABSENT), None)
    assert status["classification"]["state"] == "complete" and attempts == []
    engine.dispose()


# ---- API contract ----------------------------------------------------------------------------------------------------


def test_status_endpoint_contract_and_durable_pause_resume(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend.api.app import create_app

    _library_0516(temp_db_url, n_papers=2)
    monkeypatch.delenv("CALLOSUM_APP_DATA_DIR", raising=False)
    monkeypatch.delenv("CALLOSUM_MODERNIZATION", raising=False)
    app = create_app(db_url=temp_db_url)
    app.state.arctic_model_status = lambda: ABSENT
    with TestClient(app) as client:
        body = client.get("/modernization").json()
        assert body["enabled"] is False and body["disabled_reason"] == "development_checkout"
        assert body["classification"]["papers_pending"] == 2 and body["classification"]["state"] == "disabled"
        assert body["indexing"]["missing_chunks"] == 4 and body["model"]["verified"] is False
        assert "%" not in str(body) and "eta" not in body and "percent" not in str(body).lower()
        path_bits = [Path(temp_db_url.split("///", 1)[1]).name, str(Path.home())]
        assert not any(bit in client.get("/modernization").text for bit in path_bits)
        assert client.post("/modernization/pause").json()["intent"] == PAUSED
        assert client.get("/papers").status_code == 200  # ordinary library use is unaffected
    engine = make_engine(temp_db_url)
    assert read_intent(engine) == PAUSED  # durable
    engine.dispose()
    with TestClient(create_app(db_url=temp_db_url)) as client:
        assert client.get("/modernization").json()["intent"] == PAUSED
        assert client.post("/modernization/resume").json()["intent"] == AUTO


def test_enabled_coordinator_runs_from_the_app_lifespan(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend.api.app import create_app

    _library_0516(temp_db_url, n_papers=2)
    monkeypatch.setenv("CALLOSUM_MODERNIZATION", "1")
    app = create_app(db_url=temp_db_url)
    app.state.arctic_model_status = lambda: ABSENT
    with TestClient(app) as client:
        _wait(lambda: client.get("/modernization").json()["classification"]["state"] == "complete", 60)
        body = client.get("/modernization").json()
        assert body["enabled"] and body["coordinating_here"] and body["indexing"]["state"] == "waiting_for_model"
        assert client.get("/papers").status_code == 200
    assert not app.state.modernization._thread.is_alive()  # stopped with the app
