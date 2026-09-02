from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.backend.api.routers.summaries import SummarizeRequest, _run_summarize_job
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import (
    chunks,
    citation_mappings,
    evidence_quotes,
    papers,
    summaries,
    summary_sentences,
)
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from app.backend.summarization.overview import FakeOverviewGenerator, OverviewSentence
from app.backend.summarization.overview_lifecycle import acquire_overview, generate_overview
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from tests.api_helpers import (
    ApiFakeEmbeddingModel,
    ConstantSupportScorer,
    InMemoryVectorStore,
    _seed_summarization_library,
    _summarization_app,
)


def _summary_generator(chunk_id: int) -> FakeSummaryGenerator:
    return FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[CandidateCitation(chunk_id=chunk_id, quote="Facial anomalies influence social judgments.")],
            )
        ]
    )


@dataclass
class BlockingOverviewGenerator:
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    calls: int = 0
    name: str = "blocking-overview"

    def generate(self, *, verified_claims, scope_ref):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.started.set()
        if not self.release.wait(10):
            raise TimeoutError("test did not release overview")
        return [OverviewSentence(text="Overview.", claim_indices=[0])]


@dataclass
class FailingOverviewGenerator:
    error: Exception
    calls: int = 0
    name: str = "failing-overview"

    def generate(self, *, verified_claims, scope_ref):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise self.error


def test_primary_is_committed_and_job_done_while_overview_is_blocked(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    overview = BlockingOverviewGenerator()
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=overview,
    )
    job_id = app.state.summary_jobs.create()
    worker = threading.Thread(
        target=_run_summarize_job,
        args=(app, job_id, SummarizeRequest(scope_type="papers", paper_ids=[seeded["facial_paper_id"]])),
    )
    worker.start()
    assert overview.started.wait(10)

    job = app.state.summary_jobs.get(job_id)
    assert job is not None and job.status == "done" and job.result is not None
    assert job.result.overview_status == "pending"
    assert [stage.key for stage in job.completed_stages] == [
        "preparing_sources",
        "generating_synthesis",
        "verifying_citations",
        "finalizing_result",
    ]
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        row = conn.execute(select(summaries)).mappings().one()
        assert row["overview_status"] == "running"
        assert row["overview_json"] is None
        assert conn.execute(select(func.count()).select_from(summary_sentences)).scalar_one() == 1
        assert conn.execute(select(func.count()).select_from(citation_mappings)).scalar_one() == 1
        assert conn.execute(select(func.count()).select_from(evidence_quotes)).scalar_one() == 1

    overview.release.set()
    worker.join(10)
    assert not worker.is_alive()
    with engine.connect() as conn:
        row = conn.execute(select(summaries)).mappings().one()
        assert row["overview_status"] == "complete"
        assert row["overview_json"] == [{"text": "Overview.", "claim_ordinals": [0]}]
    engine.dispose()


def test_inline_overview_generation_registers_a_status_popover_job(temp_db_url: str) -> None:
    # Finding 4 (backlog #57 fixwave): Phase A already marks the primary summary_jobs row "done"
    # before Phase B's real, egress-gated provider call even starts (see the comment in
    # _run_summarize_job) -- so the ONLY way this in-flight provider call is visible in the global
    # Status popover is the shared overview_jobs entry generate_overview() itself registers.
    seeded = _seed_summarization_library(temp_db_url)
    overview = BlockingOverviewGenerator()
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=overview,
    )
    job_id = app.state.summary_jobs.create()
    worker = threading.Thread(
        target=_run_summarize_job,
        args=(app, job_id, SummarizeRequest(scope_type="papers", paper_ids=[seeded["facial_paper_id"]])),
    )
    worker.start()
    assert overview.started.wait(10)

    primary = app.state.summary_jobs.get(job_id)
    assert primary is not None and primary.status == "done"  # Phase A already finished
    running = list(app.state.overview_jobs.list_all())
    assert len(running) == 1
    _, job = running[0]
    assert job.status == "running"
    assert job.nav == {"summary_id": primary.result.summary_id}

    overview.release.set()
    worker.join(10)
    finished = list(app.state.overview_jobs.list_all())
    assert len(finished) == 1
    assert finished[0][1].status == "done"


