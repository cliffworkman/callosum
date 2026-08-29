"""Word add-in task-pane + manifest routes (inc 164, SP1).

Architecture A: callosum serves the task pane over HTTPS, same-origin with the API (zero egress, desktop Word only).
These tests cover the file/manifest serving + the install convenience; the in-Word round-trip is the user's manual
verification (no headless Word). The pure task-pane logic is unit-tested separately by `node --test adapters/word/`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.api.routers import word as word_router
from tests.api_helpers import _annotation_body, _seed_library

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(temp_db_url: str) -> TestClient:
    return TestClient(create_app(db_url=temp_db_url))


@pytest.mark.parametrize(
    ("name", "ctype"),
    [
        ("taskpane.html", "text/html"),
        ("taskpane.js", "javascript"),
        ("taskpane_core.js", "javascript"),
        ("taskpane.css", "text/css"),
        ("icon.png", "image/png"),
    ],
)
def test_taskpane_files_are_served_with_the_right_type(client: TestClient, name: str, ctype: str) -> None:
    r = client.get(f"/integrations/word/{name}")
    assert r.status_code == 200
    assert ctype in r.headers["content-type"]
    assert r.content  # non-empty


def test_manifest_is_served_and_points_at_the_https_taskpane(client: TestClient) -> None:
    r = client.get("/integrations/word/manifest.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    body = r.text
    assert "https://localhost:8443/integrations/word/taskpane.html" in body
    assert "b7e8c1d2-4f3a-4b5c-9d6e-0a1b2c3d4e5f" in body  # the fixed app GUID
    assert "ReadWriteDocument" in body


def test_manifest_web_is_served_and_points_at_the_tunnel_taskpane(client: TestClient) -> None:
    r = client.get("/integrations/word/manifest-web.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    body = r.text
    assert "https://callosum-tunnel.clffwrkmn.net/integrations/word/taskpane.html" in body
    assert "e0dbec68-063a-49cc-a6c9-07f99850d9f1" in body  # a DIFFERENT GUID from the desktop manifest
    assert "e0dbec68" not in body.replace("e0dbec68-063a-49cc-a6c9-07f99850d9f1", "")  # sanity: exactly one Id
    assert "b7e8c1d2-4f3a-4b5c-9d6e-0a1b2c3d4e5f" not in body  # never the desktop manifest's identity
    # the explanatory XML comment may mention localhost:8443 for contrast; no FUNCTIONAL element may reference it
    assert 'DefaultValue="https://localhost:8443' not in body
    assert "<AppDomain>https://localhost:8443</AppDomain>" not in body


def test_unknown_file_is_404_not_a_traversal(client: TestClient) -> None:
    # No dynamic {filename} route exists (each file has its own route), so an undefined path is a plain 404 —
    # there is structurally no traversal surface.
    assert client.get("/integrations/word/secrets.txt").status_code == 404
    assert client.get("/integrations/word/../app.py").status_code == 404


def test_install_opens_the_addin_folder(client: TestClient, monkeypatch) -> None:
    opened: dict[str, str] = {}
    monkeypatch.setattr(word_router, "_open_with_os", lambda path: opened.setdefault("path", path))
    r = client.post("/integrations/word/install", json={})
    assert r.status_code == 200 and r.json()["opened"] is True
    assert opened["path"].replace("\\", "/").endswith("adapters/word")


def test_install_degrades_when_no_handler(client: TestClient, monkeypatch) -> None:
    def boom(path: str) -> None:
        raise OSError("no handler")

    monkeypatch.setattr(word_router, "_open_with_os", boom)
    r = client.post("/integrations/word/install", json={})
    assert r.status_code == 200  # never 500
    assert r.json()["opened"] is False


def test_no_egress_from_the_taskpane_assets(client: TestClient) -> None:
    # The task pane fetches the local API same-origin; the ONLY external reference is Microsoft's office.js SDK
    # (required by Office). Assert no library/AI host leaks into the served assets.
    html = client.get("/integrations/word/taskpane.html").text
    js = client.get("/integrations/word/taskpane.js").text
    assert "appsforoffice.microsoft.com" in html  # the Office platform SDK (expected)
    for forbidden in ("generativelanguage", "openai.com", "anthropic.com", "clffwrkmn.net"):
        assert forbidden not in html and forbidden not in js


def test_word_evidence_projection_is_read_only_and_privacy_minimized(temp_db_url: str) -> None:
    paper_id = _seed_library(temp_db_url)["facial_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    created = client.post(
        f"/papers/{paper_id}/annotations",
        json=_annotation_body(note="Author's saved interpretation"),
    )
    assert created.status_code == 201

    response = client.get(f"/integrations/word/evidence/{paper_id}")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": created.json()["id"],
            "page": 2,
            "anchor_text": "Compared with typical faces",
            "note": "Author's saved interpretation",
        }
    ]
    assert client.post(f"/integrations/word/evidence/{paper_id}", json={}).status_code == 405
    assert client.get("/integrations/word/evidence/999999").status_code == 404


def test_word_evidence_projection_fails_instead_of_silently_truncating(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(word_router, "get_paper", lambda _conn, _paper_id: {})
    row = {"id": 1, "page": 1, "anchor_text": "quote", "note": None}
    monkeypatch.setattr(
        word_router,
        "list_annotations_for_paper",
        lambda _conn, _paper_id: [row] * (word_router.WORD_EVIDENCE_MAX + 1),
    )
    with pytest.raises(HTTPException, match="saved highlights"):
        word_router.word_evidence(1, object())

    oversize = dict(row, anchor_text="x" * (word_router.WORD_EVIDENCE_QUOTE_MAX + 1))
    monkeypatch.setattr(word_router, "list_annotations_for_paper", lambda _conn, _paper_id: [oversize])
    with pytest.raises(HTTPException, match="display limits"):
        word_router.word_evidence(1, object())

    core = (PROJECT_ROOT / "adapters" / "word" / "taskpane_core.js").read_text(encoding="utf-8")
    assert f"var EVIDENCE_QUOTE_MAX = {word_router.WORD_EVIDENCE_QUOTE_MAX};" in core
    assert f"var EVIDENCE_NOTE_MAX = {word_router.WORD_EVIDENCE_NOTE_MAX};" in core


def test_word_adapter_paths_are_narrowly_allowed_through_shared_tunnel() -> None:
    config = (PROJECT_ROOT / "adapters" / "googledocs" / "cloudflared-config.yml").read_text(encoding="utf-8")
    ingress = next(line.strip() for line in config.splitlines() if line.strip().startswith("path: ^/(papers|"))
    pattern = ingress.removeprefix("path: ")
    for allowed in (
        "/papers",
        "/papers/export",
        "/integrations/word/evidence/42",
        "/citations/render-document",
        "/citations/suggest",
        "/citations/classify-stance",
        "/citations/zotero/resolve",
        "/citations/styles",
        "/statements/pending",
    ):
        assert re.fullmatch(pattern, allowed), allowed
    for blocked in (
        "/papers/42",
        "/papers/42/annotations",
        "/integrations/word/evidence/not-an-id",
        "/citations/classify-stance/other",
        "/citations/zotero/resolve/other",
        "/statements",
        "/statements/other",
    ):
        assert not re.fullmatch(pattern, blocked), blocked
    assert "statements/pending" in ingress
    assert "statements/" in ingress
    assert "statements/*" not in ingress
    assert "statements)$" not in ingress
