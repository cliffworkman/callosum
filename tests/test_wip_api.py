"""Local-only API contracts for the WIP foundation."""

from __future__ import annotations

from pathlib import Path

import pytest
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


def test_missing_manuscript_relinks_without_losing_identity_or_workflow(temp_db_url: str, tmp_path: Path) -> None:
    original = tmp_path / "Original draft"
    original.mkdir()
    (original / "draft.md").write_text("# Draft", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    root = client.post(
        "/wip/watch-roots",
        json={"path": str(original), "discovery_mode": "folder"},
    ).json()
    _poll(client, client.post(f"/wip/watch-roots/{root['id']}/scan").json()["job_id"])
    manuscript = client.get("/wip/manuscripts").json()[0]
    file_before = client.get(f"/wip/manuscripts/{manuscript['id']}/files").json()[0]
    client.patch(
        f"/wip/manuscripts/{manuscript['id']}",
        json={"title_override": "Preserved title", "stage": "drafting"},
    )

    relocated = tmp_path / "Relocated draft"
    original.rename(relocated)
    _poll(client, client.post(f"/wip/watch-roots/{root['id']}/scan").json()["job_id"])
    assert client.get(f"/wip/manuscripts/{manuscript['id']}").json()["state"] == "missing"

    relinked = client.post(
        f"/wip/manuscripts/{manuscript['id']}/relink",
        json={"path": str(relocated)},
    )
    assert relinked.status_code == 200
    payload = relinked.json()
    assert payload["uid"] == manuscript["uid"]
    assert payload["display_title"] == "Preserved title"
    assert payload["stage"] == "drafting"
    assert payload["state"] == "active"
    assert Path(payload["root_path"]) == relocated
    file_after = client.get(f"/wip/manuscripts/{manuscript['id']}/files").json()[0]
    assert file_after["id"] == file_before["id"]
    roots = client.get("/wip/watch-roots").json()
    assert Path(roots[0]["path"]) == relocated
    events = client.get(f"/wip/manuscripts/{manuscript['id']}/activity").json()
    assert any(event["event_type"] == "manuscript-relinked" for event in events)


def test_relink_refuses_folder_owned_by_another_manuscript(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    manuscripts = []
    for name in ("First", "Second"):
        folder = tmp_path / name
        folder.mkdir()
        root = client.post(
            "/wip/watch-roots",
            json={"path": str(folder), "discovery_mode": "folder"},
        ).json()
        _poll(client, client.post(f"/wip/watch-roots/{root['id']}/scan").json()["job_id"])
        manuscripts = client.get("/wip/manuscripts").json()
    assert len(manuscripts) == 2
    first_id = next(row["id"] for row in manuscripts if row["derived_title"] == "First")
    result = client.post(f"/wip/manuscripts/{first_id}/relink", json={"path": str(tmp_path / "Second")})
    assert result.status_code == 409
    assert "another WIP manuscript" in result.json()["detail"]


def test_wip_routes_deny_remote_forwarded_and_read_only_access(
    temp_db_url: str,
    monkeypatch,
) -> None:
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.get("/wip/manuscripts", headers={"host": "example.com"}).status_code == 403
    assert (
        client.post(
            "/wip/manuscripts/1/relink",
            headers={"host": "example.com"},
            json={"path": str(Path.cwd())},
        ).status_code
        == 403
    )
    assert client.get("/wip/manuscripts", headers={"x-forwarded-for": "203.0.113.5"}).status_code == 403
    monkeypatch.setenv("CALLOSUM_READ_ONLY", "1")
    assert client.get("/wip/manuscripts").status_code == 403
    assert client.get("/wip/browse-dirs").status_code == 403


def test_browse_dirs_lists_subfolders_and_supports_navigation(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    root = tmp_path / "Library"
    (root / "Papers").mkdir(parents=True)
    (root / "Manuscripts").mkdir()
    (root / "notes.txt").write_text("not a folder", encoding="utf-8")
    (root / "__pycache__").mkdir()  # in SKIP_DIRECTORY_NAMES -- must never be listed

    at_root = client.get("/wip/browse-dirs", params={"path": str(root)})
    assert at_root.status_code == 200
    body = at_root.json()
    assert body["path"] == str(root)
    assert body["parent"] == str(root.parent)
    assert body["truncated"] is False
    assert body["error"] is None
    names = {entry["name"] for entry in body["entries"]}
    assert names == {"Papers", "Manuscripts"}  # neither the file nor __pycache__ appear

    into_child = client.get("/wip/browse-dirs", params={"path": str(root / "Papers")})
    assert into_child.json()["parent"] == str(root)

    default = client.get("/wip/browse-dirs")
    assert default.status_code == 200
    assert default.json()["path"] == str(Path.home().resolve())


def test_browse_dirs_root_has_no_parent(tmp_path_factory, temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    fs_root = Path(tmp_path_factory.getbasetemp().anchor)  # e.g. "C:\\" on Windows, "/" on POSIX
    result = client.get("/wip/browse-dirs", params={"path": str(fs_root)})
    assert result.status_code == 200
    assert result.json()["parent"] is None


def test_browse_dirs_skips_symlinks(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    root = tmp_path / "WithLink"
    target = tmp_path / "LinkTarget"
    root.mkdir()
    target.mkdir()
    try:
        (root / "shortcut").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted in this test environment (e.g. unprivileged Windows)")
    (root / "real").mkdir()
    result = client.get("/wip/browse-dirs", params={"path": str(root)})
    names = {entry["name"] for entry in result.json()["entries"]}
    assert names == {"real"}


def test_browse_dirs_caps_entries_and_flags_truncated(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    root = tmp_path / "Big"
    root.mkdir()
    for index in range(1005):
        (root / f"folder-{index:04d}").mkdir()
    result = client.get("/wip/browse-dirs", params={"path": str(root)})
    body = result.json()
    assert len(body["entries"]) == 1000
    assert body["truncated"] is True


def test_browse_dirs_reports_unreadable_folder_without_crashing(temp_db_url: str, tmp_path: Path, monkeypatch) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    root = tmp_path / "Locked"
    root.mkdir()
    real_iterdir = Path.iterdir

    def fake_iterdir(self):
        if str(self) == str(root):
            raise PermissionError("Permission denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    result = client.get("/wip/browse-dirs", params={"path": str(root)})
    assert result.status_code == 200
    body = result.json()
    assert body["entries"] == []
    assert body["truncated"] is False
    assert "Permission denied" in body["error"]
    assert body["parent"] == str(root.parent)  # "Up one level" still usable


def test_browse_dirs_rejects_missing_or_non_directory_path(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    missing = client.get("/wip/browse-dirs", params={"path": str(tmp_path / "does-not-exist")})
    assert missing.status_code == 422

    a_file = tmp_path / "file.txt"
    a_file.write_text("x", encoding="utf-8")
    not_a_dir = client.get("/wip/browse-dirs", params={"path": str(a_file)})
    assert not_a_dir.status_code == 422
