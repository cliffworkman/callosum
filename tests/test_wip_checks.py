"""Deterministic WIP tool-run, finding, and validity contracts."""

from __future__ import annotations

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


def test_statcheck_run_is_snapshot_bound_reviewable_and_hash_invalidated(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text("Results: t(18) = 2.10, p = .90.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    root_id, manuscript_id, _ = _setup(client, folder)

    empty = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()
    assert empty["tools"][0]["id"] == "statcheck"
    assert empty["runs"] == []
    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={})
    assert run.status_code == 200
    payload = run.json()
    assert payload["tool_id"] == "statcheck"
    assert payload["tool_version"] == "1"
    assert payload["validity"] == "current-with-findings"
    assert "No surfaced inconsistency never means" in payload["coverage"]
    assert payload["structured_result_json"]["checked"] == 1
    first_run_id = payload["id"]
    finding = payload["findings"][0]
    assert finding["kind"] == "candidate"
    assert finding["quote"] == "t(18) = 2.10, p = .90"
    assert finding["coordinate_precision"] is None

    reviewed = client.patch(f"/wip/findings/{finding['id']}", json={"disposition": "resolved"})
    assert reviewed.status_code == 200
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "current"

    draft.write_text("Results changed: t(18) = 2.10, p = .04.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll(client, scan["job_id"])
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "potentially-stale"

    rerun = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={})
    assert rerun.status_code == 200
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] in {"current", "current-with-findings"}
    assert next(item for item in runs if item["id"] == first_run_id)["validity"] == "stale"


def test_statcheck_no_findings_states_coverage_not_cleanliness(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("No inline tests in this draft.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={}).json()
    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["structured_result_json"]["checked"] == 0
    assert "No surfaced inconsistency never means the manuscript is clean." in run["coverage"]


def test_wip_check_routes_remain_local_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    headers = {"host": "example.com"}
    assert client.get("/wip/manuscripts/1/checks", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/statcheck", headers=headers).status_code == 403
    assert client.patch("/wip/findings/1", headers=headers, json={"disposition": "resolved"}).status_code == 403
