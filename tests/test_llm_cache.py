from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

from app.backend.llm.cache import repair_summary_cache
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import chunks, llm_cache
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence
from tests.api_helpers import _seed_summarization_library, _summarization_app

# A generation cache hit must cost zero LLM calls AND return an identical (re-verified) result. This
# generator counts its calls and lets a test set a distinct cache_signature, so we can prove hit/miss.


class CountingSummaryGenerator:
    def __init__(self, sentences, *, name="counting-summary-generator", signature=None):
        self.sentences = sentences
        self.name = name
        self._signature = signature
        self.calls = 0

    @property
    def cache_signature(self) -> str:
        return self._signature if self._signature is not None else self.name

    def generate(self, *, source_chunks, scope_ref, conn=None):
        self.calls += 1
        return list(self.sentences)


def _facial(seeded, *, quote="Facial anomalies influence social judgments."):
    return [
        CandidateSummarySentence(
            text="Facial anomalies influence social judgments.",
            citations=[CandidateCitation(chunk_id=seeded["facial_chunk_id"], quote=quote)],
        )
    ]


def _summarize(client, *, query="facial social judgment", top_k=2):
    started = client.post("/summarize", json={"scope_type": "query", "query": query, "top_k": top_k})
    assert started.status_code == 202
    return client.get(f"/summarize/{started.json()['job_id']}").json()


def _shape(result):
    """The meaningful output (text + verification outcome), ignoring per-row ids that differ each run."""
    return [
        (
            s["text"],
            s["flagged"],
            [
                (c["quote"], c["chunk_id"], c["status"], c["quote_confidence"], c["coordinate_precision"])
                for c in s["citations"]
            ],
        )
        for s in result["sentences"]
    ]


def _gen_shape(result):
    """Only the cached GENERATION output (sentence text + cited quotes), not the re-run verification verdict.
    The cache guarantees identical candidates; verification re-runs against the current environment."""
    return [(s["text"], [(c["quote"], c["chunk_id"]) for c in s["citations"]]) for s in result["sentences"]]


def test_cache_hit_returns_identical_and_generates_once(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    first = _summarize(client)
    second = _summarize(client)

    assert first["status"] == "done" and second["status"] == "done"
    assert gen.calls == 1  # the second call was a cache hit (zero tokens)
    assert first["summary_status"] == second["summary_status"]
    assert _shape(first) == _shape(second)  # identical result


def test_changed_chunk_version_forces_miss(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    _summarize(client)
    assert gen.calls == 1
    engine = make_engine(temp_db_url)  # bump the cited chunk's version → key changes
    with engine.begin() as conn:
        conn.execute(update(chunks).where(chunks.c.id == seeded["facial_chunk_id"]).values(chunk_version="bumped-v2"))
    engine.dispose()

    _summarize(client)
    assert gen.calls == 2  # a changed keyed input forces a miss


def test_verification_runs_on_cache_hit(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded, quote="This quote is not present in the source chunk."))
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    first = _summarize(client)
    second = _summarize(client)

    assert gen.calls == 1  # cache hit on the second run
    assert first["summary_status"] == "flagged"
    assert second["summary_status"] == "flagged"  # verification re-ran on the cached candidates
    assert second["sentences"][0]["flagged"] is True
    assert second["sentences"][0]["citations"][0]["quote_confidence"] == 0.0


def _summarize_papers(client, paper_id):
    # A papers scope selects chunks in pure DB order (no vector ranking), so the chunk set — and thus the
    # cache key — is identical across fresh app instances (unlike a query scope, whose ranking depends on
    # the per-app in-memory vector store).
    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [paper_id]})
    assert started.status_code == 202
    return client.get(f"/summarize/{started.json()['job_id']}").json()


def test_cache_persists_across_app_instances(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen1 = CountingSummaryGenerator(_facial(seeded))
    first = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen1)), seeded["facial_paper_id"])
    assert gen1.calls == 1

    gen2 = CountingSummaryGenerator(_facial(seeded))  # a fresh app on the SAME db (≈ restart)
    second = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen2)), seeded["facial_paper_id"])

    assert gen2.calls == 0  # served from the persisted SQLite cache (no regeneration)
    assert _gen_shape(first) == _gen_shape(second)  # identical cached generation output


