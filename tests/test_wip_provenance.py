"""Exact local content-checkpoint contracts for WIP manuscripts."""

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


def _setup(client: TestClient, folder: Path, filename: str = "draft.md") -> tuple[int, int]:
    created = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    scan = client.post(f"/wip/watch-roots/{created['id']}/scan").json()
    assert _poll(client, scan["job_id"])["status"] == "done"
    manuscript_id = client.get("/wip/manuscripts").json()[0]["id"]
    file_id = next(
        row["id"]
        for row in client.get(f"/wip/manuscripts/{manuscript_id}/files").json()
        if row["relative_path"] == filename
    )
    return manuscript_id, file_id


def test_primary_stage_and_manual_checkpoints_are_exact_and_deduplicated(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text("# Results\n\nThe first result.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id, file_id = _setup(client, folder)

    selected = client.patch(
        f"/wip/manuscripts/{manuscript_id}/files/{file_id}",
        json={"is_primary": True},
    )
    assert selected.status_code == 200
    file = selected.json()
    assert file["extraction_status"] == "complete"
    assert file["extracted_from_whole_hash"] == file["whole_file_hash"]
    initial = client.get(f"/wip/manuscripts/{manuscript_id}/snapshots").json()
    assert [(row["reason"], row["identity_status"]) for row in initial] == [("primary-file-replacement", "current")]
    assert initial[0]["evidence_context_json"] == ["# Results", "The first result."]
    assert (
        client.patch(
            f"/wip/manuscripts/{manuscript_id}/files/{file_id}",
            json={"is_primary": True},
        ).status_code
        == 200
    )
    assert len(client.get(f"/wip/manuscripts/{manuscript_id}/snapshots").json()) == 1

    staged = client.patch(f"/wip/manuscripts/{manuscript_id}", json={"stage": "drafting"})
    assert staged.status_code == 200
    assert {row["reason"] for row in client.get(f"/wip/manuscripts/{manuscript_id}/snapshots").json()} == {
        "primary-file-replacement",
        "stage-transition",
    }

    first_manual = client.post(f"/wip/manuscripts/{manuscript_id}/snapshots", json={}).json()
    second_manual = client.post(f"/wip/manuscripts/{manuscript_id}/snapshots", json={}).json()
    assert first_manual["created"] is True
    assert second_manual["created"] is False
    assert first_manual["uid"] == second_manual["uid"]


def test_changed_file_is_potentially_stale_until_reextracted(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    draft = folder / "draft.md"
    draft.write_text("Original manuscript text.", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id, file_id = _setup(client, folder)
    assert (
        client.patch(
            f"/wip/manuscripts/{manuscript_id}/files/{file_id}",
            json={"is_primary": True},
        ).status_code
        == 200
    )

    draft.write_text("Changed manuscript text.", encoding="utf-8")
    root_id = client.get("/wip/watch-roots").json()[0]["id"]
    scan = client.post(f"/wip/watch-roots/{root_id}/scan").json()
    assert _poll(client, scan["job_id"])["status"] == "done"
    snapshots = client.get(f"/wip/manuscripts/{manuscript_id}/snapshots").json()
    assert snapshots[0]["identity_status"] == "potentially-stale"

    created = client.post(f"/wip/manuscripts/{manuscript_id}/snapshots", json={})
    assert created.status_code == 200
    snapshots = client.get(f"/wip/manuscripts/{manuscript_id}/snapshots").json()
    assert snapshots[0]["identity_status"] == "current"
    assert any(row["identity_status"] == "stale" for row in snapshots[1:])


def test_unsupported_primary_is_selected_but_checkpoint_is_refused_honestly(
    temp_db_url: str,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    (folder / "draft.rtf").write_text(r"{\rtf1 Draft}", encoding="utf-8")
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id, file_id = _setup(client, folder, "draft.rtf")

    selected = client.patch(
        f"/wip/manuscripts/{manuscript_id}/files/{file_id}",
        json={"is_primary": True},
    )
    assert selected.status_code == 200
    assert selected.json()["extraction_status"] == "unsupported"
    rejected = client.post(f"/wip/manuscripts/{manuscript_id}/snapshots", json={})
    assert rejected.status_code == 422
    assert "Unsupported primary manuscript format" in rejected.json()["detail"]


def test_snapshot_routes_remain_local_only(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert (
        client.get(
            "/wip/manuscripts/1/snapshots",
            headers={"x-forwarded-for": "203.0.113.5"},
        ).status_code
        == 403
    )
