"""Filesystem discovery and persistence contracts for local WIP workspaces."""

from __future__ import annotations

from pathlib import Path

from app.backend.persistence.database import make_engine
from app.backend.persistence.wip_repo import (
    create_watch_root,
    get_manuscript,
    list_activity,
    list_files,
    list_manuscripts,
    reconcile_watch_root,
    update_manuscript,
)
from app.backend.wip.discovery import inspect_watch_root
from app.backend.wip.paths import path_key


def _root(conn, folder: Path, mode: str = "folder", exclusions: list[str] | None = None) -> dict:
    return create_watch_root(
        conn,
        path=str(folder.resolve()),
        path_key=path_key(folder),
        discovery_mode=mode,
        excluded_children=exclusions or [],
    )


def test_folder_mode_discovers_one_stable_manuscript_and_files(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Price of a Scar"
    folder.mkdir()
    (folder / "draft.docx").write_bytes(b"draft")
    (folder / "cover letter.txt").write_text("Dear editor", encoding="utf-8")
    engine = make_engine(temp_db_url)

    with engine.begin() as conn:
        root = _root(conn, folder)
        first = reconcile_watch_root(conn, root, inspect_watch_root(root))
        manuscript = list_manuscripts(conn)[0]
        original_uid = manuscript["uid"]
        original_activity = list_activity(conn, manuscript["id"])

        second = reconcile_watch_root(conn, root, inspect_watch_root(root))
        repeated = list_manuscripts(conn)[0]

        assert first == {
            "added": 1,
            "restored": 0,
            "missing": 0,
            "files_added": 2,
            "files_missing": 0,
            "errors": 0,
        }
        assert second["added"] == 0 and second["files_added"] == 0
        assert repeated["uid"] == original_uid
        assert repeated["display_title"] == "Price of a Scar"
        assert len(list_activity(conn, manuscript["id"])) == len(original_activity)
        assert {row["role"] for row in list_files(conn, manuscript["id"])} == {
            "manuscript-candidate",
            "cover-letter",
        }


def test_children_mode_is_immediate_only_and_honors_exclusions(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "WIPs"
    included = folder / "Included"
    nested = included / "not-a-workspace"
    excluded = folder / "Excluded"
    nested.mkdir(parents=True)
    excluded.mkdir()
    (nested / "notes.md").write_text("# Notes", encoding="utf-8")
    (excluded / "draft.md").write_text("# Draft", encoding="utf-8")
    engine = make_engine(temp_db_url)

    with engine.begin() as conn:
        root = _root(conn, folder, "children", ["Excluded"])
        result = reconcile_watch_root(conn, root, inspect_watch_root(root))
        manuscripts = list_manuscripts(conn)

        assert result["added"] == 1
        assert [row["display_title"] for row in manuscripts] == ["Included"]
        assert [row["relative_path"] for row in list_files(conn, manuscripts[0]["id"])] == ["not-a-workspace/notes.md"]


def test_missing_then_restored_preserves_identity_metadata_and_activity(temp_db_url: str, tmp_path: Path) -> None:
    folder = tmp_path / "Manuscript"
    folder.mkdir()
    (folder / "paper.md").write_text("# Draft", encoding="utf-8")
    engine = make_engine(temp_db_url)

    with engine.begin() as conn:
        root = _root(conn, folder)
        reconcile_watch_root(conn, root, inspect_watch_root(root))
        manuscript = list_manuscripts(conn)[0]
        update_manuscript(
            conn,
            manuscript["id"],
            {"title_override": "A deliberate title", "stage": "drafting"},
        )
        original_uid = manuscript["uid"]

    (folder / "paper.md").unlink()
    folder.rmdir()
    with engine.begin() as conn:
        missing = reconcile_watch_root(conn, root, inspect_watch_root(root))
        row = get_manuscript(conn, manuscript["id"])
        assert missing["missing"] == 1
        assert row["state"] == "missing"

    folder.mkdir()
    (folder / "paper.md").write_text("# Revised", encoding="utf-8")
    with engine.begin() as conn:
        restored = reconcile_watch_root(conn, root, inspect_watch_root(root))
        row = get_manuscript(conn, manuscript["id"])
        events = [event["event_type"] for event in list_activity(conn, manuscript["id"])]

        assert restored["restored"] == 1
        assert row["uid"] == original_uid
        assert row["display_title"] == "A deliberate title"
        assert row["stage"] == "drafting"
        assert row["state"] == "active"
        assert events.count("folder-missing") == 1
        assert events.count("folder-restored") == 1


def test_same_title_at_distinct_paths_remains_distinct(temp_db_url: str, tmp_path: Path) -> None:
    one = tmp_path / "one" / "Draft"
    two = tmp_path / "two" / "Draft"
    one.mkdir(parents=True)
    two.mkdir(parents=True)
    engine = make_engine(temp_db_url)

    with engine.begin() as conn:
        for folder in (one, two):
            root = _root(conn, folder)
            reconcile_watch_root(conn, root, inspect_watch_root(root))
        manuscripts = list_manuscripts(conn)

        assert len(manuscripts) == 2
        assert len({row["uid"] for row in manuscripts}) == 2
        assert {row["display_title"] for row in manuscripts} == {"Draft"}
