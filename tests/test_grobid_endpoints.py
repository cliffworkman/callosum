"""GROBID settings + JobStore + per-paper/bulk parse endpoints (backlog #30 Stage 2, task 9)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_paper
from app.backend.persistence.schema_grobid import paper_sections


def _await_bulk_job(client: TestClient, job_id: str) -> dict:
    for _ in range(200):
        body = client.get(f"/grobid/library/parse/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError("bulk parse job never finished")


def _paper_with_local_pdf(conn, tmp_path, *, title: str) -> int:
    """A paper with a real, locally-resolvable PDF attachment -- survives the bulk job's
    _papers_with_local_pdf filter, unlike a bare create_paper() call (metadata-only)."""
    pdf_path = tmp_path / f"{title}.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    pid = create_paper(conn, title=title, csl_json={"title": title})
    create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        resolved_path=str(pdf_path),
        role="primary",
    )
    return pid


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


def test_bulk_parse_scoped_to_paper_ids_only_touches_those_papers(temp_db_url: str, tmp_path) -> None:
    # backlog #58: a real regression this session found -- a stale, un-restarted uvicorn process silently
    # ignored this scoping request field entirely and re-parsed the WHOLE 214-paper library instead of the one
    # selected paper. This proves the actual filtering logic in isolation (no live server/restart involved).
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        scoped_pid = _paper_with_local_pdf(conn, tmp_path, title="Scoped")
        _paper_with_local_pdf(conn, tmp_path, title="Not scoped")
    c = TestClient(create_app(db_url=temp_db_url))
    c.post("/grobid/settings", json={"url": "http://127.0.0.1:8070"})
    with patch(
        "app.backend.api.routers.grobid.parse_paper_structure",
        return_value={"sections_found": 1, "chunks_mapped": 1},
    ):
        r = c.post("/grobid/library/parse", json={"paper_ids": [scoped_pid]})
        assert r.status_code == 202
        result = _await_bulk_job(c, r.json()["job_id"])
    assert result["status"] == "done"
    assert result["summary"]["papers"] == 1
    assert result["summary"]["papers_parsed"] == 1


def test_bulk_parse_only_unparsed_excludes_papers_with_existing_sections(temp_db_url: str, tmp_path) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        already_parsed_pid = _paper_with_local_pdf(conn, tmp_path, title="Already parsed")
        conn.execute(
            paper_sections.insert().values(
                paper_id=already_parsed_pid,
                title="Discussion",
                section_kind="discussion",
                page_start=1,
                page_end=1,
                order_index=0,
            )
        )
        _paper_with_local_pdf(conn, tmp_path, title="Never parsed")
    c = TestClient(create_app(db_url=temp_db_url))
    c.post("/grobid/settings", json={"url": "http://127.0.0.1:8070"})
    with patch(
        "app.backend.api.routers.grobid.parse_paper_structure",
        return_value={"sections_found": 1, "chunks_mapped": 1},
    ):
        r = c.post("/grobid/library/parse", json={"only_unparsed": True})
        assert r.status_code == 202
        result = _await_bulk_job(c, r.json()["job_id"])
    assert result["status"] == "done"
    assert result["summary"]["papers"] == 1  # the already-parsed paper is excluded


def test_bulk_parse_excludes_metadata_only_papers_from_the_candidate_count(temp_db_url: str, tmp_path) -> None:
    # A metadata-only paper (no local PDF) can never be parsed by GROBID -- it must not be counted as
    # "considered" at all, not merely silently no-op'd and lumped into papers_skipped.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper_with_local_pdf(conn, tmp_path, title="Has a PDF")
        create_paper(conn, title="Metadata only", csl_json={"title": "Metadata only"})  # no attachment at all
    c = TestClient(create_app(db_url=temp_db_url))
    c.post("/grobid/settings", json={"url": "http://127.0.0.1:8070"})
    with patch(
        "app.backend.api.routers.grobid.parse_paper_structure",
        return_value={"sections_found": 1, "chunks_mapped": 1},
    ):
        r = c.post("/grobid/library/parse", json={})
        assert r.status_code == 202
        result = _await_bulk_job(c, r.json()["job_id"])
    assert result["status"] == "done"
    assert result["summary"]["papers"] == 1
    assert result["summary"]["papers_parsed"] == 1
    assert result["summary"]["papers_skipped"] == 0


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
