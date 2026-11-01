"""Inc 618: automatic Arctic S activation, complete-index fallback to MiniLM, catch-up, and explicit user choices.

Disposable databases, synthetic encoders (``FakeArctic`` at the 3-d test dimension), and the real Ask route via the
FastAPI app. Index builds go through the production supervisor/worker loop (thread launcher) or through
``build_profile_index``. Automatic selection is enabled the way the packaged app enables it
(``CALLOSUM_MODERNIZATION``); the Arctic checkpoint's readiness is injected, so no model is ever loaded or downloaded.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update

from app.backend.api.routers import summaries as summaries_router
from app.backend.api.routers.embedding_index import index_supervisor
from app.backend.api.routers.modernization import coordinator
from app.backend.embeddings import index_runs, retrieval_resolution
from app.backend.embeddings.index_supervisor import IndexSupervisor, SupervisorConfig, ThreadLauncher
from app.backend.embeddings.profile_index import build_profile_index
from app.backend.embeddings.profiles import (
    ACTIVE_RETRIEVAL_PROFILE_SETTING,
    ARCTIC_S_PROFILE_KEY,
    BASELINE_PROFILE_KEY,
    PROFILES,
    profile_coverage,
)
from app.backend.embeddings.retrieval_resolution import (
    SOURCE_MODERNIZATION,
    SOURCE_USER,
    Preference,
    activate_arctic,
    read_preference,
    set_user_preference,
)
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.modernization import PAUSED, read_intent
from app.backend.persistence.annotations_repo import create_annotation
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import (
    annotations,
    chunks,
    citation_mappings,
    embeddings,
    library_settings,
    papers,
    summaries,
)
from app.backend.persistence.sqlite_retry import run_write
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence
from app.backend.summarization.query_planner import Facet, QueryPlan
from tests.api_helpers import _seed_summarization_library, _summarization_app
from tests.test_embedding_profiles import FakeArctic
from tests.test_index_recovery import Probe

ARCTIC = PROFILES[ARCTIC_S_PROFILE_KEY]
ROOT = Path(__file__).resolve().parents[1]
CLAIM = "Facial anomalies influence social judgments."


@pytest.fixture()
def small_arctic(monkeypatch: pytest.MonkeyPatch):
    profile = dataclasses.replace(ARCTIC, dimension=3)
    monkeypatch.setitem(PROFILES, ARCTIC_S_PROFILE_KEY, profile)
    return profile


@pytest.fixture(autouse=True)
def plenty_of_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resource checks see a fixed, ample snapshot (as in the inc-617 tests), so results never depend on the load of
    the machine running the suite. The thread worker the app builds binds ``measure`` as a default argument."""
    monkeypatch.setattr(ThreadLauncher.__init__, "__defaults__", (Probe(), None))


