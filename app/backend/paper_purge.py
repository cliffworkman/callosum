"""Permanent paper deletion with contained cleanup of Callosum-managed attachment files."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Connection, select

from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.paper_lifecycle_repo import (
    purge_paper,
    purgeable_trashed_paper_ids,
)
from app.backend.persistence.schema import attachments

_log = logging.getLogger(__name__)
_STAGING_DIR_NAME = ".callosum-delete-staging"


class ManagedFilePurgeError(RuntimeError):
    """A managed file could not be staged safely, so its paper was left in Trash."""


@dataclass
class _StagedFile:
    original: Path
    staged: Path


@dataclass
class _ManagedFileStage:
    staging_dir: Path
    files: list[_StagedFile] = field(default_factory=list)

    def restore(self) -> None:
        failures: list[str] = []
        for item in reversed(self.files):
            if not item.staged.exists():
                continue
            try:
                item.original.parent.mkdir(parents=True, exist_ok=True)
                _move_file(item.staged, item.original)
            except OSError as exc:
                failures.append(f"{item.original}: {exc}")
        self._remove_empty_staging_dir()
        if failures:
            raise ManagedFilePurgeError("Could not restore staged managed files: " + "; ".join(failures))

    def discard(self) -> None:
        for item in self.files:
            try:
                item.staged.unlink(missing_ok=True)
            except OSError:
                # The database purge has committed. Keep the file isolated from the library and retry manually;
                # never pretend it is still an active attachment or restore it under a now-deleted record.
                _log.exception("Could not remove staged managed attachment %s", item.staged)
        self._remove_empty_staging_dir()

    def _remove_empty_staging_dir(self) -> None:
        try:
            self.staging_dir.rmdir()
        except OSError:
            pass


def purge_paper_permanently(
    conn: Connection,
    paper_id: int,
    *,
    vector_store: VectorStore,
    managed_library_dir: str | Path,
) -> bool:
    """Purge one trashed paper, deleting only files Callosum owns inside its managed library root."""
    if paper_id not in purgeable_trashed_paper_ids(conn, paper_id=paper_id):
        return False
    stage = _stage_managed_attachment_files(conn, [paper_id], managed_library_dir)
    try:
        if not purge_paper(conn, paper_id, vector_store=vector_store):
            conn.rollback()
            stage.restore()
            return False
        conn.commit()
    except Exception:
        conn.rollback()
        stage.restore()
        raise
    stage.discard()
    return True


def purge_trash_permanently(
    conn: Connection,
    *,
    vector_store: VectorStore,
    managed_library_dir: str | Path,
) -> int:
    """Purge every eligible trashed paper and its exclusively owned managed files in one transaction."""
    paper_ids = purgeable_trashed_paper_ids(conn)
    if not paper_ids:
        return 0
    stage = _stage_managed_attachment_files(conn, paper_ids, managed_library_dir)
    try:
        purged = sum(purge_paper(conn, paper_id, vector_store=vector_store) for paper_id in paper_ids)
        conn.commit()
    except Exception:
        conn.rollback()
        stage.restore()
        raise
    stage.discard()
    return purged


def _stage_managed_attachment_files(
    conn: Connection, paper_ids: list[int], managed_library_dir: str | Path
) -> _ManagedFileStage:
    root = Path(managed_library_dir).expanduser().resolve(strict=False)
    staging_dir = root / _STAGING_DIR_NAME
    stage = _ManagedFileStage(staging_dir=staging_dir)
    target_ids = set(paper_ids)
    if not target_ids:
        return stage

    rows = conn.execute(
        select(
            attachments.c.paper_id,
            attachments.c.storage_mode,
            attachments.c.original_path,
            attachments.c.resolved_path,
        )
    ).mappings()
    target_paths: dict[str, Path] = {}
    other_references: set[str] = set()
    for row in rows:
        raw_path = row["resolved_path"] or row["original_path"]
        normalized = _normalized_path(raw_path)
        if normalized is None:
            continue
        key = _path_key(normalized)
        if int(row["paper_id"]) not in target_ids:
            other_references.add(key)
        elif row["storage_mode"] == "managed":
            target_paths.setdefault(key, normalized)

    candidates = [
        path
        for key, path in target_paths.items()
        if key not in other_references and _is_owned_regular_file(path, root, staging_dir)
    ]
    if not candidates:
        return stage

    try:
        _prepare_staging_dir(staging_dir, root)
        for source in candidates:
            destination = staging_dir / f"{source.stem[:80]}.{uuid4().hex}.deleting{source.suffix}"
            _move_file(source, destination)
            stage.files.append(_StagedFile(original=source, staged=destination))
    except OSError as exc:
        try:
            stage.restore()
        except ManagedFilePurgeError as restore_exc:
            raise ManagedFilePurgeError(
                f"Managed-file staging failed ({exc}); rollback also failed: {restore_exc}"
            ) from exc
        raise ManagedFilePurgeError(f"Could not stage managed attachment for deletion: {exc}") from exc
    return stage


def _normalized_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    try:
        return Path(raw_path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path))


def _is_owned_regular_file(path: Path, root: Path, staging_dir: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    if path == root or path == staging_dir or staging_dir in path.parents:
        return False
    return path.exists() and path.is_file() and not path.is_symlink()


def _prepare_staging_dir(staging_dir: Path, root: Path) -> None:
    staging_dir.mkdir(parents=True, exist_ok=True)
    if staging_dir.is_symlink() or staging_dir.resolve(strict=True) != staging_dir:
        raise OSError("managed-file staging path must be a real directory inside the library root")
    try:
        staging_dir.relative_to(root)
    except ValueError as exc:
        raise OSError("managed-file staging path escaped the library root") from exc


def _move_file(source: Path, destination: Path) -> None:
    source.replace(destination)
