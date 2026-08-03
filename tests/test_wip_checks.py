"""Deterministic WIP tool-run, finding, and validity contracts."""

from __future__ import annotations

from pathlib import Path

import fitz
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
    assert empty["tools"][1]["id"] == "transparency"
    assert empty["runs"] == []
    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/statcheck", json={})
    assert run.status_code == 200
    payload = run.json()
    assert payload["tool_id"] == "statcheck"
    assert payload["tool_version"] == "2"
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


def test_transparency_run_is_snapshot_bound_and_persists_positive_facts_only(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text(
        "Data are available at https://osf.io/abcd. Analysis code is available on GitHub. "
        "The authors declare no conflicts of interest. This work was funded by the NSF. "
        "The analysis plan was preregistered at AsPredicted.",
        encoding="utf-8",
    )
    client = TestClient(create_app(db_url=temp_db_url))
    root_id, manuscript_id, _ = _setup(client, folder)

    response = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={})

    assert response.status_code == 200
    run = response.json()
    assert run["tool_id"] == "transparency"
    assert run["tool_version"] == "1"
    assert run["validity"] == "current"
    assert "no result is a transparency score or judgment" in run["coverage"]
    result = run["structured_result_json"]
    assert len(result["checks"]) == 7
    assert result["present"] >= 5
    assert len(run["findings"]) == result["present"]
    assert all(finding["kind"] == "fact" for finding in run["findings"])
    assert all(finding["disposition"] is None for finding in run["findings"])
    assert all(finding["quote"] for finding in run["findings"])
    assert all(finding["coordinate_precision"] is None for finding in run["findings"])
    assert not any("not-detected" in finding["finding_type"] for finding in run["findings"])

    fact_id = run["findings"][0]["id"]
    rejected_review = client.patch(f"/wip/findings/{fact_id}", json={"disposition": "resolved"})
    assert rejected_review.status_code == 422
    assert rejected_review.json()["detail"] == "Only candidate findings have a review disposition"

    draft.write_text("The manuscript text changed completely.", encoding="utf-8")
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    _poll(client, scan["job_id"])
    runs = client.get(f"/wip/manuscripts/{manuscript_id}/checks").json()["runs"]
    assert runs[0]["validity"] == "potentially-stale"


def test_transparency_no_detections_retains_coverage_without_negative_findings(
    temp_db_url: str, tmp_path: Path
) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("A short manuscript introduction.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={}).json()

    assert run["validity"] == "current"
    assert run["findings"] == []
    assert run["structured_result_json"]["present"] == 0
    statuses = {check["key"]: check["status"] for check in run["structured_result_json"]["checks"]}
    assert statuses["data_availability"] == "not-found"
    assert statuses["registration"] == "not-applicable"
    assert "'Not detected' never means absent" in run["coverage"]


def test_transparency_preserves_region_page_only_for_pdf_sources(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Data are available in the OSF repository.")
    document.save(draft)
    document.close()
    client = TestClient(create_app(db_url=temp_db_url))
    _, manuscript_id, _ = _setup(client, folder)

    run = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={}).json()

    data_check = next(check for check in run["structured_result_json"]["checks"] if check["key"] == "data_availability")
    data_fact = next(finding for finding in run["findings"] if finding["finding_type"].startswith("transparency-data"))
    assert data_check["page"] == 1
    assert data_check["coordinate_precision"] == "region"
    assert data_fact["coordinate_precision"] == "region"


def test_transparency_rejects_missing_manuscript_and_missing_primary_file(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    missing = client.post("/wip/manuscripts/999/checks/transparency", json={})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "WIP manuscript not found"

    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.txt").write_text("Data are available in a repository.", encoding="utf-8")
    root = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    scan = client.post(f"/wip/watch-roots/{root['id']}/scan").json()
    _poll(client, scan["job_id"])
    manuscript_id = client.get("/wip/manuscripts").json()[0]["id"]

    no_primary = client.post(f"/wip/manuscripts/{manuscript_id}/checks/transparency", json={})
    assert no_primary.status_code == 422
    assert no_primary.json()["detail"] == "Select a primary manuscript file before creating a checkpoint"


def test_wip_check_routes_remain_local_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    headers = {"host": "example.com"}
    assert client.get("/wip/manuscripts/1/checks", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/statcheck", headers=headers).status_code == 403
    assert client.post("/wip/manuscripts/1/checks/transparency", headers=headers).status_code == 403
    assert client.patch("/wip/findings/1", headers=headers, json={"disposition": "resolved"}).status_code == 403
