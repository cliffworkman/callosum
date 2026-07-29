from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.api import create_app
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper, soft_delete_paper
from app.backend.persistence.schema import (
    citation_mappings,
    evidence_quotes,
    summaries,
    summary_sentences,
)
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from app.backend.summarization.pipeline import SummaryScope, _source_chunks_for_scope
from tests.api_helpers import (
    ApiFakeEmbeddingModel,
    ConstantSupportScorer,
    _seed_summarization_library,
    _summarization_app,
)


def test_summarize_query_job_completes_with_verified_citation_payload(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="Facial anomalies influence social judgments.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial social judgment", "top_k": 2})
    body = started.json()
    result = client.get(f"/summarize/{body['job_id']}")

    assert started.status_code == 202
    assert body["status"] == "pending"
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "done"
    assert payload["summary_id"] is not None
    assert payload["summary_status"] == "verified"
    assert payload["sentences"][0]["text"] == "Facial anomalies influence social judgments."
    assert payload["sentences"][0]["flagged"] is False
    citation = payload["sentences"][0]["citations"][0]
    assert citation["paper_id"] == seeded["facial_paper_id"]
    assert citation["paper_title"] == "API Summarization Facial Paper"
    assert citation["page_start"] == 1

    # inc 415: the real pipeline's freshly-created summary_id must match what gets published as the
    # Status-navigation hint — a synthetic JobStore-only test wouldn't catch the two drifting apart.
    status_row = next(j for j in client.get("/status/jobs").json()["jobs"] if j["job_id"] == body["job_id"])
    assert status_row["nav"] == {"summary_id": payload["summary_id"]}
    assert citation["page_end"] == 1
    assert citation["quote"] == "Facial anomalies influence social judgments."
    assert citation["retrieval_confidence"] == pytest.approx(1.0)
    assert citation["quote_confidence"] == 1.0
    assert citation["support_confidence"] == 1.0
    assert citation["status"] == "verified"
    assert citation["coordinate_precision"] == "region"
    assert citation["bbox_json"][0]["coordinate_precision"] == "region"


def test_summarize_job_reports_real_progress_during_verification(temp_db_url: str) -> None:
    """inc 408: Ask's job now reports real per-claim progress once verification starts (retrieval + generation
    stay indeterminate — no sub-progress signal for a single opaque LLM call). End-to-end through the real
    /summarize endpoint + JobStore, not just the pipeline function directly."""
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"], quote="Facial anomalies influence social judgments."
                    )
                ],
            ),
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments, restated.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"], quote="Facial anomalies influence social judgments."
                    )
                ],
            ),
        ]
    )
    app = _summarization_app(temp_db_url, generator=generator)
    client = TestClient(app)

    started = client.post("/summarize", json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]})
    job_id = started.json()["job_id"]
    assert client.get(f"/summarize/{job_id}").json()["status"] == "done"

    job = app.state.summary_jobs.get(job_id)
    assert job.progress is not None
    assert (job.progress.current, job.progress.total, job.progress.label) == (2, 2, "Verifying claim")


def test_summarize_papers_and_cluster_scopes_validate_and_run(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="Facial anomalies influence social judgments.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    papers_job = client.post(
        "/summarize",
        json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]},
    ).json()
    cluster_job = client.post(
        "/summarize",
        json={"scope_type": "cluster_node", "cluster_node_id": seeded["cluster_node_id"]},
    ).json()

    assert client.get(f"/summarize/{papers_job['job_id']}").json()["status"] == "done"
    assert client.get(f"/summarize/{cluster_job['job_id']}").json()["status"] == "done"


def test_query_scope_retrieval_excludes_trashed_papers(temp_db_url: str) -> None:
    # inc 66: the query scope selects chunks across the whole library — a trashed paper must drop out.
    seeded = _seed_summarization_library(temp_db_url)  # facial + banana (unrelated) papers, one chunk each
    engine = make_engine(temp_db_url)
    model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
    scope = SummaryScope(scope_type="query", query="banana orchard")
    with engine.begin() as conn:
        before = {
            c.paper_id for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=10)
        }
        assert seeded["unrelated_paper_id"] in before  # banana paper is retrievable while live

        assert soft_delete_paper(conn, seeded["unrelated_paper_id"]) is True
        after = {
            c.paper_id for c in _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=10)
        }
        assert seeded["unrelated_paper_id"] not in after  # trashed → excluded from a new synthesis
        assert seeded["facial_paper_id"] in after  # the live paper is still retrievable
    engine.dispose()


