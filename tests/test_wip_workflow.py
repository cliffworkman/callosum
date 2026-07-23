"""Workflow contracts for WIP sections, tasks, and Library references."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers


def _manuscript(client: TestClient, folder: Path) -> int:
    created = client.post(
        "/wip/watch-roots",
        json={"path": str(folder), "discovery_mode": "folder"},
    ).json()
    assert client.post(f"/wip/watch-roots/{created['id']}/scan").status_code == 202
    return client.get("/wip/manuscripts").json()[0]["id"]


def test_sections_are_seeded_editable_reorderable_and_custom_deletable(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, folder)

    sections = client.get(f"/wip/manuscripts/{manuscript_id}/sections").json()
    assert len(sections) == 13
    assert [section["name"] for section in sections[:3]] == ["Title page", "Abstract", "Introduction"]
    abstract = sections[1]
    changed = client.patch(
        f"/wip/manuscripts/{manuscript_id}/sections/{abstract['id']}",
        json={"status": "drafting", "notes": "Needs a final sentence"},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "drafting"

    custom = client.post(
        f"/wip/manuscripts/{manuscript_id}/sections",
        json={"name": "Plain-language summary"},
    ).json()
    reordered_ids = [custom["id"], *[section["id"] for section in sections]]
    reordered = client.put(
        f"/wip/manuscripts/{manuscript_id}/sections/order",
        json={"section_ids": reordered_ids},
    )
    assert reordered.status_code == 200
    assert reordered.json()[0]["name"] == "Plain-language summary"
    assert client.delete(f"/wip/manuscripts/{manuscript_id}/sections/{abstract['id']}").status_code == 422
    assert client.delete(f"/wip/manuscripts/{manuscript_id}/sections/{custom['id']}").status_code == 204


def test_tasks_and_reference_links_round_trip_with_activity(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Draft"
    folder.mkdir()
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, folder)
    section_id = client.get(f"/wip/manuscripts/{manuscript_id}/sections").json()[4]["id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = int(
            conn.execute(
                insert(papers).values(
                    title="A linked source",
                    year=2024,
                    csl_json={"type": "article-journal", "title": "A linked source"},
                )
            ).inserted_primary_key[0]
        )

    task = client.post(
        f"/wip/manuscripts/{manuscript_id}/tasks",
        json={"title": "Rewrite results", "section_id": section_id, "due_date": "2026-08-01"},
    )
    assert task.status_code == 201
    completed = client.patch(
        f"/wip/manuscripts/{manuscript_id}/tasks/{task.json()['id']}",
        json={"status": "complete"},
    )
    assert completed.json()["completed_at"] is not None

    linked = client.post(
        f"/wip/manuscripts/{manuscript_id}/references",
        json={"paper_id": paper_id, "relationship_state": "to-cite"},
    )
    assert linked.status_code == 200
    assert linked.json()["paper_title"] == "A linked source"
    assert client.get(f"/wip/papers/{paper_id}").json()[0]["display_title"] == "Draft"
    events = {row["event_type"] for row in client.get(f"/wip/manuscripts/{manuscript_id}/activity").json()}
    assert {"task-created", "task-completed", "reference-linked"} <= events
    assert client.delete(f"/wip/manuscripts/{manuscript_id}/references/{paper_id}").status_code == 204
    assert client.delete(f"/wip/manuscripts/{manuscript_id}/tasks/{task.json()['id']}").status_code == 204
