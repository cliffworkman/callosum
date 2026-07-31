"""inc 231 (backlog B3) — local OCR of scanned / image-only PDFs into a *searchable* copy.

Hermetic: no Tesseract binary. A fake page-runner returns a real single-page PDF *with* a text layer (built via
PyMuPDF), so `make_searchable_pdf` produces a genuine searchable PDF that the NORMAL extraction pipeline turns into
chunks. The endpoint runs with an injected fake embedding model + in-memory vector store."""

from __future__ import annotations

import fitz

from app.backend.api import create_app
from app.backend.pdf_processing.extraction import extract_pdf
from app.backend.pdf_processing.ingest import ingest_pdf_scaffold
from app.backend.pdf_processing.ocr import make_searchable_pdf
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import get_attachments_for_paper, get_chunks_for_paper
from tests.api_helpers import ApiFakeEmbeddingModel, InMemoryVectorStore

OCR_TEXT = "ultimatum game bargaining behaviour"


def _text_pdf_bytes(text: str = OCR_TEXT) -> bytes:
    """A 1-page PDF WITH a real text layer — stands in for Tesseract's searchable-PDF output for one page."""
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((30, 60), text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _fake_page_runner(png: bytes, lang: str) -> bytes:
    return _text_pdf_bytes()


def _image_only_pdf(path) -> None:
    """A scanned-style PDF: a page with NO text layer (just a drawn rectangle) → 0 chunks on normal extraction."""
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.draw_rect(fitz.Rect(20, 20, 280, 280), fill=(0.85, 0.85, 0.85))
    doc.save(str(path))
    doc.close()


# --- the engine -------------------------------------------------------------


def test_make_searchable_pdf_embeds_a_text_layer(tmp_path):
    src = tmp_path / "scan.pdf"
    out = tmp_path / "scan-ocr.pdf"
    _image_only_pdf(src)
    # the source has no text layer
    assert all(not page.blocks for page in extract_pdf(src).pages)

    pages = make_searchable_pdf(src, out, runner=_fake_page_runner)
    assert pages == 1 and out.is_file()
    # the output IS searchable — the normal extractor now finds the OCR'd text
    result = extract_pdf(out)
    text = " ".join(block.text for page in result.pages for block in page.blocks)
    assert "ultimatum" in text.lower()


def test_tesseract_exe_resolves_override_then_path_then_common(tmp_path, monkeypatch):
    import app.backend.pdf_processing.ocr as ocr_mod

    fake_bin = tmp_path / "tesseract.exe"
    fake_bin.write_bytes(b"x")

    # 1. CALLOSUM_TESSERACT_PATH override wins (even over PATH)
    monkeypatch.setenv("CALLOSUM_TESSERACT_PATH", str(fake_bin))
    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _n: "/somewhere/on/path/tesseract")
    assert ocr_mod.tesseract_exe() == str(fake_bin)

    # 2. no override → PATH (shutil.which)
    monkeypatch.delenv("CALLOSUM_TESSERACT_PATH", raising=False)
    assert ocr_mod.tesseract_exe() == "/somewhere/on/path/tesseract"

    # 3. not on PATH → the common install locations (the installed-but-not-on-PATH case)
    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _n: None)
    monkeypatch.setattr(ocr_mod, "_COMMON_TESSERACT_PATHS", (str(fake_bin),))
    assert ocr_mod.tesseract_exe() == str(fake_bin)

    # 4. nowhere → None → not available
    monkeypatch.setattr(ocr_mod, "_COMMON_TESSERACT_PATHS", (str(tmp_path / "missing.exe"),))
    assert ocr_mod.tesseract_exe() is None and ocr_mod.tesseract_available() is False


def test_make_searchable_pdf_merges_multiple_pages(tmp_path):
    src = tmp_path / "scan2.pdf"
    out = tmp_path / "scan2-ocr.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=300, height=300).draw_rect(fitz.Rect(10, 10, 290, 290), fill=(0.9, 0.9, 0.9))
    doc.save(str(src))
    doc.close()
    assert make_searchable_pdf(src, out, runner=_fake_page_runner) == 3


