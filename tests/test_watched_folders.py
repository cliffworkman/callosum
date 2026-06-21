"""Tests for watched library folders (inc 98) — hermetic (fitz-built fixture PDFs; injected fake model + no-op
Crossref). Scanning registers a watched folder; rescan reconciles; un-watching keeps the papers."""

from __future__ import annotations

from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.watched_repo import (
    add_watched_folder,
    list_watched_folders,
    remove_watched_folder,
    touch_last_scanned,
)


def _make_pdf(path: Path, text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 60), text, fontsize=12)
    doc.save(path)
    doc.close()
    return path


class _FakeModel:
    name = "fake-watch"
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


def _poll(client, url):
    result = {}
    for _ in range(30):
        result = client.get(url).json()
        if result["status"] in ("done", "error"):
            break
    return result


def test_watched_repo_add_idempotent_list_touch_remove(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        first = add_watched_folder(conn, "/a/b")
        again = add_watched_folder(conn, "/a/b")  # idempotent on the UNIQUE path
        assert first == again
        add_watched_folder(conn, "/c/d")
        assert {r["path"] for r in list_watched_folders(conn)} == {"/a/b", "/c/d"}
        touch_last_scanned(conn, "/a/b")
        rows = {r["path"]: r for r in list_watched_folders(conn)}
        assert rows["/a/b"]["last_scanned_at"] is not None and rows["/c/d"]["last_scanned_at"] is None
        assert remove_watched_folder(conn, int(first)) is True
        assert {r["path"] for r in list_watched_folders(conn)} == {"/c/d"}


def test_scan_registers_watched_then_rescan_picks_up_new(temp_db_url, tmp_path):
    folder = tmp_path / "lib"
    folder.mkdir()
    _make_pdf(folder / "a.pdf", "Alpha analytical engine study one.")
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel(), crossref_client=_NoCrossref()))

    started = client.post("/library/scan", json={"folder": str(folder)})
    assert _poll(client, f"/library/scan/{started.json()['job_id']}")["status"] == "done"
    watched = client.get("/library/watched").json()
    assert len(watched) == 1 and watched[0]["last_scanned_at"]  # scanning registered + stamped the folder
    folder_id = watched[0]["id"]
    assert len(client.get("/papers").json()) == 1

    _make_pdf(folder / "b.pdf", "Beta computation memoir two.")  # a new file drops into the watched folder
    rescan = client.post("/library/watched/rescan")
    assert rescan.status_code == 202
    done = _poll(client, f"/library/watched/rescan/{rescan.json()['job_id']}")
    assert done["status"] == "done" and done["summary"]["added"] == 1  # the new PDF is picked up
    assert len(client.get("/papers").json()) == 2

    again = _poll(client, f"/library/watched/rescan/{client.post('/library/watched/rescan').json()['job_id']}")
    assert again["summary"]["added"] == 0 and again["summary"]["unchanged"] == 2  # idempotent (content-dedup)

    # un-watching drops the watch but keeps the papers
    assert client.delete(f"/library/watched/{folder_id}").status_code == 204
    assert client.get("/library/watched").json() == []
    assert len(client.get("/papers").json()) == 2
    assert client.get("/library/watched/rescan/nope").status_code == 404