def test_retry_overview_generation_also_registers_a_status_popover_job(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    failing = FailingOverviewGenerator(RuntimeError("first attempt"))
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=failing,
    )
    client = TestClient(app)
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}).json()
    failed = client.get(f"/summarize/{started['job_id']}").json()
    summary_id = failed["summary_id"]
    assert len(list(app.state.overview_jobs.list_all())) == 1  # the inline Phase-A attempt above

    app.state.overview_generator = FakeOverviewGenerator([OverviewSentence("Recovered.", [0])])
    retried = client.post(f"/summaries/{summary_id}/overview/retry", json={})
    assert retried.status_code == 202

    jobs = list(app.state.overview_jobs.list_all())
    assert len(jobs) == 2  # the failed inline attempt + this retry
    latest = max(jobs, key=lambda item: item[1].finished_at or 0)
    assert latest[1].status == "done"
    assert latest[1].nav == {"summary_id": summary_id}


def test_phase_a_failure_rolls_back_entire_primary(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)

    def fail_persistence(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("injected primary persistence failure")

    monkeypatch.setattr("app.backend.summarization.pipeline._persist_verification", fail_persistence)
    with pytest.raises(RuntimeError, match="primary persistence"):
        summarize_scope(
            engine,
            scope=SummaryScope(scope_type="papers", paper_ids=[seeded["facial_paper_id"]]),
            generator=_summary_generator(seeded["facial_chunk_id"]),
            model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
            support_scorer=ConstantSupportScorer(),
            overview_requested=True,
        )
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(summaries)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(summary_sentences)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(citation_mappings)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(evidence_quotes)).scalar_one() == 0
    engine.dispose()


@dataclass
class BlockingSummaryGenerator:
    chunk_id: int
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    calls: int = 0
    name: str = "blocking-summary"

    def generate(self, *, source_chunks, scope_ref, engine=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.started.set()
        if not self.release.wait(10):
            raise TimeoutError("test did not release generation")
        return [
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(chunk_id=self.chunk_id, quote="Facial anomalies influence social judgments.")
                ],
            )
        ]


def test_no_connection_held_during_generation_call(temp_db_url: str) -> None:
    """Wave 3 regression (reliability): two independent writers on the same engine must not lock each
    other out while a slow generation call (Phase 2) is in flight. A query-scoped request forces Phase 1
    (retrieval) to write fresh embeddings before generation even starts (``_rank_chunks_for_query`` ->
    ``embed_chunks``) -- the exact shape that used to hold SQLite's writer lock for the whole pipeline.
    Phase 1 must have committed and released its connection before Phase 2 starts."""
    seeded = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    generator = BlockingSummaryGenerator(chunk_id=seeded["facial_chunk_id"])

    worker = threading.Thread(
        target=summarize_scope,
        kwargs=dict(
            engine=engine,
            scope=SummaryScope(scope_type="papers", paper_ids=[seeded["facial_paper_id"]], query="facial anomalies"),
            generator=generator,
            model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
            support_scorer=ConstantSupportScorer(),
        ),
    )
    worker.start()
    assert generator.started.wait(10)

    write_done = threading.Event()

    def independent_writer() -> None:
        with engine.begin() as conn:
            conn.execute(update(papers).where(papers.c.id == seeded["facial_paper_id"]).values(priority=1))
        write_done.set()

    writer = threading.Thread(target=independent_writer)
    writer.start()
    assert write_done.wait(2), (
        "an independent write on the same engine blocked while generation was in flight -- "
        "Phase 1's connection/writer-lock is still held during the (potentially slow) generation call"
    )
    writer.join(10)

    generator.release.set()
    worker.join(10)
    assert not worker.is_alive()
    engine.dispose()


