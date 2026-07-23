"""Path normalization and containment rules for local WIP workspaces."""

from __future__ import annotations

import os
from pathlib import Path


def path_key(path: str | Path) -> str:
    """Return the platform-correct stable comparison key for a local path."""
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        resolved = candidate.absolute()
    normalized = os.path.normpath(str(resolved))
    return os.path.normcase(normalized)


def relative_path_key(path: str | Path) -> str:
    normalized = os.path.normpath(str(path)).replace("\\", "/")
    return os.path.normcase(normalized)


def trusted_child(root: str | Path, relative: str | Path) -> Path:
    """Resolve a stored root-relative path and reject containment escapes."""
    root_path = Path(root).expanduser().resolve(strict=False)
    candidate = (root_path / Path(relative)).resolve(strict=False)
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("Stored file path escapes its manuscript root") from exc
    return candidate
