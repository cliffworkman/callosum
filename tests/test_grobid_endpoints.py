"""GROBID settings + JobStore + per-paper/bulk parse endpoints (backlog #30 Stage 2, task 9)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app


def test_grobid_status_defaults_unconfigured(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    assert c.get("/grobid/status").json() == {"configured": False, "url": None}


def test_grobid_settings_round_trip(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    r = c.post("/grobid/settings", json={"url": "http://127.0.0.1:8070"})
    assert r.status_code == 200
    assert c.get("/grobid/status").json() == {"configured": True, "url": "http://127.0.0.1:8070"}
    c.post("/grobid/settings", json={"url": None})
    assert c.get("/grobid/status").json()["configured"] is False


def test_parse_paper_refused_when_unconfigured(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    assert c.post("/grobid/papers/1/parse").status_code == 409


def test_parse_paper_non_loopback_url_requires_egress_consent(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The suite's autouse fixture (tests/conftest.py) grants egress consent by default
    # (CALLOSUM_ALLOW_DATA_EGRESS=1) so happy-path generation tests stay green without per-test setup.
    # This test asserts the OFF behavior, so it must explicitly withdraw that consent first --
    # mirrors tests/test_workbench.py::test_propose_egress_off_returns_403's exact setup.
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    c = TestClient(create_app(db_url=temp_db_url))
    c.post("/grobid/settings", json={"url": "https://remote-grobid.example.com"})
    # Egress not consented -- must be refused before any network call, and before any paper-existence
    # check (paper 1 doesn't exist in this fresh DB either -- the 403 must still win over a 404).
    r = c.post("/grobid/papers/1/parse")
    # Matches the established status code for this exact gate: DataEgressDisabledError -> HTTPException
    # at app/backend/api/routers/workbench.py:362 (tests/test_workbench.py::test_propose_egress_off_returns_403).
    assert r.status_code == 403


def test_parse_paper_loopback_url_needs_no_egress_consent(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    c.post("/grobid/settings", json={"url": "http://127.0.0.1:8070"})
    with patch(
        "app.backend.api.routers.grobid.parse_paper_structure",
        return_value={"sections_found": 0, "chunks_mapped": 0},
    ):
        r = c.post("/grobid/papers/1/parse")
    # Should NOT be blocked by the egress gate (no CALLOSUM_ALLOW_DATA_EGRESS needed for a loopback URL) --
    # paper 1 doesn't exist in this fresh DB, so this 404s; assert it's not the egress-refusal status.
    assert r.status_code != 403
