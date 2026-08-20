"""Endpoint-level tests for the native Zotero library import route (backlog #57 Phase 1) --
POST/GET /library/zotero/import[/{job_id}] (app/backend/api/routers/library_zotero.py). The importer-level
behavior these endpoints wrap is covered directly in tests/test_zotero_importer.py; these tests exercise the
job lifecycle, request validation, and error surfacing through the real HTTP contract."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import chunks, embeddings, papers
from tests.test_zotero_importer import _create_zotero_schema, _make_pdf, _make_zotero_fixture


class _FakeModel:
    name = "fake-zotero-import"
    version = "v1"
    dimension = 4
    normalization = "none"

    def encode_texts(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _make_empty_zotero_fixture(zotero_dir: Path) -> Path:
    """A syntactically valid but zero-item Zotero library -- same schema as _make_zotero_fixture, no rows."""
    zotero_dir.mkdir()
    conn = sqlite3.connect(zotero_dir / "zotero.sqlite")
    try:
        _create_zotero_schema(conn)
        conn.commit()
    finally:
        conn.close()
    return zotero_dir


def test_zotero_import_endpoint_happy_path(temp_db_url: str, tmp_path: Path) -> None:
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel()))
    started = client.post("/library/zotero/import", json={"zotero_data_dir": str(zotero_dir)})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(60):
        result = client.get(f"/library/zotero/import/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    assert result["summary"]["papers_created"] == 3
    assert result["summary"]["chunks_created"] > 0
    assert len(client.get("/papers").json()) == result["summary"]["papers_created"]


def test_zotero_import_endpoint_nonexistent_directory_422(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    started = client.post("/library/zotero/import", json={"zotero_data_dir": str(tmp_path / "nope")})
    assert started.status_code == 422


def test_zotero_import_endpoint_missing_zotero_sqlite(temp_db_url: str, tmp_path: Path) -> None:
    empty_dir = tmp_path / "not_zotero"
    empty_dir.mkdir()
    # _embedding_model(app) is constructed unconditionally at the top of the background job, before the
    # FileNotFoundError this test targets is even raised -- inject the fake so this stays fast/hermetic like
    # every other test here, not just the ones that actually reach embedding.
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel()))
    started = client.post("/library/zotero/import", json={"zotero_data_dir": str(empty_dir)})
    assert started.status_code == 202  # passes the is_dir() pre-check; fails inside the job
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/library/zotero/import/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "error"
    assert "zotero.sqlite" in result["detail"]
    assert "Traceback" not in result["detail"]


def test_zotero_import_status_404_for_unknown_job(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/library/zotero/import/does-not-exist").status_code == 404


def test_zotero_import_endpoint_empty_library(temp_db_url: str, tmp_path: Path) -> None:
    zotero_dir = _make_empty_zotero_fixture(tmp_path / "zotero_empty")
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel()))
    started = client.post("/library/zotero/import", json={"zotero_data_dir": str(zotero_dir)})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/library/zotero/import/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    assert result["summary"] == {
        "papers_created": 0,
        "papers_matched": 0,
        "attachments_created": 0,
        "chunks_created": 0,
        "attachment_errors": 0,
        "attachment_error_details": [],
    }


def test_zotero_import_matched_paper_embeds_newly_created_chunks(temp_db_url: str, tmp_path: Path) -> None:
    # Endpoint-level analog of test_zotero_importer.py's importer-level "second run populates chunk ids for a
    # previously-missing PDF" test -- this one additionally proves the matched (not newly-created) paper's new
    # chunks actually get embedded, per ZoteroImportResult.chunk_ids_by_paper's own documented rationale: a
    # matched paper still needs embed_chunks for brand-new chunks even though it's excluded from
    # created_paper_ids (which only gates embed_papers + the retraction check).
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel()))

    started = client.post("/library/zotero/import", json={"zotero_data_dir": str(zotero_dir)})
    job_id = started.json()["job_id"]
    first = {}
    for _ in range(60):
        first = client.get(f"/library/zotero/import/{job_id}").json()
        if first["status"] in ("done", "error"):
            break
    assert first["status"] == "done", first
    assert first["summary"]["papers_created"] == 3

    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        key_only_paper_id = conn.execute(select(papers.c.id).where(papers.c.zotero_item_key == "KEYONLY1")).scalar_one()
        chunk_count_before = conn.execute(
            select(func.count()).select_from(chunks).where(chunks.c.paper_id == key_only_paper_id)
        ).scalar_one()
    assert chunk_count_before == 0

    # Materialize the previously-missing linked PDF, then re-run the import against the same directory + DB.
    _make_pdf(zotero_dir / "missing-linked.pdf")
    started2 = client.post("/library/zotero/import", json={"zotero_data_dir": str(zotero_dir)})
    job_id2 = started2.json()["job_id"]
    second = {}
    for _ in range(60):
        second = client.get(f"/library/zotero/import/{job_id2}").json()
        if second["status"] in ("done", "error"):
            break
    assert second["status"] == "done", second
    assert second["summary"]["papers_created"] == 0  # KEYONLY1 already exists -- matched, not created
    assert second["summary"]["chunks_created"] > 0

    with engine.connect() as conn:
        chunk_ids = list(conn.execute(select(chunks.c.id).where(chunks.c.paper_id == key_only_paper_id)).scalars())
        assert chunk_ids
        embedded_chunk_ids = set(
            conn.execute(
                select(embeddings.c.target_id).where(
                    embeddings.c.target_type == "chunk", embeddings.c.target_id.in_(chunk_ids)
                )
            ).scalars()
        )
    assert embedded_chunk_ids == set(chunk_ids)  # the matched paper's brand-new chunks were embedded too