def test_summary_section_filter_limits_source_chunks_without_changing_verification(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Sectioned", csl_json={"title": "Sectioned"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="sectioned",
        )
        methods_chunk = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Methods chunk describes recruitment.",
            page_start=2,
            page_end=2,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="methods-v1",
            source_attachment_checksum="sectioned",
            section="methods",
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Results chunk describes outcomes.",
            page_start=5,
            page_end=5,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="results-v1",
            source_attachment_checksum="sectioned",
            section="results",
        )
        model, store = ApiFakeEmbeddingModel(), InMemoryVectorStore()
        scope = SummaryScope(scope_type="papers", paper_ids=[paper_id], sections=["methods"])
        source_chunks = _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=10)

    assert [chunk.chunk_id for chunk in source_chunks] == [methods_chunk]
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Methods chunk describes recruitment.",
                citations=[CandidateCitation(chunk_id=methods_chunk, quote="Methods chunk describes recruitment.")],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))
    started = client.post(
        "/summarize",
        json={"scope_type": "papers", "paper_ids": [paper_id], "sections": ["methods"], "top_k": 10},
    )
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["summary_status"] == "verified"
    assert result["source_chunk_count"] == 1
    assert result["section_filter"] == ["methods"]
    assert result["sentences"][0]["citations"][0]["section"] == "methods"


def test_summary_section_filter_rejects_unknown_keys(temp_db_url: str) -> None:
    client = TestClient(_summarization_app(temp_db_url))

    response = client.post("/summarize", json={"scope_type": "query", "query": "x", "sections": ["made-up"]})

    assert response.status_code == 400
    assert "Unknown synthesis section filter" in response.json()["detail"]


def test_summarize_invalid_body_and_unknown_job(temp_db_url: str) -> None:
    client = TestClient(_summarization_app(temp_db_url))

    unknown_scope = client.post("/summarize", json={"scope_type": "axis"})
    missing_query = client.post("/summarize", json={"scope_type": "query"})
    missing_job = client.get("/summarize/not-a-job")

    assert unknown_scope.status_code == 422
    assert missing_query.status_code == 400
    assert missing_job.status_code == 404


def test_summarize_real_generator_without_egress_fails_gracefully(
    temp_db_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_summarization_library(temp_db_url)
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    client = TestClient(
        create_app(
            db_url=temp_db_url,
            embedding_model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
            support_scorer=ConstantSupportScorer(),
        )
    )

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial"})
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "error"
    # inc 149: the BYOK/multi-provider era message points the user at Settings (egress is no longer env-only).
    assert "data-egress consent" in result["detail"]
    assert "Settings" in result["detail"]


def test_summarize_hallucinated_quote_remains_flagged_at_endpoint(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="This quote is not present in the source chunk.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial"})
    result = client.get(f"/summarize/{started.json()['job_id']}").json()
    citation = result["sentences"][0]["citations"][0]

    assert result["status"] == "done"
    assert result["summary_status"] == "flagged"
    assert result["sentences"][0]["flagged"] is True
    assert citation["status"] != "verified"
    assert citation["quote_confidence"] == 0.0
    assert citation["coordinate_precision"] is None
    assert citation["bbox_json"] is None


def test_summaries_list_returns_history_with_counts_and_pagination(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="Facial anomalies influence social judgments.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    query_job = client.post("/summarize", json={"scope_type": "query", "query": "facial social judgments"}).json()
    papers_job = client.post(
        "/summarize",
        json={"scope_type": "papers", "paper_ids": [seeded["facial_paper_id"]]},
    ).json()
    query_summary_id = client.get(f"/summarize/{query_job['job_id']}").json()["summary_id"]
    papers_summary_id = client.get(f"/summarize/{papers_job['job_id']}").json()["summary_id"]

    first_page = client.get("/summaries", params={"limit": 1, "offset": 0}).json()
    second_page = client.get("/summaries", params={"limit": 1, "offset": 1}).json()

    assert first_page == [
        {
            "summary_id": papers_summary_id,
            "scope_type": "papers",
            "scope_label": "1 paper",
            "status": "verified",
            "created_at": first_page[0]["created_at"],
            "sentence_count": 1,
            "verified_sentence_count": 1,
            "flagged_sentence_count": 0,
            "imported": False,
        }
    ]
    assert first_page[0]["created_at"]
    assert second_page[0]["summary_id"] == query_summary_id
    assert second_page[0]["scope_label"] == "facial social judgments"


def test_summary_readback_matches_completed_job_result_shape(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="Facial anomalies influence social judgments.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial"}).json()
    completed = client.get(f"/summarize/{started['job_id']}").json()
    reloaded = client.get(f"/summaries/{completed['summary_id']}").json()

    assert reloaded["status"] == "done"
    assert reloaded["job_id"] == f"summary:{completed['summary_id']}"
    assert reloaded["summary_id"] == completed["summary_id"]
    assert reloaded["summary_status"] == completed["summary_status"]
    assert reloaded["source_chunk_count"] == completed["source_chunk_count"]
    assert reloaded["section_filter"] == completed["section_filter"]
    assert reloaded["sentences"] == completed["sentences"]
    citation = reloaded["sentences"][0]["citations"][0]
    assert set(citation) == {
        "mapping_id",
        "evidence_quote_id",
        "chunk_id",
        "paper_id",
        "paper_title",
        "page_start",
        "page_end",
        "section",
        "quote",
        "retrieval_confidence",
        "quote_confidence",
        "support_confidence",
        "status",
        "coordinate_precision",
        "bbox_json",
        "attachment_id",
    }
    # #5: a citation carries the exact (PDF) attachment its evidence came from, not just the paper.
    assert citation["attachment_id"] == seeded["facial_attachment_id"]


