"""Manuscript-specific WIP search, facet, count, and sort contracts."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.api import create_app


def _poll(client: TestClient, job_id: str) -> None:
    for _ in range(30):
        result = client.get(f"/wip/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            assert result["status"] == "done"
            return
    raise AssertionError("scan did not finish")


def _titles(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [row["display_title"] for row in response.json()]


def test_wip_facets_counts_and_count_sorts_use_workflow_state(temp_db_url: str, tmp_path: Path) -> None:
    parent = tmp_path / "WIPs"
    for name in ("Alpha", "Beta", "Gamma"):
        folder = parent / name
        folder.mkdir(parents=True)
        text = "Results: t(18) = 2.10, p = .90." if name == "Alpha" else f"# {name}"
        (folder / "draft.md").write_text(text, encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    root = client.post(
        "/wip/watch-roots",
        json={"path": str(parent), "discovery_mode": "children"},
    ).json()
    _poll(client, client.post(f"/wip/watch-roots/{root['id']}/scan").json()["job_id"])
    rows = {row["derived_title"]: row for row in client.get("/wip/manuscripts").json()}
    alpha_id = rows["Alpha"]["id"]
    beta_id = rows["Beta"]["id"]

    assert (
        client.patch(
            f"/wip/manuscripts/{alpha_id}",
            json={
                "manuscript_type": "systematic-review",
                "target_journal": "Journal of Tests",
                "deadline": (date.today() - timedelta(days=1)).isoformat(),
                "stage": "drafting",
            },
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/wip/manuscripts/{beta_id}",
            json={"deadline": (date.today() + timedelta(days=10)).isoformat()},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/wip/manuscripts/{alpha_id}/tasks",
            json={"title": "Resolve the analysis"},
        ).status_code
        == 201
    )
    alpha_file = client.get(f"/wip/manuscripts/{alpha_id}/files").json()[0]
    assert (
        client.patch(
            f"/wip/manuscripts/{alpha_id}/files/{alpha_file['id']}",
            json={"is_primary": True},
        ).status_code
        == 200
    )
    assert client.post(f"/wip/manuscripts/{alpha_id}/checks/statcheck", json={}).status_code == 200

    (parent / "Alpha" / "draft.md").write_text("Results changed.", encoding="utf-8")
    _poll(client, client.post(f"/wip/watch-roots/{root['id']}/scan").json()["job_id"])
    indexed = {row["derived_title"]: row for row in client.get("/wip/manuscripts").json()}
    assert indexed["Alpha"]["open_task_count"] == 1
    assert indexed["Alpha"]["unresolved_finding_count"] == 1
    assert indexed["Alpha"]["stale_check_count"] == 1
    assert indexed["Alpha"]["missing_primary_file"] is False
    assert indexed["Beta"]["missing_primary_file"] is True

    assert _titles(client.get("/wip/manuscripts", params={"query": "systematic"})) == ["Alpha"]
    assert _titles(
        client.get(
            "/wip/manuscripts",
            params={
                "manuscript_type": "systematic",
                "target_journal": "Tests",
                "deadline": "overdue",
                "modified_days": 7,
            },
        )
    ) == ["Alpha"]
    assert _titles(client.get("/wip/manuscripts", params={"deadline": "next-30-days"})) == ["Beta"]
    assert _titles(client.get("/wip/manuscripts", params={"deadline": "none"})) == ["Gamma"]
    assert _titles(
        client.get(
            "/wip/manuscripts",
            params={
                "has_open_tasks": True,
                "has_unresolved_findings": True,
                "has_stale_checks": True,
            },
        )
    ) == ["Alpha"]
    assert set(_titles(client.get("/wip/manuscripts", params={"missing_primary": True}))) == {"Beta", "Gamma"}
    assert _titles(client.get("/wip/manuscripts", params={"sort": "open_tasks"}))[0] == "Alpha"
    assert _titles(client.get("/wip/manuscripts", params={"sort": "unresolved_findings"}))[0] == "Alpha"
