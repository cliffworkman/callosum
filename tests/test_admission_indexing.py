"""The post-admission indexing invariant, enforced across every metadata-admission front end (#61).

**The rule under test:** if a record is admitted to the active Library and has enough metadata to
participate in the paper-level index, its indexing state must not depend on which front end created it.

Callosum has no single successful-admission lifecycle seam — a dozen ``create_paper`` call sites and
no post-admission hook — so this was previously a convention each front end had to remember, and
several did not. This test is what makes the invariant enforced rather than remembered: a new
admission endpoint that forgets to index fails here instead of silently shipping papers that are
invisible to every paper-level vector path.

Hermetic: fake embedding model + in-memory vector store, injected Crossref, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.acquisition.fetch import library_dir
from app.backend.api import create_app
from app.backend.embeddings.admission import ensure_paper_indexed
from app.backend.embeddings.pipeline import PAPER_TEXT_VERSION, paper_embedding_text
from app.backend.embeddings.vector_store import InMemoryVectorStore, SQLiteVecVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import attachments, chunks, embeddings, papers
from tests.api_helpers import ApiFakeEmbeddingModel
from tests.test_capture import _direct_pdf_capture_id, _paired, _pdf_with_front_matter_doi
from tests.test_import_queue import _ui_instance  # noqa: F401 -- isolate the capture role/session

IOANNIDIS_PDF = Path(__file__).parent / "fixtures/capture/ioannidis-pmed.0020124.pdf"
IOANNIDIS_DOI = "10.1371/journal.pmed.0020124"


class _FakeCrossref:
    def resolve_doi(self, conn, doi):
        from integrations.crossref.adapter import CrossrefResolution

        return CrossrefResolution(
            doi=doi,
            resolved=True,
            csl_json={
                "DOI": doi,
                "title": "An Admitted Paper",
                "abstract": "Enough text for the paper-level embedding to be non-empty.",
                "container-title": "Journal of Admission",
                "issued": {"date-parts": [[2024]]},
                "author": [{"family": "Rivera", "given": "A"}],
            },
        )


def _paper_embedding_count(db_url: str, paper_id: int) -> int:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        count = conn.execute(
            select(func.count())
            .select_from(embeddings)
            .where(embeddings.c.target_type == "paper", embeddings.c.target_id == paper_id)
        ).scalar_one()
    engine.dispose()
    return int(count)


def _client(temp_db_url: str, *, model=None, store=None) -> TestClient:
    return TestClient(
        create_app(
            db_url=temp_db_url,
            crossref_client=_FakeCrossref(),
            embedding_model=model or ApiFakeEmbeddingModel(),
            vector_store=store or InMemoryVectorStore(),
        )
    )


def _admit_by_doi(client: TestClient) -> int:
    resp = client.post("/papers/by-doi", json={"doi": "10.1/admitted-by-doi", "acquire_oa": False})
    assert resp.status_code in (200, 201), resp.text  # 201 on create, 200 when surfacing an existing paper
    return int(resp.json()["paper_id"])


def _admit_by_discovery_save(client: TestClient) -> int:
    resp = client.post(
        "/discovery/save",
        json={
            "title": "An Admitted Paper",
            "doi": "10.1/admitted-by-discovery",
            "abstract": "Enough text for the paper-level embedding to be non-empty.",
            "authors": ["Rivera, A"],
            "journal": "Journal of Admission",
            "year": 2024,
        },
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["paper_id"])


def _admit_by_zotero_resolve(client: TestClient) -> int:
    resp = client.post(
        "/citations/zotero/resolve",
        json={
            "items": [
                {
                    "item_data": {
                        "type": "article-journal",
                        "title": "An Admitted Paper",
                        "DOI": "10.1/admitted-by-zotero",
                        "issued": {"date-parts": [[2024]]},
                        "author": [{"family": "Rivera", "given": "A"}],
                    },
                    "uris": ["http://zotero.org/users/1/items/ADMIT001"],
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()[0]["paper_id"])


def _capture_pdf(client: TestClient, pdf: Path) -> dict:
    headers = _paired(client)
    capture_id = _direct_pdf_capture_id(client, headers)
    response = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _admit_by_capture_confirmation(client: TestClient) -> int:
    """Drive capture -> review -> confirmation, including real PDF extraction/chunk indexing."""
    with client.app.state.engine.connect() as conn:
        before_papers = conn.execute(select(func.count()).select_from(papers)).scalar_one()
        before_embeddings = conn.execute(select(func.count()).select_from(embeddings)).scalar_one()
    body = _capture_pdf(client, IOANNIDIS_PDF)
    if body["paper_id"] is None:
        item = client.get("/library/import-queue").json()["items"][0]
        path = f"/library/import-queue/{item['artifact_id']}"
        assert item["best_candidate"]["disposition"] == "observed_unverified"
        assert client.post(path + "/preview-doi", json={"doi": IOANNIDIS_DOI}).status_code == 200
        with client.app.state.engine.connect() as conn:
            assert conn.execute(select(func.count()).select_from(papers)).scalar_one() == before_papers
            assert conn.execute(select(func.count()).select_from(embeddings)).scalar_one() == before_embeddings
        response = client.post(path + "/confirm", json={"doi": IOANNIDIS_DOI, "source": "candidate"})
        assert response.status_code == 200, response.text
        assert response.json()["promotion_state"] == "promoted"
        paper_id = response.json()["resolved_paper_id"]
        evidence = client.get(path).json()["evidence"]
        assert evidence["user_actions"][-1]["action"] == "user_confirmed_candidate"
    else:
        paper_id = body["paper_id"]
    with client.app.state.engine.connect() as conn:
        assert conn.execute(select(papers.c.doi).where(papers.c.id == paper_id)).scalar_one() == IOANNIDIS_DOI
        attached = conn.execute(select(attachments).where(attachments.c.paper_id == paper_id)).mappings().one()
        assert Path(attached["resolved_path"]).read_bytes() == IOANNIDIS_PDF.read_bytes()
        chunk_ids = conn.execute(select(chunks.c.id).where(chunks.c.paper_id == paper_id)).scalars().all()
        assert chunk_ids  # count depends on the development vs packaged PyMuPDF version
        assert conn.execute(
            select(func.count())
            .select_from(embeddings)
            .where(
                embeddings.c.target_type == "chunk",
                embeddings.c.target_id.in_(chunk_ids),
                embeddings.c.vector_store_ref.is_not(None),
            )
        ).scalar_one() == len(chunk_ids)
    assert client.get("/library/import-queue").json()["items"] == []
    return int(paper_id)


def _admit_by_automatic_capture(client: TestClient) -> int:
    pdf = library_dir().parent / "automatic.pdf"
    if not pdf.exists():
        _pdf_with_front_matter_doi(pdf, title="An Admitted Paper", dois=["10.1234/automatic"])
    body = _capture_pdf(client, pdf)
    assert body["paper_id"] is not None, body
    assert client.get("/library/import-queue").json()["items"] == []
    return int(body["paper_id"])


ADMISSION_FRONT_ENDS = [
    pytest.param(_admit_by_doi, id="library-add-by-doi"),
    pytest.param(_admit_by_discovery_save, id="discovery-save"),
    pytest.param(_admit_by_zotero_resolve, id="zotero-citation-resolve"),
    pytest.param(_admit_by_capture_confirmation, id="capture-pdf-confirmation"),
    pytest.param(_admit_by_automatic_capture, id="capture-pdf-automatic"),
]


@pytest.mark.parametrize("admit", ADMISSION_FRONT_ENDS)
def test_every_admission_front_end_indexes_the_paper(temp_db_url: str, admit) -> None:
    client = _client(temp_db_url)
    paper_id = admit(client)
    assert _paper_embedding_count(temp_db_url, paper_id) == 1, (
        "an admitted paper must be indexed regardless of which front end created it"
    )


@pytest.mark.parametrize("admit", ADMISSION_FRONT_ENDS)
def test_admission_indexing_does_no_duplicate_work_on_a_second_run(temp_db_url: str, admit) -> None:
    """The invariant is idempotent: re-admitting the same record must not write a second embedding."""
    client = _client(temp_db_url)
    paper_id = admit(client)
    again = admit(client)

    assert again == paper_id, "the second admission should surface the same paper, not create another"
    assert _paper_embedding_count(temp_db_url, paper_id) == 1


class RecordingModel(ApiFakeEmbeddingModel):
    def __init__(self):
        super().__init__()
        object.__setattr__(self, "calls", [])

    def encode_texts(self, texts):
        self.calls.extend(texts)
        return super().encode_texts(texts)


@pytest.mark.parametrize("indexed", [False, True], ids=["missing-index", "valid-index"])
@pytest.mark.parametrize(
    "admit,doi",
    [(_admit_by_capture_confirmation, IOANNIDIS_DOI), (_admit_by_automatic_capture, "10.1234/automatic")],
    ids=["confirmed", "automatic"],
)
def test_capture_reuses_existing_paper_and_current_index(temp_db_url, indexed, admit, doi):
    model = RecordingModel()
    client = _client(temp_db_url, model=model)
    engine = client.app.state.engine
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="An Admitted Paper", doi=doi, csl_json={"title": "An Admitted Paper"})
        metadata_text = paper_embedding_text(conn.execute(select(papers)).mappings().one())
    if indexed:
        ensure_paper_indexed(engine, paper_id, model=model, vector_store=client.app.state.vector_store)
    model.calls.clear()
    assert admit(client) == paper_id
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(papers)).scalar_one() == 1
        entry = conn.execute(select(embeddings).where(embeddings.c.target_type == "paper")).mappings().one()
        assert entry["source_text_version"] == PAPER_TEXT_VERSION
        assert entry["vector_store_ref"]
        assert entry["id"] in client.app.state.vector_store.vectors
        before_embeddings = list(conn.execute(select(embeddings)).mappings())
        before_chunks = list(conn.execute(select(chunks)).mappings())
        before_attachments = list(conn.execute(select(attachments)).mappings())
    assert model.calls.count(metadata_text) == (0 if indexed else 1)
    model.calls.clear()
    assert admit(client) == paper_id
    assert model.calls == []  # same-content recapture neither re-embeds nor duplicates the PDF
    with engine.connect() as conn:
        assert list(conn.execute(select(embeddings)).mappings()) == before_embeddings
        assert list(conn.execute(select(chunks)).mappings()) == before_chunks
        assert list(conn.execute(select(attachments)).mappings()) == before_attachments


def test_retry_repairs_missing_paper_index_after_nonfatal_model_failure(temp_db_url, monkeypatch, caplog):
    from app.backend.capture import provisional

    model = RecordingModel()
    client = _client(temp_db_url, model=model)
    assert _capture_pdf(client, IOANNIDIS_PDF)["paper_id"] is None
    item = client.get("/library/import-queue").json()["items"][0]
    path = f"/library/import-queue/{item['artifact_id']}"

    def unavailable(*args, **kwargs):
        raise RuntimeError("test embedding unavailable")

    with monkeypatch.context() as faults:
        faults.setattr(model, "encode_texts", unavailable)
        faults.setattr(provisional, "attach_pdf_to_paper", unavailable)
        result = client.post(path + "/confirm", json={"doi": IOANNIDIS_DOI, "source": "candidate"})
    assert result.status_code == 200
    assert result.json()["promotion_state"] == "indexing_unavailable"
    paper_id = result.json()["resolved_paper_id"]
    assert _paper_embedding_count(temp_db_url, paper_id) == 0
    assert "commit_each: skipped an item" in caplog.text
    assert client.get(path + "/pdf").content == IOANNIDIS_PDF.read_bytes()
    before = client.get(path).json()["evidence"]
    result = client.post(path + "/retry")
    assert result.status_code == 200 and result.json()["promotion_state"] == "promoted"
    assert result.json()["resolved_paper_id"] == paper_id
    assert _paper_embedding_count(temp_db_url, paper_id) == 1
    after = client.get(path).json()["evidence"]
    assert after["user_actions"][:-1] == before["user_actions"]
    assert after["user_actions"][-1]["action"] == "retry_attempted"
    # Re-capture exercises content deduplication and the intact real attachment/chunk checks.
    assert _admit_by_capture_confirmation(client) == paper_id


def test_metadata_index_failure_does_not_fail_successful_pdf_promotion(temp_db_url, monkeypatch, caplog):
    model = RecordingModel()
    client = _client(temp_db_url, model=model)
    original = model.encode_texts

    def fail_only_metadata(texts):
        # Distinguish the ordinary metadata text from the real fixture's scientific chunks.
        if len(texts) == 1 and texts[0].startswith("An Admitted Paper Enough text"):
            raise RuntimeError("test metadata model unavailable")
        return original(texts)

    monkeypatch.setattr(model, "encode_texts", fail_only_metadata)
    paper_id = _admit_by_capture_confirmation(client)
    assert _paper_embedding_count(temp_db_url, paper_id) == 0
    assert "commit_each: skipped an item" in caplog.text


def test_attachment_conflict_still_indexes_the_admitted_paper(temp_db_url, monkeypatch):
    from app.backend.capture import provisional

    client = _client(temp_db_url)
    _capture_pdf(client, IOANNIDIS_PDF)
    item = client.get("/library/import-queue").json()["items"][0]
    path = f"/library/import-queue/{item['artifact_id']}"
    monkeypatch.setattr(provisional, "attachment_decision", lambda *args, **kwargs: (False, "test conflict"))
    result = client.post(path + "/confirm", json={"doi": IOANNIDIS_DOI, "source": "candidate"})
    assert result.status_code == 200 and result.json()["promotion_state"] == "attachment_conflict"
    assert _paper_embedding_count(temp_db_url, result.json()["resolved_paper_id"]) == 1
    assert client.get(path + "/pdf").content == IOANNIDIS_PDF.read_bytes()
    with client.app.state.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(attachments)).scalar_one() == 0


def test_confirmation_persists_paper_and_chunk_vectors_across_database_reopen(temp_db_url):
    store = SQLiteVecVectorStore()
    client = _client(temp_db_url, store=store)
    paper_id = _admit_by_capture_confirmation(client)
    client.app.state.engine.dispose()
    engine = make_engine(temp_db_url)
    try:
        with engine.connect() as conn:
            store.ensure_ready(conn, 3)  # real sqlite-vec storage; injected deterministic 3D model
            records = list(conn.execute(select(embeddings)).mappings())
            vectors = dict(conn.exec_driver_sql("SELECT rowid, embedding FROM callosum_vec_embeddings_3").all())
            assert set(vectors) == {r["id"] for r in records}
            assert all(len(vector) == 12 for vector in vectors.values())
            paper_records = [r for r in records if r["target_type"] == "paper"]
            assert len(paper_records) == 1 and paper_records[0]["target_id"] == paper_id
            assert paper_records[0]["source_text_version"] == PAPER_TEXT_VERSION
            hits = store.search(conn, vector=[1.0, 0.0, 0.0], top_k=1, candidate_embedding_ids={paper_records[0]["id"]})
            assert [hit.embedding_id for hit in hits] == [paper_records[0]["id"]]
    finally:
        engine.dispose()