def test_summary_citation_attachment_id_is_none_for_non_pdf_supplementary_text(temp_db_url: str) -> None:
    # #5: a citation whose text came from a non-PDF supplementary-text attachment (docx/html/jats-xml) must NOT
    # carry that attachment's id -- chunks.attachment_id is non-null regardless of attachment type, but surfacing
    # a non-PDF id would make the reader 404 as "not a PDF" instead of today's honest fallback (open the paper's
    # primary PDF, scroll to the placeholder page 1, no highlight -- the accepted null-precision behavior).
    seeded = _seed_summarization_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        docx_attachment_id = create_attachment(
            conn,
            paper_id=seeded["facial_paper_id"],
            storage_mode="linked",
            availability="available",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            attachment_type="docx",
            role="supplementary-text",
        )
        docx_chunk_id = create_chunk(
            conn,
            paper_id=seeded["facial_paper_id"],
            attachment_id=docx_attachment_id,
            text="A supplementary passage from the docx copy.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="document-text-offsets",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="docx-chunk-v1",
            source_attachment_checksum="docx-checksum",
            bbox_json=[],
        )
    engine.dispose()
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="A supplementary passage from the docx copy.",
                citations=[
                    CandidateCitation(
                        chunk_id=docx_chunk_id,
                        quote="A supplementary passage from the docx copy.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial"}).json()
    completed = client.get(f"/summarize/{started['job_id']}").json()

    citation = completed["sentences"][0]["citations"][0]
    assert citation["chunk_id"] == docx_chunk_id
    assert citation["attachment_id"] is None


def test_summary_readback_preserves_flagged_hallucination_guard(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="This quote is not present in the source chunk.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial"}).json()
    completed = client.get(f"/summarize/{started['job_id']}").json()
    reloaded = client.get(f"/summaries/{completed['summary_id']}").json()
    citation = reloaded["sentences"][0]["citations"][0]

    assert reloaded["summary_status"] == "flagged"
    assert reloaded["sentences"][0]["flagged"] is True
    assert citation["status"] != "verified"
    assert citation["quote_confidence"] == 0.0
    assert citation["coordinate_precision"] is None
    assert citation["bbox_json"] is None


def test_delete_summary_removes_trust_spine_rows_and_404s(temp_db_url: str) -> None:
    seeded = _seed_summarization_library(temp_db_url)
    generator = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="Facial anomalies influence social judgments.",
                    )
                ],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=generator))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial"}).json()
    summary_id = client.get(f"/summarize/{started['job_id']}").json()["summary_id"]
    deleted = client.delete(f"/summaries/{summary_id}")
    missing_delete = client.delete("/summaries/999999")
    missing_get = client.get(f"/summaries/{summary_id}")

    assert deleted.status_code == 204
    assert missing_delete.status_code == 404
    assert missing_get.status_code == 404
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(summaries)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(summary_sentences)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(citation_mappings)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(evidence_quotes)).scalar_one() == 0
    engine.dispose()


# ── egress gate at the DI seam (inc 58) ──────────────────────────────────────


def _facial_generator(seeded: dict) -> FakeSummaryGenerator:
    return FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Facial anomalies influence social judgments.",
                citations=[
                    CandidateCitation(
                        chunk_id=seeded["facial_chunk_id"],
                        quote="Facial anomalies influence social judgments.",
                    )
                ],
            )
        ]
    )


def test_summarize_injected_generator_blocked_when_egress_off(
    temp_db_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hole closed: an injected generator that does NOT self-gate is still blocked at the seam when
    egress is disabled — the job errors with DataEgressDisabledError instead of running the fake."""
    seeded = _seed_summarization_library(temp_db_url)
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    client = TestClient(_summarization_app(temp_db_url, generator=_facial_generator(seeded)))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial", "top_k": 2})
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "error"
    assert "DataEgressDisabledError" in result["detail"]  # the wrapper blocked before the fake ran
    assert result.get("summary_id") is None  # no summary produced from the injected fake


def test_summarize_injected_generator_runs_when_egress_on(
    temp_db_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavior preserved: with egress enabled, the injected fake IS called and produces the summary."""
    seeded = _seed_summarization_library(temp_db_url)
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")
    client = TestClient(_summarization_app(temp_db_url, generator=_facial_generator(seeded)))

    started = client.post("/summarize", json={"scope_type": "query", "query": "facial", "top_k": 2})
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert result["status"] == "done"
    assert result["sentences"][0]["text"] == "Facial anomalies influence social judgments."
