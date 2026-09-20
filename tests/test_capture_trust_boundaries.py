"""Explicit filesystem trust boundaries for browser capture (#61) -- the CodeQL `py/path-injection` findings on
PR #103 (Import Queue PDF stream, capture attachment path) and the pairing-secret file's creation mode.

The two rules under test (see `app/backend/capture/trusted_paths.py`):
  1. a route id is a LOOKUP key only: syntactically a Callosum id -> lookup -> server-owned state; the filename of
     anything written derives from the server-minted id, not from the route text;
  2. a stored path is trusted only after it is RESOLVED: a queued PDF is served only if it is a real file directly
     under the resolved Import Queue directory (a symlink pointing outside is refused).
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from sqlalchemy import update

from app.backend.acquisition.fetch import library_dir
from app.backend.api.routers import capture as capture_router
from app.backend.capture import pairing
from app.backend.capture.trusted_paths import is_canonical_id, managed_capture_pdf_path, resolve_queued_pdf
from app.backend.persistence import provisional_artifacts_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import provisional_artifacts
from tests.test_capture import _capture_slot, _client, _one_page_pdf, _paired
from tests.test_import_queue import _queue_pending_item

MALFORMED_IDS = [
    "not-a-real-id",
    "A" * 32,  # uppercase hex is not the canonical (lowercase) form
    "0" * 31,
    "0" * 33,
    "..%5c..%5cevil",  # decodes to ..\..\evil
    "0" * 31 + "g",
]


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


# ── pure helpers ─────────────────────────────────────────────────────────────────────────────────────────────────


def test_only_canonical_uuid_hex_is_a_callosum_id() -> None:
    assert is_canonical_id("0123456789abcdef0123456789abcdef")
    for bad in [*MALFORMED_IDS, "", "../x", "0123456789abcdef0123456789abcde/", None, 123]:
        assert not is_canonical_id(bad), bad


def test_managed_capture_filename_derives_from_a_server_minted_id_only(tmp_path: Path) -> None:
    minted = "0123456789abcdef0123456789abcdef"
    assert managed_capture_pdf_path(tmp_path, minted) == tmp_path / f"capture-{minted}.pdf"
    for hostile in ("../escape", "..\\escape", "a/b", "x" * 32, minted.upper()):
        with pytest.raises(ValueError):
            managed_capture_pdf_path(tmp_path, hostile)


def test_a_queued_pdf_resolves_only_when_it_is_a_real_file_directly_under_the_resolved_queue(tmp_path: Path) -> None:
    queue = tmp_path / "_Import Queue"
    queue.mkdir()
    ok = queue / ("a" * 32 + ".pdf")
    ok.write_bytes(b"%PDF-1.7 ok")
    assert resolve_queued_pdf(str(ok), queue) == ok.resolve()

    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.7 secret")
    assert resolve_queued_pdf(str(outside), queue) is None  # stored path outside the queue

    nested = queue / "sub"
    nested.mkdir()
    (nested / "deep.pdf").write_bytes(b"%PDF-1.7")
    assert resolve_queued_pdf(str(nested / "deep.pdf"), queue) is None  # not DIRECTLY under the queue
    assert resolve_queued_pdf(str(queue / "missing.pdf"), queue) is None
    assert resolve_queued_pdf(str(queue), queue) is None  # a directory is not a file
    assert resolve_queued_pdf("\0not-a-path", queue) is None


def test_a_queue_local_symlink_that_targets_outside_the_queue_is_refused(tmp_path: Path) -> None:
    queue = tmp_path / "_Import Queue"
    queue.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.7 secret")
    link = queue / ("b" * 32 + ".pdf")
    _symlink_or_skip(link, outside)
    assert resolve_queued_pdf(str(link), queue) is None


# ── the Import Queue PDF stream (py/path-injection: import_queue.py) ─────────────────────────────────────────────


def _row_path(client, artifact_id: str) -> Path:
    engine = make_engine(client.app.state.db_url)
    with engine.begin() as conn:
        row = provisional_artifacts_repo.get(conn, artifact_id)
    engine.dispose()
    return Path(str(row["pdf_path"]))


def _set_row_path(client, artifact_id: str, path: Path) -> None:
    engine = make_engine(client.app.state.db_url)
    with engine.begin() as conn:
        conn.execute(
            update(provisional_artifacts).where(provisional_artifacts.c.id == artifact_id).values(pdf_path=str(path))
        )
    engine.dispose()


def test_an_ordinary_queue_pdf_is_served(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    response = client.get(f"/library/import-queue/{artifact_id}/pdf")
    assert response.status_code == 200
    assert response.content == _row_path(client, artifact_id).read_bytes()


def test_a_database_path_outside_the_queue_is_refused(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.7 not the queue's")
    _set_row_path(client, artifact_id, outside)
    assert client.get(f"/library/import-queue/{artifact_id}/pdf").status_code == 404


def test_a_queue_local_symlink_targeting_outside_is_refused_over_http(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    artifact_id = _queue_pending_item(client, tmp_path)
    queued = _row_path(client, artifact_id)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.7 must never be served")
    queued.unlink()
    _symlink_or_skip(queued, outside)
    response = client.get(f"/library/import-queue/{artifact_id}/pdf")
    assert response.status_code == 404
    assert b"must never be served" not in response.content


@pytest.mark.parametrize("bad_id", MALFORMED_IDS)
def test_malformed_artifact_ids_are_answered_like_unknown_ones_on_every_route(temp_db_url: str, bad_id: str) -> None:
    """Each route keeps its own existing 'unknown' status (retry has always said 422); a malformed id never reaches
    a lookup, a path or the delete machinery."""
    client = _client(temp_db_url)
    base = f"/library/import-queue/{bad_id}"
    assert client.get(base).status_code == 404
    assert client.get(f"{base}/pdf").status_code == 404
    assert client.post(f"{base}/preview-doi", json={"doi": "10.1234/x"}).status_code == 404
    assert client.post(f"{base}/confirm", json={"doi": "10.1234/x", "source": "manual"}).status_code == 404
    assert client.post(f"{base}/retry").status_code == 422
    assert client.delete(base).status_code == 404


# ── the capture attachment path (py/path-injection: capture.py) ──────────────────────────────────────────────────


def test_a_normal_capture_attaches_under_its_server_minted_name(temp_db_url: str, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _capture_slot(client, headers)
    pdf = _one_page_pdf(tmp_path / "paper.pdf")
    response = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["capture_id"] == capture_id
    assert (library_dir() / f"capture-{capture_id}.pdf").is_file()


@pytest.mark.parametrize("bad_id", MALFORMED_IDS)
def test_malformed_capture_ids_cannot_reach_the_filesystem(temp_db_url: str, tmp_path: Path, bad_id: str) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    _capture_slot(client, headers)  # a live pending capture exists, so only the id syntax can be what refuses
    root = library_dir()
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) if root.exists() else []
    pdf = _one_page_pdf(tmp_path / "paper.pdf")
    response = client.post(
        f"/capture/item/{bad_id}/pdf", content=pdf.read_bytes(), headers={**headers, "content-type": "application/pdf"}
    )
    assert response.status_code == 404
    after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) if root.exists() else []
    assert after == before, "a refused capture id must not create, move or delete any file"


def test_the_attachment_filename_comes_from_the_pending_objects_minted_id_not_the_route(
    temp_db_url: str, tmp_path: Path
) -> None:
    client = _client(temp_db_url)
    headers = _paired(client)
    route_id = _capture_slot(client, headers)
    minted = "f" * 32  # a different, canonical id held in server-owned state
    capture_router._pending[route_id].server_capture_id = minted
    pdf = _one_page_pdf(tmp_path / "paper.pdf")
    response = client.post(
        f"/capture/item/{route_id}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["capture_id"] == minted
    assert (library_dir() / f"capture-{minted}.pdf").is_file()
    assert not (library_dir() / f"capture-{route_id}.pdf").exists(), "the route text must not name the file"


# ── the pairing secret file's creation mode ──────────────────────────────────────────────────────────────────────


def test_rotating_the_pairing_secret_leaves_a_valid_file_and_no_temp_behind(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings" / "app-settings.json"))
    secret = pairing.rotate_pairing_secret()
    path = pairing.pairing_file_path()
    assert pairing.read_pairing_secret() == secret
    assert not path.with_name(path.name + ".tmp").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits (Windows relies on the user profile ACLs)")
def test_the_pairing_file_is_owner_only_from_birth_even_under_a_permissive_umask(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings" / "app-settings.json"))
    seen: list[int] = []
    real_replace = Path.replace

    def spy(self: Path, target):
        seen.append(
            stat.S_IMODE(self.stat().st_mode)
        )  # the mode of the TEMP file at the moment it is renamed into place
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", spy)
    old_umask = os.umask(0)  # the worst case: nothing masked
    try:
        pairing.rotate_pairing_secret()
    finally:
        os.umask(old_umask)
    assert seen == [0o600], "the secret was on disk with broader-than-owner permissions before the rename"
    assert stat.S_IMODE(pairing.pairing_file_path().stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_stale_wide_mode_temp_file_is_never_reused_for_the_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings" / "app-settings.json"))
    path = pairing.pairing_file_path()
    path.parent.mkdir(parents=True)
    stale = path.with_name(path.name + ".tmp")
    stale.write_text("stale contents from a crashed run", encoding="utf-8")
    stale.chmod(0o666)
    pairing.rotate_pairing_secret()
    assert "stale" not in path.read_text(encoding="utf-8")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
