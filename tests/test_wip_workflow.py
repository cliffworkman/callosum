"""Workflow contracts for WIP sections, tasks, and Library references."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Connection, insert

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers, wip_tasks
from app.backend.persistence.wip_workflow_repo import list_tasks


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


# ── task ordering (#102): completion -> due date -> created_at DESC -> id DESC ────────────────────────────────────
#
# `created_at` comes from SQLite's one-second CURRENT_TIMESTAMP, so two tasks made in the same second cannot be told apart by
# it. `id` (an INTEGER PRIMARY KEY, i.e. SQLite's rowid) is the insertion-order proxy used ONLY as the final tie-break; it must
# never outrank completion state, due date or created_at.

_T0 = datetime(2026, 8, 11, 12, 0, 0)


def _add_task(
    conn: Connection,
    manuscript_id: int,
    title: str,
    *,
    created_at: datetime,
    due_date: date | None = None,
    completed_at: datetime | None = None,
) -> int:
    result = conn.execute(
        insert(wip_tasks).values(
            uid=str(uuid4()),
            manuscript_id=manuscript_id,
            title=title,
            status="complete" if completed_at is not None else "open",
            created_at=created_at,
            due_date=due_date,
            completed_at=completed_at,
        )
    )
    return int(result.inserted_primary_key[0])


def _ordered_titles(temp_db_url: str, tmp_path: Path, build) -> list[str]:
    folder = tmp_path / "Draft"
    folder.mkdir()
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, folder)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        build(conn, manuscript_id)
        titles = [task["title"] for task in list_tasks(conn, manuscript_id)]
    engine.dispose()
    return titles


def test_tasks_created_in_the_same_second_list_newest_inserted_first(temp_db_url: str, tmp_path: Path) -> None:
    def build(conn: Connection, manuscript_id: int) -> None:
        first = _add_task(conn, manuscript_id, "A (lower id)", created_at=_T0)
        second = _add_task(conn, manuscript_id, "B (higher id)", created_at=_T0)
        assert first < second  # insertion order is what the id records

    assert _ordered_titles(temp_db_url, tmp_path, build) == ["B (higher id)", "A (lower id)"]


def test_a_task_created_in_a_later_second_lists_first(temp_db_url: str, tmp_path: Path) -> None:
    def build(conn: Connection, manuscript_id: int) -> None:
        _add_task(conn, manuscript_id, "A (lower id)", created_at=_T0)
        _add_task(conn, manuscript_id, "B (higher id)", created_at=_T0 + timedelta(seconds=1))

    assert _ordered_titles(temp_db_url, tmp_path, build) == ["B (higher id)", "A (lower id)"]


def test_the_whole_task_ordering_contract_id_is_only_the_final_tiebreak(temp_db_url: str, tmp_path: Path) -> None:
    due_early, due_mid, due_late = date(2026, 8, 1), date(2026, 8, 10), date(2026, 8, 20)

    def build(conn: Connection, manuscript_id: int) -> None:
        # Insertion order = id order. Apart from the final tie-break, each expectation differs from what id alone would give.
        _add_task(conn, manuscript_id, "mid: newer, lower id", created_at=_T0 + timedelta(seconds=9), due_date=due_mid)
        _add_task(conn, manuscript_id, "mid: older, higher id", created_at=_T0 + timedelta(seconds=2), due_date=due_mid)
        _add_task(conn, manuscript_id, "late: tie, lower id", created_at=_T0 + timedelta(seconds=5), due_date=due_late)
        _add_task(conn, manuscript_id, "late: tie, higher id", created_at=_T0 + timedelta(seconds=5), due_date=due_late)
        _add_task(conn, manuscript_id, "early: oldest, higher id", created_at=_T0, due_date=due_early)
        _add_task(
            conn,
            manuscript_id,
            "complete: newest, highest id, earliest due",
            created_at=_T0 + timedelta(seconds=60),
            due_date=date(2026, 7, 1),
            completed_at=_T0 + timedelta(seconds=70),
        )

    assert _ordered_titles(temp_db_url, tmp_path, build) == [
        "early: oldest, higher id",  # due date outranks created_at and id
        "mid: newer, lower id",  # same due date: created_at DESC outranks id
        "mid: older, higher id",
        "late: tie, higher id",  # same due date AND same created_at second: id DESC is the final tie-break
        "late: tie, lower id",
        "complete: newest, highest id, earliest due",  # completion state outranks everything
    ]
