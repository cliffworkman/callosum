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
from app.backend.persistence.schema import attachments, chunks, embeddings, papers


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

    first = scan_library_folder(engine, folder)  # inc A2: owns its own per-file transactions
    assert len(first["added"]) == 2 and not first["unchanged"] and not first["removed"]
    # every added paper has a linked attachment with a checksum
    with engine.connect() as conn:
        rows = list(
            conn.execute(select(attachments.c.storage_mode, attachments.c.checksum, attachments.c.import_source))
        )
    assert all(r[0] == "linked" and r[1] and r[2] == "library-scan" for r in rows)

    again = scan_library_folder(engine, folder)  # re-scan → all unchanged (content dedup by checksum)
    assert len(again["unchanged"]) == 2 and not again["added"]

    (folder / "b.pdf").unlink()  # remove one on disk → flagged missing (non-destructive)
    third = scan_library_folder(engine, folder)
    with engine.connect() as conn:
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

    scanned = scan_library_folder(engine, scan_dir)
    with engine.connect() as conn:
        paper_count = conn.execute(select(func.count()).select_from(papers)).scalar_one()

    assert not scanned["added"]
    assert len(scanned["unchanged"]) == 1
    unchanged = scanned["unchanged"][0]
    assert unchanged["matched_by"] == "checksum"
    assert unchanged["paper_id"] == paper_id
    assert unchanged["attachment_id"] == attachment_id
    assert unchanged["import_source"] == "zotero"
    assert paper_count == 1


def test_scan_reconnects_exact_moved_pdf_without_reprocessing(temp_db_url, tmp_path):
    original_dir = tmp_path / "original"
    recovered_dir = tmp_path / "recovered"
    original_dir.mkdir()
    recovered_dir.mkdir()
    original = _make_pdf(original_dir / "paper.pdf", "The attachment and its chunks must survive relocation.")
    engine = make_engine(temp_db_url)

    first = scan_library_folder(engine, original_dir)
    assert len(first["added"]) == 1
    paper_id = first["added"][0]["paper_id"]
    with engine.connect() as conn:
        before = conn.execute(
            select(attachments.c.id, attachments.c.checksum).where(attachments.c.paper_id == paper_id)
        ).one()
        chunk_ids_before = list(conn.execute(select(chunks.c.id).where(chunks.c.attachment_id == before.id)).scalars())

    recovered = recovered_dir / "renamed.pdf"
    original.replace(recovered)
    second = scan_library_folder(engine, recovered_dir)

    assert not second["added"] and not second["removed"] and not second["unchanged"]
    assert len(second["relinked"]) == 1
    assert second["relinked"][0]["paper_id"] == paper_id
    assert second["relinked"][0]["attachment_id"] == before.id
    with engine.connect() as conn:
        after = conn.execute(select(attachments).where(attachments.c.id == before.id)).mappings().one()
        chunk_ids_after = list(conn.execute(select(chunks.c.id).where(chunks.c.attachment_id == before.id)).scalars())
        assert conn.execute(select(func.count()).select_from(papers)).scalar_one() == 1
    assert after["availability"] == "available"
    assert after["storage_mode"] == "linked"
    assert after["resolved_path"] == str(recovered.resolve())
    assert after["checksum"] == before.checksum
    assert chunk_ids_after == chunk_ids_before and chunk_ids_after


def test_scan_endpoint_reports_reconnected_pdf_and_serves_it(temp_db_url, tmp_path):
    original_dir = tmp_path / "old"
    recovered_dir = tmp_path / "new"
    original_dir.mkdir()
    recovered_dir.mkdir()
    original = _make_pdf(original_dir / "paper.pdf", "An API-level reconnection regression fixture.")
    engine = make_engine(temp_db_url)
    first = scan_library_folder(engine, original_dir)
    paper_id = first["added"][0]["paper_id"]
    recovered = recovered_dir / "paper.pdf"
    original.replace(recovered)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel(), crossref_client=_NoCrossref()))

    started = client.post("/library/scan", json={"folder": str(recovered_dir)})
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/library/scan/{job_id}").json()
        if result["status"] in ("done", "error"):
            break

    assert result["status"] == "done", result
    assert result["summary"]["relinked"] == 1
    assert result["summary"]["added"] == 0
    assert client.get(f"/papers/{paper_id}/pdf").content == recovered.read_bytes()


