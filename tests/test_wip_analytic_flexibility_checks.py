"""WIP-side analytic-flexibility check endpoint + persistence (backlog #37, plan Task 6)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.llm.providers import ProviderError


def _poll(client: TestClient, job_id: str) -> None:
    for _ in range(30):
        result = client.get(f"/wip/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            assert result["status"] == "done"
            return
    raise AssertionError("scan did not finish")


def _setup(client: TestClient, folder: Path) -> tuple[int, int, int]:
    root = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    scan = client.post(f"/wip/watch-roots/{root['id']}/scan").json()
    _poll(client, scan["job_id"])
    manuscript_id = client.get("/wip/manuscripts").json()[0]["id"]
    file_id = client.get(f"/wip/manuscripts/{manuscript_id}/files").json()[0]["id"]
    assert (
        client.patch(
            f"/wip/manuscripts/{manuscript_id}/files/{file_id}",
            json={"is_primary": True},
        ).status_code
        == 200
    )
    return root["id"], manuscript_id, file_id


def test_analytic_flexibility_check_endpoint_appears_in_checks_list(temp_db_url: str) -> None:
    c = TestClient(create_app(db_url=temp_db_url))
    # A fresh DB has no manuscript with id 1 -- 404 is acceptable here, this test only cares about the
    # tools roster once a manuscript does exist (proven by the next test).
    r = c.get("/wip/manuscripts/1/checks")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert any(tool["id"] == "analytic-flexibility" for tool in r.json()["tools"])


def test_analytic_flexibility_run_maps_unanchored_to_null_coordinate_precision(
    temp_db_url: str, tmp_path: Path
) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(
        "Methods: Participants who failed the attention check were excluded from the primary analysis.",
        encoding="utf-8",
    )
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    empty = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()
    assert any(tool["id"] == "analytic-flexibility" and tool["kind"] == "provider-ai" for tool in empty["tools"])

    with patch(
        "app.backend.api.routers.wip_checks.AnalyticFlexibilityAssistant.propose",
        return_value=[
            {
                "category": "exclusion-criteria",
                "quote": "Participants who failed the attention check were excluded from the primary analysis.",
            }
        ],
    ):
        response = client.post(f"/wip/manuscripts/{manuscript_id}/checks/analytic-flexibility", json={})

    assert response.status_code == 200
    run = response.json()
    assert run["tool_id"] == "analytic-flexibility"
    assert run["tool_version"] == "1"
    assert run["structured_result_json"]["methods_text_found"] is True
    assert run["structured_result_json"]["candidate_count"] == 1
    assert len(run["findings"]) == 1
    finding = run["findings"][0]
    assert finding["kind"] == "candidate"
    assert finding["finding_type"] == "analytic-flexibility-exclusion-criteria"
    assert finding["quote"] == "Participants who failed the attention check were excluded from the primary analysis."
    # The draft is a non-PDF file, so no on-disk PDF exists to search -> anchor_quote never runs -> honestly
    # "unanchored" rather than a fabricated location (coordinate-honesty invariant #2).
    assert finding["details_json"]["anchor_state"] == "unanchored"
    # The wip_findings.coordinate_precision CHECK constraint permits only NULL/'exact'/'region' -- "unanchored"
    # has no matching literal, so it must map to NULL here, while the fuller anchor_state value stays
    # inspectable inside details_json (asserted above) rather than silently dropped.
    assert finding["coordinate_precision"] is None
    assert finding["disposition"] == "open"


def test_analytic_flexibility_run_refuses_before_any_network_call_when_egress_off(
    temp_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The suite's autouse fixture (tests/conftest.py) grants egress consent by default; withdraw it explicitly
    # to assert the OFF behavior (mirrors tests/test_analytic_flexibility.py's identical Library-side setup).
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    client = TestClient(create_app(db_url=temp_db_url))
    # Manuscript 1 doesn't exist in this fresh DB either -- the egress refusal must still win over a 404.
    response = client.post("/wip/manuscripts/1/checks/analytic-flexibility", json={})
    assert response.status_code == 403


def test_analytic_flexibility_run_missing_manuscript_short_circuits_before_llm_work(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    # AnalyticFlexibilityAssistant.propose is deliberately NOT mocked: if the 404 check didn't short-circuit
    # before any snapshot/LLM work, this would attempt a real (and failing) network call instead of a clean 404.
    response = client.post("/wip/manuscripts/999/checks/analytic-flexibility", json={})
    assert response.status_code == 404
    assert response.json()["detail"] == "WIP manuscript not found"


def test_analytic_flexibility_route_remains_local_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    headers = {"host": "example.com"}
    assert client.post("/wip/manuscripts/1/checks/analytic-flexibility", headers=headers).status_code == 403


def test_analytic_flexibility_run_returns_502_and_logs_activity_when_provider_fails(
    temp_db_url: str, tmp_path: Path
) -> None:
    """Final-review Finding 3 (WIP side): a ProviderError must surface as a friendly 502 (not an unhandled 500),
    mirroring routers/workbench.py's propose_row pattern -- and, unlike that endpoint, must also leave a matching
    tool-run-failed activity so the earlier dangling tool-run-started entry isn't left orphaned (mirrors the
    existing ContentIdentityError failure path in this same handler)."""
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(
        "Methods: Participants who failed the attention check were excluded from the primary analysis.",
        encoding="utf-8",
    )
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    with patch(
        "app.backend.api.routers.wip_checks.AnalyticFlexibilityAssistant.propose",
        side_effect=ProviderError("HTTP 429: rate limited"),
    ):
        response = client.post(f"/wip/manuscripts/{manuscript_id}/checks/analytic-flexibility", json={})

    assert response.status_code == 502
    assert "AI provider failed" in response.json()["detail"]

    activity = client.get(f"/wip/manuscripts/{manuscript_id}/activity").json()
    failed_events = [event for event in activity if event["event_type"] == "tool-run-failed"]
    assert len(failed_events) == 1
    assert "provider failed" in failed_events[0]["summary"].lower()
    # The started/failed pair must be balanced -- no dangling started-with-no-matching-failed entry.
    started_events = [event for event in activity if event["event_type"] == "tool-run-started"]
    assert len(started_events) == len(failed_events) == 1