# --- the endpoint -----------------------------------------------------------


def _app(temp_db_url):
    return create_app(
        db_url=temp_db_url,
        embedding_model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
    )


def _seed_scanned_paper(temp_db_url, tmp_path) -> int:
    src = tmp_path / "seed-scan.pdf"
    _image_only_pdf(src)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = ingest_pdf_scaffold(conn, src, title="Scanned paper")
        paper_id = int(result["paper_id"])
        assert not get_chunks_for_paper(
            conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES
        )  # no text layer → 0 chunks (the OCR target)
    engine.dispose()
    return paper_id


def _drive(client, paper_id):
    r = client.post("/papers/ocr/run", json={"paper_id": paper_id})
    if r.status_code != 202:
        return r
    jid = r.json()["job_id"]
    data = {}
    for _ in range(60):
        data = client.get(f"/papers/ocr/run/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    return data


def test_ocr_endpoint_makes_a_scanned_paper_searchable(temp_db_url, tmp_path, monkeypatch):
    paper_id = _seed_scanned_paper(temp_db_url, tmp_path)
    from fastapi.testclient import TestClient as _Client

    import app.backend.api.routers.ocr as ocr_router

    def fake_msp(src, out, **kw):
        return make_searchable_pdf(src, out, runner=_fake_page_runner, on_progress=kw.get("on_progress"))

    monkeypatch.setattr(ocr_router, "make_searchable_pdf", fake_msp)

    client = _Client(_app(temp_db_url))
    done = _drive(client, paper_id)
    assert done["status"] == "done"
    assert done["result"]["pages"] == 1 and done["result"]["chunks_created"] >= 1

    # the paper is now searchable, and the OCR'd copy is the primary attachment (marked import_source="ocr")
    detail = client.get(f"/papers/{paper_id}").json()
    assert detail["chunk_count"] >= 1
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        atts = get_attachments_for_paper(conn, paper_id)
        primaries = [a for a in atts if (a["role"] or "") == "primary"]
        assert len(primaries) == 1 and primaries[0]["import_source"] == "ocr"
        assert len(atts) == 2  # the original scanned attachment is kept (non-destructive)
    engine.dispose()


def test_ocr_endpoint_404_and_422(temp_db_url, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient as _Client

    client = _Client(_app(temp_db_url))
    # unknown paper → 404
    assert client.post("/papers/ocr/run", json={"paper_id": 999999}).status_code == 404

    # a paper with a text layer (chunks) → 422 (OCR is only for scanned PDFs with none)
    seed = tmp_path / "text.pdf"
    seed.write_bytes(_text_pdf_bytes("already has text"))
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        with_text = int(ingest_pdf_scaffold(conn, seed, title="Has text")["paper_id"])
        assert get_chunks_for_paper(conn, with_text, document_roles=ARTICLE_DOCUMENT_ROLES)  # it has chunks
    engine.dispose()
    assert client.post("/papers/ocr/run", json={"paper_id": with_text}).status_code == 422

    # unknown job id → 404
    assert client.get("/papers/ocr/run/nope").status_code == 404


def test_ocr_job_fails_gracefully_when_tesseract_missing(temp_db_url, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient as _Client

    import app.backend.api.routers.ocr as ocr_router
    from app.backend.pdf_processing.ocr import TesseractUnavailable

    paper_id = _seed_scanned_paper(temp_db_url, tmp_path)

    def boom(src, out, **kw):
        raise TesseractUnavailable("Tesseract OCR is not installed. Install it and restart callosum.")

    monkeypatch.setattr(ocr_router, "make_searchable_pdf", boom)
    client = _Client(_app(temp_db_url))
    done = _drive(client, paper_id)
    assert done["status"] == "error" and "not installed" in (done["detail"] or "")