def test_scanning_one_watched_folder_does_not_mark_another_folder_missing(temp_db_url, tmp_path):
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    _make_pdf(folder_a / "a.pdf", "Alpha lives in watched folder A.")
    _make_pdf(folder_b / "b.pdf", "Beta lives in watched folder B.")
    engine = make_engine(temp_db_url)

    scan_library_folder(engine, folder_a)
    scan_library_folder(engine, folder_b)
    rescanned = scan_library_folder(engine, folder_a)

    assert not rescanned["removed"]
    with engine.connect() as conn:
        availability = list(conn.execute(select(attachments.c.availability)).scalars())
    assert availability == ["available", "available"]


def test_scan_progress_reports_the_per_file_basename(temp_db_url, tmp_path):
    # inc 214 (#4): on_progress now receives (current, total, filename) so the UI can show "Reading <file>".
    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "alpha.pdf", "Alpha one.")
    _make_pdf(folder / "beta.pdf", "Beta two.")
    calls: list[tuple[int, int, str]] = []
    scan_library_folder(make_engine(temp_db_url), folder, on_progress=lambda c, t, name: calls.append((c, t, name)))
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


def test_scan_commits_per_paper_partial_progress(temp_db_url, tmp_path, monkeypatch):
    """Per-paper commits: a failure embedding the 2nd paper leaves the 1st fully embedded, and the job still
    completes (skip-on-error) — NOT a whole-job rollback. Under the old single-transaction job, either both
    papers embed or the whole run rolls back; only per-paper commits give exactly one embedded + status done."""
    from app.backend.api.routers import library as lib_mod

    real_embed_papers = lib_mod.embed_papers
    calls = {"n": 0}

    def flaky_embed_papers(conn, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # per-paper, embed_papers is called once per paper → fail on the 2nd paper
            raise RuntimeError("boom embedding the 2nd paper")
        return real_embed_papers(conn, **kwargs)

    monkeypatch.setattr(lib_mod, "embed_papers", flaky_embed_papers)

    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "a.pdf", "Alpha analytical engine study one.")
    _make_pdf(folder / "b.pdf", "Beta computation memoir two.")
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel(), crossref_client=_NoCrossref()))
    started = client.post("/library/scan", json={"folder": str(folder)})
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(60):
        result = client.get(f"/library/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            break
    assert result["status"] == "done"  # per-paper skip → the run completes, not a whole-job error

    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(papers)).scalar() == 2  # both rows inserted (phase 1)
        paper_embs = conn.execute(
            select(func.count()).select_from(embeddings).where(embeddings.c.target_type == "paper")
        ).scalar()
    engine.dispose()
    assert paper_embs == 1  # only paper #1 committed its embedding; paper #2's whole item rolled back


def test_scan_commits_each_file_itself(temp_db_url, tmp_path):
    """A2: scan_library_folder owns its transactions (per-file commits) — a fresh connection sees the added papers
    with NO caller transaction, proving each file committed itself (was: one savepoint-per-file txn the caller
    committed at the end, which held the write lock for the whole extraction phase)."""
    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "a.pdf", "Alpha analytical engine study one.")
    _make_pdf(folder / "b.pdf", "Beta computation memoir two.")
    engine = make_engine(temp_db_url)
    scanned = scan_library_folder(engine, folder)  # no caller transaction
    assert len(scanned["added"]) == 2
    with engine.connect() as conn:  # a fresh connection sees them → each file was committed by the function
        assert conn.execute(select(func.count()).select_from(papers)).scalar() == 2
    engine.dispose()