@pytest.fixture()
def automatic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Automatic selection on, exactly as in the packaged app; the coordinator thread is not started (tests tick)."""
    monkeypatch.setenv("CALLOSUM_MODERNIZATION", "1")


class Recorder:
    """A fake summary generator (the ``FakeSummaryGenerator`` interface) that records the evidence it was given, to
    compare retrieval between operations, and can run a hook between retrieval and the verify+persist step."""

    name = "fake-summary-generator"

    def __init__(self, sentences, hook=None) -> None:  # type: ignore[no-untyped-def]
        self.sentences = list(sentences)
        self.seen: list[list[int]] = []
        self.hook = hook

    def generate(self, *, source_chunks, scope_ref, engine=None):  # type: ignore[no-untyped-def]
        self.seen.append([c.chunk_id for c in source_chunks])
        if self.hook is not None:
            self.hook()
        return list(self.sentences)


class Env:
    """One disposable library and an app over it, with switchable model readiness."""

    def __init__(self, db_url: str, *, store: InMemoryVectorStore | None = None, hook=None) -> None:  # type: ignore[no-untyped-def]
        self.db_url = db_url
        self.engine = make_engine(db_url)
        self.model = {"track": "arctic-s", "state": "verified"}
        self.arctic = FakeArctic()
        self.seeded = getattr(self, "seeded", None)
        self.generator = Recorder([], hook=hook)
        self.app = _summarization_app(db_url, generator=self.generator)
        self.store = store or self.app.state.vector_store
        self.app.state.vector_store = self.store
        self.app.state.profile_embedding_models = {ARCTIC_S_PROFILE_KEY: self.arctic}
        self.status_fn = lambda: dict(self.model)  # replaceable after the coordinator exists
        self.app.state.arctic_model_status = lambda: self.status_fn()
        self.client = TestClient(self.app)
        index_supervisor(self.app).probe = Probe()
        coordinator(self.app).classifier.probe = Probe()

    def cite(self, chunk_id: int) -> None:
        self.generator.sentences = [
            CandidateSummarySentence(text=CLAIM, citations=[CandidateCitation(chunk_id=chunk_id, quote=CLAIM)])
        ]

    def build(self, **kwargs) -> dict:  # type: ignore[no-untyped-def]
        return build_profile_index(self.engine, model=FakeArctic(), vector_store=self.store, **kwargs)

    def ask(self, **body) -> dict:  # type: ignore[no-untyped-def]
        body = {"scope_type": "query", "query": "facial", "top_k": 2, **body}
        started = self.client.post("/summarize", json=body)
        assert started.status_code in (200, 202), started.text
        return self.client.get(f"/summarize/{started.json()['job_id']}").json()

    def provenance(self, payload: dict) -> dict:
        assert payload["status"] == "done", payload
        with self.engine.connect() as conn:
            ref = conn.execute(
                select(summaries.c.scope_ref_json).where(summaries.c.id == payload["summary_id"])
            ).scalar_one()
        return ref["retrieval_embedding"]

    def tick(self, rounds: int = 1) -> dict:
        managed = coordinator(self.app)
        supervisor = index_supervisor(self.app)
        for _ in range(rounds):
            managed.tick()
            for live in list(supervisor._live.values()):
                join = getattr(live.handle, "join", None)
                if join:
                    join(5)
            supervisor.tick()
        return managed.status()

    def nudge(self) -> None:
        """One coordinator + supervisor check without waiting for a worker (to interrupt work in flight)."""
        coordinator(self.app).tick()
        index_supervisor(self.app).tick()

    def settle(self, timeout: float = 30.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.tick()
            run = status["indexing"]["run_state"]
            if run not in set(index_runs.ACTIVE_STATES) and not index_supervisor(self.app)._live:
                return self.tick()
            time.sleep(0.05)
        return self.tick()

    def profiles(self) -> dict:
        return self.client.get("/embedding-profiles").json()


def _env(db_url: str, **kwargs) -> Env:  # type: ignore[no-untyped-def]
    seeded = _seed_summarization_library(db_url)
    env = Env(db_url, **kwargs)
    env.seeded = seeded
    env.cite(seeded["facial_chunk_id"])
    return env


def _import_paper(engine, title: str = "Imported Paper", text: str = "Facial cues shape trust.") -> list[int]:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        pid = create_paper(conn, title=title, csl_json={"title": title}, processing_tier="fully-chunked")
        att = create_attachment(
            conn,
            paper_id=pid,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum=f"import-{title}",
            role="article-fulltext",
        )
        return [
            create_chunk(
                conn,
                paper_id=pid,
                attachment_id=att,
                text=f"{text} ({i})",
                page_start=1,
                page_end=1,
                bbox_coordinate_system="pdf-points-top-left",
                extraction_tool="fixture",
                extraction_version="1",
                chunking_strategy="paragraph",
                chunk_version=f"paragraph:fixture-1:{title[:8]}-{i}",
                source_attachment_checksum=f"import-{title}",
                section="results",
            )
            for i in range(2)
        ]


def _arctic_complete(env: Env) -> bool:
    with env.engine.connect() as conn:
        return profile_coverage(conn, PROFILES[ARCTIC_S_PROFILE_KEY])["complete"]


def _snapshot(engine) -> dict:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        return {
            "papers": [tuple(r) for r in conn.execute(select(papers).order_by(papers.c.id))],
            "chunks": [tuple(r) for r in conn.execute(select(chunks).order_by(chunks.c.id))],
            "annotations": [tuple(r) for r in conn.execute(select(annotations).order_by(annotations.c.id))],
            "citations": [tuple(r) for r in conn.execute(select(citation_mappings).order_by(citation_mappings.c.id))],
            "minilm": [
                tuple(r)
                for r in conn.execute(
                    select(embeddings).where(embeddings.c.model_name != ARCTIC.model_name).order_by(embeddings.c.id)
                )
            ],
        }


# ---- activation and resolution -----------------------------------------------------------------------------------


def test_complete_verified_index_is_used_automatically_and_activation_is_recorded(
    temp_db_url: str, small_arctic, automatic
) -> None:
    env = _env(temp_db_url)
    env.build()
    payload = env.ask()
    record = env.provenance(payload)
    assert record["profile"] == ARCTIC_S_PROFILE_KEY and record["model_version"] == ARCTIC.model_version
    assert record["preference"] == "automatic" and record["fallback_reason"] is None
    assert record["index_verified_complete"] is True and record["intended_profile"] == ARCTIC_S_PROFILE_KEY
    assert env.arctic.query_calls  # the profile's own query side ranked the evidence
    assert payload["model_provenance"]["retrieval"]["note"] is None

    assert read_preference(env.engine.connect()) == Preference(None, None)  # resolution did not need the record
    status = env.tick()
    assert status["retrieval_preference"] == {
        "profile": ARCTIC_S_PROFILE_KEY,
        "source": SOURCE_MODERNIZATION,
        "legacy": False,
        "arctic_activated": True,
    }
    state = env.profiles()
    assert state["active"] == ARCTIC_S_PROFILE_KEY and state["preference"] == "automatic"
    assert state["explanation"].startswith("Using Arctic S")
    env.tick(3)  # idempotent: repeated checks change nothing
    with env.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(library_settings)).scalar_one() >= 2
        assert read_preference(conn) == Preference(ARCTIC_S_PROFILE_KEY, SOURCE_MODERNIZATION)


def test_partial_index_falls_back_to_minilm_and_never_searches_arctic(
    temp_db_url: str, small_arctic, automatic
) -> None:
    env = _env(temp_db_url)
    calls = {"n": 0}
    env.build(should_cancel=lambda: (calls.__setitem__("n", calls["n"] + 1) or calls["n"] > 1), batch_size=1)
    assert not _arctic_complete(env)
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "indexing"
    assert record["index_verified_complete"] is False and record["intended_profile"] == ARCTIC_S_PROFILE_KEY
    assert env.arctic.query_calls == []  # no Arctic query was ever encoded or searched
    assert env.profiles()["explanation"] == "Using MiniLM while the Arctic S index is being built."
    status = env.tick()
    assert not status["retrieval_preference"]["arctic_activated"]  # a partial index is never activated


def test_import_falls_back_then_catches_up_and_returns_to_arctic_with_no_click(
    temp_db_url: str, small_arctic, automatic
) -> None:
    env = _env(temp_db_url)
    status = env.settle()  # the coordinator schedules the first build itself, then activates it
    assert status["indexing"]["state"] == "complete" and status["retrieval_preference"]["arctic_activated"]
    first = env.ask()
    assert env.provenance(first)["profile"] == ARCTIC_S_PROFILE_KEY
    before = _snapshot(env.engine)

    new_chunks = _import_paper(env.engine)
    fallback = env.ask()
    record = env.provenance(fallback)
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "catching_up"
    assert fallback["model_provenance"]["retrieval"]["note"].startswith("MiniLM was used while newly added")
    assert env.profiles()["explanation"].startswith("Using MiniLM while newly added")

    status = env.settle()  # the import is caught up without any user action
    assert status["indexing"]["missing_chunks"] == 0 and status["indexing"]["state"] == "complete"
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY
    after = _snapshot(env.engine)
    assert after["papers"][: len(before["papers"])] == before["papers"]
    assert [c for c in after["chunks"] if c[0] not in new_chunks] == before["chunks"]
    assert after["annotations"] == before["annotations"]
    assert after["citations"][: len(before["citations"])] == before["citations"]
    assert after["minilm"][: len(before["minilm"])] == before["minilm"]  # existing MiniLM vectors unchanged


def test_import_during_the_first_build_is_included_before_activation(temp_db_url: str, small_arctic, automatic) -> None:
    env = _env(temp_db_url)
    env.tick()  # schedules the first build
    _import_paper(env.engine, title="During")
    status = env.settle()
    assert status["indexing"]["missing_chunks"] == 0 and status["retrieval_preference"]["arctic_activated"]
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY


def test_in_place_chunk_change_is_detected_promptly(temp_db_url: str, small_arctic, automatic) -> None:
    """617's signature summed version lengths, so an equal-length in-place version change was invisible until the
    30-minute safety refresh. Inc 618 checksums the versions: the change is seen on the next check."""
    env = _env(temp_db_url)
    env.settle()
    managed = coordinator(env.app)
    signature = managed._signature_now()
    chunk_id = env.seeded["facial_chunk_id"]
    with env.engine.begin() as conn:
        old = conn.execute(select(chunks.c.chunk_version).where(chunks.c.id == chunk_id)).scalar_one()
        new = old[:-1] + ("0" if old[-1] != "0" else "1")
        conn.execute(update(chunks).where(chunks.c.id == chunk_id).values(chunk_version=new))
    assert len(new) == len(old) and managed._signature_now() != signature
    assert env.provenance(env.ask())["fallback_reason"] == "catching_up"  # the per-Ask check is authoritative
    status = env.settle()
    assert status["indexing"]["missing_chunks"] == 0
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY


def test_attachment_role_swap_with_equal_counts_changes_the_signature(temp_db_url: str, automatic) -> None:
    env = _env(temp_db_url)
    a = _import_paper(env.engine, title="SwapA")
    b = _import_paper(env.engine, title="SwapB")
    managed = coordinator(env.app)
    with env.engine.begin() as conn:
        att_b = conn.execute(select(chunks.c.attachment_id).where(chunks.c.id == b[0])).scalar_one()
        from app.backend.persistence.schema import attachments

        conn.execute(update(attachments).where(attachments.c.id == att_b).values(role="supplement"))
    signature = managed._signature_now()
    with env.engine.begin() as conn:
        att_a = conn.execute(select(chunks.c.attachment_id).where(chunks.c.id == a[0])).scalar_one()
        conn.execute(update(attachments).where(attachments.c.id == att_a).values(role="supplement"))
        conn.execute(update(attachments).where(attachments.c.id == att_b).values(role="article-fulltext"))
    assert managed._signature_now() != signature


# ---- explicit choices ------------------------------------------------------------------------------------------------


def test_explicit_minilm_stays_minilm_after_arctic_is_ready(temp_db_url: str, small_arctic, automatic) -> None:
    env = _env(temp_db_url)
    assert env.client.put("/embedding-profiles/active", json={"key": BASELINE_PROFILE_KEY}).status_code == 200
    status = env.settle()
    assert status["indexing"]["state"] == "complete"  # the index is still built in the background
    assert not status["retrieval_preference"]["arctic_activated"]
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["preference"] == "user"
    assert record["fallback_reason"] is None and record["intended_profile"] is None
    state = env.profiles()
    assert (
        state["preference"] == BASELINE_PROFILE_KEY
        and state["explanation"] == "Using MiniLM (baseline) because you selected it."
    )
    assert (
        env.client.put("/embedding-profiles/active", json={"key": "automatic"}).json()["active"] == ARCTIC_S_PROFILE_KEY
    )
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY


def test_explicitly_forced_incomplete_arctic_fails_closed_with_a_way_back(
    temp_db_url: str, small_arctic, automatic
) -> None:
    env = _env(temp_db_url)
    env.build()
    assert env.client.put("/embedding-profiles/active", json={"key": ARCTIC_S_PROFILE_KEY}).status_code == 200
    assert env.provenance(env.ask())["preference"] == "user"
    count = env.engine.connect().execute(select(func.count()).select_from(summaries)).scalar_one()
    _import_paper(env.engine)
    payload = env.ask()
    assert payload["status"] == "error" and "Arctic S index covers" in payload["detail"]
    assert "automatic selection" in payload["detail"] and "does not search a partial index" in payload["detail"]
    assert env.engine.connect().execute(select(func.count()).select_from(summaries)).scalar_one() == count
    state = env.profiles()
    assert state["ask_blocked"] and state["preference"] == ARCTIC_S_PROFILE_KEY
    env.client.put("/embedding-profiles/active", json={"key": "automatic"})
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] in ("indexing", "catching_up")


def test_legacy_unmarked_selections_are_kept_as_the_users(temp_db_url: str, small_arctic, automatic) -> None:
    env = _env(temp_db_url)
    with env.engine.begin() as conn:  # a pre-618 row: the key, with no record of who chose it
        conn.execute(insert(library_settings).values(key=ACTIVE_RETRIEVAL_PROFILE_SETTING, value=BASELINE_PROFILE_KEY))
    env.build()
    env.tick()
    with env.engine.connect() as conn:
        assert read_preference(conn) == Preference(BASELINE_PROFILE_KEY, SOURCE_USER, legacy=True)
    assert env.provenance(env.ask())["profile"] == BASELINE_PROFILE_KEY  # never auto-switched
    state = env.profiles()
    assert state["legacy_preference"] is True and state["preference"] == BASELINE_PROFILE_KEY

    with env.engine.begin() as conn:  # a legacy Arctic choice that has become incomplete keeps failing closed
        conn.execute(update(library_settings).values(value=ARCTIC_S_PROFILE_KEY))
    _import_paper(env.engine)
    assert env.ask()["status"] == "error"


def test_user_choice_made_during_activation_wins(temp_db_url: str, small_arctic, automatic, monkeypatch) -> None:
    env = _env(temp_db_url)
    env.build()
    real = retrieval_resolution.profile_coverage
    writer: list[threading.Thread] = []

    def coverage_then_user_writes(conn, profile):  # type: ignore[no-untyped-def]
        result = real(conn, profile)
        if not writer:  # the user clicks MiniLM while activation holds the write transaction
            t = threading.Thread(target=lambda: run_write(env.engine, lambda c: set_user_preference(c, "minilm")))
            writer.append(t)
            t.start()
            time.sleep(0.3)
        return result

    monkeypatch.setattr(retrieval_resolution, "profile_coverage", coverage_then_user_writes)
    assert run_write(env.engine, lambda c: activate_arctic(c, model_verified=True)) == "activated"
    writer[0].join(10)
    with env.engine.connect() as conn:
        assert read_preference(conn) == Preference(BASELINE_PROFILE_KEY, SOURCE_USER)  # serialized after; user last
    monkeypatch.setattr(retrieval_resolution, "profile_coverage", real)
    assert run_write(env.engine, lambda c: activate_arctic(c, model_verified=True)) == "user_preference"
    with env.engine.connect() as conn:
        assert read_preference(conn) == Preference(BASELINE_PROFILE_KEY, SOURCE_USER)


def test_two_processes_activate_once(temp_db_url: str, small_arctic) -> None:
    env = _env(temp_db_url)
    env.build()
    script = (
        "import dataclasses, sys\n"
        "from app.backend.embeddings import profiles\n"
        "profiles.PROFILES['arctic-s'] = dataclasses.replace(profiles.PROFILES['arctic-s'], dimension=3)\n"
        "from app.backend.embeddings.retrieval_resolution import activate_arctic\n"
        "from app.backend.persistence.database import make_engine\n"
        "from app.backend.persistence.sqlite_retry import run_write\n"
        "engine = make_engine(sys.argv[1])\n"
        "print(run_write(engine, lambda c: activate_arctic(c, model_verified=True), attempts=20))\n"
    )
    procs = [
        subprocess.Popen([sys.executable, "-c", script, temp_db_url], cwd=str(ROOT), stdout=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    outcomes = sorted(p.communicate(timeout=120)[0].strip() for p in procs)
    assert outcomes == ["activated", "already_active"]
    with env.engine.connect() as conn:
        assert read_preference(conn) == Preference(ARCTIC_S_PROFILE_KEY, SOURCE_MODERNIZATION)
        rows = conn.execute(select(func.count()).select_from(library_settings)).scalar_one()
    assert rows == 2


# ---- startup, restart, pause, model readiness, stale rows --------------------------------------------------------------


def test_startup_with_an_already_complete_index_uses_arctic_immediately(
    temp_db_url: str, small_arctic, automatic
) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    store = InMemoryVectorStore()
    build_profile_index(make_engine(temp_db_url), model=FakeArctic(), vector_store=store)
    env = Env(temp_db_url, store=store)  # a fresh app session on that library
    env.cite(seeded["facial_chunk_id"])
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY  # no coordinator check needed
    assert env.tick()["retrieval_preference"]["arctic_activated"]


def test_restart_during_catch_up_resumes_and_returns_to_arctic(temp_db_url: str, small_arctic, automatic) -> None:
    store = InMemoryVectorStore()  # the persistent vector store both sessions share
    env = _env(temp_db_url, store=store)
    env.settle()
    for i in range(3):
        _import_paper(env.engine, title=f"Batch{i}")
    supervisor = index_supervisor(env.app)
    env.app.state.profile_embedding_models[ARCTIC_S_PROFILE_KEY] = SlowArctic()  # the launcher reads this per check
    index_runs.update_run(env.engine, ARCTIC_S_PROFILE_KEY, batch_size=1)  # an existing row keeps its own size
    env.nudge()  # catch-up starts
    time.sleep(0.4)
    coordinator(env.app).shutdown()
    supervisor.shutdown()  # the app closes mid catch-up
    assert not _arctic_complete(env)

    second = Env(temp_db_url, store=store)
    second.cite(env.seeded["facial_chunk_id"])
    assert second.provenance(second.ask())["fallback_reason"] == "catching_up"
    index_supervisor(second.app).reconcile_on_startup()
    status = second.settle()
    assert status["indexing"]["missing_chunks"] == 0
    assert second.provenance(second.ask())["profile"] == ARCTIC_S_PROFILE_KEY


@dataclasses.dataclass
class SlowArctic(FakeArctic):
    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        time.sleep(0.25 * len(texts))
        return super().encode_texts(texts)


def test_pause_and_cancel_keep_minilm_while_incomplete_but_never_block_a_complete_index(
    temp_db_url: str, small_arctic, automatic
) -> None:
    env = _env(temp_db_url)
    env.settle()
    env.client.post("/modernization/pause")
    assert read_intent(env.engine) == PAUSED
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY  # Pause stops work, not use of a complete index
    _import_paper(env.engine)
    env.tick(2)
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "paused"
    env.client.post("/modernization/resume")
    supervisor = index_supervisor(env.app)
    env.app.state.profile_embedding_models[ARCTIC_S_PROFILE_KEY] = SlowArctic()
    index_runs.update_run(env.engine, ARCTIC_S_PROFILE_KEY, batch_size=1)  # an existing row keeps its own size
    env.nudge()
    supervisor.cancel(ARCTIC_S_PROFILE_KEY)
    env.settle()
    assert supervisor.row(ARCTIC_S_PROFILE_KEY)["state"] == "cancelled"
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "cancelled"
    assert env.profiles()["explanation"] == "Using MiniLM: Arctic S indexing was cancelled."


@pytest.mark.parametrize("state", ["absent", "downloading", "corrupt", "raises"])
def test_missing_or_invalid_checkpoint_keeps_automatic_on_minilm(
    temp_db_url: str, small_arctic, automatic, state
) -> None:
    env = _env(temp_db_url)
    env.build()
    if state == "raises":
        env.status_fn = lambda: (_ for _ in ()).throw(OSError("unreadable state file"))
    else:
        env.model["state"] = state
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "model_unavailable"
    assert env.arctic.query_calls == []
    assert not env.tick()["retrieval_preference"]["arctic_activated"]
    with env.engine.connect() as conn:
        assert run_write(env.engine, lambda c: activate_arctic(c, model_verified=False)) == "model_unavailable"
        assert read_preference(conn) == Preference(None, None)
    # A user who explicitly chose Arctic keeps the inc-608 behaviour: the complete index is used.
    env.client.put("/embedding-profiles/active", json={"key": ARCTIC_S_PROFILE_KEY})
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY


def test_model_becoming_unavailable_after_activation_falls_back(temp_db_url: str, small_arctic, automatic) -> None:
    env = _env(temp_db_url)
    env.settle()
    env.model["state"] = "corrupt"
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "model_unavailable"


def test_completed_run_row_does_not_prove_coverage(temp_db_url: str, small_arctic, automatic) -> None:
    env = _env(temp_db_url)
    env.settle()
    assert index_supervisor(env.app).row(ARCTIC_S_PROFILE_KEY)["state"] == "completed"
    with env.engine.begin() as conn:  # a vector row disappears; the run row still says completed
        victim = conn.execute(
            select(embeddings.c.id).where(embeddings.c.model_name == ARCTIC.model_name).limit(1)
        ).scalar_one()
        conn.execute(delete(embeddings).where(embeddings.c.id == victim))
    assert index_supervisor(env.app).row(ARCTIC_S_PROFILE_KEY)["state"] == "completed"
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "catching_up"
    assert run_write(env.engine, lambda c: activate_arctic(c, model_verified=True)) == "incomplete"


# ---- in-flight operations --------------------------------------------------------------------------------------------


def test_an_ask_keeps_the_model_it_started_with_when_a_build_finishes_mid_operation(
    temp_db_url: str, small_arctic, automatic
) -> None:
    holder: dict[str, Env] = {}
    env = _env(temp_db_url, hook=lambda: holder["env"].build())  # completes the index between retrieval and save
    holder["env"] = env
    record = env.provenance(env.ask())
    assert record["profile"] == BASELINE_PROFILE_KEY and record["fallback_reason"] == "indexing"
    env.generator.hook = None
    assert env.provenance(env.ask())["profile"] == ARCTIC_S_PROFILE_KEY  # the next one resolves afresh


def test_an_import_between_resolution_and_ranking_fails_closed_and_saves_nothing(
    temp_db_url: str, small_arctic, automatic, monkeypatch
) -> None:
    env = _env(temp_db_url)
    env.build()
    real = summaries_router.resolve_profile_embedding_model

    def resolve_then_import(app, profile):  # type: ignore[no-untyped-def]
        _import_paper(env.engine, title="Racing")
        return real(app, profile)

    monkeypatch.setattr(summaries_router, "resolve_profile_embedding_model", resolve_then_import)
    with env.engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(summaries)).scalar_one()
    payload = env.ask()
    assert payload["status"] == "error" and payload["detail"] == summaries_router.AUTOMATIC_CHANGED_MESSAGE
    with env.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(summaries)).scalar_one() == count
    monkeypatch.setattr(summaries_router, "resolve_profile_embedding_model", real)
    assert env.provenance(env.ask())["fallback_reason"] == "indexing"  # the next Ask falls back cleanly


# ---- every route, same policy, same science ------------------------------------------------------------------------


def test_every_ask_route_records_the_same_resolution(temp_db_url: str, small_arctic, automatic, monkeypatch) -> None:
    env = _env(temp_db_url)
    plan = QueryPlan(scope="broad", facets=(Facet("a", "facial"), Facet("b", "social judgments")), planner_used=True)
    monkeypatch.setattr(summaries_router, "plan_query", lambda *a, **k: plan)
    faceted_body = {"query": "facial and social judgments"}
    selected_body = {"scope_type": "papers", "paper_ids": [env.seeded["facial_paper_id"]], "query": "facial"}
    for expected, reason in ((BASELINE_PROFILE_KEY, "indexing"), (ARCTIC_S_PROFILE_KEY, None)):
        if expected == ARCTIC_S_PROFILE_KEY:
            env.build()
        for body in ({}, selected_body, faceted_body):
            record = env.provenance(env.ask(**body))
            assert (record["profile"], record["fallback_reason"], record["preference"]) == (
                expected,
                reason,
                "automatic",
            )


def test_same_effective_model_retrieves_identically_whatever_chose_it(
    temp_db_url: str, small_arctic, automatic
) -> None:
    env = _env(temp_db_url)
    _import_paper(env.engine, title="Extra")
    env.build()
    automatic_arctic = env.ask()
    env.client.put("/embedding-profiles/active", json={"key": ARCTIC_S_PROFILE_KEY})
    explicit_arctic = env.ask()
    env.client.put("/embedding-profiles/active", json={"key": BASELINE_PROFILE_KEY})
    explicit_minilm = env.ask()
    env.client.put("/embedding-profiles/active", json={"key": "automatic"})
    env.model["state"] = "absent"
    fallback_minilm = env.ask()
    # The generator ran once per effective model: each second operation was an inc-493 synthesis-cache hit, which
    # requires the exact same ordered evidence. What chose the model does not change what it retrieves.
    assert len(env.generator.seen) == 2 and env.generator.seen[0] != env.generator.seen[1]
    for a, b in ((automatic_arctic, explicit_arctic), (explicit_minilm, fallback_minilm)):
        ca, cb = a["sentences"][0]["citations"][0], b["sentences"][0]["citations"][0]
        assert (ca["status"], ca["retrieval_confidence"], ca["support_confidence"]) == (
            cb["status"],
            cb["retrieval_confidence"],
            cb["support_confidence"],
        )


def test_annotations_survive_activation_and_fallback(temp_db_url: str, small_arctic, automatic) -> None:
    env = _env(temp_db_url)
    with env.engine.begin() as conn:
        create_annotation(
            conn, paper_id=env.seeded["facial_paper_id"], page=1, color="yellow", bboxes_json=[], anchor_text="x"
        )
    before = _snapshot(env.engine)
    env.settle()
    env.ask()
    after = _snapshot(env.engine)
    assert after["annotations"] == before["annotations"] and after["chunks"] == before["chunks"]
    assert after["minilm"][: len(before["minilm"])] == before["minilm"]


# ---- the manual-build provisioning loophole (inc 617 residual) ---------------------------------------------------------


def test_manual_build_never_loads_an_unverified_managed_checkpoint(
    temp_db_url: str, small_arctic, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.backend.model_provisioning import runner

    monkeypatch.delenv("CALLOSUM_DISABLE_MODEL_PROVISIONING", raising=False)
    monkeypatch.setenv("CALLOSUM_MODEL_PROVISIONING", "1")
    verified = {"value": False}
    monkeypatch.setattr(runner.Provisioner, "is_verified", lambda self: verified["value"])
    _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    loads: list[str] = []
    launcher = ThreadLauncher(
        engine, lambda key: loads.append(key) or FakeArctic(), InMemoryVectorStore(), probe=Probe()
    )
    supervisor = IndexSupervisor(engine, SupervisorConfig(db_url=temp_db_url), launcher, probe=Probe())
    supervisor.start(small_arctic)  # Settings -> Build index, before provisioning has verified the model
    for _ in range(3):
        supervisor.tick()
    row = supervisor.row(ARCTIC_S_PROFILE_KEY)
    assert loads == [] and supervisor._live == {}
    assert row["state"] == "queued" and row["failure_kind"] == "model_not_ready"
    from app.backend.api.routers.embedding_index import _message

    assert _message(row).startswith("Waiting for the model download")

    verified["value"] = True
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, next_retry_at=index_runs.now())
    deadline = time.monotonic() + 30
    while (supervisor.row(ARCTIC_S_PROFILE_KEY) or {}).get("state") != "completed" and time.monotonic() < deadline:
        for live in list(supervisor._live.values()):
            live.handle.join(1)
        supervisor.tick()
    assert loads == [ARCTIC_S_PROFILE_KEY] and supervisor.row(ARCTIC_S_PROFILE_KEY)["state"] == "completed"
    engine.dispose()


def test_source_checkouts_keep_the_developer_build_path(temp_db_url: str, small_arctic) -> None:
    from app.backend.model_provisioning import checkpoint_pending

    assert checkpoint_pending(ARCTIC.model_name) is False  # provisioning off (tests, source checkouts)
    assert checkpoint_pending("some/untracked-model") is False


def test_forced_arctic_never_loads_an_unverified_managed_checkpoint(
    temp_db_url: str, small_arctic, automatic, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete index outlives its checkpoint's verification (a damaged model cache): a user-forced Arctic Ask must
    then fail closed instead of loading with ``local_files_only=False``, which could fetch from the Hub."""
    from app.backend.model_provisioning import runner

    env = _env(temp_db_url)
    env.build()
    env.client.put("/embedding-profiles/active", json={"key": ARCTIC_S_PROFILE_KEY})
    monkeypatch.delenv("CALLOSUM_DISABLE_MODEL_PROVISIONING", raising=False)
    monkeypatch.setenv("CALLOSUM_MODEL_PROVISIONING", "1")
    monkeypatch.setattr(runner.Provisioner, "is_verified", lambda self: False)
    loads: list[object] = []
    real = summaries_router.resolve_profile_embedding_model
    monkeypatch.setattr(
        summaries_router, "resolve_profile_embedding_model", lambda app, p: loads.append(p) or real(app, p)
    )
    payload = env.ask()
    assert payload["status"] == "error" and "not verified" in payload["detail"] and loads == []
    assert env.profiles()["ask_blocked"]
    env.client.put("/embedding-profiles/active", json={"key": "automatic"})
    env.model["state"] = "corrupt"
    assert env.provenance(env.ask())["fallback_reason"] == "model_unavailable"
