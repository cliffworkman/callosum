"""Library-side analytic-flexibility orchestration + endpoint (backlog #37, plan Task 4)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.backend.analytic_flexibility import propose_analytic_flexibility
from app.backend.api import create_app
from app.backend.persistence.repository import create_attachment, create_paper
from app.backend.persistence.schema import chunks
from app.backend.persistence.schema_findings import paper_findings
from integrations.gemini.generator import GeminiConfig


def _seed_paper_with_methods_chunk(conn) -> tuple[int, int]:
    pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
    aid = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum="x",
        import_source="test",
        attachment_type="pdf",
        role="article-fulltext",
    )
    conn.execute(
        chunks.insert().values(
            paper_id=pid,
            attachment_id=aid,
            text="Participants under 18 were excluded.",
            section="methods",
            page_start=3,
            page_end=3,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="deadbeef",
        )
    )
    return pid, aid


def test_propose_analytic_flexibility_writes_findings_from_llm_candidates(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, _aid = _seed_paper_with_methods_chunk(conn)
        config = GeminiConfig(
            provider="gemini", model="gemini-2.5-flash-lite", api_key="fake", data_egress_enabled=True
        )
        with (
            patch(
                "app.backend.analytic_flexibility.AnalyticFlexibilityAssistant.propose",
                return_value=[{"category": "exclusion-criteria", "quote": "Participants under 18 were excluded."}],
            ),
            patch(
                "app.backend.analytic_flexibility.primary_pdf_path",
                return_value=None,  # no on-disk PDF -> anchor_quote never runs -> unanchored
            ),
        ):
            result = propose_analytic_flexibility(conn, pid, config)
        rows = (
            conn.execute(
                select(paper_findings).where(
                    paper_findings.c.paper_id == pid, paper_findings.c.source == "analytic-flexibility"
                )
            )
            .mappings()
            .all()
        )
    eng.dispose()
    assert result == {"candidates_found": 1, "methods_text_found": True}
    assert len(rows) == 1
    assert rows[0]["kind"] == "candidate"
    assert rows[0]["tier"] == "speculative"
    assert rows[0]["payload"]["category"] == "exclusion-criteria"
    # No PDF path -> honestly unanchored, never fabricated (coordinate-honesty invariant #2).
    assert rows[0]["payload"]["anchor_state"] == "unanchored"


def test_propose_analytic_flexibility_reports_no_methods_text_honestly(temp_db_url: str) -> None:
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid = create_paper(conn, title="T", csl_json={"title": "T", "type": "article-journal"})
        config = GeminiConfig(
            provider="gemini", model="gemini-2.5-flash-lite", api_key="fake", data_egress_enabled=True
        )
        # Deliberately NOT mocking AnalyticFlexibilityAssistant.propose: a paper with no methods-section text
        # must never reach the LLM at all -- if it did, this would attempt a real (and failing) network call.
        result = propose_analytic_flexibility(conn, pid, config)
    eng.dispose()
    assert result == {"candidates_found": 0, "methods_text_found": False}


def test_endpoint_refused_when_egress_not_consented(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # The suite's autouse fixture (tests/conftest.py) grants egress consent by default; withdraw it explicitly
    # to assert the OFF behavior (mirrors tests/test_grobid_endpoints.py's identical setup).
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    c = TestClient(create_app(db_url=temp_db_url))
    # Paper 1 doesn't exist in this fresh DB either -- the egress refusal must still win over a 404.
    r = c.post("/papers/1/analytic-flexibility")
    assert r.status_code == 403