@dataclass
class ChunkMutatingSummaryGenerator:
    engine: object
    chunk_id: int
    fresh_version: str
    fresh_text: str
    calls: int = 0
    name: str = "chunk-mutating-summary"

    def generate(self, *, source_chunks, scope_ref, engine=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        # Simulate a concurrent chunk re-extraction landing during generation (Phase 2) -- exactly the
        # gap _refresh_source_chunks (Phase 3) exists to close.
        with self.engine.begin() as conn:
            conn.execute(
                update(chunks)
                .where(chunks.c.id == self.chunk_id)
                .values(chunk_version=self.fresh_version, text=self.fresh_text)
            )
        return [
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments in the study.",
                citations=[CandidateCitation(chunk_id=self.chunk_id, quote=self.fresh_text)],
            )
        ]


def test_verification_uses_fresh_chunk_data_when_mutated_during_generation(temp_db_url: str) -> None:
    """Wave 3 regression (correctness/staleness): a chunk mutated between Phase 1 (retrieval) and Phase 3
    (verify + persist) must be verified against its FRESH text/version, never the Phase-1 snapshot --
    otherwise the persisted chunk_version_verified_against provenance and the quote-match outcome could
    silently disagree with each other, exactly the "stale-write correctness bug" both the original and
    Codex's independent provider-integration audits flagged. The cited quote only exists in the fresh
    (post-mutation) text; a verifier still using the stale Phase-1 snapshot would score it unverified."""
    seeded = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    fresh_text = "Facial anomalies also influence long-term social judgments after treatment."
    generator = ChunkMutatingSummaryGenerator(
        engine=engine,
        chunk_id=seeded["facial_chunk_id"],
        fresh_version="summary-chunk-v2-mutated",
        fresh_text=fresh_text,
    )

    result = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[seeded["facial_paper_id"]]),
        generator=generator,
        model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        support_scorer=ConstantSupportScorer(),
    )

    assert generator.calls == 1
    citation = result.sentences[0].citations[0]
    assert citation.quote_confidence == 1.0
    assert citation.status == "verified"
    with engine.connect() as conn:
        mapping_row = conn.execute(select(citation_mappings)).mappings().one()
        summary_row = conn.execute(select(summaries)).mappings().one()
    assert mapping_row["chunk_version_verified_against"] == "summary-chunk-v2-mutated"
    assert summary_row["chunk_version_verified_against"] == "summary-chunk-v2-mutated"
    engine.dispose()


@pytest.mark.parametrize(
    "overview",
    [
        FailingOverviewGenerator(TimeoutError("timeout")),
        FailingOverviewGenerator(RuntimeError("provider")),
        FakeOverviewGenerator(sentences=[]),
        FakeOverviewGenerator(sentences=[OverviewSentence(text="bad reference", claim_indices=[99])]),
    ],
    ids=["timeout", "provider-error", "malformed-empty", "invalid-postprocessing"],
)
def test_overview_failure_never_rolls_back_primary(temp_db_url: str, overview) -> None:  # type: ignore[no-untyped-def]
    seeded = _seed_summarization_library(temp_db_url)
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=overview,
    )
    client = TestClient(app)
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}).json()
    result = client.get(f"/summarize/{started['job_id']}").json()

    assert result["status"] == "done"
    assert result["summary_status"] == "verified"
    assert result["overview_status"] == "failed"
    assert result["overview"] is None
    assert len(result["sentences"]) == 1
    assert len(result["sentences"][0]["citations"]) == 1


def test_overview_db_write_failure_isolated_and_retryable(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=FakeOverviewGenerator([OverviewSentence("Overview.", [0])]),
    )
    monkeypatch.setattr(
        "app.backend.summarization.overview_lifecycle._persist_overview",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("overview write failed")),
    )
    client = TestClient(app)
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}).json()
    result = client.get(f"/summarize/{started['job_id']}").json()
    assert result["status"] == "done"
    assert result["overview_status"] == "failed"
    assert result["sentences"][0]["citations"][0]["status"] == "verified"


