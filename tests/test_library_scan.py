"""Tests for the library-folder scan (inc 87) — hermetic (fitz-built fixture PDFs; injected fake model +
no-op Crossref; no real network)."""

from __future__ import annotations

from pathlib import Path

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.api import create_app
from app.backend.pdf_processing.extraction import file_sha256
from app.backend.pdf_processing.library_scan import scan_library_folder
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_paper
from app.backend.persistence.schema import attachments, papers


def _make_pdf(path: Path, text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 60), text, fontsize=12)
    doc.save(path)
    doc.close()
    return path


class _FakeModel:
    name = "fake-scan"
    version = "v1"
    dimension = 4
    normalization = "none"

    def encode_texts(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class _UnresolvedResolution:
    resolved = False
    csl_json = None
    error = None


class _NoCrossref:
    def resolve_doi(self, conn, doi):
        return _UnresolvedResolution()


def test_scan_adds_new_skips_unchanged_flags_removed(temp_db_url, tmp_path):
    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "a.pdf", "Alpha analytical engine study one.")
    _make_pdf(folder / "b.pdf", "Beta computation memoir two.")
    engine = make_engine(temp_db_url)

    with engine.begin() as conn:
        first = scan_library_folder(conn, folder)
    assert len(first["added"]) == 2 and not first["unchanged"] and not first["removed"]
    # every added paper has a linked attachment with a checksum
    with engine.begin() as conn:
        rows = list(
            conn.execute(select(attachments.c.storage_mode, attachments.c.checksum, attachments.c.import_source))
        )
    assert all(r[0] == "linked" and r[1] and r[2] == "library-scan" for r in rows)

    with engine.begin() as conn:  # re-scan → all unchanged (content dedup by checksum)
        again = scan_library_folder(conn, folder)
    assert len(again["unchanged"]) == 2 and not again["added"]

    (folder / "b.pdf").unlink()  # remove one on disk → flagged missing (non-destructive)
    with engine.begin() as conn:
        third = scan_library_folder(conn, folder)
        missing = list(conn.execute(select(attachments.c.availability).where(attachments.c.availability == "missing")))
    assert len(third["removed"]) == 1 and len(third["unchanged"]) == 1 and len(missing) == 1


def test_scan_dedups_same_content_from_different_source_path_and_provenance(temp_db_url, tmp_path):
    existing_dir = tmp_path / "existing"
    scan_dir = tmp_path / "scan"
    existing_dir.mkdir()
    scan_dir.mkdir()
    original = _make_pdf(existing_dir / "zotero-copy.pdf", "Same bytes from a previous import.")
    duplicate = scan_dir / "renamed-copy.pdf"
    duplicate.write_bytes(original.read_bytes())
    checksum = file_sha256(original)
    engine = make_engine(temp_db_url)

    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Already imported",
            csl_json={"id": "existing", "type": "document", "title": "Already imported"},
            imported_source="zotero",
        )
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(original),
            resolved_path=str(original.resolve()),
            checksum=checksum,
            file_size=original.stat().st_size,
            content_type="application/pdf",
            import_source="zotero",
            attachment_type="pdf",
            role="primary",
        )

    with engine.begin() as conn:
        scanned = scan_library_folder(conn, scan_dir)
        paper_count = conn.execute(select(func.count()).select_from(papers)).scalar_one()

    assert not scanned["added"]
    assert len(scanned["unchanged"]) == 1
    unchanged = scanned["unchanged"][0]
    assert unchanged["matched_by"] == "checksum"
    assert unchanged["paper_id"] == paper_id
    assert unchanged["attachment_id"] == attachment_id
    assert unchanged["import_source"] == "zotero"
    assert paper_count == 1


def test_scan_progress_reports_the_per_file_basename(temp_db_url, tmp_path):
    # inc 214 (#4): on_progress now receives (current, total, filename) so the UI can show "Reading <file>".
    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "alpha.pdf", "Alpha one.")
    _make_pdf(folder / "beta.pdf", "Beta two.")
    calls: list[tuple[int, int, str]] = []
    with make_engine(temp_db_url).begin() as conn:
        scan_library_folder(conn, folder, on_progress=lambda c, t, name: calls.append((c, t, name)))
    assert [c[2] for c in calls] == ["alpha.pdf", "beta.pdf"]  # sorted; basenames, not full paths
    assert all(c[1] == 2 for c in calls)  # total carried through


def test_scan_endpoint_processes_folder(temp_db_url, tmp_path):
    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "one.pdf", "Alpha analytical engine study.")
    _make_pdf(folder / "two.pdf", "Beta computation memoir.")
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel(), crossref_client=_NoCrossref()))

    started = client.post("/library/scan", json={"folder": str(folder)})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/library/scan/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    assert result["summary"]["added"] == 2
    # the new papers are in the library; unresolved (no Crossref) → the inc-80 Unsorted view
    assert len(client.get("/papers").json()) == 2
    assert len(client.get("/papers", params={"needs_review": "true"}).json()) == 2


def test_scan_surfaces_per_file_errors(temp_db_url, tmp_path):
    # inc 155: a file that can't be read is isolated AND surfaced in the done-summary (path + reason).
    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "good.pdf", "A valid analytical paper.")
    (folder / "broken.pdf").write_bytes(b"this is not a pdf at all")
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel(), crossref_client=_NoCrossref()))
    started = client.post("/library/scan", json={"folder": str(folder)})
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/library/scan/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    s = result["summary"]
    assert s["errors"] >= 1
    assert any("broken.pdf" in e["path"] for e in s["error_details"])
    assert all(e["error"] for e in s["error_details"])  # each carries a non-empty reason


def test_scan_nonexistent_folder_422(temp_db_url, tmp_path):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/library/scan", json={"folder": str(tmp_path / "nope")}).status_code == 422
