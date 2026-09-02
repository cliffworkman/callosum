"""Library-side analytic-flexibility orchestration + endpoint (backlog #37, plan Task 4)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.backend.analytic_flexibility import propose_analytic_flexibility
from app.backend.api import create_app
from app.backend.llm.providers import ProviderError
from app.backend.persistence.findings_repo import get_paper_findings
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


def test_propose_analytic_flexibility_bounds_methods_text_tighter_for_managed_local(temp_db_url: str) -> None:
    """Real measured worst-case combined input (this cap + the sibling WIP cap) was 20,703 chars -- already
    at/past the 20,000-char default, and well past the managed Local AI preview's ~10,240-token budget."""
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
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
        for i in range(15):  # 15 x 1,000-char methods chunks -- fits under the 20,000 cloud cap, not under 8,000
            conn.execute(
                chunks.insert().values(
                    paper_id=pid,
                    attachment_id=aid,
                    text="x" * 1000,
                    section="methods",
                    page_start=i + 1,
                    page_end=i + 1,
                    bbox_coordinate_system="pdf-points-top-left",
                    extraction_tool="test",
                    extraction_version="1",
                    chunking_strategy="test",
                    chunk_version="1",
                    source_attachment_checksum="deadbeef",
                )
            )
        config = GeminiConfig(provider="managed_local", model="callosum-managed-local", data_egress_enabled=False)
        received = {}

        def _capture_propose(self, *, text):
            received["len"] = len(text)
            return []

        with (
            patch("app.backend.analytic_flexibility.AnalyticFlexibilityAssistant.propose", _capture_propose),
            patch("app.backend.analytic_flexibility.primary_pdf_path", return_value=None),
        ):
            propose_analytic_flexibility(conn, pid, config)
    eng.dispose()
    assert received["len"] <= 8000


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


def test_empty_proposals_do_not_supersede_a_prior_finding(temp_db_url: str) -> None:
    """Final-review Finding 2: upsert_findings' replace-set semantics DELETE every existing finding whose
    content_key isn't in the new set. parse_proposals never raises on malformed/garbage model output -- it
    returns [] instead -- so an empty/malformed LLM response must NOT be allowed to wipe prior candidates
    (including ones a user already reviewed). Seed one real finding, then re-run with a mocked EMPTY proposal
    list, and confirm the original finding row survives untouched."""
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
            patch("app.backend.analytic_flexibility.primary_pdf_path", return_value=None),
        ):
            first = propose_analytic_flexibility(conn, pid, config)
        assert first == {"candidates_found": 1, "methods_text_found": True}
        before = get_paper_findings(conn, pid, source="analytic-flexibility")
        assert len(before["candidates"]) == 1
        original_id = before["candidates"][0]["id"]

        # Simulate a malformed/truncated LLM response: parse_proposals returns [] rather than raising.
        with patch(
            "app.backend.analytic_flexibility.AnalyticFlexibilityAssistant.propose",
            return_value=[],
        ):
            second = propose_analytic_flexibility(conn, pid, config)
        after = get_paper_findings(conn, pid, source="analytic-flexibility")
    eng.dispose()
    assert second == {"candidates_found": 0, "methods_text_found": True}
    # The prior candidate must still be present, unchanged -- not superseded into oblivion.
    assert len(after["candidates"]) == 1
    assert after["candidates"][0]["id"] == original_id
    assert after["candidates"][0]["payload"]["category"] == "exclusion-criteria"


def test_endpoint_returns_502_when_provider_fails(temp_db_url: str) -> None:
    """Final-review Finding 3: a ProviderError (bad key, 429, provider 5xx) must surface as a friendly 502,
    not an unhandled 500 -- mirrors routers/workbench.py's propose_row pattern."""
    eng = create_engine(temp_db_url)
    with eng.begin() as conn:
        pid, _aid = _seed_paper_with_methods_chunk(conn)
    eng.dispose()
    c = TestClient(create_app(db_url=temp_db_url))
    with patch(
        "app.backend.analytic_flexibility.AnalyticFlexibilityAssistant.propose",
        side_effect=ProviderError("HTTP 429: rate limited"),
    ):
        r = c.post(f"/papers/{pid}/analytic-flexibility")
    assert r.status_code == 502
    assert "AI provider failed" in r.json()["detail"]
