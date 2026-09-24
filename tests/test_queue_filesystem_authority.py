"""Filesystem authority for the Import Queue (#61) -- the CodeQL `py/path-injection` findings on PR #103.

The property under test is architectural, not a source spelling:

    a persisted arbitrary path is NOT filesystem authority, and a request string is only a lookup claim.

A queue operation names an artifact by route id. The id is matched against the server-owned ACTIVE queue ids and every path
is derived from the stored id (`trusted_paths`, `owned_artifacts`). So a deliberately poisoned `provisional_artifacts.pdf_path`
must not make Callosum read, copy or delete anything outside the Import Queue, and must not displace the deterministic
`<queue>/<id>.pdf` entry. Two capabilities are kept apart: an entry may be UNLINKED without being safe to FOLLOW.

Symlink cases skip where links cannot be created (Windows without the privilege); the Linux CI job exercises them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import update

from app.backend.acquisition.fetch import library_dir
from app.backend.api.routers import capture as capture_router
from app.backend.capture import provisional
from app.backend.capture.owned_artifacts import resolve_owned_queue_artifact_id
from app.backend.capture.provisional import queue_dir, sidecar_path
from app.backend.capture.provisional_recovery import recover_at_startup
from app.backend.capture.trusted_paths import (
    is_plain_file,
    managed_capture_pdf_path,
    queue_filename_id,
    queued_pdf_entry_path,
    queued_pdf_read_path,
)
from app.backend.persistence import capture_events_repo, provisional_artifacts_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import get_attachments_for_paper
from app.backend.persistence.schema import provisional_artifacts
from tests.test_capture import _client, _pdf_with_metadata_title
from tests.test_import_queue import _queue_pending_item

GOOD_ID = "0123456789abcdef0123456789abcdef"
HOSTILE_IDS = [
    "../escape",
    "..\\escape",
    "a/b",
    "",
    "0" * 31,
    "0" * 33,
    GOOD_ID.upper(),
    "0" * 31 + "g",
    GOOD_ID + ".pdf",
]
CONFIRM = {"doi": "10.1234/found-in-pdf", "source": "manual"}


@pytest.fixture(autouse=True)
def _ui_instance(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CALLOSUM_INSTANCE_ROLE", "ui")
    capture_router._reset_for_tests()
    yield
    capture_router._reset_for_tests()


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:  # Windows without the privilege, or a filesystem without links
        pytest.skip(f"cannot create a symlink in this environment: {exc}")


def _queue_file(artifact_id: str) -> Path:
    return queued_pdf_entry_path(queue_dir(library_dir()), artifact_id)


def _outside_file(
    tmp_path: Path, content: bytes = b"%PDF-1.7 OUTSIDE -- must never be read, copied or deleted"
) -> Path:
    outside = tmp_path / "outside" / "secret.pdf"
    outside.parent.mkdir()
    outside.write_bytes(content)
    return outside


def _poison_pdf_path(client, artifact_id: str, path: Path) -> None:
    engine = make_engine(client.app.state.db_url)
    with engine.begin() as conn:
        conn.execute(
            update(provisional_artifacts).where(provisional_artifacts.c.id == artifact_id).values(pdf_path=str(path))
        )
    engine.dispose()


def _get_row(client, artifact_id: str):
    engine = make_engine(client.app.state.db_url)
    with engine.begin() as conn:
        row = provisional_artifacts_repo.get(conn, artifact_id)
    engine.dispose()
    return row


# ── the pure helpers ─────────────────────────────────────────────────────────────────────────────────────────────


def test_a_queue_filename_is_an_identity_only_in_its_exact_canonical_form() -> None:
    assert queue_filename_id(f"{GOOD_ID}.pdf") == GOOD_ID
    for name in (
        f"{GOOD_ID.upper()}.pdf",  # upper-case hex
        f"{GOOD_ID}.PDF",  # extension case
        f"{GOOD_ID}.pdf.tmp",
        f".{GOOD_ID}.pdf",
        f"{GOOD_ID} .pdf",
        f"{GOOD_ID[:-1]}.pdf",
        f"x{GOOD_ID}.pdf",
        "notes.pdf",
        "",
    ):
        assert queue_filename_id(name) is None, name


@pytest.mark.parametrize("hostile", HOSTILE_IDS)
def test_every_managed_path_constructor_refuses_a_non_canonical_id(tmp_path: Path, hostile: str) -> None:
    """Defense in depth: even a caller that should hold an owned id cannot build a path from anything else."""
    for build in (
        lambda: managed_capture_pdf_path(tmp_path, hostile),
        lambda: queued_pdf_entry_path(tmp_path, hostile),
        lambda: queued_pdf_read_path(tmp_path, hostile),
        lambda: sidecar_path(tmp_path, hostile),
    ):
        with pytest.raises(ValueError):
            build()


def test_the_entry_path_is_the_lexical_direct_child_whether_or_not_it_exists(tmp_path: Path) -> None:
    assert queued_pdf_entry_path(tmp_path, GOOD_ID) == tmp_path / f"{GOOD_ID}.pdf"


def test_the_read_path_follows_only_a_plain_regular_file_directly_in_the_queue(tmp_path: Path) -> None:
    queue = tmp_path / "_Import Queue"
    queue.mkdir()
    entry = queue / f"{GOOD_ID}.pdf"
    assert queued_pdf_read_path(queue, GOOD_ID) is None  # missing
    entry.write_bytes(b"%PDF-1.7 ok")
    assert queued_pdf_read_path(queue, GOOD_ID) == entry.resolve()
    entry.unlink()
    entry.mkdir()  # a directory occupying the entry is not a file
    assert queued_pdf_read_path(queue, GOOD_ID) is None


def test_a_symlink_is_removable_as_an_entry_but_never_readable(tmp_path: Path) -> None:
    queue = tmp_path / "_Import Queue"
    queue.mkdir()
    other = queue / ("e" * 32 + ".pdf")
    other.write_bytes(b"%PDF-1.7 a regular file INSIDE the queue")
    outside = _outside_file(tmp_path)
    for target in (outside, other):  # a link to elsewhere AND a link to a plain file in the same queue
        link = queue / f"{GOOD_ID}.pdf"
        _symlink_or_skip(link, target)
        assert not is_plain_file(link)
        assert queued_pdf_read_path(queue, GOOD_ID) is None
        queued_pdf_entry_path(queue, GOOD_ID).unlink()  # unlink removes the link itself...
        assert not link.is_symlink() and target.read_bytes()  # ...and never touches the target


# ── the server-owned active-id allowlist ─────────────────────────────────────────────────────────────────────────


class _Claim(str):
    """A request string, distinguishable from a stored value by type."""


def test_the_owned_id_is_the_stored_value_of_an_active_artifact_and_never_the_request(
    temp_db_url: str, tmp_path: Path
) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        owned = resolve_owned_queue_artifact_id(conn, _Claim(artifact_id))
        unknown = resolve_owned_queue_artifact_id(conn, "f" * 32)
        malformed = [resolve_owned_queue_artifact_id(conn, bad) for bad in HOSTILE_IDS]
    engine.dispose()
    assert owned == artifact_id
    assert type(owned) is str, "the returned id must be the stored value, not the request object"
    assert unknown is None
    assert malformed == [None] * len(HOSTILE_IDS)


def test_a_promoted_artifact_is_no_longer_an_owned_queue_operand(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    assert (
        client.post(f"/library/import-queue/{artifact_id}/confirm", json=CONFIRM).json()["promotion_state"]
        == "promoted"
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert resolve_owned_queue_artifact_id(conn, artifact_id) is None
    engine.dispose()
    # It stays in persistence as provenance, but deletion is a queue operation and the queue no longer holds it.
    assert client.delete(f"/library/import-queue/{artifact_id}").status_code == 404
    assert _get_row(client, artifact_id) is not None


# ── a poisoned persisted pdf_path is not authority ───────────────────────────────────────────────────────────────


def test_serving_ignores_a_poisoned_pdf_path_and_serves_the_owned_queue_entry(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    queued_bytes = _queue_file(artifact_id).read_bytes()
    outside = _outside_file(tmp_path)
    _poison_pdf_path(client, artifact_id, outside)

    response = client.get(f"/library/import-queue/{artifact_id}/pdf")
    assert response.status_code == 200
    assert response.content == queued_bytes
    assert b"OUTSIDE" not in response.content


def test_serving_refuses_when_the_owned_entry_is_gone_even_if_the_poisoned_path_exists(
    temp_db_url: str, tmp_path: Path
) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    outside = _outside_file(tmp_path)
    _poison_pdf_path(client, artifact_id, outside)
    _queue_file(artifact_id).unlink()

    response = client.get(f"/library/import-queue/{artifact_id}/pdf")
    assert response.status_code == 404
    assert b"OUTSIDE" not in response.content


def test_serving_refuses_a_symlinked_queue_entry(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    outside = _outside_file(tmp_path)
    entry = _queue_file(artifact_id)
    entry.unlink()
    _symlink_or_skip(entry, outside)

    response = client.get(f"/library/import-queue/{artifact_id}/pdf")
    assert response.status_code == 404
    assert b"OUTSIDE" not in response.content


def test_confirm_promotes_the_owned_queue_bytes_and_never_touches_a_poisoned_path(
    temp_db_url: str, tmp_path: Path
) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    queued_bytes = _queue_file(artifact_id).read_bytes()
    outside = _outside_file(tmp_path)
    outside_bytes = outside.read_bytes()
    _poison_pdf_path(client, artifact_id, outside)

    data = client.post(f"/library/import-queue/{artifact_id}/confirm", json=CONFIRM).json()
    assert data["promotion_state"] == "promoted"

    staged = managed_capture_pdf_path(library_dir(), artifact_id)
    assert staged.read_bytes() == queued_bytes, "the canonical copy must come from the owned queue entry"
    assert outside.read_bytes() == outside_bytes, "a poisoned path must never be read, moved or removed"
    assert not _queue_file(artifact_id).exists()  # the queue entry (and only it) went away after promotion
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert len(get_attachments_for_paper(conn, data["resolved_paper_id"])) == 1
    engine.dispose()


def test_confirm_refuses_a_symlinked_queue_entry_and_copies_nothing_from_outside(
    temp_db_url: str, tmp_path: Path
) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    outside = _outside_file(tmp_path)
    outside_bytes = outside.read_bytes()
    entry = _queue_file(artifact_id)
    entry.unlink()
    _symlink_or_skip(entry, outside)

    data = client.post(f"/library/import-queue/{artifact_id}/confirm", json=CONFIRM).json()
    assert data["promotion_state"] == "processing_failed"
    assert not managed_capture_pdf_path(library_dir(), artifact_id).exists(), "nothing may be staged from a symlink"
    assert outside.read_bytes() == outside_bytes
    assert entry.is_symlink(), "a refused entry is left in place, not silently deleted"


def test_retry_uses_the_owned_queue_entry_and_never_a_poisoned_path(
    temp_db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    queued_bytes = _queue_file(artifact_id).read_bytes()

    real_attach = provisional.attach_pdf_to_paper

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated embedding model failure")

    monkeypatch.setattr(provisional, "attach_pdf_to_paper", _boom)
    failed = client.post(f"/library/import-queue/{artifact_id}/confirm", json=CONFIRM).json()
    assert failed["promotion_state"] in {"indexing_unavailable", "processing_failed"}

    monkeypatch.setattr(provisional, "attach_pdf_to_paper", real_attach)
    outside = _outside_file(tmp_path)
    outside_bytes = outside.read_bytes()
    _poison_pdf_path(client, artifact_id, outside)

    retried = client.post(f"/library/import-queue/{artifact_id}/retry").json()
    assert retried["promotion_state"] == "promoted"
    assert managed_capture_pdf_path(library_dir(), artifact_id).read_bytes() == queued_bytes
    assert outside.read_bytes() == outside_bytes


def test_delete_removes_the_owned_entries_and_never_a_poisoned_path(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    outside = _outside_file(tmp_path)
    outside_bytes = outside.read_bytes()
    _poison_pdf_path(client, artifact_id, outside)
    assert _queue_file(artifact_id).is_file()

    assert client.delete(f"/library/import-queue/{artifact_id}").status_code == 204
    assert not _queue_file(artifact_id).exists()
    assert not sidecar_path(library_dir(), artifact_id).exists()
    assert outside.read_bytes() == outside_bytes, (
        "deleting a capture must never delete a path the database merely names"
    )
    assert _get_row(client, artifact_id) is None


def test_delete_removes_a_symlinked_queue_entry_as_a_link_and_leaves_its_target(
    temp_db_url: str, tmp_path: Path
) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    outside = _outside_file(tmp_path)
    outside_bytes = outside.read_bytes()
    entry = _queue_file(artifact_id)
    entry.unlink()
    _symlink_or_skip(entry, outside)

    assert client.delete(f"/library/import-queue/{artifact_id}").status_code == 204
    assert not entry.is_symlink() and not entry.exists(), "the link itself is removed"
    assert outside.read_bytes() == outside_bytes, "its target is untouched"


# ── startup recovery: a directory entry is identity only in its exact canonical form ─────────────────────────────


def _row_count(temp_db_url: str) -> int:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        count = len(provisional_artifacts_repo.all_ids(conn))
    engine.dispose()
    return count


def test_recovery_ignores_and_leaves_untouched_every_non_canonical_queue_entry(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    root = library_dir()
    queue = queue_dir(root)
    queue.mkdir(parents=True, exist_ok=True)
    stray = [
        queue / "notes.pdf",
        queue / (("A" * 8 + "b" * 24) + ".pdf"),  # upper-case hex
        queue / (("c" * 32) + ".pdf.tmp"),
        queue / ("." + ("d" * 32) + ".pdf"),
        queue / (("9" * 31) + ".pdf"),
    ]
    for path in stray:
        _pdf_with_metadata_title(path, title=None)
    before = {p.name: p.read_bytes() for p in stray}

    recover_at_startup(engine, root)
    engine.dispose()

    assert _row_count(temp_db_url) == 0, "a non-canonical name must never become an artifact identity"
    assert {p.name: p.read_bytes() for p in stray} == before, "and must never be deleted or altered"


def test_recovery_never_adopts_or_reads_a_symlinked_queue_entry(temp_db_url: str, tmp_path: Path) -> None:
    engine = make_engine(temp_db_url)
    root = library_dir()
    queue = queue_dir(root)
    queue.mkdir(parents=True, exist_ok=True)
    outside = _outside_file(tmp_path)
    outside_bytes = outside.read_bytes()
    _symlink_or_skip(queue / (("a" * 32) + ".pdf"), outside)

    recover_at_startup(engine, root)
    engine.dispose()

    assert _row_count(temp_db_url) == 0
    assert outside.read_bytes() == outside_bytes


def test_recovery_still_adopts_a_canonical_plain_file(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    root = library_dir()
    artifact_id = "b" * 32
    queue_dir(root).mkdir(parents=True, exist_ok=True)
    _pdf_with_metadata_title(queued_pdf_entry_path(queue_dir(root), artifact_id), title=None)

    recover_at_startup(engine, root)
    engine.dispose()
    assert _row_count(temp_db_url) == 1


def test_recovery_does_not_follow_a_symlinked_sidecar(temp_db_url: str, tmp_path: Path) -> None:
    engine = make_engine(temp_db_url)
    root = library_dir()
    artifact_id = "c" * 32
    queue_dir(root).mkdir(parents=True, exist_ok=True)
    _pdf_with_metadata_title(queued_pdf_entry_path(queue_dir(root), artifact_id), title=None)
    poison = tmp_path / "poison.json"
    poison.write_text(
        '{"first_capture_event": {"capture_event_id": "'
        + "1" * 32
        + '", "source_url": "https://evil.example/planted"}}',
        encoding="utf-8",
    )
    sidecar = sidecar_path(root, artifact_id)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    _symlink_or_skip(sidecar, poison)

    recover_at_startup(engine, root)
    engine.dispose()

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        events = capture_events_repo.list_for_artifact(conn, artifact_id)
    engine.dispose()
    assert len(events) == 1
    assert events[0]["source_url"] != "https://evil.example/planted", "the planted sidecar must not supply provenance"