def test_malformed_cached_chunk_id_regenerates_instead_of_crashing(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen1 = CountingSummaryGenerator(_facial(seeded))
    first = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen1)), seeded["facial_paper_id"])
    assert first["status"] == "done"
    assert gen1.calls == 1
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            update(llm_cache)
            .where(llm_cache.c.namespace == "summary")
            .values(
                output_json={
                    "sentences": [
                        {
                            "text": "Facial anomalies influence social judgments.",
                            "citations": [
                                {"chunk_id": "chunk_1", "quote": "Facial anomalies influence social judgments."}
                            ],
                        }
                    ]
                }
            )
        )
    engine.dispose()
    gen2 = CountingSummaryGenerator(_facial(seeded))
    second = _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen2)), seeded["facial_paper_id"])

    assert second["status"] == "done"
    assert gen2.calls == 1
    assert second["sentences"][0]["citations"][0]["chunk_id"] == seeded["facial_chunk_id"]


def test_repair_summary_cache_removes_only_malformed_summary_rows(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    _summarize_papers(TestClient(_summarization_app(temp_db_url, generator=gen)), seeded["facial_paper_id"])
    malformed = {
        "sentences": [
            {
                "text": "Facial anomalies influence social judgments.",
                "citations": [{"chunk_id": "chunk_1", "quote": "Facial anomalies influence social judgments."}],
            }
        ]
    }
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            insert(llm_cache),
            [
                {
                    "namespace": "summary",
                    "input_hash": "bad-summary",
                    "signature": "test",
                    "output_json": malformed,
                },
                {
                    "namespace": "other",
                    "input_hash": "bad-other",
                    "signature": "test",
                    "output_json": malformed,
                },
            ],
        )
        result = repair_summary_cache(conn)
        summary_rows = conn.execute(
            select(func.count()).select_from(llm_cache).where(llm_cache.c.namespace == "summary")
        ).scalar_one()
        other_rows = conn.execute(
            select(func.count()).select_from(llm_cache).where(llm_cache.c.namespace == "other")
        ).scalar_one()
    engine.dispose()

    assert result == {"scanned": 2, "removed": 1}
    assert summary_rows == 1
    assert other_rows == 1


def test_settings_repair_summary_cache_endpoint_commits(temp_db_url: str) -> None:
    _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            insert(llm_cache).values(
                namespace="summary",
                input_hash="bad-summary",
                signature="test",
                output_json={"sentences": [{"text": "x", "citations": [{"chunk_id": "chunk_1", "quote": "x"}]}]},
            )
        )
    client = TestClient(_summarization_app(temp_db_url))

    response = client.post("/settings/repair-summary-cache", json={})

    assert response.status_code == 200
    assert response.json() == {"scanned": 1, "removed": 1}
    with engine.connect() as conn:
        remaining = conn.execute(select(func.count()).select_from(llm_cache)).scalar_one()
    engine.dispose()
    assert remaining == 0


def test_signature_change_forces_miss(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen_a = CountingSummaryGenerator(_facial(seeded), signature="model-A/summary-v1")
    _summarize(TestClient(_summarization_app(temp_db_url, generator=gen_a)))
    assert gen_a.calls == 1

    gen_b = CountingSummaryGenerator(_facial(seeded), signature="model-B/summary-v2")
    _summarize(TestClient(_summarization_app(temp_db_url, generator=gen_b)))
    assert gen_b.calls == 1  # different model/prompt-version → miss


def test_cache_row_written(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    gen = CountingSummaryGenerator(_facial(seeded))
    _summarize(TestClient(_summarization_app(temp_db_url, generator=gen)))

    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        count = conn.execute(
            select(func.count()).select_from(llm_cache).where(llm_cache.c.namespace == "summary")
        ).scalar_one()
    engine.dispose()
    assert count == 1
