"""Bounded, non-following filesystem discovery for WIP manuscript roots."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.backend.wip.paths import path_key, relative_path_key

MAX_FILES_PER_MANUSCRIPT = 5000
MAX_SCAN_DEPTH = 20
SKIP_DIRECTORY_NAMES = {".git", ".hg", ".svn", "__pycache__", "node_modules"}


@dataclass(frozen=True)
class DiscoveredFile:
    relative_path: str
    path_key: str
    role: str
    file_size: int
    modified_at: datetime
    whole_file_hash: str | None


@dataclass(frozen=True)
class DiscoveredManuscript:
    root_path: str
    path_key: str
    derived_title: str
    last_activity_at: datetime | None
    files: tuple[DiscoveredFile, ...]


@dataclass(frozen=True)
class ScanInspection:
    manuscripts: tuple[DiscoveredManuscript, ...]
    errors: tuple[str, ...]


def inspect_watch_root(root: dict) -> ScanInspection:
    base = Path(str(root["path"])).expanduser()
    if not base.is_dir():
        return ScanInspection((), (f"Watch root is unavailable: {base}",))

    excluded = {str(name).casefold() for name in (root.get("excluded_children_json") or [])}
    if root["discovery_mode"] == "folder":
        candidates = [base]
    else:
        try:
            candidates = sorted(
                (
                    child
                    for child in base.iterdir()
                    if child.is_dir() and not child.is_symlink() and child.name.casefold() not in excluded
                ),
                key=lambda item: item.name.casefold(),
            )
        except OSError as exc:
            return ScanInspection((), (f"Could not list watch root: {type(exc).__name__}: {exc}",))

    manuscripts: list[DiscoveredManuscript] = []
    errors: list[str] = []
    for candidate in candidates:
        try:
            manuscripts.append(_inspect_manuscript(candidate))
        except OSError as exc:
            errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
    return ScanInspection(tuple(manuscripts), tuple(errors))


def inspect_manuscript(root: str | Path) -> DiscoveredManuscript:
    candidate = Path(root).expanduser()
    if not candidate.is_dir() or candidate.is_symlink():
        raise OSError("Manuscript folder must be an existing non-symlink directory")
    return _inspect_manuscript(candidate)


def _inspect_manuscript(root: Path) -> DiscoveredManuscript:
    files: list[DiscoveredFile] = []
    latest: datetime | None = _mtime(root)
    root_parts = len(root.parts)

    def onerror(exc: OSError) -> None:
        raise exc

    for current, dirs, names in os.walk(root, topdown=True, onerror=onerror, followlinks=False):
        current_path = Path(current)
        depth = len(current_path.parts) - root_parts
        dirs[:] = [
            name
            for name in dirs
            if depth < MAX_SCAN_DEPTH and name not in SKIP_DIRECTORY_NAMES and not (current_path / name).is_symlink()
        ]
        for name in sorted(names, key=str.casefold):
            candidate = current_path / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            stat = candidate.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, UTC).replace(tzinfo=None)
            relative = candidate.relative_to(root).as_posix()
            files.append(
                DiscoveredFile(
                    relative_path=relative,
                    path_key=relative_path_key(relative),
                    role=_suggest_role(candidate),
                    file_size=int(stat.st_size),
                    modified_at=modified,
                    whole_file_hash=_file_hash(candidate, int(stat.st_size)),
                )
            )
            if latest is None or modified > latest:
                latest = modified
            if len(files) >= MAX_FILES_PER_MANUSCRIPT:
                raise OSError(f"file limit exceeded ({MAX_FILES_PER_MANUSCRIPT})")
    return DiscoveredManuscript(
        root_path=str(root.resolve(strict=False)),
        path_key=path_key(root),
        derived_title=root.name or str(root),
        last_activity_at=latest,
        files=tuple(files),
    )


def _mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(tzinfo=None)
    except OSError:
        return None


def _suggest_role(path: Path) -> str:
    stem = path.stem.casefold()
    suffix = path.suffix.casefold()
    if "cover" in stem and "letter" in stem:
        return "cover-letter"
    if "response" in stem and ("review" in stem or "rebuttal" in stem):
        return "response-to-reviewers"
    if "supp" in stem or "appendix" in stem:
        return "supplement"
    if "checklist" in stem:
        return "reporting-checklist"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".tif", ".tiff"}:
        return "figure"
    if suffix in {".csv", ".tsv", ".xlsx", ".xls"}:
        return "table"
    if suffix in {".docx", ".odt", ".md", ".tex", ".txt", ".html", ".htm", ".xml", ".jats", ".pdf"}:
        return "manuscript-candidate"
    return "other"


def _file_hash(path: Path, size: int) -> str | None:
    if size > 256 * 1024 * 1024:
        return None
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
