"""Local-only API contracts for the WIP foundation."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.api import create_app


def _poll(client: TestClient, job_id: str) -> dict:
    result: dict = {}
    for _ in range(30):
        result = client.get(f"/wip/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            break
    return result


def test_watch_root_scan_and_manuscript_edit_round_trip(temp_db_url: str, tmp_path: Path) -> None:
    root = tmp_path / "Studies"
    manuscript = root / "Facial Anomaly"
    manuscript.mkdir(parents=True)
    (manuscript / "draft.md").write_text("# Draft", encoding="utf-8")
    app = create_app(db_url=temp_db_url)
    opened: list[tuple[str, bool]] = []
    app.state.wip_path_opener = lambda path, *, reveal: opened.append((str(path), reveal))
    client = TestClient(app)

    created = client.post(
        "/wip/watch-roots",
        json={"path": str(root), "discovery_mode": "children", "excluded_children": []},
    )
    assert created.status_code == 201
    root_id = created.json()["id"]
    scan = client.post(f"/wip/watch-roots/{root_id}/scan")
    assert scan.status_code == 202
    done = _poll(client, scan.json()["job_id"])
    assert done["status"] == "done"
    assert done["summary"]["added"] == 1

    rows = client.get("/wip/manuscripts").json()
    assert len(rows) == 1
    manuscript_id = rows[0]["id"]
    edited = client.patch(
        f"/wip/manuscripts/{manuscript_id}",
        json={"title_override": "Visible WIP title", "stage": "drafting", "target_journal": "BRM"},
    )
    assert edited.status_code == 200
    assert edited.json()["display_title"] == "Visible WIP title"
    assert edited.json()["stage"] == "drafting"
    file = client.get(f"/wip/manuscripts/{manuscript_id}/files").json()[0]
    assert file["relative_path"] == "draft.md"
    assert len(file["whole_file_hash"]) == 64
    made_primary = client.patch(
        f"/wip/manuscripts/{manuscript_id}/files/{file['id']}",
        json={"is_primary": True},
    )
    assert made_primary.status_code == 200
    assert made_primary.json()["is_primary"] is True
    assert made_primary.json()["role"] == "primary-manuscript"
    assert client.post(f"/wip/manuscripts/{manuscript_id}/files/{file['id']}/open").status_code == 204
    assert client.post(f"/wip/manuscripts/{manuscript_id}/files/{file['id']}/reveal").status_code == 204
    assert opened == [(str(manuscript / "draft.md"), False), (str(manuscript / "draft.md"), True)]
    event_types = {event["event_type"] for event in client.get(f"/wip/manuscripts/{manuscript_id}/activity").json()}
    assert {
        "manuscript-discovered",
        "file-added",
        "manuscript-renamed",
        "stage-changed",
        "primary-file-changed",
    } <= event_types


def test_watch_root_validation_pause_and_delete_preserves_manuscript(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Paper"
    folder.mkdir()
    client = TestClient(create_app(db_url=temp_db_url))

    assert (
        client.post(
            "/wip/watch-roots",
            json={"path": str(tmp_path / "absent"), "discovery_mode": "folder"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/wip/watch-roots",
            json={"path": str(folder), "discovery_mode": "children", "excluded_children": ["../escape"]},
        ).status_code
        == 422
    )
    created = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    duplicate = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    assert duplicate["uid"] == created["uid"]
    assert client.post(f"/wip/watch-roots/{created['id']}/scan").status_code == 202
    manuscripts = client.get("/wip/manuscripts").json()
    assert len(manuscripts) == 1

    assert client.patch(f"/wip/watch-roots/{created['id']}", json={"enabled": False}).status_code == 200
    assert client.post(f"/wip/watch-roots/{created['id']}/scan").status_code == 409
    assert client.delete(f"/wip/watch-roots/{created['id']}").status_code == 204
    preserved = client.get(f"/wip/manuscripts/{manuscripts[0]['id']}").json()
    assert preserved["uid"] == manuscripts[0]["uid"]


def test_wip_routes_deny_remote_forwarded_and_read_only_access(
    temp_db_url: str,
    monkeypatch,
) -> None:
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.get("/wip/manuscripts", headers={"host": "example.com"}).status_code == 403
    assert client.get("/wip/manuscripts", headers={"x-forwarded-for": "203.0.113.5"}).status_code == 403
    monkeypatch.setenv("CALLOSUM_READ_ONLY", "1")
    assert client.get("/wip/manuscripts").status_code == 403