def test_failed_overview_retries_same_summary_and_complete_is_immutable(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    failing = FailingOverviewGenerator(RuntimeError("first attempt"))
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=failing,
    )
    client = TestClient(app)
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}).json()
    failed = client.get(f"/summarize/{started['job_id']}").json()
    summary_id = failed["summary_id"]
    primary = failed["sentences"]

    successful = FakeOverviewGenerator([OverviewSentence("Recovered.", [0])])
    app.state.overview_generator = successful
    retried = client.post(f"/summaries/{summary_id}/overview/retry", json={})
    completed = client.get(f"/summaries/{summary_id}").json()
    immutable = client.post(f"/summaries/{summary_id}/overview/retry", json={}).json()

    assert retried.status_code == 202 and retried.json()["accepted"] is True
    assert completed["summary_id"] == summary_id
    assert completed["sentences"] == primary
    assert completed["overview_status"] == "complete"
    assert completed["overview"] == [{"text": "Recovered.", "claim_ordinals": [0]}]
    assert immutable == {"summary_id": summary_id, "accepted": False, "overview_status": "complete"}
    assert failing.calls == 1


def test_concurrent_retry_cas_runs_one_provider_call(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=FailingOverviewGenerator(RuntimeError("first")),
    )
    client = TestClient(app)
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}).json()
    summary_id = client.get(f"/summarize/{started['job_id']}").json()["summary_id"]
    engine = make_engine(temp_db_url)
    barrier = threading.Barrier(2)
    acquired: list[bool] = []

    def contender() -> None:
        barrier.wait()
        with engine.begin() as conn:
            acquired.append(acquire_overview(conn, summary_id, allow_pending=True, allow_failed=True))

    threads = [threading.Thread(target=contender) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(acquired) == [False, True]

    successful = FakeOverviewGenerator([OverviewSentence("Winner.", [0])])
    assert generate_overview(engine, summary_id=summary_id, generator=successful, acquired=True) == "complete"
    with engine.connect() as conn:
        row = conn.execute(select(summaries)).mappings().one()
        assert row["overview_json"] == [{"text": "Winner.", "claim_ordinals": [0]}]
    engine.dispose()


def test_stale_running_is_manually_reclaimable_but_reload_causes_no_egress(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    app = _summarization_app(
        temp_db_url,
        generator=_summary_generator(seeded["facial_chunk_id"]),
        overview_generator=FailingOverviewGenerator(RuntimeError("first")),
    )
    client = TestClient(app)
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}).json()
    summary_id = client.get(f"/summarize/{started['job_id']}").json()["summary_id"]
    counter = BlockingOverviewGenerator()
    app.state.overview_generator = counter
    engine = make_engine(temp_db_url)
    stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=6)
    with engine.begin() as conn:
        conn.execute(
            update(summaries)
            .where(summaries.c.id == summary_id)
            .values(overview_status="running", overview_updated_at=stale)
        )

    reloaded = client.get(f"/summaries/{summary_id}").json()
    assert reloaded["overview_status"] == "running"
    assert counter.calls == 0
    with engine.begin() as conn:
        assert acquire_overview(conn, summary_id, allow_pending=True, allow_failed=True) is True
    engine.dispose()


def test_legacy_rows_have_safe_non_pending_compatibility(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    app = _summarization_app(temp_db_url, generator=_summary_generator(seeded["facial_chunk_id"]))
    client = TestClient(app)
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]}).json()
    summary_id = client.get(f"/summarize/{started['job_id']}").json()["summary_id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            update(summaries)
            .where(summaries.c.id == summary_id)
            .values(overview_status=None, overview_updated_at=None, overview_json=None)
        )
    assert client.get(f"/summaries/{summary_id}").json()["overview_status"] == "not_requested"
    with engine.begin() as conn:
        conn.execute(
            update(summaries)
            .where(summaries.c.id == summary_id)
            .values(overview_json=[{"text": "Legacy.", "claim_ordinals": [0]}])
        )
    complete = client.get(f"/summaries/{summary_id}").json()
    assert complete["overview_status"] == "complete"
    assert complete["overview"] == [{"text": "Legacy.", "claim_ordinals": [0]}]
    engine.dispose()
