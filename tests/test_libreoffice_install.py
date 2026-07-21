"""LibreOffice plugin install/download endpoints (inc 162).

The OS file-opener is monkeypatched so no real process/GUI launches in tests; the real Extension-Manager open is
the user's manual check. The full extension (install + dispatcher) is verified through real LibreOffice by
`adapters/libreoffice/run_roundtrip.py` (also runs in CI — see `.github/workflows/libreoffice-adapter.yml`).
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.api.routers import libreoffice as lo


def test_download_plugin_returns_oxt_zip(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.get("/integrations/libreoffice/plugin.oxt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.sun.star.package-bundle")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names = set(z.namelist())
    assert {"Addons.xcu", "callosum_addon.py", "callosum_cite.py", "META-INF/manifest.xml"} <= names


def test_install_opens_the_os_handler(temp_db_url: str, monkeypatch) -> None:
    opened: dict[str, str] = {}
    monkeypatch.setattr(lo, "_open_with_os", lambda path: opened.setdefault("path", path))
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/integrations/libreoffice/install", json={})
    assert r.status_code == 200 and r.json()["opened"] is True
    assert opened["path"].endswith("callosum.oxt")


def test_install_degrades_when_no_handler(temp_db_url: str, monkeypatch) -> None:
    def boom(path):
        raise OSError("no handler")

    monkeypatch.setattr(lo, "_open_with_os", boom)
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/integrations/libreoffice/install", json={})
    assert r.status_code == 200  # never 500
    assert r.json()["opened"] is False and "Download" in r.json()["detail"]


def test_install_rejects_wrong_method(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/integrations/libreoffice/install").status_code == 405
