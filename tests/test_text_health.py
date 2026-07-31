from __future__ import annotations

from pathlib import Path

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper, get_chunks_for_paper
from app.backend.persistence.schema import embeddings
from tests.api_helpers import ApiFakeEmbeddingModel


def test_text_health_overview_and_missing_section_batch(temp_db_url: str, tmp_path: Path) -> None:
    sectioned_pdf = _make_sectioned_pdf(tmp_path / "sectioned.pdf")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        needs = _paper_with_pdf(conn, sectioned_pdf, title="Needs sections")
        create_chunk(
            conn,
            paper_id=needs["paper_id"],
            attachment_id=needs["attachment_id"],
            text="old text without a section",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="old",
            extraction_version="0",
            chunking_strategy="old",
            chunk_version="old",
            source_attachment_checksum="old",
            section=None,
            bbox_json=[{"page": 1, "x0": 1, "y0": 1, "x1": 2, "y1": 2}],
        )
        no_chunks = _paper_with_pdf(conn, sectioned_pdf, title="Scanned candidate")
        no_pdf = create_paper(conn, title="No PDF", csl_json={"title": "No PDF"})
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url, embedding_model=ApiFakeEmbeddingModel()))
    overview = client.get("/papers/text-health/overview").json()

    assert overview["counts"]["missing_section_labels"] == 1
    assert overview["counts"]["no_chunks"] == 1
    assert overview["counts"]["no_local_pdf"] >= 1
    by_id = {item["paper_id"]: item for item in overview["items"]}
    assert "missing_section_labels" in by_id[needs["paper_id"]]["flags"]
    assert by_id[no_chunks["paper_id"]]["status"] == "needs_ocr_or_better_pdf"
    assert by_id[no_pdf]["status"] == "no_local_pdf"

    done = _run_job(client, client.post("/papers/text-health/reprocess", json={"mode": "missing_section_labels"}))

    assert done["summary"]["total"] == 1
    assert done["summary"]["reprocessed"] == 1
    with make_engine(temp_db_url).begin() as conn:
        chunks = get_chunks_for_paper(conn, needs["paper_id"], document_roles=ARTICLE_DOCUMENT_ROLES)
        no_chunk_rows = get_chunks_for_paper(conn, no_chunks["paper_id"], document_roles=ARTICLE_DOCUMENT_ROLES)
        chunk_ids = [chunk["id"] for chunk in chunks]
        embedded = conn.execute(
            select(func.count())
            .select_from(embeddings)
            .where(embeddings.c.target_type == "chunk", embeddings.c.target_id.in_(chunk_ids))
        ).scalar_one()
    assert {chunk["section"] for chunk in chunks} == {"abstract", "methods"}
    assert no_chunk_rows == []
    # Reprocess must re-embed the fresh chunks so the paper stays retrievable in vector search — regression:
    # it used to delete the old chunks' embeddings without adding any for the new ones.
    assert chunk_ids and embedded == len(chunk_ids)


def test_selected_text_reprocess_skips_no_chunks_and_no_local_pdf(temp_db_url: str, tmp_path: Path) -> None:
    sectioned_pdf = _make_sectioned_pdf(tmp_path / "sectioned-selected.pdf")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ready = _paper_with_pdf(conn, sectioned_pdf, title="Ready")
        create_chunk(
            conn,
            paper_id=ready["paper_id"],
            attachment_id=ready["attachment_id"],
            text="old text",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="old",
            extraction_version="0",
            chunking_strategy="old",
            chunk_version="old",
            source_attachment_checksum="old",
            bbox_json=[{"page": 1, "x0": 1, "y0": 1, "x1": 2, "y1": 2}],
        )
        no_chunks = _paper_with_pdf(conn, sectioned_pdf, title="No chunks")
        no_pdf = create_paper(conn, title="No PDF", csl_json={"title": "No PDF"})
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url, embedding_model=ApiFakeEmbeddingModel()))
    started = client.post(
        "/papers/text-health/reprocess",
        json={"mode": "selected", "paper_ids": [ready["paper_id"], no_chunks["paper_id"], no_pdf]},
    )
    done = _run_job(client, started)

    assert done["summary"]["total"] == 3
    assert done["summary"]["reprocessed"] == 1
    assert done["summary"]["skipped_no_chunks"] == 1
    assert done["summary"]["skipped_no_local_pdf"] == 1


def test_reprocess_empty_extraction_preserves_existing_chunks(temp_db_url: str, tmp_path: Path) -> None:
    blank_pdf = _make_blank_pdf(tmp_path / "blank.pdf")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        seeded = _paper_with_pdf(conn, blank_pdf, title="Blank")
        create_chunk(
            conn,
            paper_id=seeded["paper_id"],
            attachment_id=seeded["attachment_id"],
            text="existing text should remain",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="old",
            extraction_version="0",
            chunking_strategy="old",
            chunk_version="old",
            source_attachment_checksum="old",
            bbox_json=[{"page": 1, "x0": 1, "y0": 1, "x1": 2, "y1": 2}],
        )
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url, embedding_model=ApiFakeEmbeddingModel()))
    response = client.post(f"/papers/{seeded['paper_id']}/reprocess-pdf")

    assert response.status_code == 422
    with make_engine(temp_db_url).begin() as conn:
        chunks = get_chunks_for_paper(conn, seeded["paper_id"], document_roles=ARTICLE_DOCUMENT_ROLES)
    assert [chunk["text"] for chunk in chunks] == ["existing text should remain"]


def _run_job(client: TestClient, started):
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    for _ in range(20):
        status = client.get(f"/papers/text-health/reprocess/{job_id}").json()
        if status["status"] == "done":
            return status
    raise AssertionError("job did not finish")


def _paper_with_pdf(conn, pdf_path: Path, *, title: str) -> dict[str, int]:
    paper_id = create_paper(conn, title=title, csl_json={"title": title})
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        original_path=str(pdf_path),
        resolved_path=str(pdf_path),
        checksum="seed",
        file_size=pdf_path.stat().st_size,
        content_type="application/pdf",
        attachment_type="pdf",
        role="primary",
    )
    return {"paper_id": paper_id, "attachment_id": attachment_id}


def _make_sectioned_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=560, height=280)
    page.insert_text((50, 45), "Abstract", fontsize=16)
    page.insert_text((50, 85), "Data are available at OSF.", fontsize=12)
    page.insert_text((50, 135), "Methods", fontsize=16)
    page.insert_text((50, 175), "We recruited participants and analyzed survey responses.", fontsize=12)
    document.save(path)
    document.close()
    return path


def _make_blank_pdf(path: Path) -> Path:
    document = fitz.open()
    document.new_page(width=400, height=300)
    document.save(path)
    document.close()
    return path
