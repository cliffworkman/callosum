"""B5 SP1 (inc 237): the read-only mobile-reading boundaries.

Two layers make the mobile tunnel read-only: the cloudflared ingress **path allowlist** (defense in depth — only read
paths reach localhost) and the **method gate** (`CALLOSUM_READ_ONLY=1` → every mutating method is 403, the real
boundary, since a path like `/papers/5` serves both GET reads and DELETE writes and cloudflared matches path only)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app

MOBILE_CONFIG = Path(__file__).resolve().parents[1] / "adapters" / "mobile" / "cloudflared-config.yml"


def _ingress_regex() -> re.Pattern[str]:
    for line in MOBILE_CONFIG.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("path:"):
            return re.compile(s.split("path:", 1)[1].strip())
    raise AssertionError("no `path:` rule found in the mobile ingress config")


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/health",
        "/papers",
        "/papers/5",
        "/papers/5/pdf",
        "/papers/5/annotations",
        "/papers/5/chunks",
        "/summaries",
        "/summaries/7",
        "/axes",
        "/axes/3/clusters",
        "/tags",
        "/tags/colors",
        "/reading-queue",
        "/help/corpus",
    ],
)
def test_mobile_ingress_forwards_read_paths(path: str) -> None:
    assert _ingress_regex().match(path), path


@pytest.mark.parametrize(
    "path",
    [
        "/settings",
        "/library/scan",
        "/library/import",
        "/library/enrich/refresh",
        "/methods/statcheck/run",
        "/discovery/save",
        "/discovery/search",
        "/feed",
        "/gaps",
        "/agent/status",
        "/findings/overview",
        "/papers/citation-counts/refresh",
        "/papers/ocr/run",
        "/axes/3/score",
        "/axes/suggest",
        "/citations/render",
    ],
)
def test_mobile_ingress_blocks_write_and_config_paths(path: str) -> None:
    assert not _ingress_regex().match(path), path


def test_read_only_mode_blocks_mutating_methods(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALLOSUM_READ_ONLY", "1")
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers").status_code == 200  # reads pass
    assert client.post("/summarize", json={"scope_type": "query", "query": "x"}).status_code == 403  # write → 403
    assert client.delete("/papers/999").status_code == 403  # write → 403 before the handler (not a 404)
    # a POST that shares a read path (POST /papers/export path-matches the ingress) is still blocked by the method gate:
    assert client.post("/papers/export", json={"paper_ids": [1], "format": "bibtex"}).status_code == 403


def test_read_only_off_by_default_lets_writes_reach_the_handler(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CALLOSUM_READ_ONLY", raising=False)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.delete("/papers/999").status_code == 404  # reaches the handler (missing paper), not the 403 gate


def test_health_advertises_read_only(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # B5 SP2: the frontend reads read_only off /health (forwarded + token-exempt over the read-only tunnel).
    monkeypatch.setenv("CALLOSUM_READ_ONLY", "1")
    assert TestClient(create_app(db_url=temp_db_url)).get("/health").json()["read_only"] is True
    monkeypatch.delenv("CALLOSUM_READ_ONLY", raising=False)
    assert TestClient(create_app(db_url=temp_db_url)).get("/health").json()["read_only"] is False
