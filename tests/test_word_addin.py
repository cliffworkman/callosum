"""Word add-in task-pane + manifest routes (inc 164, SP1).

Architecture A: callosum serves the task pane over HTTPS, same-origin with the API (zero egress, desktop Word only).
These tests cover the file/manifest serving + the install convenience; the in-Word round-trip is the user's manual
verification (no headless Word). The pure task-pane logic is unit-tested separately by `node --test adapters/word/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.api.routers import word as word_router

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


def test_word_statement_handoff_is_narrowly_allowed_through_shared_tunnel() -> None:
    config = (PROJECT_ROOT / "adapters" / "googledocs" / "cloudflared-config.yml").read_text(encoding="utf-8")
    ingress = next(line.strip() for line in config.splitlines() if line.strip().startswith("path: ^/(papers|"))
    assert "statements/pending" in ingress
    assert "statements/" in ingress
    assert "statements/*" not in ingress
    assert "statements)$" not in ingress
