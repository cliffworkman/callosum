"""Superuser-only diagnostics (inc 468) — hermetic. Reuses test_auth_oidc.py's exact
_configured/_sign_in/FakeOidcClient pattern for driving a real superuser sign-in."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from tests.test_auth_oidc import FakeOidcClient, _configured, _sign_in


def test_diagnostics_403s_when_signed_out(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/diagnostics").status_code == 403


def test_diagnostics_403s_for_non_superuser(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _configured(monkeypatch)
    monkeypatch.setenv("CALLOSUM_SUPERUSER_ORCIDS", "0000-0009-9999-9999")  # someone else
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=FakeOidcClient()))
    _sign_in(client)
    assert client.get("/settings").json()["account"]["is_superuser"] is False
    assert client.get("/diagnostics").status_code == 403


def test_diagnostics_returns_stats_for_superuser(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _configured(monkeypatch)
    monkeypatch.setenv("CALLOSUM_SUPERUSER_ORCIDS", "0000-0002-1825-0097")  # the fake's verified ORCID
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=FakeOidcClient()))
    _sign_in(client)
    assert client.get("/settings").json()["account"]["is_superuser"] is True

    r = client.get("/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert body["paper_count"] == 0 and body["chunk_count"] == 0 and body["embedding_count"] == 0
    assert body["remote_access_enabled"] is False  # default off
    assert body["sync_enabled"] is False  # default off
    assert body["sync_server_configured"] is False
    assert body["db_reachable"] is True and body["db_migrated"] is True
    assert body["app_version"] is None or isinstance(body["app_version"], str)


def test_diagnostics_counts_reflect_real_library_state(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend.persistence.database import make_engine
    from app.backend.persistence.repository import create_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="A Paper", csl_json={"title": "A Paper"})
    engine.dispose()

    _configured(monkeypatch)
    monkeypatch.setenv("CALLOSUM_SUPERUSER_ORCIDS", "0000-0002-1825-0097")
    client = TestClient(create_app(db_url=temp_db_url, oidc_client=FakeOidcClient()))
    _sign_in(client)
    body = client.get("/diagnostics").json()
    assert body["paper_count"] == 1
