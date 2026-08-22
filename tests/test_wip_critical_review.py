"""Local-only, exact-snapshot WIP critical-read contracts."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

from app.backend.api import create_app
from app.backend.embeddings.vector_store import VectorHit
from app.backend.methods.critical_review import (
    MAX_CRITIQUE_CLAIMS,
    ChunkInfo,
    extract_block_claim_sentences,
    library_article_chunk_embedding_ids,
    search_contested_claims,
)
from app.backend.persistence import schema
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.summarization.verification import Stance
from app.backend.wip.content import ContentBlock


class _FakeEmbedModel:
    name = "fake-wip"
    version = "v1"
    normalization = "none"
    dimension = 3

    def __init__(self, *, fail: bool = False, on_encode=None) -> None:
        self.fail = fail
        self.on_encode = on_encode
        self.encoded: list[str] = []
        self.calls: list[list[str]] = []

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        self.encoded.extend(texts)
        if self.on_encode is not None:
            self.on_encode()
        if self.fail:
            raise RuntimeError("private model path C:/Users/private/model")
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeVectorStore:
    kind = "fake-read-only"

    def __init__(self, hit_embedding_id: int | None = None) -> None:
        self.hit_embedding_id = hit_embedding_id
        self.searches: list[set[int]] = []

    def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
        candidates = set(candidate_embedding_ids or set())
        self.searches.append(candidates)
        if self.hit_embedding_id in candidates:
            return [VectorHit(embedding_id=self.hit_embedding_id, distance=0.1)]
        return []


class _FakeStanceScorer:
    model_name = "fake-local-nli"

    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.batch_calls: list[list[tuple[str, str]]] = []

    def classify_stance(self, *, sentence: str, passage: str) -> Stance | None:
        if self.unavailable:
            return None
        return Stance("contrast", 0.83, {"support": 0.05, "contrast": 0.83, "mention": 0.12})

    def classify_stances(self, pairs: list[tuple[str, str]]) -> list[Stance | None]:
        self.batch_calls.append(list(pairs))
        return [self.classify_stance(sentence=sentence, passage=passage) for sentence, passage in pairs]


def _poll_scan(client: TestClient, job_id: str) -> None:
    for _ in range(30):
        result = client.get(f"/wip/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            assert result["status"] == "done"
            return
    raise AssertionError("scan did not finish")


def _setup_wip(client: TestClient, folder: Path, text: str) -> tuple[int, int, Path]:
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(text, encoding="utf-8")
    root = client.post("/wip/watch-roots", json={"path": str(folder), "discovery_mode": "folder"}).json()
    scan = client.post(f"/wip/watch-roots/{root['id']}/scan").json()
    _poll_scan(client, scan["job_id"])
    manuscript_id = client.get("/wip/manuscripts").json()[0]["id"]
    file_id = client.get(f"/wip/manuscripts/{manuscript_id}/files").json()[0]["id"]
    assert (
        client.patch(f"/wip/manuscripts/{manuscript_id}/files/{file_id}", json={"is_primary": True}).status_code == 200
    )
    return int(root["id"]), int(manuscript_id), draft


def _library_embedding(db_url: str, *, role: str = "article-fulltext", model: str = "fake-wip") -> tuple[int, int, int]:
    with make_engine(db_url).begin() as conn:
        paper_id = create_paper(conn, title="Contrasting replication", csl_json={"title": "Contrasting replication"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum=f"attachment-{paper_id}",
            import_source="test",
            attachment_type="pdf",
            role=role,
        )
        chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="A preregistered replication found no measurable effect under the same conditions.",
            page_start=7,
            page_end=7,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="v1",
            source_attachment_checksum=f"attachment-{paper_id}",
        )
        embedding_id = int(
            conn.execute(
                insert(schema.embeddings).values(
                    target_type="chunk",
                    target_id=chunk_id,
                    model_name=model,
                    model_version="v1",
                    dimension=3,
                    normalization="none",
                    source_text_version="v1",
                )
            ).inserted_primary_key[0]
        )
    return paper_id, attachment_id, embedding_id


def _start_and_get(client: TestClient, manuscript_id: int) -> tuple[dict, dict]:
    start = client.post(f"/wip/manuscripts/{manuscript_id}/critical-read", json={})
    assert start.status_code == 202
    job = client.get(f"/wip/critical-read/{start.json()['job_id']}")
    assert job.status_code == 200
    return start.json(), job.json()


def test_wip_critical_read_persists_grounded_exact_snapshot_receipt_without_embeddings(
    temp_db_url: str, tmp_path: Path
) -> None:
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    root_id, manuscript_id, draft = _setup_wip(
        client,
        tmp_path / "private-draft",
        "Our intervention reliably improves the primary outcome in comparable populations. Results: t(18) = 2.10, p = .90.",
    )
    method_run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={}).json()
    paper_id, attachment_id, embedding_id = _library_embedding(temp_db_url)
    embed_model = _FakeEmbedModel()
    vector_store = _FakeVectorStore(embedding_id)
    stance_scorer = _FakeStanceScorer()
    app.state.wip_critical_review_deps = {
        "embed_model": embed_model,
        "vector_store": vector_store,
        "stance_scorer": stance_scorer,
    }
    with make_engine(temp_db_url).connect() as conn:
        embeddings_before = conn.scalar(select(func.count()).select_from(schema.embeddings))

    _, job = _start_and_get(client, manuscript_id)

    assert job["status"] == "done"
    run = job["run"]
    assert run["tool_id"] == "critical-read" and run["tool_version"] == "1"
    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["file_id"] and run["snapshot_id"]
    result = run["structured_result_json"]
    assert result["retrieval"] == {
        "status": "complete",
        "claims_considered": 2,
        "eligible_chunk_embeddings": 1,
        "retrieved_passages": 2,
        "classified_passages": 2,
    }
    assert 1 <= len(result["claims"]) <= MAX_CRITIQUE_CLAIMS
    assert all(claim["page"] is None and claim["coordinate_precision"] is None for claim in result["claims"])
    evidence = result["contested_claims"][0]
    assert evidence["claim"] in {claim["text"] for claim in result["claims"]}
    assert evidence["passage"].startswith("A preregistered replication")
    assert evidence["other_paper_id"] == paper_id
    assert evidence["other_paper_title"] == "Contrasting replication"
    assert evidence["attachment_id"] == attachment_id
    assert evidence["page"] == 7 and evidence["other_coordinate_precision"] == "region"
    assert evidence["stance"] == "contrast" and evidence["confidence"] == 0.83
    statcheck = next(item for item in result["method_signals"] if item["tool_id"] == "statcheck")
    assert statcheck["status"] == "available" and statcheck["tool_run_id"] == method_run["id"]
    assert all(item["status"] == "unavailable" for item in result["method_signals"] if item["tool_id"] != "statcheck")
    assert run["parameters_json"]["embedding_model"] == "fake-wip"
    assert run["parameters_json"]["stance_model"] == "fake-local-nli"
    assert embed_model.encoded == [claim["text"] for claim in result["claims"]]
    assert embed_model.calls == [[claim["text"] for claim in result["claims"]]]
    assert len(stance_scorer.batch_calls) == 1 and len(stance_scorer.batch_calls[0]) == 2
    assert all(search == {embedding_id} for search in vector_store.searches)
    with make_engine(temp_db_url).connect() as conn:
        assert conn.scalar(select(func.count()).select_from(schema.embeddings)) == embeddings_before

    status_json = client.get("/status/jobs").text
    assert "WIP Critical Read" in status_json and '"manuscript_id":' in status_json
    assert '"compute_kind":"Local AI"' in status_json
    assert "Our intervention reliably improves" not in status_json
    assert "preregistered replication" not in status_json
    assert str(tmp_path) not in status_json

    draft.write_text("This changed manuscript now makes a different claim about the outcome.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll_scan(client, scan["job_id"])
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert next(item for item in runs if item["id"] == run["id"])["validity"] == "potentially-stale"


def test_wip_critical_read_honestly_reports_empty_claim_and_corpus_scopes(temp_db_url: str, tmp_path: Path) -> None:
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    _, manuscript_id, _ = _setup_wip(client, tmp_path / "short", "Tiny.")
    embed_model = _FakeEmbedModel()
    app.state.wip_critical_review_deps = {
        "embed_model": embed_model,
        "vector_store": _FakeVectorStore(),
        "stance_scorer": _FakeStanceScorer(),
    }
    _, no_claims = _start_and_get(client, manuscript_id)
    assert no_claims["status"] == "done"
    assert no_claims["run"]["structured_result_json"]["retrieval"]["status"] == "no-claims"
    assert embed_model.encoded == []

    _, manuscript_id_2, _ = _setup_wip(
        client, tmp_path / "corpus-free", "This adequately long manuscript sentence is eligible for comparison."
    )
    _, empty_corpus = _start_and_get(client, manuscript_id_2)
    assert empty_corpus["status"] == "done"
    assert empty_corpus["run"]["structured_result_json"]["retrieval"]["status"] == "empty-library-corpus"
    assert embed_model.encoded == []


def test_wip_critical_read_records_nli_and_model_unavailability_without_guessing(
    temp_db_url: str, tmp_path: Path
) -> None:
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    _, manuscript_id, _ = _setup_wip(
        client, tmp_path / "unavailable", "This sufficiently long claim is suitable for local comparison."
    )
    _, _, embedding_id = _library_embedding(temp_db_url)
    app.state.wip_critical_review_deps = {
        "embed_model": _FakeEmbedModel(),
        "vector_store": _FakeVectorStore(embedding_id),
        "stance_scorer": _FakeStanceScorer(unavailable=True),
    }
    _, nli_job = _start_and_get(client, manuscript_id)
    nli_result = nli_job["run"]["structured_result_json"]
    assert nli_result["retrieval"]["status"] == "nli-unavailable"
    assert nli_result["contested_claims"] == []

    app.state.wip_critical_review_deps = {
        "embed_model": _FakeEmbedModel(fail=True),
        "vector_store": _FakeVectorStore(embedding_id),
        "stance_scorer": _FakeStanceScorer(),
    }
    _, failed_model_job = _start_and_get(client, manuscript_id)
    assert failed_model_job["status"] == "done"
    failed_result = failed_model_job["run"]["structured_result_json"]
    assert failed_result["retrieval"]["status"] == "local-model-unavailable"
    assert "C:/Users/private" not in str(failed_model_job)


def test_wip_critical_read_failure_is_generic_and_preserves_manuscript(
    temp_db_url: str, tmp_path: Path, monkeypatch
) -> None:
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    _, manuscript_id, draft = _setup_wip(
        client, tmp_path / "failure", "This private claim must never appear in a failed job response."
    )
    app.state.wip_critical_review_deps = {
        "embed_model": _FakeEmbedModel(),
        "vector_store": _FakeVectorStore(),
        "stance_scorer": _FakeStanceScorer(),
    }

    def fail_store(*args, **kwargs):
        raise RuntimeError(f"database failure involving {draft}")

    monkeypatch.setattr("app.backend.api.routers.wip_critical_review.store_critical_review_run", fail_store)
    start, job = _start_and_get(client, manuscript_id)
    assert start["status"] == "pending"
    assert job == {
        "job_id": start["job_id"],
        "status": "error",
        "detail": "Local critical read could not complete. The manuscript remains unchanged.",
        "run": None,
    }
    assert draft.read_text(encoding="utf-8").startswith("This private claim")
    assert str(draft) not in str(job) and "This private claim" not in str(job)


def test_wip_critical_read_refuses_to_persist_when_primary_changes_mid_job(temp_db_url: str, tmp_path: Path) -> None:
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    _, manuscript_id, draft = _setup_wip(
        client, tmp_path / "changing", "This original manuscript claim is long enough for comparison."
    )
    _, _, embedding_id = _library_embedding(temp_db_url)

    def change_draft() -> None:
        draft.write_text(
            "This replacement manuscript claim arrived while the local read was running.", encoding="utf-8"
        )

    app.state.wip_critical_review_deps = {
        "embed_model": _FakeEmbedModel(on_encode=change_draft),
        "vector_store": _FakeVectorStore(embedding_id),
        "stance_scorer": _FakeStanceScorer(),
    }
    start, job = _start_and_get(client, manuscript_id)
    assert job == {
        "job_id": start["job_id"],
        "status": "error",
        "detail": "The primary manuscript changed during the local critical read. Run it again from the new text.",
        "run": None,
    }
    assert draft.read_text(encoding="utf-8").startswith("This replacement manuscript")
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert not any(run["tool_id"] == "critical-read" for run in runs)


def test_wip_critical_read_rejects_missing_manuscript_primary_and_unknown_job(temp_db_url: str, tmp_path: Path) -> None:
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    assert client.post("/wip/manuscripts/999/critical-read", json={}).status_code == 404
    _, manuscript_id, _ = _setup_wip(client, tmp_path / "no-primary", "A manuscript sentence long enough to read.")
    files = client.get(f"/wip/manuscripts/{manuscript_id}/files").json()
    assert (
        client.patch(f"/wip/manuscripts/{manuscript_id}/files/{files[0]['id']}", json={"is_primary": False}).status_code
        == 200
    )
    response = client.post(f"/wip/manuscripts/{manuscript_id}/critical-read", json={})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Select a primary manuscript file")
    assert client.get("/wip/critical-read/not-a-job").status_code == 404


def test_library_critical_corpus_requires_matching_model_article_role_and_live_paper(temp_db_url: str) -> None:
    _, _, eligible = _library_embedding(temp_db_url)
    _, _, supplement = _library_embedding(temp_db_url, role="supplement")
    _, _, wrong_model = _library_embedding(temp_db_url, model="different")
    with make_engine(temp_db_url).begin() as conn:
        wrong_model_paper = conn.scalar(
            select(schema.chunks.c.paper_id)
            .join(schema.embeddings, schema.embeddings.c.target_id == schema.chunks.c.id)
            .where(schema.embeddings.c.id == wrong_model)
        )
        conn.execute(
            update(schema.papers)
            .where(schema.papers.c.id == wrong_model_paper)
            .values(deleted_at=func.current_timestamp())
        )
        ids = library_article_chunk_embedding_ids(conn, model_name="fake-wip", model_version="v1", normalization="none")
    assert ids == {eligible}
    assert supplement not in ids and wrong_model not in ids


def test_extract_block_claims_is_bounded_deduplicated_and_honest_about_coordinates() -> None:
    sentences = [f"This is bounded claim sentence number {index} with enough ordinary text." for index in range(20)]
    blocks = [ContentBlock(" ".join(sentences + [sentences[0]]), "Results", 4, 4)]
    non_pdf = extract_block_claim_sentences(blocks, has_real_pages=False)
    assert len(non_pdf) == MAX_CRITIQUE_CLAIMS
    assert len({claim.text for claim in non_pdf}) == MAX_CRITIQUE_CLAIMS
    assert all(claim.page is None and claim.coordinate_precision is None for claim in non_pdf)
    pdf = extract_block_claim_sentences(blocks, has_real_pages=True)
    assert all(claim.page == 4 and claim.coordinate_precision == "region" for claim in pdf)


def test_critical_search_rejects_vector_hits_outside_the_server_selected_corpus() -> None:
    class OutOfScopeVectorStore:
        def search(self, conn, *, vector, top_k, candidate_embedding_ids=None):
            return [VectorHit(embedding_id=99, distance=0.01)]

    report = search_contested_claims(
        None,
        None,
        embed_model=_FakeEmbedModel(),
        vector_store=OutOfScopeVectorStore(),
        stance_scorer=_FakeStanceScorer(),
        resolve_chunk=lambda hit: ChunkInfo(9, "A supplement passage must not escape its scope.", 2),
        claim_sentences=["This manuscript contains a sufficiently long test claim."],
        other_chunk_ids={1},
    )
    assert report.contested_claims == []
    assert report.retrieved_passages == 0
    assert report.retrieval_status == "no-retrievable-passages"
