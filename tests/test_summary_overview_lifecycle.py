from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.backend.api.routers.summaries import SummarizeRequest, _run_summarize_job
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import citation_mappings, evidence_quotes, summaries, summary_sentences
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


def test_phase_a_failure_rolls_back_entire_primary(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)

    def fail_persistence(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("injected primary persistence failure")

    monkeypatch.setattr("app.backend.summarization.pipeline._persist_verification", fail_persistence)
    with pytest.raises(RuntimeError, match="primary persistence"):
        with engine.begin() as conn:
            summarize_scope(
                conn,
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
