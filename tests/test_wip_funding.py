"""Discover > Funding wired to WIP manuscripts (inc 403) -- a run tags research_funding_profiles with the
manuscript as its source and becomes visible from the manuscript's own /funding-runs history."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.api import create_app


def _poll_scan(client: TestClient, job_id: str) -> None:
    for _ in range(30):
        result = client.get(f"/wip/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            assert result["status"] == "done"
            return
    raise AssertionError("scan did not finish")


def _manuscript(client: TestClient, folder: Path) -> int:
    folder.mkdir()
    (folder / "draft.txt").write_text("An early idea.", encoding="utf-8")
    root = client.post("/wip/watch-roots", json={"path": str(folder), "discovery_mode": "folder"}).json()
    scan = client.post(f"/wip/watch-roots/{root['id']}/scan").json()
    _poll_scan(client, scan["job_id"])
    return client.get("/wip/manuscripts").json()[0]["id"]


def _run_funding(client: TestClient, manuscript_id: int) -> dict:
    start = client.post(
        "/funding-discovery/run",
        json={
            "description": "pilot community mental health implementation",
            "field": "public health",
            "manuscript_id": manuscript_id,
        },
    )
    assert start.status_code == 202, start.text
    job_id = start.json()["job_id"]
    done: dict = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done
    return done["report"]


def test_funding_run_tags_and_lists_for_a_wip_manuscript(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    manuscript_title = client.get(f"/wip/manuscripts/{manuscript_id}").json()["display_title"]

    report = _run_funding(client, manuscript_id)
    assert report["profile"]["source_kind"] == "wip-manuscript"
    assert report["profile"]["source_id"] == str(manuscript_id)
    assert report["profile"]["title"] == manuscript_title

    runs = client.get(f"/wip/manuscripts/{manuscript_id}/funding-runs")
    assert runs.status_code == 200
    listed = runs.json()["runs"]
    assert len(listed) == 1
    assert listed[0]["run_id"] == report["run_id"]
    assert listed[0]["title"] == manuscript_title


def test_funding_run_rejects_paper_id_and_manuscript_id_together(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/funding-discovery/run", json={"paper_id": 1, "manuscript_id": 1})
    assert r.status_code == 422


def test_funding_run_404s_for_a_missing_manuscript(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/funding-discovery/run", json={"description": "x", "manuscript_id": 999999})
    assert r.status_code == 404


def test_funding_runs_list_404s_for_a_missing_manuscript_and_is_scoped(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/wip/manuscripts/999999/funding-runs").status_code == 404

    manuscript_a = _manuscript(client, tmp_path / "DraftA")
    manuscript_b = _manuscript(client, tmp_path / "DraftB")
    _run_funding(client, manuscript_a)

    assert len(client.get(f"/wip/manuscripts/{manuscript_a}/funding-runs").json()["runs"]) == 1
    assert client.get(f"/wip/manuscripts/{manuscript_b}/funding-runs").json()["runs"] == []


def test_wip_funding_runs_route_remains_local_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    headers = {"host": "example.com"}
    assert client.get("/wip/manuscripts/1/funding-runs", headers=headers).status_code == 403
